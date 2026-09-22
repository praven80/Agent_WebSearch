"""Option 2: web search with Amazon Bedrock AgentCore.

The tool is given to the model: the agent calls ``tools/list``, discovers
``WebSearch`` with its input schema, and from there the model decides whether a
search is needed, what query to send, and whether to search again after seeing
the results.

There is no provider SDK, no API key, and no response-mapping code in this file.
The Gateway snapshots the tool schema, resolves the endpoint, governs the
parameters, and authenticates to the AWS-owned Web Search backend with its own
IAM service role.
"""

from __future__ import annotations

from ..agent_runtime import run_agent
from ..config import WEB_SEARCH_USD_PER_QUERY, Settings
from ..gateway import (
    TOOL_SUFFIX,
    build_mcp_client,
)
from ..gateway import (
    preflight as gateway_preflight,
)
from ..tool_policy import SearchPolicy
from ..types import RunResult
from .base import Mode

MODE_KEY = "agentcore_search"


def preflight(settings: Settings) -> tuple[bool, str]:
    return gateway_preflight(settings)


def run(question: str, settings: Settings) -> RunResult:
    # Pins maxResults and injects the domain / published-date filters on every
    # search, so the sidebar settings are authoritative rather than suggestions
    # the model may ignore.
    policy = SearchPolicy.for_settings(settings)

    def tools_setup(stack, result: RunResult):
        policy.run = result  # so overrides show up in the execution trace
        result.log(
            f"Connecting to the Gateway in {settings.gateway_region} "
            "(SigV4 / AWS_IAM inbound)."
        )
        client = build_mcp_client(settings)
        # Entering the stack keeps the MCP session open for the whole agent loop,
        # so the model can search more than once.
        stack.enter_context(client)
        tools = client.list_tools_sync()
        names = [t.tool_name for t in tools]
        result.log(f"tools/list discovered: {', '.join(names) if names else '(none)'}")
        if not any(n.endswith(TOOL_SUFFIX) for n in names):
            result.log(
                "WARNING: no WebSearch tool in the Gateway's tool list. Check that "
                "the web-search target exists and is READY."
            )
        result.log("Schema handed to the model: it chooses whether and what to search.")
        result.log(f"Results per search pinned to {policy.max_results} by policy.")
        result.log(f"Request filters: {settings.filters_summary()}")
        result.log("Outbound auth handled by the Gateway's IAM service role: no API key.")
        result.log("Query is served inside AWS; it is not sent to a third-party engine.")
        return tools

    return run_agent(
        mode_key=MODE_KEY,
        question=question,
        settings=settings,
        tools_setup=tools_setup,
        search_cost_per_query=WEB_SEARCH_USD_PER_QUERY,
        extra_hooks=[policy],
    )


MODE = Mode(
    key=MODE_KEY,
    number=2,
    label="Web search with AgentCore",
    tagline="Managed connector discovered and driven by the model",
    icon="🟠",
    run=run,
    preflight=preflight,
    explanation=(
        "The integration is one connector id and a tools/list call. There is no "
        "search code in the application at all.",
        "The model decides whether a search is needed, reformulates the question "
        "into a good query, and can search again after seeing the results.",
        "No API key anywhere. The Gateway authenticates outbound with its own IAM "
        "service role; callers authenticate inbound with SigV4.",
        "Queries stay inside AWS. Nothing is sent to a third-party search engine, "
        "which removes a whole category of security review.",
        "Amazon-operated index over tens of billions of documents, refreshed "
        "within minutes, with a knowledge graph for high-confidence facts.",
        "Semantic snippet extraction returns the passages that bear on the query, "
        "so you spend fewer tokens on page boilerplate.",
        "Results can be restricted to domains you trust and to a publication-date "
        "window, enforced on every request rather than suggested to the model.",
        "You only pay for searches the model actually needed: $7 per 1,000 queries.",
        "Framework agnostic over standard MCP: Strands here, but LangGraph or "
        "CrewAI discover the same tool the same way.",
    ),
    offers_search=True,
)
