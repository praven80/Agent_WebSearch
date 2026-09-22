"""Smoke-test every API endpoint without a browser or a running server.

Uses FastAPI's TestClient, so the real route handlers and the real ``demo``
package execute. Endpoints that need AWS are expected to fail cleanly with a
useful status code when credentials are absent -- that is asserted, not skipped.

Run:  .venv/bin/python verify_api.py
"""

from __future__ import annotations

import sys

from fastapi.testclient import TestClient

from api.main import app

FAILURES: list[str] = []
client = TestClient(app)


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"ok    {label}")
    else:
        print(f"FAIL  {label}" + (f": {detail}" if detail else ""))
        FAILURES.append(label)


SETTINGS = {
    "settings": {
        "modelId": "us.anthropic.claude-sonnet-4-6",
        "gatewayUrl": "https://abc123.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp",
        "maxResults": 5,
        "domainInclude": ["https://www.python.org/downloads/", "python.org"],
        "domainExclude": ["reddit.com"],
        "publishedFrom": "2026-01-01",
        "publishedTo": "2026-09-15",
    }
}


def test_health() -> None:
    print("\n-- /api/health --")
    r = client.get("/api/health")
    check("200", r.status_code == 200, str(r.status_code))
    check("reports ok", r.json().get("status") == "ok", r.text)


def test_bootstrap() -> None:
    print("\n-- /api/bootstrap --")
    r = client.get("/api/bootstrap")
    check("200", r.status_code == 200, r.text[:200])
    body = r.json()
    check("settings present", "settings" in body)
    check("model options non-empty", len(body.get("modelOptions", [])) > 0)
    check("sample questions present", len(body.get("sampleQuestions", [])) >= 4)
    c = body.get("constraints", {})
    check("maxQueryChars is 200", c.get("maxQueryChars") == 200, str(c))
    check("maxResults range is 1-25", c.get("maxResultsRange") == [1, 25], str(c))
    check("domain cap is 100", c.get("maxDomainsPerList") == 100, str(c))
    check(
        "three Web Search regions listed",
        c.get("webSearchRegions") == ["us-east-1", "eu-west-1", "ap-northeast-1"],
        str(c.get("webSearchRegions")),
    )
    check(
        "search price is $0.007/query",
        abs(c.get("searchUsdPerQuery", 0) - 0.007) < 1e-9,
        str(c.get("searchUsdPerQuery")),
    )


def test_readiness() -> None:
    print("\n-- /api/readiness --")
    r = client.post("/api/readiness", json=SETTINGS)
    check("200", r.status_code == 200, r.text[:300])
    body = r.json()

    modes = body.get("modes", [])
    check("two options returned", len(modes) == 2, str(len(modes)))
    check("numbered 1 and 2", [m["number"] for m in modes] == [1, 2], str(modes))
    check(
        "explanation bullets present (renamed from talking points)",
        all(len(m["explanation"]) > 0 for m in modes),
    )
    check("each option carries a readiness reason", all(m["readyReason"] for m in modes))

    gw = body.get("gateway", {})
    check("gateway recognised as configured", gw.get("configured") is True, str(gw))
    check("gateway region parsed from the URL", gw.get("region") == "us-east-1", str(gw))
    check("region reported as supported", gw.get("regionSupported") is True, str(gw))

    # Filters must survive the round trip, with the pasted URL normalised and the
    # duplicate collapsed.
    s = body.get("settings", {})
    check(
        "domain include normalised and de-duplicated",
        s.get("domainInclude") == ["python.org"],
        str(s.get("domainInclude")),
    )
    check("domain exclude carried", s.get("domainExclude") == ["reddit.com"], str(s))
    check("filters reported active", s.get("filtersActive") is True, str(s))
    check(
        "filters payload matches the documented schema",
        s.get("searchFilters")
        == {
            "domainFilter": {"include": ["python.org"], "exclude": ["reddit.com"]},
            "publishedDateFilter": {"from": "2026-01-01", "to": "2026-09-15"},
        },
        str(s.get("searchFilters")),
    )

    creds = body.get("credentials", {})
    check("credentials block present", "ok" in creds and "message" in creds, str(creds))
    print(f"      credentials: ok={creds.get('ok')}: {str(creds.get('message'))[:90]}")


