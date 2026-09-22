"""Convert the demo package's dataclasses into JSON the React app consumes.

Kept separate from the route handlers so the wire format is defined in one place.
Field names are camelCase, matching the TypeScript types in web/src/api/types.ts.
"""

from __future__ import annotations

import contextlib
import json
from typing import Any

from demo.architecture import ARCH_DETAILS, CLOSING_POINTS, COMPARISON_ROWS, diagram_svg
from demo.config import Settings
from demo.modes.base import Mode
from demo.types import Citation, RunResult, ToolCall


def citation_json(citation: Citation) -> dict[str, Any]:
    return {
        "title": citation.title,
        "displayTitle": citation.display_title,
        "url": citation.url,
        "domain": citation.domain,
        "publishedDate": citation.published_date,
        "snippet": citation.snippet,
    }


def _pretty(raw: Any) -> str:
    """Pretty-print a tool payload in full. Never truncates.

    The customer asks to see exactly what the Web Search tool returned, and this
    is also verbatim what the model received, so nothing is trimmed here.
    """
    text = raw if isinstance(raw, str) else json.dumps(raw, default=str)
    # Re-indent when the payload is JSON; leave it untouched when it is not.
    with contextlib.suppress(json.JSONDecodeError, TypeError):
        text = json.dumps(json.loads(text), indent=2, ensure_ascii=False)
    return text


def tool_call_json(call: ToolCall) -> dict[str, Any]:
    payload = _pretty(call.raw_result) if call.raw_result else ""
    return {
        "name": call.name,
        "arguments": call.arguments,
        "resultSummary": call.result_summary,
        "rawResult": payload,
        "rawResultChars": len(payload),
        "durationSeconds": call.duration_s,
        "error": call.error,
    }


def run_result_json(result: RunResult) -> dict[str, Any]:
    m = result.metrics
    return {
        "modeKey": result.mode_key,
        "question": result.question,
        "answer": result.answer,
        "ok": result.ok,
        "grounded": result.grounded,
        "error": result.error,
        "trace": list(result.trace),
        "citations": [citation_json(c) for c in result.citations],
        "toolCalls": [tool_call_json(c) for c in result.tool_calls],
        "metrics": {
            "latencySeconds": m.latency_s,
            "inputTokens": m.input_tokens,
            "outputTokens": m.output_tokens,
            "totalTokens": m.total_tokens,
            "modelCycles": m.model_cycles,
            "searchQueries": m.search_queries,
            "modelCostUsd": m.model_cost_usd,
            "searchCostUsd": m.search_cost_usd,
            "totalCostUsd": m.total_cost_usd,
        },
    }


def mode_json(mode: Mode, settings: Settings) -> dict[str, Any]:
    ready, reason = mode.preflight(settings)
    return {
        "key": mode.key,
        "number": mode.number,
        "label": mode.label,
        "title": mode.title,
        "tagline": mode.tagline,
        "icon": mode.icon,
        "explanation": list(mode.explanation),
        "ready": ready,
        "readyReason": reason,
        "offersSearch": mode.offers_search,
    }


def architecture_json(mode: Mode, settings: Settings) -> dict[str, Any]:
    detail = ARCH_DETAILS[mode.key]
    region = settings.aws_region if mode.key == "no_search" else settings.gateway_region
    return {
        "key": mode.key,
        "number": mode.number,
        "title": mode.title,
        "tagline": mode.tagline,
        "summary": detail.summary,
        "diagramSvg": diagram_svg(
            mode.key,
            model_id=settings.model_id,
            region=region,
        ),
        "components": [
            {"component": c[0], "operatedBy": c[1], "responsibility": c[2]}
            for c in detail.components
        ],
        "requestFlow": list(detail.request_flow),
        "youOwn": list(detail.you_own),
        "awsOwns": list(detail.aws_owns),
        "security": [{"name": n, "value": v} for n, v in detail.security],
        "cost": [{"name": n, "value": v} for n, v in detail.cost],
        "codeCaption": detail.code_caption,
        "code": detail.code,
        "iam": detail.iam,
        "links": [{"label": label, "url": url} for label, url in detail.links],
    }


def comparison_json() -> dict[str, Any]:
    return {
        "rows": [
            {"dimension": r[0], "noSearch": r[1], "withAgentCore": r[2]}
            for r in COMPARISON_ROWS
        ],
        "closingPoints": list(CLOSING_POINTS),
    }


def settings_json(settings: Settings) -> dict[str, Any]:
    return {
        "awsRegion": settings.aws_region,
        "awsProfile": settings.aws_profile,
        "modelId": settings.model_id,
        "gatewayUrl": settings.gateway_url,
        "gatewayRegion": settings.gateway_region,
        "gatewayConfigured": settings.gateway_configured,
        "maxResults": settings.max_results,
        "domainInclude": list(settings.domain_include),
        "domainExclude": list(settings.domain_exclude),
        "publishedFrom": settings.published_from,
        "publishedTo": settings.published_to,
        "filtersActive": settings.filters_active,
        "filtersSummary": settings.filters_summary(),
        "searchFilters": settings.search_filters(),
    }
