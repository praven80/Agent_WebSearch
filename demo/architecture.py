"""Architecture diagrams and show-and-tell detail for each option.

Diagrams are hand-authored SVG so they render identically everywhere and stay
legible when projected. All three share one canvas size and palette, so switching
between them in front of a customer changes only what matters.
"""

from __future__ import annotations

from dataclasses import dataclass, field

CANVAS_W = 1010
CANVAS_H = 360

# Palette
INK = "#16232e"
MUTED = "#5b6b78"
AWS_ORANGE = "#ff9900"
AWS_SQUID = "#232f3e"
GREY = "#8899a6"
AMBER = "#e8a33d"
TEAL = "#2e8b6f"
RED = "#c0392b"
PANEL = "#ffffff"
CANVAS_BG = "#f7f9fb"


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _box(
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    lines: tuple[str, ...] = (),
    *,
    stroke: str = AWS_SQUID,
    fill: str = PANEL,
    title_color: str | None = None,
    dashed: bool = False,
) -> str:
    """A rounded node box with a bold title and small detail lines."""
    dash = ' stroke-dasharray="5 4"' if dashed else ""
    title_y = y + (26 if lines else h / 2 + 5)
    parts = [
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="2"{dash}/>',
        f'<text x="{x + w / 2}" y="{title_y}" text-anchor="middle" '
        f'font-size="14" font-weight="700" fill="{title_color or INK}">{_esc(title)}</text>',
    ]
    for i, line in enumerate(lines):
        parts.append(
            f'<text x="{x + w / 2}" y="{title_y + 18 + i * 15}" text-anchor="middle" '
            f'font-size="11.5" fill="{MUTED}">{_esc(line)}</text>'
        )
    return "".join(parts)


def _boundary(x: float, y: float, w: float, h: float, label: str, color: str) -> str:
    """A dashed trust/account boundary with a label in the top-left corner."""
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="none" '
        f'stroke="{color}" stroke-width="2" stroke-dasharray="8 5" opacity="0.85"/>'
        f'<text x="{x + 12}" y="{y + 19}" font-size="12" font-weight="700" '
        f'fill="{color}" letter-spacing="0.4">{_esc(label)}</text>'
    )


def _arrow(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    label: str = "",
    sub: str = "",
    *,
    color: str = AWS_SQUID,
    dashed: bool = False,
    marker: str = "arrow",
    label_above: bool = True,
) -> str:
    dash = ' stroke-dasharray="6 4"' if dashed else ""
    parts = [
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" '
        f'stroke-width="2"{dash} marker-end="url(#{marker})"/>'
    ]
    if label or sub:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        # Stack the labels clear of the line: two lines need 26px of headroom,
        # one needs 10px. Getting this wrong puts text on top of the arrow.
        if label_above:
            label_y = my - (26 if sub else 10)
        else:
            label_y = my + 20
        if label:
            parts.append(
                f'<text x="{mx}" y="{label_y}" text-anchor="middle" font-size="11" '
                f'font-weight="600" fill="{color}">{_esc(label)}</text>'
            )
        if sub:
            sub_y = label_y + 14 if label else my - 10
            parts.append(
                f'<text x="{mx}" y="{sub_y}" text-anchor="middle" font-size="10.5" '
                f'fill="{MUTED}">{_esc(sub)}</text>'
            )
    return "".join(parts)


def _caption(text: str, color: str) -> str:
    return (
        f'<rect x="18" y="{CANVAS_H - 44}" width="{CANVAS_W - 36}" height="30" rx="7" '
        f'fill="{color}" opacity="0.10"/>'
        f'<text x="{CANVAS_W / 2}" y="{CANVAS_H - 24}" text-anchor="middle" '
        f'font-size="12.5" font-weight="700" fill="{color}">{_esc(text)}</text>'
    )