def test_no_filters_omitted() -> None:
    print("\n-- filters omitted when unset --")
    r = client.post(
        "/api/readiness",
        json={
            "settings": {
                "gatewayUrl": "https://a.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp",
                "domainInclude": [],
                "domainExclude": [],
            }
        },
    )
    check("200", r.status_code == 200, r.text[:200])
    s = r.json()["settings"]
    check("searchFilters empty", s["searchFilters"] == {}, str(s["searchFilters"]))
    check("filtersActive false", s["filtersActive"] is False)
    check("summary reads 'none'", s["filtersSummary"] == "none", s["filtersSummary"])


def test_architecture() -> None:
    print("\n-- /api/architecture --")
    r = client.post("/api/architecture", json=SETTINGS)
    check("200", r.status_code == 200, r.text[:300])
    options = r.json().get("options", [])
    check("two options", len(options) == 2, str(len(options)))
    for opt in options:
        key = opt["key"]
        check(f"[{key}] has an SVG diagram", opt["diagramSvg"].startswith("<svg"))
        check(f"[{key}] diagram is well-formed", opt["diagramSvg"].endswith("</svg>"))
        check(f"[{key}] has components", len(opt["components"]) > 0)
        check(f"[{key}] has request flow", len(opt["requestFlow"]) > 0)
        check(f"[{key}] has security rows", len(opt["security"]) > 0)
        check(f"[{key}] has cost rows", len(opt["cost"]) > 0)
        check(f"[{key}] has code", len(opt["code"]) > 50)
        check(f"[{key}] no failure-modes field remains", "failureModes" not in opt)
    sec_names = [s["name"] for o in options for s in o["security"]]
    check(
        "'Confused deputy' row removed",
        "Confused deputy" not in sec_names,
        str(sec_names),
    )
    check(
        "'Content controls' row present", "Content controls" in sec_names, str(sec_names)
    )


def test_comparison() -> None:
    print("\n-- /api/comparison --")
    r = client.get("/api/comparison")
    check("200", r.status_code == 200, r.text[:200])
    body = r.json()
    rows = body.get("rows", [])
    check("rows present", len(rows) >= 10, str(len(rows)))
    check(
        "each row has two option columns",
        all({"dimension", "noSearch", "withAgentCore"} <= set(r) for r in rows),
    )
    check("closing points present", len(body.get("closingPoints", [])) > 0)
    blob = str(body).lower()
    for banned in ("duckduckgo", "tavily", "serper", "third-party search api"):
        check(f"no reference to {banned}", banned not in blob)


def test_run_validation() -> None:
    print("\n-- /api/run validation --")
    r = client.post("/api/run/not_a_mode", json={"question": "x", **SETTINGS})
    check("unknown option -> 404", r.status_code == 404, str(r.status_code))

    r = client.post("/api/run/no_search", json={"question": "", **SETTINGS})
    check("empty question -> 422", r.status_code == 422, str(r.status_code))

    r = client.post(
        "/api/run/agentcore_search",
        json={"question": "x", "settings": {"gatewayUrl": "http://evil.example.com"}},
    )
    # Preflight reports the first blocker it finds. Without credentials that is the
    # credential check rather than the URL; either way it must be a 409 carrying an
    # actionable reason rather than a 500.
    detail = r.json().get("detail", "")
    check(
        "not-ready option -> 409 with an actionable reason",
        r.status_code == 409 and len(detail) > 10,
        f"{r.status_code} {r.text[:160]}",
    )
    check(
        "reason names either credentials or the Gateway URL",
        "credentials" in detail.lower() or "gateway url" in detail.lower(),
        detail,
    )

    r = client.post(
        "/api/run/no_search",
        json={"question": "x", "settings": {"maxResults": 99}},
    )
    check("maxResults above 25 -> 422", r.status_code == 422, str(r.status_code))


def test_openapi() -> None:
    print("\n-- OpenAPI schema --")
    r = client.get("/openapi.json")
    check("schema served", r.status_code == 200, str(r.status_code))
    paths = r.json().get("paths", {})
    for expected in (
        "/api/health",
        "/api/bootstrap",
        "/api/readiness",
        "/api/run/{mode_key}",
        "/api/architecture",
        "/api/comparison",
    ):
        check(f"documents {expected}", expected in paths, str(list(paths)))

    # Endpoints whose UI was removed must not linger in the schema.
    for removed in ("/api/tools", "/api/credentials/refresh"):
        check(f"no {removed} endpoint remains", removed not in paths, str(list(paths)))


def main() -> int:
    test_health()
    test_bootstrap()
    test_readiness()
    test_no_filters_omitted()
    test_architecture()
    test_comparison()
    test_run_validation()
    test_openapi()

    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed: {', '.join(FAILURES)}")
        return 1
    print("all API checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
