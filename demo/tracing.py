"""Capture what the agent actually did, so the demo can show it rather than
assert it.

:class:`ToolCallRecorder` is a Strands hook provider that records every tool
invocation -- name, arguments, duration, and the raw result payload. Both
Both options use the same recorder, which is what makes the side-by-side trace
comparison fair.
"""

from __future__ import annotations

import json
from typing import Any

from strands.hooks import AfterToolCallEvent, HookRegistry

from .types import Citation, ToolCall

# Keys the Web Search tool uses for each observation.
_TITLE_KEYS = ("title", "name")
_URL_KEYS = ("url", "link", "href")
_DATE_KEYS = ("publishedDate", "published_date", "date")
_TEXT_KEYS = ("text", "snippet", "body", "content", "description")


def _first(mapping: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


class ToolCallRecorder:
    """Strands hook provider that appends a :class:`ToolCall` per invocation."""

    def __init__(self) -> None:
        self.calls: list[ToolCall] = []

    def register_hooks(self, registry: HookRegistry, **_: Any) -> None:
        registry.add_callback(AfterToolCallEvent, self._on_after_tool_call)

    def _on_after_tool_call(self, event: AfterToolCallEvent) -> None:
        tool_use = getattr(event, "tool_use", None) or {}
        name = tool_use.get("name", "unknown")
        arguments = tool_use.get("input") or {}
        raw = _result_text(getattr(event, "result", None))

        result = getattr(event, "result", None)
        exception = getattr(event, "exception", None)
        error: str | None = None
        if exception is not None:
            error = f"{type(exception).__name__}: {exception}"
        elif isinstance(result, dict) and result.get("status") == "error":
            error = raw[:500] or "tool reported an error"

        self.calls.append(
            ToolCall(
                name=name,
                arguments=arguments
                if isinstance(arguments, dict)
                else {"input": arguments},
                result_summary=_summarize(raw),
                raw_result=raw,
                duration_s=float(getattr(event, "duration", 0.0) or 0.0),
                error=error,
            )
        )

    @property
    def search_query_count(self) -> int:
        """How many searches were billed -- one per successful tool call."""
        return sum(1 for call in self.calls if call.error is None)

    def citations(self) -> list[Citation]:
        """De-duplicated citations across every recorded tool call."""
        seen: set[str] = set()
        out: list[Citation] = []
        for call in self.calls:
            for citation in extract_citations(call.raw_result):
                key = citation.url or citation.display_title
                if key in seen:
                    continue
                seen.add(key)
                out.append(citation)
        return out


def _result_text(result: Any) -> str:
    """Flatten an MCP/Strands ToolResult into the text payload it carries.

    Handles both shapes this demo sees: the dict the agent loop produces, and the
    dict ``MCPClient.call_tool_sync`` returns for a direct call --
    ``{"status": ..., "toolUseId": ..., "content": [{"text": ...}], "isError": ...}``.
    Note that ``call_tool_sync`` returns a *dict*, not an object with attributes;
    reaching for ``.content`` on it silently yields nothing.
    """
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        blocks = result.get("content") or []
        parts: list[str] = []
        for block in blocks:
            if isinstance(block, dict):
                if isinstance(block.get("text"), str):
                    parts.append(block["text"])
                elif "json" in block:
                    parts.append(json.dumps(block["json"]))
            elif isinstance(block, str):
                parts.append(block)
        if parts:
            return "\n".join(parts)
        return json.dumps(result, default=str)
    return str(result)


def _summarize(raw: str, limit: int = 160) -> str:
    """A one-line label for the trace, e.g. "10 result(s) returned".

    This is deliberately short. It is NOT the raw payload -- ``ToolCall.raw_result``
    keeps the complete document, and the UI renders that in full.
    """
    payload = _parse_payload(raw)
    if payload is not None:
        results = payload.get("results")
        if isinstance(results, list):
            return f"{len(results)} result(s) returned"
    flat = " ".join(raw.split())
    return flat[:limit] + ("..." if len(flat) > limit else "")


def _parse_payload(raw: str) -> dict[str, Any] | None:
    """The Web Search tool returns a JSON document inside a text content block."""
    if not raw or not raw.lstrip().startswith(("{", "[")):
        return None
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if isinstance(parsed, list):
        return {"results": parsed}
    return parsed if isinstance(parsed, dict) else None


def extract_citations(raw: Any) -> list[Citation]:
    """Pull ``{title, url, publishedDate, text}`` observations out of a payload.

    Handles the Web Search response shape -- a JSON document nested in a text
    content block, with a ``results`` array -- whether it arrives wrapped in an
    MCP ``ToolResult`` envelope from the agent loop, or as the bare
    payload from a direct ``tools/call`` (Option 2).
    """
    if not isinstance(raw, str):
        raw = _result_text(raw)
    payload = _parse_payload(raw)
    if payload is None:
        return []

    observations = payload.get("results")
    if not isinstance(observations, list):
        observations = payload.get("observations")
    if not isinstance(observations, list):
        return []

    citations: list[Citation] = []
    for obs in observations:
        if not isinstance(obs, dict):
            continue
        url = _first(obs, _URL_KEYS)
        title = _first(obs, _TITLE_KEYS)
        text = _first(obs, _TEXT_KEYS)
        # Knowledge-graph observations come back with null title and url and
        # structured facts in `text`. Keep them, labelled, rather than dropping.
        if not url and not title and text:
            title = "Knowledge graph fact"
        if not (url or title or text):
            continue
        citations.append(
            Citation(
                title=title,
                url=url,
                published_date=_first(obs, _DATE_KEYS),
                snippet=text,
            )
        )
    return citations