def _svg(body: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CANVAS_W} {CANVAS_H}" '
        f'width="100%" role="img" '
        f'font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Helvetica, Arial, sans-serif">'
        "<defs>"
        f'<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        f'markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{AWS_SQUID}"/></marker>'
        f'<marker id="arrowAmber" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        f'markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{AMBER}"/></marker>'
        f'<marker id="arrowTeal" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        f'markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{TEAL}"/></marker>'
        f'<marker id="arrowRed" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        f'markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{RED}"/></marker>'
        "</defs>"
        f'<rect width="{CANVAS_W}" height="{CANVAS_H}" rx="10" fill="{CANVAS_BG}"/>'
        f"{body}</svg>"
    )


# --------------------------------------------------------------------------- #
# Option 1: no web search
# --------------------------------------------------------------------------- #


def _svg_no_search(model_id: str, region: str) -> str:
    body = "".join(
        [
            f'<text x="20" y="34" font-size="15" font-weight="800" fill="{INK}">'
            f"Option 1: No web search</text>",
            f'<text x="20" y="53" font-size="11.5" fill="{MUTED}">'
            f"One InvokeModel call. The model has no path to anything published after training.</text>",
            _boundary(205, 78, 505, 205, f"YOUR AWS ACCOUNT · {region}", AWS_ORANGE),
            _box(20, 158, 150, 74, "Analyst", ("asks a question",), stroke=GREY),
            _box(
                228,
                150,
                210,
                90,
                "Strands agent",
                ("React + Cloudscape UI", "tools: none"),
                stroke=GREY,
            ),
            _box(
                480,
                150,
                210,
                90,
                "Amazon Bedrock",
                (_short_model(model_id), "bedrock:InvokeModel"),
                stroke=AWS_ORANGE,
            ),
            _arrow(172, 195, 226, 195),
            _arrow(440, 195, 478, 195),
            _box(
                790,
                150,
                200,
                90,
                "Public web",
                ("live prices, releases,", "today's news"),
                stroke=GREY,
                fill="#eef1f4",
                title_color=MUTED,
                dashed=True,
            ),
            _arrow(
                694, 195, 786, 195, "no path", color=RED, dashed=True, marker="arrowRed"
            ),
            f'<text x="740" y="228" text-anchor="middle" font-size="20" font-weight="800" '
            f'fill="{RED}">✕</text>',
            _caption(
                "Knowledge frozen at the training cutoff · no citations possible · lowest cost and latency",
                GREY,
            ),
        ]
    )
    return _svg(body)


# --------------------------------------------------------------------------- #
# Option 2: web search with AgentCore
# --------------------------------------------------------------------------- #


def _svg_agentcore_search(model_id: str, region: str) -> str:
    body = "".join(
        [
            f'<text x="20" y="34" font-size="15" font-weight="800" fill="{INK}">'
            f"Option 2: Web search with Amazon Bedrock AgentCore</text>",
            f'<text x="20" y="53" font-size="11.5" fill="{MUTED}">'
            f"One managed connector. SigV4 in, IAM service role out, no key anywhere, no egress.</text>",
            _boundary(155, 66, 345, 224, f"YOUR AWS ACCOUNT · {region}", AWS_ORANGE),
            _boundary(596, 150, 398, 140, "AWS SERVICE ACCOUNT", TEAL),
            _box(20, 180, 118, 74, "Analyst", ("asks a question",), stroke=GREY),
            _box(
                166,
                92,
                170,
                56,
                "Amazon Bedrock",
                (_short_model(model_id),),
                stroke=AWS_ORANGE,
            ),
            _box(
                166,
                175,
                150,
                84,
                "Strands agent",
                ("MCP client", "SigV4-signed"),
                stroke=TEAL,
            ),
            _arrow(241, 173, 241, 152, color=AWS_ORANGE, marker="arrowTeal"),
            _box(
                336,
                175,
                154,
                84,
                "AgentCore Gateway",
                ("MCP protocol", "AWS_IAM inbound"),
                stroke=TEAL,
                title_color="#1d6b54",
            ),
            _box(
                612,
                175,
                168,
                84,
                "web-search connector",
                ("connectorId:", "web-search"),
                stroke=TEAL,
            ),
            _box(
                800,
                175,
                180,
                84,
                "Amazon web index",
                ("tens of billions of docs", "+ knowledge graph"),
                stroke=TEAL,
            ),
            _arrow(140, 217, 164, 217),
            _arrow(318, 217, 334, 217, marker="arrowTeal", color=TEAL),
            # Crosses the trust boundary, so it gets the widest gap in the diagram.
            _arrow(
                486,
                217,
                608,
                217,
                "IAM service role",
                "InvokeWebSearch",
                color=TEAL,
                marker="arrowTeal",
            ),
            _arrow(782, 217, 798, 217, color=TEAL, marker="arrowTeal"),
            # Sits over the Gateway box, clear of the vertical Bedrock arrow at x=241.
            f'<text x="413" y="166" text-anchor="middle" font-size="10.5" '
            f'fill="{MUTED}">tools/list → WebSearch</text>',
            _caption(
                "Query served entirely inside AWS · no third-party egress · $7 per 1,000 queries",
                TEAL,
            ),
        ]
    )
    return _svg(body)


