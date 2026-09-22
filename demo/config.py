"""Configuration for the AgentCore Web Search demo.

Everything is resolved from the environment (or a local ``.env``) so the app can
be handed to a customer with nothing but a file to fill in. Nothing here reads
or prints credential *values* -- only whether a credential is present.
"""

from __future__ import annotations

import os
import pathlib
import re
from dataclasses import dataclass
from typing import Any

# Regions where the AgentCore Web Search connector is available.
WEB_SEARCH_REGIONS = ("us-east-1", "eu-west-1", "ap-northeast-1")

# Published list price for the managed Web Search tool: $7 per 1,000 queries.
WEB_SEARCH_USD_PER_QUERY = 7.0 / 1000.0

# Hard limits from the Web Search input schema.
MAX_QUERY_CHARS = 200
MAX_RESULTS_RANGE = (1, 25)

# Request-level domain filters allow up to 100 entries per list (connector 1.2.0+).
MAX_DOMAINS_PER_LIST = 100


def normalize_domain(value: str) -> str:
    """Reduce a pasted URL or host to the bare domain the filter expects.

    Accepts ``https://www.python.org/downloads/`` and returns ``python.org``. The
    leading ``www.`` is dropped because a root domain already matches its
    subdomains, so the shorter form is strictly more permissive and less
    surprising.
    """
    text = (value or "").strip().strip(",").strip()
    if not text:
        return ""
    if "//" in text:
        text = text.split("//", 1)[1]
    text = text.split("/", 1)[0].split("?", 1)[0]
    # Strip a port, e.g. example.com:8443
    if ":" in text:
        text = text.split(":", 1)[0]
    text = text.strip().lower().rstrip(".")
    if text.startswith("www."):
        text = text[4:]
    return text


def parse_domain_list(raw: str) -> tuple[str, ...]:
    """Parse a comma-, space- or newline-separated domain list, de-duplicated."""
    if not raw:
        return ()
    tokens = raw.replace(",", "\n").replace(" ", "\n").splitlines()
    out: list[str] = []
    for token in tokens:
        domain = normalize_domain(token)
        if domain and domain not in out:
            out.append(domain)
    return tuple(out[:MAX_DOMAINS_PER_LIST])


# An AgentCore Gateway MCP endpoint. Validated before we connect so a typo fails
# fast with a clear message instead of signing a request to an unintended host.
GATEWAY_HOST_RE = re.compile(
    r"^[a-z0-9-]+\.gateway\.bedrock-agentcore\.[a-z0-9-]+\.amazonaws\.com$"
)

# Rough on-demand Bedrock text pricing (USD per 1M tokens) for the models this
# demo offers. Used only to put an order-of-magnitude number next to each run --
# it is an estimate, not a bill.
# Models offered in the picker, with approximate on-demand pricing.
#
# Amazon Nova Pro and Nova Lite are deliberately excluded. Both answer fine with no
# tools, but on the Web Search path Bedrock returns
# "modelStreamErrorException: Model produced invalid sequence as part of ToolUse",
# most likely because of the nested filters object in the tool's input schema. Only
# models verified end to end on both options belong here.
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "us.anthropic.claude-sonnet-4-6": (3.00, 15.00),
    "us.anthropic.claude-haiku-4-5-20251001-v1:0": (1.00, 5.00),
}

# Friendly names for the model picker. Keys must match MODEL_PRICING.
MODEL_LABELS: dict[str, str] = {
    "us.anthropic.claude-sonnet-4-6": "Claude Sonnet 4.6",
    "us.anthropic.claude-haiku-4-5-20251001-v1:0": "Claude Haiku 4.5",
}

DEFAULT_MODEL_ID = "us.anthropic.claude-sonnet-4-6"


def load_dotenv(start: pathlib.Path | None = None) -> None:
    """Load ``KEY=VALUE`` lines from a project-local ``.env`` into ``os.environ``.

    Existing environment variables win, so an exported value always overrides
    the file. Called once at import time by :func:`load_settings`.
    """
    base = start or pathlib.Path(__file__).resolve().parent.parent
    env_path = base / ".env"
    if not env_path.is_file():
        return
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def region_from_gateway_url(url: str) -> str | None:
    """Pull the AWS region out of a Gateway host name, or return ``None``."""
    match = re.search(
        r"gateway\.bedrock-agentcore\.([a-z0-9-]+)\.amazonaws\.com", url or ""
    )
    return match.group(1) if match else None


