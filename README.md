# Web Search on Amazon Bedrock AgentCore demo

A two-option demo that runs the same question through the same model, once without
web search and once with the AWS-managed Web Search connector on an AgentCore
Gateway, and shows the difference side by side.

| | Option | What it is |
|---|---|---|
| 🧠 | **1. No web search** | A Bedrock model answering from training data alone |
| 🟠 | **2. Web search with AgentCore** | The managed `web-search` connector, discovered by the model via MCP `tools/list` |

Web search goes through the AWS-managed Web Search tool. **No third-party search
engine is used anywhere**: there is no search SDK in `requirements.txt` and no
search API key in `.env.example`.

## Stack

- **Front end**: React 19 + TypeScript + [Cloudscape](https://cloudscape.design/),
  styled like an AWS service console. Built by Vite into static files. Model answers
  are markdown, rendered with `react-markdown` + `remark-gfm`; raw HTML is left
  disabled, since the text summarises pages fetched off the open web.
- **API**: FastAPI, wrapping the agent logic in `demo/`. Runs under uvicorn locally
  and on Lambda (via Mangum) when deployed.
- **Agent**: Strands Agents with a Bedrock model, connected to the Gateway over
  SigV4-signed Streamable HTTP MCP.
- **Hosting**: one CloudFront distribution: static bundle from a private S3 bucket,
  `/api/*` to an API Gateway HTTP API in front of the Lambda.

```
Browser ──► CloudFront ──┬──► S3 (private, OAC)                  static bundle
   (no sign-in)          │
                         └──► API Gateway ──► Lambda ──┬──► Bedrock (model)
                              (Lambda            │     └──► AgentCore Gateway
                               authorizer)       │            └──► web-search connector
                                                 └──► CloudWatch Logs
```

## Layout

```
demo/                     Agent logic. No UI or web framework imports.
  config.py               Settings, Gateway URL validation, domain parsing, pricing
  types.py                Citation, ToolCall, RunMetrics, RunResult
  agent_runtime.py        Shared Strands/Bedrock loop, metrics, cost estimation
  gateway.py              The only path to Web Search: MCP over SigV4
  tool_policy.py          Pins maxResults and injects filters on every search
  tracing.py              Tool-call recorder, Web Search response parsing
  architecture.py         SVG diagrams + per-option architecture detail
  modes/
    no_search.py          Option 1
    agentcore_search.py   Option 2
api/
  main.py                 FastAPI routes
  serialize.py            Dataclasses -> camelCase JSON
  lambda_handler.py       Mangum handler + origin-secret guard
web/src/
  App.tsx                 Console shell: top bar, side nav, readiness banner
  api/                    Typed fetch client mirroring api/serialize.py
  components/
    SearchControls.tsx    maxResults + domain and published-date filters
    ResultCard.tsx        One option: verdict, metrics, answer, sources, trace
    Markdown.tsx          Renders model output; raw HTML deliberately disabled
    SettingsPanel.tsx     Tools drawer: model and Gateway URL
  pages/                  Run, Architecture, Side by side
  shell/                  Top bar, side nav, hash routing
  state/                  Settings + readiness
infra/                    AgentCore Gateway + web-search target (CloudFormation)
deploy/                   S3 + CloudFront + Lambda hosting (CloudFormation)
verify_api.py             API contract tests (no AWS needed)
verify_pipeline.py        Agent pipeline tests (no AWS needed)
live_check.py             One real end-to-end run against a deployed Gateway
```

## Prerequisites

- Python 3.10-3.14 (`mcp-proxy-for-aws` requires `<3.15`)
- Node 20+
- AWS credentials with `bedrock:InvokeModel`, plus permission to create IAM roles,
  AgentCore, S3, Lambda, API Gateway and CloudFront resources
- AWS CLI v2. Use **≥ 2.35.0** if you want the CLI to render connector targets;
  earlier versions deploy fine but print `SDK_UNKNOWN_MEMBER` for them
- A region where Web Search is available: **us-east-1**, **eu-west-1**, or
  **ap-northeast-1**

## Run locally

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env

# One-time: create the Gateway and attach the web-search connector.
# Writes AGENTCORE_GATEWAY_URL into .env for you.
./infra/deploy.sh --region us-east-1

# Terminal 1: the API holds the AWS credentials and runs the agent.
.venv/bin/uvicorn api.main:app --reload --port 8000

# Terminal 2: the UI, proxying /api to port 8000.
cd web && npm install && npm run dev
```

Open http://localhost:5173.

## Deploy

```bash
./deploy/deploy-app.sh --region us-east-1
```

Builds the bundle, packages the Lambda, deploys the stack, uploads the bundle and
invalidates the cache. Prints the CloudFront URL, which needs no sign-in. Re-running
the script is the way to ship any change.

Set `API_CONCURRENCY_LIMIT` to change the Lambda concurrency cap (default 5).

## Access control

**There is no viewer authentication.** Anyone with the CloudFront URL can run the
demo. That is a deliberate choice for shareability, and it means the protections are
about bounding cost and locking down the path to the agent, not about who may use it.

- **Reserved concurrency** of 5 on the API Lambda. Each grounded run costs roughly
  $0.03 (Bedrock tokens plus $7 per 1,000 searches), so this is the spend ceiling:
  beyond 5 in-flight runs, requests are throttled rather than billed. Raise it with
  `API_CONCURRENCY_LIMIT` if a demo needs more headroom.
- **`MaxSearchResults`** caps results per search server-side, so a single run cannot
  be made expensive by the caller.
- **Gateway authorizer**: a `REQUEST`-type Lambda authorizer on the API Gateway route,
  validating a secret that only CloudFront injects. The header is the authorizer's
  identity source, so a request that omits it is rejected with 401 before the
  authorizer even runs, and decisions are cached for 300 seconds. This is what makes
  the route `AuthorizationType: CUSTOM` rather than `NONE`.
- **Origin secret** checked in the application Lambda as well, so a request that
  somehow reaches the function without coming through CloudFront still gets nothing.

Both secret checks compare in constant time. The application Lambda uses its own
execution role, scoped to `InvokeGateway` on the one Gateway ARN plus `InvokeModel`;
the authorizer has a separate role with CloudWatch Logs only. No AWS credentials ever
reach the browser.

> The gateway authorizer exists because an unauthenticated route is flagged by AWS
> AppSec scanners ("API gateway has no authorizer") and, more importantly, because
> relying only on a check inside the application put the sole guard at the wrong
> layer. If `DEMO_ORIGIN_SECRET` were ever unset, the API would have been open.

> Tear the stack down when you are done demoing (`./deploy/teardown-app.sh`). An
> open endpoint that can spend money should not outlive its purpose.

## What the demo shows

Option 1 establishes the problem; Option 2 adds one connector and nothing else.

- **Grounding**: Option 1 cannot answer a question about today and has no sources.
  Option 2 answers with titles, URLs and publication dates.
- **Zero integration code**: the agent calls `tools/list` and the `WebSearch` tool is
  there, schema included. No search SDK, no API key, no response-parsing glue.
- **No third-party egress**: the query is served inside AWS.
- **The model decides**: ask it something that needs no lookup and it searches zero
  times and bills nothing.
- **Governance**: `maxResults` and the domain / published-date filters are enforced
  server-side on every call, overriding whatever the model asks for.
- **Agentic retrieval**: the model writes its own query, and on an open-ended
  question it will search again after reading the first set of results. `maxResults`
  is a per-search cap, so a run that searches three times can return roughly three
  times that many unique sources. The Sources header states the count and the number
  of searches for exactly this reason.

### Suggested flow

1. **Architecture tab**: walk Option 1, then Option 2. Land on the trust boundary:
   the query crosses into an AWS service account, not out to the internet.
2. **Run tab**: pick a sample question and run both. Option 1 hedges and names its
   cutoff; Option 2 cites sources. Open Option 2's execution trace to show the query
   the model wrote for itself and the full payload it received.
3. **Search controls**, on the Run page under the question form. Restrict the include
   list to one domain, or set a published-date window, and run again. The trace then
   reads `Policy: model omitted maxResults, pinned to 3; filters applied`, which is the
   governance story: the operator's values are injected server-side whatever the model
   asks for.
4. **Ask something that needs no lookup**: type your own question, for example a
   summarise-or-rewrite task. Option 2 searches zero times and costs about a third as
   much as a grounded question. The model, not your code, decided.
5. **Side by side tab**: close on the cost row: $7 per 1,000 queries, only when the
   model searches.

Switching the model is also worth a moment if cost comes up: Haiku 4.5 is roughly half
the cost and twice the speed of Sonnet 4.6 and still returns grounded, cited answers.

## Configuration

All optional; `.env.example` documents each key.

| Variable | Purpose |
|---|---|
| `AGENTCORE_GATEWAY_URL` | Gateway MCP endpoint. Written by `infra/deploy.sh`. |
| `AWS_REGION` | Region for Bedrock and the Gateway. |
| `AWS_PROFILE` | Named profile for local runs. Omit to use the default credential chain. Unused when deployed, where the Lambda's execution role applies. |
| `BEDROCK_MODEL_ID` | Model both options use. Must be one of the ids in `MODEL_PRICING`. |
| `MAX_SEARCH_RESULTS` | Results per search, 1-25, enforced server-side. |
| `SEARCH_DOMAIN_INCLUDE` / `SEARCH_DOMAIN_EXCLUDE` | Domain filters. Full URLs are reduced to the bare domain. |
| `SEARCH_PUBLISHED_FROM` / `SEARCH_PUBLISHED_TO` | Publication-date bounds, `YYYY-MM-DD`. |

Exported environment variables override `.env`. If the app points somewhere
unexpected, check your shell first.

## Tests and code quality

Both test scripts run offline with no AWS credentials.

```bash
.venv/bin/python verify_api.py       # API contract, filter payloads, error handling
.venv/bin/python verify_pipeline.py  # response parsing, tracing, cost accounting
```

Lint and type checks:

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m ruff check .            # lint, configured in pyproject.toml
.venv/bin/python -m ruff format --check .   # formatting
cd web && npm run typecheck                 # tsc, strict, with unused-code checks on
```

There is no ESLint: `noUnusedLocals` and `noUnusedParameters` in `web/tsconfig.json`
already fail the build on dead code, which is the risk worth guarding in a project
this size.

`verify_pipeline.py` drives the real Strands agent loop with a scripted fake model,
so Web Search response parsing, citation extraction and the `$7/1,000` accounting are
exercised rather than assumed. It also asserts no third-party search SDK is declared
or imported anywhere.

After deploying, one real run:

```bash
.venv/bin/python live_check.py       # costs ~$0.007 per search plus model tokens
```

## Cost and cleanup

- **Web Search**: $7 per 1,000 queries, billed only when the model chooses to search.
- **Bedrock**: on-demand token pricing. Figures in the app are estimates from list
  pricing, not a bill.
- **Hosting**: CloudFront, S3, API Gateway and Lambda, all effectively free at demo
  volumes.

```bash
./deploy/teardown-app.sh --region us-east-1     # hosting: S3, CloudFront, Lambda
./infra/teardown.sh --region us-east-1          # Gateway + web-search target
```

## Troubleshooting

| Symptom | Cause |
|---|---|
| Option 2 not ready | No Gateway URL, or credentials unusable. Check the readiness banner. |
| Option 2 shows no sources | The model judged the answer settled and did not search. Expected for stable facts; ask about something recent. The verdict alert says which happened. |
| More sources than `maxResults` | `maxResults` is per search, not per run. A compound question ("how did it close, and why did it move?") makes the model search once per part. Single-intent questions give one search and exactly the requested count. |
| 403 from the Gateway | The caller needs `bedrock-agentcore:InvokeGateway` on the Gateway ARN. |
| Trace says no `WebSearch` tool was discovered | The Gateway target is not `READY`. Check `aws bedrock-agentcore-control list-gateway-targets`. |
| Gateway in the wrong region | Web Search exists only in us-east-1, eu-west-1, ap-northeast-1. |
| Local UI cannot reach the API | uvicorn is not running on port 8000. |
| Stale credentials in the UI | The identity lookup is memoised per process. Restart uvicorn after re-exporting credentials. |
| `401` from the deployed API | A request that did not come through CloudFront. Direct API Gateway calls are rejected by the authorizer by design. |
| `429` from the deployed API | More than `API_CONCURRENCY_LIMIT` runs in flight. Retry, or raise the cap and redeploy. |
| `modelStreamErrorException ... invalid sequence as part of ToolUse` | The selected model cannot handle the Web Search tool schema. This is why only Claude Sonnet 4.6 and Haiku 4.5 are offered; Nova Pro and Lite fail here. |

## Acceptable use

Search results must be displayed with the source citations and links returned with
them: the Sources panel does this. Results may not be extracted or stored in bulk,
or used to build a competing index.

## Reference

- [Web Search Tool: AgentCore Developer Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-target-connector-web-search-tool.html)
- [Introducing Web Search on Amazon Bedrock AgentCore: AWS ML Blog](https://aws.amazon.com/blogs/machine-learning/introducing-web-search-on-amazon-bedrock-agentcore/)

The Gateway CloudFormation follows the pattern in
[aws-samples/sample-agentcore-websearch-agent-skill](https://github.com/aws-samples/sample-agentcore-websearch-agent-skill)
(MIT-0).