def _short_model(model_id: str) -> str:
    """Trim a long inference-profile id so it fits inside a diagram box."""
    tail = model_id.split(".")[-1]
    return tail if len(tail) <= 30 else tail[:29] + "…"


def diagram_svg(mode_key: str, *, model_id: str, region: str) -> str:
    """The SVG for one option, parameterised with the live demo configuration."""
    if mode_key == "no_search":
        return _svg_no_search(model_id, region)
    if mode_key == "agentcore_search":
        return _svg_agentcore_search(model_id, region)
    raise KeyError(mode_key)


# --------------------------------------------------------------------------- #
# Show-and-tell detail per option
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ArchDetail:
    """Everything the architecture tab shows beneath the diagram."""

    summary: str
    # (component, who runs it, what it does)
    components: tuple[tuple[str, str, str], ...]
    request_flow: tuple[str, ...]
    you_own: tuple[str, ...]
    aws_owns: tuple[str, ...]
    security: tuple[tuple[str, str], ...]
    cost: tuple[tuple[str, str], ...]
    code_caption: str
    code: str
    iam: str | None = None
    links: tuple[tuple[str, str], ...] = field(default_factory=tuple)


DOC_LINKS = (
    (
        "Web Search Tool: AgentCore Developer Guide",
        "https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-target-connector-web-search-tool.html",
    ),
    (
        "Introducing Web Search on Amazon Bedrock AgentCore (AWS ML Blog)",
        "https://aws.amazon.com/blogs/machine-learning/introducing-web-search-on-amazon-bedrock-agentcore/",
    ),
)


