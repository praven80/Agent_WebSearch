#!/usr/bin/env bash
# Deploy the AgentCore Gateway + Web Search connector target for the demo,
# then write the resulting Gateway URL into the project's .env file.
#
#   ./infra/deploy.sh [--region us-east-1] [--stack-name agentcore-websearch-demo]
#
# Web Search is available in us-east-1, eu-west-1 and ap-northeast-1.
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="agentcore-websearch-demo"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --region)      REGION="$2"; shift 2 ;;
    --stack-name)  STACK_NAME="$2"; shift 2 ;;
    -h|--help)     sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

case "$REGION" in
  us-east-1|eu-west-1|ap-northeast-1) ;;
  *) echo "WARNING: Web Search is only available in us-east-1, eu-west-1 and ap-northeast-1 (got '$REGION')." >&2 ;;
esac

echo "==> Verifying credentials"
aws sts get-caller-identity --region "$REGION" --output table

echo
echo "==> Deploying stack '$STACK_NAME' to $REGION"
aws cloudformation deploy \
  --region "$REGION" \
  --stack-name "$STACK_NAME" \
  --template-file "$PROJECT_DIR/infra/agentcore-websearch.yaml" \
  --capabilities CAPABILITY_IAM

get_output() {
  aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}

GATEWAY_URL="$(get_output GatewayUrl)"
GATEWAY_ARN="$(get_output GatewayArn)"
TOOL_NAME="$(get_output ToolName)"

echo
echo "==> Stack outputs"
echo "    Gateway URL : $GATEWAY_URL"
echo "    Gateway ARN : $GATEWAY_ARN"
echo "    MCP tool    : $TOOL_NAME"

ENV_FILE="$PROJECT_DIR/.env"
touch "$ENV_FILE"
# Replace any existing values rather than appending duplicates.
python3 - "$ENV_FILE" "$GATEWAY_URL" "$REGION" <<'PY'
import pathlib, sys
path, url, region = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
updates = {"AGENTCORE_GATEWAY_URL": url, "AWS_REGION": region}
lines, seen = [], set()
for raw in path.read_text().splitlines():
    key = raw.split("=", 1)[0].strip()
    if key in updates:
        lines.append(f"{key}={updates[key]}")
        seen.add(key)
    else:
        lines.append(raw)
for key, val in updates.items():
    if key not in seen:
        lines.append(f"{key}={val}")
path.write_text("\n".join(lines).strip() + "\n")
PY

echo
echo "==> Wrote AGENTCORE_GATEWAY_URL and AWS_REGION to $ENV_FILE"
echo
echo "The caller running the demo needs bedrock-agentcore:InvokeGateway on:"
echo "    $GATEWAY_ARN"
echo "and bedrock:InvokeModel on the Bedrock model you select in the sidebar."
echo
echo "Next: streamlit run app.py"
