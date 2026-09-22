"""Shared result types for the three demo modes.

Every mode returns the same :class:`RunResult` so the UI can render them
side-by-side and the comparison table stays honest.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Citation:
    """One source the agent grounded its answer in."""

    title: str = ""
    url: str = ""
    published_date: str = ""
    snippet: str = ""

    @property
    def display_title(self) -> str:
        return self.title or self.url or "(untitled)"

    @property
    def domain(self) -> str:
        from urllib.parse import urlparse

        return urlparse(self.url).netloc if self.url else ""


@dataclass
class ToolCall:
    """A single tool invocation the agent made, captured for the trace panel."""

    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    result_summary: str = ""
    raw_result: Any = None
    duration_s: float = 0.0
    error: str | None = None


@dataclass
class RunMetrics:
    """What a single run cost, in time, tokens and dollars."""

    latency_s: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    model_cycles: int = 0
    search_queries: int = 0
    model_cost_usd: float = 0.0
    search_cost_usd: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def total_cost_usd(self) -> float:
        return self.model_cost_usd + self.search_cost_usd


@dataclass
class RunResult:
    """The full outcome of running one option against one question."""

    mode_key: str
    question: str
    answer: str = ""
    citations: list[Citation] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    metrics: RunMetrics = field(default_factory=RunMetrics)
    trace: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    @property
    def grounded(self) -> bool:
        """Did the run actually retrieve live sources?"""
        return bool(self.citations)

    def log(self, message: str) -> None:
        self.trace.append(message)
