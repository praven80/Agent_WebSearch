#!/usr/bin/env bash
# Delete the demo Gateway, its Web Search target, and the IAM service role.
# Nothing else persists on the AWS side, so this stops all charges for Option 3.
#
#   ./infra/teardown.sh [--region us-east-1] [--stack-name agentcore-websearch-demo]
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="agentcore-websearch-demo"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --region)      REGION="$2"; shift 2 ;;
    --stack-name)  STACK_NAME="$2"; shift 2 ;;
    -h|--help)     sed -n '2,8p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

echo "This will DELETE CloudFormation stack '$STACK_NAME' in $REGION,"
echo "removing the AgentCore Gateway, its Web Search target, and the IAM role."
read -r -p "Type the stack name to confirm: " CONFIRM
if [[ "$CONFIRM" != "$STACK_NAME" ]]; then
  echo "Aborted." >&2
  exit 1
fi

aws cloudformation delete-stack --region "$REGION" --stack-name "$STACK_NAME"
echo "==> Delete requested; waiting for completion"
aws cloudformation wait stack-delete-complete --region "$REGION" --stack-name "$STACK_NAME"
echo "==> Stack '$STACK_NAME' deleted"
