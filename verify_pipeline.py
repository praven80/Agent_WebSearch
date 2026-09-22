"""Offline verification of the parts that would otherwise only be checked by a
live AWS run: Web Search response parsing, tool-call tracing, citation
extraction and metrics accounting.

A scripted fake model drives the real Strands agent loop through
``demo.agent_runtime.run_agent``, so the wiring under test is the production
path -- only the model and the network are substituted.

Run:  .venv/bin/python verify_pipeline.py
"""

from __future__ import annotations

import json
import sys
from collections.abc import AsyncIterable
from typing import Any

from strands.models.model import Model

from demo import agent_runtime
from demo.config import WEB_SEARCH_USD_PER_QUERY, Settings
from demo.tracing import extract_citations

# The exact response envelope documented for the Web Search tool: a single text
# content block holding a serialised JSON document with a `results` array.
WEB_SEARCH_RESPONSE_TEXT = json.dumps(
    {
        "id": "824f89d0",
        "results": [
            {
                "text": "Python 3.13 was released on October 7, 2024, featuring "
                "improvements to the interactive interpreter, experimental "
                "free-threaded mode, and a preliminary JIT compiler.",
                "publishedDate": "2024-10-07",
                "url": "https://example.com/python/releases/3.13",
                "title": "Python 3.13 Release Highlights",
            },
            {
                "text": "The 2026 NBA Finals was the championship series...",
                "publishedDate": "04:43AM, Wednesday, June 17 2026, PDT",
                "url": "https://en.wikipedia.org/wiki/2026_NBA_Finals",
                "title": "2026 NBA Finals",
            },
            # A knowledge-graph observation: null title and url, facts in `text`.
            {"text": "founded: 1994; founder: Jeff Bezos", "title": None, "url": None},
        ],
    }
)

FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"ok    {label}")
    else:
        print(f"FAIL  {label}" + (f": {detail}" if detail else ""))
        FAILURES.append(label)


# --------------------------------------------------------------------------- #
# 1. Citation extraction against the documented response shape
# --------------------------------------------------------------------------- #


def test_citation_extraction() -> None:
    print("\n-- Web Search response parsing --")
    citations = extract_citations(WEB_SEARCH_RESPONSE_TEXT)
    check("parses all three observations", len(citations) == 3, f"got {len(citations)}")

    first = citations[0]
    check("title parsed", first.title == "Python 3.13 Release Highlights", first.title)
    check(
        "url parsed", first.url == "https://example.com/python/releases/3.13", first.url
    )
    check(
        "publishedDate parsed", first.published_date == "2024-10-07", first.published_date
    )
    check(
        "snippet parsed",
        first.snippet.startswith("Python 3.13 was released"),
        first.snippet[:40],
    )
    check("domain derived", first.domain == "example.com", first.domain)

    kg = citations[2]
    check(
        "knowledge-graph observation labelled, not dropped",
        kg.title == "Knowledge graph fact" and "Jeff Bezos" in kg.snippet,
        f"{kg.title!r} / {kg.snippet!r}",
    )

    # An MCP envelope, not just the inner text.
    envelope = {
        "status": "success",
        "toolUseId": "t1",
        "content": [{"text": WEB_SEARCH_RESPONSE_TEXT}],
    }
    check(
        "parses the full MCP ToolResult envelope", len(extract_citations(envelope)) == 3
    )

    check("non-JSON payload yields no citations", extract_citations("not json") == [])
    check("empty payload yields no citations", extract_citations("") == [])


# --------------------------------------------------------------------------- #
# 2. A scripted model that drives the real agent loop
# --------------------------------------------------------------------------- #