ARCH_DETAILS: dict[str, ArchDetail] = {
    "no_search": ArchDetail(
        summary=(
            "A single Bedrock InvokeModel call. The agent has no tools, so the only "
            "knowledge available is what the model absorbed during training. This is "
            "the baseline that makes the gap visible, and it is still the right "
            "architecture for reasoning, drafting and transformation work that does "
            "not depend on current facts."
        ),
        components=(
            ("Web app + Strands agent", "You", "Prompts the model; no tools registered"),
            ("Amazon Bedrock", "AWS", "Serves the selected foundation model"),
        ),
        request_flow=(
            "Analyst submits a question.",
            "Agent sends the system prompt plus the question to Bedrock.",
            "Model answers from parametric knowledge only.",
            "Answer is returned with no sources, because nothing was retrieved.",
        ),
        you_own=(
            "The prompt and the model choice.",
            "Communicating the knowledge cutoff to your users.",
        ),
        aws_owns=("Model hosting, scaling and inference.",),
        security=(
            ("Data path", "Question goes to Bedrock in your region and nowhere else."),
            ("Credentials", "Caller needs bedrock:InvokeModel. Nothing else."),
            ("Egress", "None beyond the Bedrock API call."),
        ),
        cost=(
            ("Model tokens", "On-demand Bedrock pricing for the selected model."),
            ("Search", "$0: no search happens."),
            ("Infrastructure", "None."),
        ),
        code_caption="The whole implementation: one agent, zero tools.",
        code="""from strands import Agent
from strands.models.bedrock import BedrockModel

agent = Agent(
    model=BedrockModel(model_id="us.anthropic.claude-sonnet-4-6"),
    system_prompt="You are a research assistant. Today is 2026-09-15.",
    # no tools: the model cannot reach anything published after training
)

result = agent("What shipped in the latest Python release?")""",
    ),
    "agentcore_search": ArchDetail(
        summary=(
            "The agent connects to an AgentCore Gateway over MCP and discovers the "
            "managed WebSearch tool with a standard tools/list call. There is no "
            "provider SDK, no API key and no response-mapping code. The Gateway "
            "snapshots the tool schema, resolves the endpoint, and authenticates to "
            "the AWS-owned Web Search backend with its own IAM service role. The "
            "query is served entirely within AWS."
        ),
        components=(
            ("Web app + Strands agent", "You", "MCP client; SigV4-signs each request"),
            (
                "AgentCore Gateway",
                "AWS (in your account)",
                "MCP endpoint, AWS_IAM inbound auth, schema governance",
            ),
            (
                "Gateway IAM service role",
                "You (created once)",
                "Outbound auth: bedrock-agentcore:InvokeWebSearch",
            ),
            (
                "web-search connector",
                "AWS service account",
                "Managed target, connectorId: web-search",
            ),
            (
                "Amazon web index + knowledge graph",
                "AWS",
                "Tens of billions of docs, refreshed within minutes",
            ),
            ("Amazon Bedrock", "AWS", "Serves the model that decides when to search"),
        ),
        request_flow=(
            "Analyst submits a question.",
            "Agent opens a SigV4-signed Streamable HTTP MCP session to the Gateway.",
            "Agent calls tools/list and discovers <target>___WebSearch with its schema.",
            "Model decides it needs current information and emits a tools/call.",
            "Gateway validates against the snapshotted schema, assumes its service role, "
            "and routes the request internally within AWS.",
            "Web Search runs the query against the Amazon index, consults the knowledge "
            "graph for entity facts, and extracts semantically relevant snippets.",
            "Results come back in the MCP envelope: a text block holding a JSON document "
            "with title, url, publishedDate and text per observation.",
            "Model composes an answer and cites the returned sources.",
        ),
        you_own=(
            "Creating the Gateway and attaching the target: one CloudFormation stack.",
            "Inbound authorization: which IAM principals may call your Gateway.",
            "Request parameters: this demo pins maxResults and injects the domain and "
            "published-date filters on every call, so the model cannot widen them.",
            "Optional target-level domain include/exclude lists, enforced at the "
            "target and invisible to the agent.",
            "Displaying the citations, which the acceptable-use terms require.",
        ),
        aws_owns=(
            "The web index: crawl, coverage, freshness, knowledge graph.",
            "Snippet extraction tuned for model context.",
            "The tool schema, endpoint resolution and service authentication.",
            "Scaling, availability and quality improvements, delivered through the "
            "same connector with no migration on your side.",
        ),
        security=(
            (
                "Data path",
                "Query is served inside AWS. It is not sent to a third-party engine.",
            ),
            (
                "Inbound auth",
                "AWS_IAM (SigV4) here: no IdP, no OAuth client, no bearer token. "
                "CUSTOM_JWT via Cognito or another IdP is the alternative.",
            ),
            (
                "Outbound auth",
                "GATEWAY_IAM_ROLE. The Gateway assumes your service role; there is "
                "no API key to store or rotate.",
            ),
            (
                "Least privilege",
                "The service role grants InvokeGateway and InvokeWebSearch only. "
                "It deliberately has no bedrock:InvokeModel. Model access belongs "
                "to the identity running the agent.",
            ),
            (
                "Content controls",
                "Domain include/exclude lists and published-date bounds are "
                "enforced on every request, so results can be restricted to "
                "sources you trust. Target-level lists are hidden from the "
                "agent entirely.",
            ),
        ),
        cost=(
            ("Search", "$7 per 1,000 queries, pay as you go. Under a cent per question."),
            (
                "Model tokens",
                "On-demand Bedrock pricing. Snippet extraction means fewer tokens "
                "spent on page boilerplate.",
            ),
            (
                "Infrastructure",
                "No persistent infrastructure beyond the Gateway and its target.",
            ),
            ("Billing", "On your AWS bill. No second vendor invoice or contract."),
        ),
        code_caption="Setup is one target; the agent side is tools/list.",
        code="""# --- one-time setup: attach the managed connector to a Gateway -------------
import boto3
control = boto3.client("bedrock-agentcore-control", region_name="us-east-1")

control.create_gateway_target(
    gatewayIdentifier=gateway_id,
    name="web-search-tool",
    targetConfiguration={"mcp": {"connector": {
        "source": {"connectorId": "web-search"},
        "configurations": [{"name": "WebSearch", "parameterValues": {}}],
    }}},
    credentialProviderConfigurations=[{"credentialProviderType": "GATEWAY_IAM_ROLE"}],
)

# --- agent side: discover the tool over MCP, SigV4-signed ------------------
from strands import Agent
from strands.tools.mcp import MCPClient
from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client

client = MCPClient(lambda: aws_iam_streamablehttp_client(
    endpoint=GATEWAY_URL,
    aws_service="bedrock-agentcore",
    aws_region="us-east-1",
))

with client:
    tools = client.list_tools_sync()          # WebSearch arrives from the Gateway
    agent = Agent(model=model, tools=tools, system_prompt=SYSTEM_PROMPT)
    result = agent("What shipped in the latest Python release?")

# No API key. No provider SDK. No response-parsing glue.""",
        iam="""{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "InvokeGateway",
      "Effect": "Allow",
      "Action": "bedrock-agentcore:InvokeGateway",
      "Resource": "arn:aws:bedrock-agentcore:us-east-1:<ACCOUNT_ID>:gateway/<gateway-id>"
    },
    {
      "Sid": "InvokeWebSearch",
      "Effect": "Allow",
      "Action": "bedrock-agentcore:InvokeWebSearch",
      "Resource": "arn:aws:bedrock-agentcore:us-east-1:aws:tool/web-search.v1"
    }
  ]
}""",
        links=DOC_LINKS,
    ),
}


