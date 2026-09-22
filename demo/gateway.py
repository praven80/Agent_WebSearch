"""The single path to Web Search: an AgentCore Gateway, over MCP, signed with SigV4.

Web Search on Amazon Bedrock AgentCore is reachable *only* as an MCP tool on a
Gateway. There is no standalone ``InvokeWebSearch`` API operation --
``bedrock-agentcore:InvokeWebSearch`` is an IAM action authorised per invocation
against the AWS-owned tool ARN, which is what the Gateway's service role uses on
your behalf.

No third-party search provider is involved anywhere.
"""

from __future__ import annotations

from strands.tools.mcp import MCPClient

from .agent_runtime import boto_session
from .config import Settings, validate_gateway_url

# The Gateway is signed as the bedrock-agentcore service.
AWS_SERVICE = "bedrock-agentcore"

# The Gateway namespaces connector tools as <targetName>___WebSearch.
TOOL_SUFFIX = "WebSearch"


def frozen_credentials(settings: Settings):
    """Resolve credentials up front so signing failures surface with context.

    We hand explicit credentials to the transport rather than a profile name --
    the profile path in mcp-proxy-for-aws mis-signs for some profile names
    (for example, names containing '+'), which shows up as an opaque 403.
    """
    creds = boto_session(settings, region=settings.gateway_region).get_credentials()
    if creds is None:
        raise RuntimeError(
            "No AWS credentials found. Run 'aws configure', set AWS_PROFILE, or "
            "assume a role before starting the demo."
        )
    return creds.get_frozen_credentials()


def build_mcp_client(settings: Settings) -> MCPClient:
    """An MCP client over a SigV4-signed Streamable HTTP connection to the Gateway."""
    from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client

    url = validate_gateway_url(settings.gateway_url)
    region = settings.gateway_region
    credentials = frozen_credentials(settings)

    def transport():
        return aws_iam_streamablehttp_client(
            endpoint=url,
            aws_service=AWS_SERVICE,
            aws_region=region,
            credentials=credentials,
        )

    return MCPClient(transport)


def preflight(settings: Settings) -> tuple[bool, str]:
    """Readiness check for the option that reaches the Gateway."""
    from .agent_runtime import check_credentials
    from .config import WEB_SEARCH_REGIONS

    creds_ok, creds_msg = check_credentials(settings)
    if not creds_ok:
        return False, f"AWS credentials not usable: {creds_msg}"
    try:
        validate_gateway_url(settings.gateway_url)
    except ValueError as exc:
        return False, str(exc)
    region = settings.gateway_region
    if region not in WEB_SEARCH_REGIONS:
        return False, (
            f"Gateway is in {region}, but Web Search is available only in "
            f"{', '.join(WEB_SEARCH_REGIONS)}."
        )
    return True, f"Gateway reachable in {region}"