class ScriptedModel(Model):
    """Emits a tool call for the first turn, then a final text answer.

    Yields the StreamEvent sequence the Strands event loop expects, which is why
    this exercises the real tool-execution and metrics path.
    """

    def __init__(
        self, tool_input: dict[str, Any], answer: str, *, call_tool: bool = True
    ) -> None:
        self.tool_input = tool_input
        self.answer = answer
        self.call_tool = call_tool
        self.turns = 0

    def update_config(self, **model_config: Any) -> None:
        return None

    def get_config(self) -> Any:
        return {}

    def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        raise NotImplementedError

    async def stream(
        self,
        messages,
        tool_specs=None,
        system_prompt=None,
        **kwargs: Any,
    ) -> AsyncIterable[dict[str, Any]]:
        self.turns += 1
        first_turn = self.turns == 1

        if first_turn and self.call_tool and tool_specs:
            tool_name = tool_specs[0]["name"]
            yield {"messageStart": {"role": "assistant"}}
            yield {
                "contentBlockStart": {
                    "start": {"toolUse": {"toolUseId": "tool-1", "name": tool_name}}
                }
            }
            yield {
                "contentBlockDelta": {
                    "delta": {"toolUse": {"input": json.dumps(self.tool_input)}}
                }
            }
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "tool_use"}}
            yield {
                "metadata": {
                    "usage": {"inputTokens": 120, "outputTokens": 30, "totalTokens": 150},
                    "metrics": {"latencyMs": 100},
                }
            }
            return

        yield {"messageStart": {"role": "assistant"}}
        yield {"contentBlockStart": {"start": {}}}
        yield {"contentBlockDelta": {"delta": {"text": self.answer}}}
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "end_turn"}}
        yield {
            "metadata": {
                "usage": {"inputTokens": 200, "outputTokens": 80, "totalTokens": 280},
                "metrics": {"latencyMs": 150},
            }
        }


def _settings() -> Settings:
    return Settings(
        aws_region="us-east-1",
        model_id="us.anthropic.claude-sonnet-4-6",
        gateway_url="https://abc123.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp",
        max_results=3,
    )


def _run_with(model: Model, tools, *, search_cost: float):
    """Run the production run_agent with the model substituted."""
    original = agent_runtime.build_model
    agent_runtime.build_model = lambda _settings: model  # type: ignore[assignment]
    try:
        return agent_runtime.run_agent(
            mode_key="test",
            question="What is the latest stable release of Python?",
            settings=_settings(),
            tools_setup=lambda _stack, _run: tools,
            search_cost_per_query=search_cost,
        )
    finally:
        agent_runtime.build_model = original  # type: ignore[assignment]


def test_agentcore_path() -> None:
    """Option 2 shape: the managed tool returning the documented Web Search envelope."""
    print("\n-- Option 2 run path (managed connector response) --")
    from strands import tool

    @tool
    def web_search_tool(query: str, maxResults: int = 5) -> str:
        """Search the web.

        Args:
            query: the query
            maxResults: result count
        """
        return WEB_SEARCH_RESPONSE_TEXT

    model = ScriptedModel(
        {"query": "latest stable Python release", "maxResults": 3},
        "The latest stable release is Python 3.13, shipped 2024-10-07 [1].",
    )
    result = _run_with(model, [web_search_tool], search_cost=WEB_SEARCH_USD_PER_QUERY)

    check("run succeeded", result.ok, str(result.error))
    check("answer captured", "Python 3.13" in result.answer, result.answer)
    check(
        "one tool call recorded", len(result.tool_calls) == 1, str(len(result.tool_calls))
    )

    if result.tool_calls:
        call = result.tool_calls[0]
        check(
            "tool arguments recorded",
            call.arguments.get("query") == "latest stable Python release",
            str(call.arguments),
        )
        check(
            "result summarised", "3 result(s)" in call.result_summary, call.result_summary
        )
        check("no tool error", call.error is None, str(call.error))

    check(
        "citations extracted from the run",
        len(result.citations) == 3,
        str(len(result.citations)),
    )
    check("run reports grounded", result.grounded)

    m = result.metrics
    check(
        "tokens accumulated across both turns", m.total_tokens == 430, str(m.total_tokens)
    )
    check("model cycles counted", m.model_cycles >= 2, str(m.model_cycles))
    check("one billable search query", m.search_queries == 1, str(m.search_queries))
    check(
        "search cost priced at $7/1000",
        abs(m.search_cost_usd - 0.007) < 1e-9,
        str(m.search_cost_usd),
    )
    # 320 in / 110 out at $3 / $15 per 1M.
    expected_model = (320 / 1e6) * 3.0 + (110 / 1e6) * 15.0
    check(
        "model cost estimated from token counts",
        abs(m.model_cost_usd - expected_model) < 1e-9,
        f"{m.model_cost_usd} vs {expected_model}",
    )
    check("latency recorded", m.latency_s > 0)


