"""Option 1: no web search.

A Bedrock model answering from parametric knowledge only. No tools, no network
egress beyond the Bedrock InvokeModel call. This is the baseline that makes the
knowledge-cutoff problem visible: ask about something recent and the model either
declines or answers confidently from stale training data.
"""

from __future__ import annotations

from ..agent_runtime import check_credentials, run_agent
from ..config import Settings
from ..types import RunResult
from .base import Mode

MODE_KEY = "no_search"


def preflight(settings: Settings) -> tuple[bool, str]:
    ok, message = check_credentials(settings)
    if not ok:
        return False, f"AWS credentials not usable: {message}"
    return True, f"Bedrock model {settings.model_id} in {settings.aws_region}"


def run(question: str, settings: Settings) -> RunResult:
    def tools_setup(_stack, result: RunResult):
        result.log("No tools attached: the model can only use training data.")
        result.log(f"Invoking {settings.model_id} in {settings.aws_region}.")
        return ()

    return run_agent(
        mode_key=MODE_KEY,
        question=question,
        settings=settings,
        tools_setup=tools_setup,
        search_cost_per_query=0.0,
    )


MODE = Mode(
    key=MODE_KEY,
    number=1,
    label="No web search",
    tagline="Model answers from training data alone",
    icon="🧠",
    run=run,
    preflight=preflight,
    explanation=(
        "Knowledge is frozen at the model's training cutoff. Anything after it "
        "is either refused or answered from stale data.",
        "No citations are possible: nothing was retrieved, so there is nothing "
        "to link to and no way for a reviewer to verify the answer.",
        "Cheapest and fastest path: one InvokeModel call, no search fees.",
        "Perfectly valid for reasoning, drafting and transformation tasks that "
        "do not depend on current facts.",
    ),
)