def validate_gateway_url(url: str) -> str:
    """Return ``url`` if it is an HTTPS AgentCore Gateway endpoint, else raise."""
    if not url:
        raise ValueError(
            "No Gateway URL configured. Deploy infra/agentcore-websearch.yaml "
            "(./infra/deploy.sh) and set AGENTCORE_GATEWAY_URL."
        )
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(f"Gateway URL must use https, got '{parsed.scheme or url}'.")
    if not parsed.hostname or not GATEWAY_HOST_RE.match(parsed.hostname):
        raise ValueError(
            "Gateway URL host is not an AgentCore Gateway endpoint. Expected "
            "<id>.gateway.bedrock-agentcore.<region>.amazonaws.com, got "
            f"'{parsed.hostname or url}'."
        )
    return url


@dataclass
class Settings:
    """Resolved demo configuration."""

    aws_region: str = "us-east-1"
    aws_profile: str | None = None
    model_id: str = DEFAULT_MODEL_ID
    gateway_url: str = ""
    max_results: int = 5
    # Request-level filters, applied to every search (connector 1.2.0+).
    domain_include: tuple[str, ...] = ()
    domain_exclude: tuple[str, ...] = ()
    # ISO-8601 (YYYY-MM-DD) publication-date bounds, inclusive.
    published_from: str | None = None
    published_to: str | None = None

    def search_filters(self) -> dict[str, Any]:
        """Build the ``filters`` object for a WebSearch call, omitting empty parts.

        Returns ``{}`` when nothing is configured, so the argument can be dropped
        entirely rather than sending empty lists the service would have to ignore.
        """
        domain_filter: dict[str, list[str]] = {}
        if self.domain_include:
            domain_filter["include"] = list(self.domain_include)
        if self.domain_exclude:
            domain_filter["exclude"] = list(self.domain_exclude)

        date_filter: dict[str, str] = {}
        if self.published_from:
            date_filter["from"] = self.published_from
        if self.published_to:
            date_filter["to"] = self.published_to

        filters: dict[str, Any] = {}
        if domain_filter:
            filters["domainFilter"] = domain_filter
        if date_filter:
            filters["publishedDateFilter"] = date_filter
        return filters

    @property
    def filters_active(self) -> bool:
        return bool(self.search_filters())

    def filters_summary(self) -> str:
        """One-line description of the active filters, for the trace and the UI."""
        parts = []
        if self.domain_include:
            parts.append(f"only {', '.join(self.domain_include)}")
        if self.domain_exclude:
            parts.append(f"excluding {', '.join(self.domain_exclude)}")
        if self.published_from or self.published_to:
            lo = self.published_from or "any"
            hi = self.published_to or "any"
            parts.append(f"published {lo} to {hi}")
        return "; ".join(parts) if parts else "none"

    @property
    def gateway_configured(self) -> bool:
        try:
            validate_gateway_url(self.gateway_url)
        except ValueError:
            return False
        return True

    @property
    def gateway_region(self) -> str:
        """Region to sign Gateway requests for -- the Gateway's own region wins."""
        return region_from_gateway_url(self.gateway_url) or self.aws_region

    def model_pricing(self) -> tuple[float, float] | None:
        """(input, output) USD per 1M tokens for the selected model, if known."""
        return MODEL_PRICING.get(self.model_id)


def load_settings() -> Settings:
    """Build :class:`Settings` from ``.env`` + environment."""
    load_dotenv()
    gateway_url = os.environ.get("AGENTCORE_GATEWAY_URL", "").strip()
    region = (
        region_from_gateway_url(gateway_url)
        or os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or "us-east-1"
    )
    return Settings(
        aws_region=region,
        aws_profile=os.environ.get("AWS_PROFILE") or None,
        model_id=os.environ.get("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID).strip()
        or DEFAULT_MODEL_ID,
        gateway_url=gateway_url,
        max_results=int(os.environ.get("MAX_SEARCH_RESULTS", "5")),
        domain_include=parse_domain_list(os.environ.get("SEARCH_DOMAIN_INCLUDE", "")),
        domain_exclude=parse_domain_list(os.environ.get("SEARCH_DOMAIN_EXCLUDE", "")),
        published_from=(os.environ.get("SEARCH_PUBLISHED_FROM") or "").strip() or None,
        published_to=(os.environ.get("SEARCH_PUBLISHED_TO") or "").strip() or None,
    )