def test_search_policy() -> None:
    """Operator settings must reach the tool, not merely be suggested to the model."""
    print("\n-- search policy: maxResults + filters --")
    from strands import tool

    from demo.tool_policy import SearchPolicy

    seen: dict[str, Any] = {}

    @tool(name="web-search-tool___WebSearch")
    def websearch(query: str, maxResults: int = 10, filters: dict | None = None) -> str:
        """Search the web.

        Args:
            query: the query
            maxResults: how many results
            filters: request-level filters
        """
        seen["maxResults"] = maxResults
        seen["filters"] = filters
        return WEB_SEARCH_RESPONSE_TEXT

    settings = Settings(
        max_results=3,
        gateway_url="https://a.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp",
        domain_include=("python.org",),
        domain_exclude=("reddit.com",),
        published_from="2026-01-01",
        published_to="2026-09-15",
    )
    policy = SearchPolicy.for_settings(settings)
    # The model asks for 25 and no filters; the policy must override both.
    model = ScriptedModel({"query": "python release", "maxResults": 25}, "Answer [1].")

    original = agent_runtime.build_model
    agent_runtime.build_model = lambda _s: model  # type: ignore[assignment]
    try:
        result = agent_runtime.run_agent(
            mode_key="test",
            question="q",
            settings=settings,
            tools_setup=lambda _st, run: (setattr(policy, "run", run), [websearch])[1],
            extra_hooks=[policy],
        )
    finally:
        agent_runtime.build_model = original  # type: ignore[assignment]

    check("run succeeded", result.ok, str(result.error))
    check(
        "model asked for 25 but the tool received the configured 3",
        seen.get("maxResults") == 3,
        f"tool received {seen.get('maxResults')}",
    )

    got = seen.get("filters") or {}
    check(
        "domain include reached the tool",
        got.get("domainFilter", {}).get("include") == ["python.org"],
        str(got),
    )
    check(
        "domain exclude reached the tool",
        got.get("domainFilter", {}).get("exclude") == ["reddit.com"],
        str(got),
    )
    check(
        "published date bounds reached the tool",
        got.get("publishedDateFilter") == {"from": "2026-01-01", "to": "2026-09-15"},
        str(got),
    )
    check(
        "override is visible in the trace",
        any("pinned to 3" in line and "filters applied" in line for line in result.trace),
        str(result.trace),
    )
    check("clamps below the range", SearchPolicy(0).max_results == 1)
    check("clamps above the range", SearchPolicy(99).max_results == 25)

    # An unrelated tool must be left alone.
    untouched = {"name": "some_other_tool", "input": {"maxResults": 25}}

    class Ev:
        tool_use = untouched

    SearchPolicy(
        3, filters={"domainFilter": {"include": ["x.com"]}}
    )._on_before_tool_call(Ev())
    check(
        "unrelated tools untouched",
        untouched["input"] == {"maxResults": 25},
        str(untouched),
    )

    # With no filters configured, the argument must be omitted entirely rather
    # than sent as an empty object.
    bare = {"name": "t___WebSearch", "input": {"query": "q"}}

    class Ev2:
        tool_use = bare

    SearchPolicy(5)._on_before_tool_call(Ev2())
    check(
        "no filters configured means no filters argument",
        "filters" not in bare["input"],
        str(bare),
    )


def test_filter_construction() -> None:
    """Settings must build a well-formed filters object and normalise domains."""
    print("\n-- filter construction --")
    from demo.config import normalize_domain, parse_domain_list

    check("bare host kept", normalize_domain("python.org") == "python.org")
    check(
        "url reduced to domain",
        normalize_domain("https://www.python.org/downloads/") == "python.org",
        normalize_domain("https://www.python.org/downloads/"),
    )
    check("port stripped", normalize_domain("example.com:8443") == "example.com")
    check(
        "case normalised",
        normalize_domain("Docs.AWS.Amazon.Com") == "docs.aws.amazon.com",
    )
    check("empty stays empty", normalize_domain("   ") == "")

    parsed = parse_domain_list(
        "python.org, https://reddit.com/r/x\n python.org \nquora.com"
    )
    check(
        "list parsed, de-duplicated, normalised",
        parsed == ("python.org", "reddit.com", "quora.com"),
        str(parsed),
    )

    many = parse_domain_list(",".join(f"d{i}.com" for i in range(150)))
    check("list capped at 100", len(many) == 100, str(len(many)))

    empty = Settings()
    check("no filters -> empty dict", empty.search_filters() == {})
    check("no filters -> inactive", not empty.filters_active)
    check("no filters -> summary reads 'none'", empty.filters_summary() == "none")

    only_include = Settings(domain_include=("python.org",))
    check(
        "include only omits exclude and dates",
        only_include.search_filters() == {"domainFilter": {"include": ["python.org"]}},
        str(only_include.search_filters()),
    )

    only_date = Settings(published_from="2026-01-01")
    check(
        "open-ended date range allowed",
        only_date.search_filters() == {"publishedDateFilter": {"from": "2026-01-01"}},
        str(only_date.search_filters()),
    )
    check("summary mentions the range", "2026-01-01" in only_date.filters_summary())


