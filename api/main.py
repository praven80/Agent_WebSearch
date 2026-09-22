"""FastAPI backend for the AgentCore Web Search demo.

This is a thin layer over the ``demo`` package. All agent behaviour -- the MCP
connection to the Gateway, the SearchPolicy that pins maxResults and injects the
domain and published-date filters, the citation parsing and the cost accounting
-- lives in ``demo`` and is unchanged. The API only marshals it to JSON for the
React front end.

Run it with:  uvicorn api.main:app --reload --port 8000
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from api.serialize import (
    architecture_json,
    comparison_json,
    mode_json,
    run_result_json,
    settings_json,
)
from demo.agent_runtime import check_credentials
from demo.config import (
    MAX_DOMAINS_PER_LIST,
    MAX_QUERY_CHARS,
    MAX_RESULTS_RANGE,
    MODEL_LABELS,
    MODEL_PRICING,
    WEB_SEARCH_REGIONS,
    WEB_SEARCH_USD_PER_QUERY,
    Settings,
    load_settings,
    parse_domain_list,
)
from demo.modes import MODES, MODES_BY_KEY

app = FastAPI(
    title="Web Search on Amazon Bedrock AgentCore demo API",
    version="1.0.0",
    description="Backend for the Cloudscape front end. Wraps the demo package.",
)

# The Vite dev server runs on a different origin during development. In a packaged
# deployment the front end is served as static files from the same origin, so this
# only matters locally.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Questions whose correct answer changes faster than any training run can keep up.
#
# Each of these is checked to make the model actually search on every model in the
# picker, because a sample question that the model answers from memory makes the
# demo look broken rather than making the point.
#
# Phrasing matters more than it looks, in two ways.
#
# 1. "What is AMZN's share price right now?" makes Haiku decline: it reads "right
#    now" as a request for live market data that a web search cannot satisfy, and
#    answers with a list of finance websites instead. Asking how the stock closed
#    is a retrieval question, and it searches.
# 2. Keep each question to a single intent. A compound question ("how did it close,
#    and why did it move?") makes the model run one search per part, so the total
#    number of sources becomes a multiple of the per-search cap, which reads as the
#    cap being ignored. Single-intent questions give one search and exactly the
#    requested number of results.
SAMPLE_QUESTIONS = [
    "What is the latest stable release of Python, and when did it ship?",
    "What did AWS announce about Bedrock AgentCore most recently?",
    "Which foundation models were released in the last two weeks?",
    "How did Amazon (AMZN) stock close most recently?",
]


class SettingsPayload(BaseModel):
    """Settings sent from the browser with each request.

    The browser never sees AWS credentials -- those stay in the server's
    environment and are resolved by boto3 there.
    """

    modelId: str | None = None
    gatewayUrl: str | None = None
    maxResults: int | None = Field(default=None, ge=1, le=25)
    domainInclude: list[str] | None = None
    domainExclude: list[str] | None = None
    publishedFrom: str | None = None
    publishedTo: str | None = None

    def to_settings(self) -> Settings:
        base = load_settings()
        include = (
            parse_domain_list("\n".join(self.domainInclude))
            if self.domainInclude is not None
            else base.domain_include
        )
        exclude = (
            parse_domain_list("\n".join(self.domainExclude))
            if self.domainExclude is not None
            else base.domain_exclude
        )
        return Settings(
            aws_region=base.aws_region,
            aws_profile=base.aws_profile,
            model_id=(self.modelId or base.model_id).strip(),
            gateway_url=(
                self.gatewayUrl if self.gatewayUrl is not None else base.gateway_url
            ).strip(),
            max_results=self.maxResults or base.max_results,
            domain_include=include,
            domain_exclude=exclude,
            published_from=self.publishedFrom or None,
            published_to=self.publishedTo or None,
        )


class RunRequest(BaseModel):
    question: str = Field(min_length=1)
    settings: SettingsPayload = Field(default_factory=SettingsPayload)


class SettingsRequest(BaseModel):
    settings: SettingsPayload = Field(default_factory=SettingsPayload)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/bootstrap")
def bootstrap() -> dict[str, Any]:
    """Everything the app needs on first paint: defaults, options and constraints."""
    settings = load_settings()
    return {
        "settings": settings_json(settings),
        "modelOptions": [
            {"id": model_id, "label": MODEL_LABELS.get(model_id, model_id)}
            for model_id in MODEL_PRICING
        ],
        "sampleQuestions": SAMPLE_QUESTIONS,
        "constraints": {
            "maxQueryChars": MAX_QUERY_CHARS,
            "maxResultsRange": list(MAX_RESULTS_RANGE),
            "maxDomainsPerList": MAX_DOMAINS_PER_LIST,
            "webSearchRegions": list(WEB_SEARCH_REGIONS),
            "searchUsdPerQuery": WEB_SEARCH_USD_PER_QUERY,
        },
    }


@app.post("/api/readiness")
def readiness(payload: SettingsRequest) -> dict[str, Any]:
    """Credential and Gateway readiness, plus per-option preflight."""
    settings = payload.settings.to_settings()
    creds_ok, creds_message = check_credentials(settings)
    gateway_region_supported = (
        settings.gateway_region in WEB_SEARCH_REGIONS
        if settings.gateway_configured
        else None
    )
    return {
        "credentials": {"ok": creds_ok, "message": creds_message},
        "gateway": {
            "configured": settings.gateway_configured,
            "region": settings.gateway_region,
            "regionSupported": gateway_region_supported,
        },
        "modes": [mode_json(mode, settings) for mode in MODES],
        "settings": settings_json(settings),
    }


@app.post("/api/run/{mode_key}")
def run_mode(mode_key: str, payload: RunRequest) -> dict[str, Any]:
    """Run one option against one question.

    One option per request, so the front end can fire both in parallel and render
    each column as soon as it lands.
    """
    mode = MODES_BY_KEY.get(mode_key)
    if mode is None:
        raise HTTPException(status_code=404, detail=f"Unknown option '{mode_key}'.")

    settings = payload.settings.to_settings()
    ready, reason = mode.preflight(settings)
    if not ready:
        raise HTTPException(status_code=409, detail=reason)

    question = payload.question.strip()
    result = mode.run(question, settings)
    return {
        "result": run_result_json(result),
        "filtersApplied": settings.search_filters(),
    }


@app.post("/api/architecture")
def architecture(payload: SettingsRequest) -> dict[str, Any]:
    """Diagrams and detail panels, parameterised with the live configuration."""
    settings = payload.settings.to_settings()
    return {"options": [architecture_json(mode, settings) for mode in MODES]}


@app.get("/api/comparison")
def comparison() -> dict[str, Any]:
    return comparison_json()