# --------------------------------------------------------------------------- #
# Cross-option comparison
# --------------------------------------------------------------------------- #

# (dimension, option 1, option 2)
COMPARISON_ROWS: tuple[tuple[str, str, str], ...] = (
    ("Answers about today", "No", "Yes"),
    ("Citations to verify", "None", "Yes: title, URL, published date"),
    ("Search backend", "None", "Amazon-operated web index"),
    ("Third-party search engine", "None", "None"),
    ("Where the query travels", "Bedrock only", "Stays inside AWS"),
    ("Credential to store and rotate", "None", "None: IAM service role"),
    ("Tool discovery", "n/a", "tools/list at run time"),
    ("Who decides to search", "n/a", "The model: only when needed"),
    ("Can search more than once", "n/a", "Yes"),
    ("Knowledge graph for entity facts", "No", "Yes"),
    ("Snippet extraction for model context", "n/a", "Managed, semantic"),
    ("Freshness", "Training cutoff", "Refreshed within minutes"),
    ("Integration code you maintain", "None", "None: one connector id"),
    ("Search cost", "$0", "$7 / 1,000, only when the model searches"),
    ("Contracts and support", "AWS", "AWS"),
    ("Framework portability", "n/a", "Standard MCP: any client"),
)

# What to say while the customer is looking at the comparison table.
CLOSING_POINTS = (
    "Option 1 is not a strawman. Keep it for work that does not depend on current "
    "facts: it is the cheapest and fastest path, and plenty of agent work fits it.",
    "Option 2 is the same model with one connector attached. There is no search code "
    "in the application: the agent calls tools/list and the tool is there.",
    "No API key anywhere. The Gateway authenticates outbound with its own IAM service "
    "role, and callers authenticate inbound with SigV4. No IdP, no bearer token.",
    "Queries are served inside AWS and are not sent to a third-party search engine, "
    "which removes an entire category of security review.",
    "The model decides whether to search at all. Ask it something that needs no "
    "lookup and it searches zero times and bills nothing. You pay only for the "
    "lookups that were actually needed.",
    "Web search complements Bedrock Knowledge Bases rather than replacing them: a "
    "knowledge base answers 'what do our documents say', web search answers 'what "
    "is true in the world right now'. Production agents commonly use both.",
)