def test_no_search_path() -> None:
    """Option 1 shape: no tools, so no citations and no search cost."""
    print("\n-- Option 1 run path (no tools) --")
    model = ScriptedModel(
        {}, "I cannot verify this; my knowledge ends earlier.", call_tool=False
    )
    result = _run_with(model, (), search_cost=0.0)

    check("run succeeded", result.ok, str(result.error))
    check("no tool calls", result.tool_calls == [])
    check("no citations", result.citations == [])
    check("reports not grounded", not result.grounded)
    check("no search cost", result.metrics.search_cost_usd == 0.0)
    check("search query count is zero", result.metrics.search_queries == 0)


def test_run_failure_is_reported() -> None:
    """A setup failure must surface as result.error, not an exception."""
    print("\n-- Failure handling --")

    def exploding_setup(_stack, _run):
        raise RuntimeError("gateway unreachable")

    original = agent_runtime.build_model
    agent_runtime.build_model = lambda _s: ScriptedModel({}, "x", call_tool=False)  # type: ignore[assignment]
    try:
        result = agent_runtime.run_agent(
            mode_key="test",
            question="q",
            settings=_settings(),
            tools_setup=exploding_setup,
        )
    finally:
        agent_runtime.build_model = original  # type: ignore[assignment]

    check("failure captured, not raised", not result.ok)
    check(
        "error message preserved",
        "gateway unreachable" in (result.error or ""),
        str(result.error),
    )
    check("latency still recorded", result.metrics.latency_s >= 0)


# --------------------------------------------------------------------------- #
# 3. No third-party search anywhere
# --------------------------------------------------------------------------- #


def test_no_third_party_dependency() -> None:
    """The demo must not be able to reach a third-party search engine at all."""
    print("\n-- No third-party search anywhere --")
    import pathlib

    banned = ("ddgs", "duckduckgo", "tavily", "serper", "SEARCH_API_KEY")

    reqs = pathlib.Path("requirements.txt").read_text().lower()
    hits = [w for w in banned if w.lower() in reqs]
    check("requirements.txt declares no search SDK", not hits, str(hits))

    env = pathlib.Path(".env.example").read_text().lower()
    hits = [w for w in banned if w.lower() in env]
    check(".env.example asks for no search API key", not hits, str(hits))

    offenders: list[str] = []
    for path in sorted(pathlib.Path("demo").rglob("*.py")):
        text = path.read_text().lower()
        for word in banned:
            # A comment saying "no third-party engine" is fine; an import is not.
            if word.lower() in text and f"import {word.lower()}" in text:
                offenders.append(f"{path}:{word}")
    check("no demo module imports a search SDK", not offenders, str(offenders))

    # The search option must resolve to the Gateway module.
    from demo.modes import AGENTCORE_SEARCH, MODES

    check("two options registered", len(MODES) == 2, str(len(MODES)))
    check(
        "options ordered 1, 2 with no gap",
        [m.number for m in MODES] == [1, 2],
        str([m.number for m in MODES]),
    )
    module = sys.modules[AGENTCORE_SEARCH.run.__module__]
    check(
        "the search option goes through demo.gateway",
        hasattr(module, "build_mcp_client"),
        f"{module.__name__} has no build_mcp_client",
    )
    check(
        "no manual/hand-wired option remains",
        not any(m.key == "manual_search" for m in MODES),
    )


def test_gateway_url_validation() -> None:
    print("\n-- Gateway URL validation --")
    from demo.config import region_from_gateway_url, validate_gateway_url

    good = "https://abc123.gateway.bedrock-agentcore.eu-west-1.amazonaws.com/mcp"
    check("valid URL accepted", validate_gateway_url(good) == good)
    check("region parsed from host", region_from_gateway_url(good) == "eu-west-1")

    for bad, why in [
        ("", "empty"),
        ("http://abc.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp", "http"),
        ("https://evil.example.com/mcp", "wrong host"),
    ]:
        try:
            validate_gateway_url(bad)
            check(f"rejects {why}", False, "accepted")
        except ValueError:
            check(f"rejects {why}", True)


def main() -> int:
    test_citation_extraction()
    test_agentcore_path()
    test_search_policy()
    test_filter_construction()
    test_no_search_path()
    test_run_failure_is_reported()
    test_no_third_party_dependency()
    test_gateway_url_validation()

    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed: {', '.join(FAILURES)}")
        return 1
    print("all pipeline checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
