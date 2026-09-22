"""Governance applied to tool calls before they leave the agent.

The model chooses *whether* to search and *what* to search for -- that is the
point of the demo. But an operator still needs hard control over the request
parameters, and a value suggested in a prompt is a request, not a guarantee.

:class:`SearchPolicy` rewrites every WebSearch call so that the operator's
settings are authoritative:

  * ``maxResults`` is pinned to the configured value.
  * ``filters.domainFilter`` restricts which sites results may come from.
  * ``filters.publishedDateFilter`` bounds how old results may be.

The filter fields require connector version 1.2.0 or later. On earlier versions
the input schema exposes only ``query`` and ``maxResults``, so sending filters
would be rejected -- hence :meth:`SearchPolicy.for_settings`, which lets the
caller disable filter injection if the target is pinned to an older connector.
"""

from __future__ import annotations

import copy
from typing import Any

from strands.hooks import BeforeToolCallEvent, HookRegistry

from .config import MAX_RESULTS_RANGE, Settings

# Single source of truth for the namespaced tool name, <target>___WebSearch.
from .gateway import TOOL_SUFFIX
from .types import RunResult


def is_web_search_tool(name: str) -> bool:
    return name == TOOL_SUFFIX or name.endswith("___" + TOOL_SUFFIX)


class SearchPolicy:
    """Force operator-controlled arguments onto every WebSearch invocation.

    Registered as a Strands hook so it applies to every call the model makes,
    including second and third searches within one run.
    """

    def __init__(
        self,
        max_results: int,
        filters: dict[str, Any] | None = None,
        run: RunResult | None = None,
    ) -> None:
        low, high = MAX_RESULTS_RANGE
        self.max_results = max(low, min(int(max_results), high))
        self.filters = copy.deepcopy(filters) if filters else {}
        self.run = run
        self.overrides = 0

    @classmethod
    def for_settings(
        cls, settings: Settings, *, send_filters: bool = True
    ) -> SearchPolicy:
        return cls(
            max_results=settings.max_results,
            filters=settings.search_filters() if send_filters else None,
        )

    def register_hooks(self, registry: HookRegistry, **_: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self._on_before_tool_call)

    def _on_before_tool_call(self, event: BeforeToolCallEvent) -> None:
        tool_use = getattr(event, "tool_use", None)
        if not isinstance(tool_use, dict):
            return
        if not is_web_search_tool(tool_use.get("name", "")):
            return

        arguments = tool_use.get("input")
        if not isinstance(arguments, dict):
            return

        notes: list[str] = []

        requested = arguments.get("maxResults")
        if requested != self.max_results:
            # Mutating the nested input dict in place is what reaches the tool --
            # the event holds a reference to the object the executor will use.
            arguments["maxResults"] = self.max_results
            asked = (
                "omitted maxResults" if requested is None else f"asked for {requested}"
            )
            notes.append(f"model {asked}, pinned to {self.max_results}")

        if self.filters:
            # Operator filters win outright. A model-supplied filter could only
            # widen the result set, which is the opposite of what a governance
            # control is for.
            arguments["filters"] = copy.deepcopy(self.filters)
            notes.append("filters applied")

        if notes:
            self.overrides += 1
            if self.run is not None:
                self.run.log("Policy: " + "; ".join(notes) + ".")
