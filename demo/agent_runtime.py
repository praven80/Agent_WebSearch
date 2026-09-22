"""Shared Bedrock/Strands plumbing used by all three demo options.

The only thing that differs between the two options is which tools the agent
is given. The model, the system prompt, the metrics collection and the cost
accounting are identical -- which is the point of the comparison.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from contextlib import ExitStack
from datetime import date
from functools import lru_cache
from typing import Any

import boto3
from botocore.config import Config
from strands import Agent
from strands.models.bedrock import BedrockModel

from .config import Settings
from .tracing import ToolCallRecorder
from .types import RunMetrics, RunResult

# Deliberately does NOT tell the model to search. Whether it can search is
# decided purely by the tools it is handed, so both options answer the same
# question under the same instructions.
SYSTEM_PROMPT_TEMPLATE = """You are a research assistant helping an analyst.
Today's date is {today}.

Answer the user's question as accurately and specifically as you can. Include
concrete figures, dates, versions and names where they are relevant.

If you have tools available and the question depends on current information, use
them, and cite the sources you used inline as [n] with a numbered source list at
the end. If you do not have a way to look up current information and the answer
depends on it, say so plainly, state the date your knowledge appears to end, and
make clear which parts of your answer may be out of date. Never invent a URL,
figure or date."""


def boto_session(settings: Settings, region: str | None = None) -> boto3.Session:
    """A boto3 session honouring AWS_PROFILE / the default credential chain."""
    kwargs: dict[str, Any] = {"region_name": region or settings.aws_region}
    if settings.aws_profile:
        kwargs["profile_name"] = settings.aws_profile
    return boto3.Session(**kwargs)


@lru_cache(maxsize=8)
def _check_credentials_cached(profile: str | None, region: str) -> tuple[bool, str]:
    """Identity lookup, memoised per (profile, region).

    The UI re-checks readiness whenever settings change, and every preflight asks
    this question, so an uncached lookup means several STS calls per keystroke --
    and when credentials are absent, each one burns seconds on retries first.
    """
    try:
        session = boto3.Session(
            **({"profile_name": profile} if profile else {}), region_name=region
        )
        identity = session.client(
            "sts",
            config=Config(connect_timeout=3, read_timeout=5, retries={"max_attempts": 2}),
        ).get_caller_identity()
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
    # Deliberately does not report the account id or the role name. The identity
    # is confirmed by the call succeeding, and this message is rendered in a
    # customer-facing UI where account details should not appear.
    del identity
    return True, "AWS credentials available"


def check_credentials(settings: Settings) -> tuple[bool, str]:
    """Return ``(ok, message)`` describing the caller's identity.

    Read-only: uses ``sts:GetCallerIdentity``, which requires no permissions.
    """
    return _check_credentials_cached(settings.aws_profile, settings.aws_region)


def build_model(settings: Settings) -> BedrockModel:
    """A Bedrock model client for the selected model id."""
    return BedrockModel(
        model_id=settings.model_id,
        boto_session=boto_session(settings),
        temperature=0.2,
    )


def estimate_model_cost(settings: Settings, in_tokens: int, out_tokens: int) -> float:
    """Approximate on-demand model cost in USD. Zero if pricing is unknown."""
    pricing = settings.model_pricing()
    if not pricing:
        return 0.0
    in_per_m, out_per_m = pricing
    return (in_tokens / 1_000_000) * in_per_m + (out_tokens / 1_000_000) * out_per_m


def _usage(result: Any) -> tuple[int, int, int]:
    """(input_tokens, output_tokens, model_cycles) from an AgentResult."""
    metrics = getattr(result, "metrics", None)
    if metrics is None:
        return 0, 0, 0
    usage = getattr(metrics, "accumulated_usage", None) or {}
    return (
        int(usage.get("inputTokens", 0) or 0),
        int(usage.get("outputTokens", 0) or 0),
        int(getattr(metrics, "cycle_count", 0) or 0),
    )


def answer_text(result: Any) -> str:
    """Flatten an AgentResult's final message into plain text."""
    message = getattr(result, "message", None) or {}
    blocks = message.get("content") if isinstance(message, dict) else None
    if not blocks:
        return str(result).strip()
    parts = [
        b["text"]
        for b in blocks
        if isinstance(b, dict) and isinstance(b.get("text"), str)
    ]
    return "\n".join(parts).strip() or str(result).strip()


ToolsSetup = Callable[[ExitStack, RunResult], Sequence[Any]]


def run_agent(
    *,
    mode_key: str,
    question: str,
    settings: Settings,
    tools_setup: ToolsSetup | None = None,
    search_cost_per_query: float = 0.0,
    model_input: str | None = None,
    extra_hooks: Sequence[Any] | None = None,
) -> RunResult:
    """Run one question through an agent and record everything it did.

    ``tools_setup`` receives an :class:`~contextlib.ExitStack` and the result
    object, and returns the tools to give the agent. The stack stays open for the
    whole run, which is what lets Option 2 hold its MCP session to the Gateway
    open while the agent loops. ``tools_setup=None`` is Option 1 -- a model with
    no way to reach the outside world.

    ``model_input`` overrides the text sent to the model while ``question`` stays
    the original for display. Option 2 uses it to hand the model a pre-retrieved
    context block, since there the retrieval happens before the model runs rather
    than being driven by it.
    """
    run = RunResult(mode_key=mode_key, question=question)
    recorder = ToolCallRecorder()
    started = time.perf_counter()

    try:
        with ExitStack() as stack:
            tools: Sequence[Any] = tools_setup(stack, run) if tools_setup else ()
            agent = Agent(
                model=build_model(settings),
                tools=list(tools) if tools else None,
                system_prompt=SYSTEM_PROMPT_TEMPLATE.format(
                    today=date.today().isoformat()
                ),
                hooks=[recorder, *(extra_hooks or ())],
                callback_handler=None,  # keep stdout clean; the UI renders the trace
            )
            run.log(f"Agent created with {len(tools)} tool(s).")
            result = agent(model_input or question)
    except Exception as exc:
        run.error = f"{type(exc).__name__}: {exc}"
        run.metrics.latency_s = time.perf_counter() - started
        run.tool_calls = recorder.calls
        run.citations = recorder.citations()
        run.log(f"Run failed: {run.error}")
        return run

    latency = time.perf_counter() - started
    in_tokens, out_tokens, cycles = _usage(result)
    queries = recorder.search_query_count

    run.answer = answer_text(result)
    run.tool_calls = recorder.calls
    run.citations = recorder.citations()
    run.metrics = RunMetrics(
        latency_s=latency,
        input_tokens=in_tokens,
        output_tokens=out_tokens,
        model_cycles=cycles,
        search_queries=queries,
        model_cost_usd=estimate_model_cost(settings, in_tokens, out_tokens),
        search_cost_usd=queries * search_cost_per_query,
    )
    run.log(
        f"Completed in {latency:.1f}s over {cycles} model cycle(s), "
        f"{queries} search call(s), {in_tokens + out_tokens} tokens."
    )
    return run
