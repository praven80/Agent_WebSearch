#!/usr/bin/env bash
# Remove the hosting stack: CloudFront distribution, S3 bucket, Lambda and role.
# Leaves the AgentCore Gateway alone -- tear that down with infra/teardown.sh.
#
#   ./deploy/teardown-app.sh [--region us-east-1] [--stack-name agentcore-websearch-app]
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="agentcore-websearch-app"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --region)     REGION="$2"; shift 2 ;;
    --stack-name) STACK_NAME="$2"; shift 2 ;;
    -h|--help)    sed -n '2,8p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"

echo "This will DELETE stack '$STACK_NAME' in $REGION (account $ACCOUNT_ID):"
echo "  - the CloudFront distribution and its URL"
echo "  - the S3 site bucket and its contents"
echo "  - the API Lambda function and its execution role"
echo
read -r -p "Type the stack name to confirm: " CONFIRM
if [[ "$CONFIRM" != "$STACK_NAME" ]]; then
  echo "Aborted." >&2
  exit 1
fi

get_output() {
  aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text 2>/dev/null || true
}

SITE_BUCKET="$(get_output SiteBucketName)"

# A versioned bucket must be emptied, including delete markers, or the stack
# delete fails. Uses only the AWS CLI so it does not depend on boto3 being
# importable from whichever python3 happens to be on PATH.
empty_versioned_bucket() {
  local bucket="$1"
  local batch
  while :; do
    batch="$(
      aws s3api list-object-versions --bucket "$bucket" --region "$REGION" \
        --max-items 500 \
        --query '{Objects: (Versions[].{Key:Key,VersionId:VersionId} || `[]`)}' \
        --output json 2>/dev/null
    )"
    if [[ -z "$batch" ]] || ! grep -q '"Key"' <<<"$batch"; then
      break
    fi
    aws s3api delete-objects --bucket "$bucket" --region "$REGION" \
      --delete "$batch" --output text >/dev/null 2>&1 || break
  done

  while :; do
    batch="$(
      aws s3api list-object-versions --bucket "$bucket" --region "$REGION" \
        --max-items 500 \
        --query '{Objects: (DeleteMarkers[].{Key:Key,VersionId:VersionId} || `[]`)}' \
        --output json 2>/dev/null
    )"
    if [[ -z "$batch" ]] || ! grep -q '"Key"' <<<"$batch"; then
      break
    fi
    aws s3api delete-objects --bucket "$bucket" --region "$REGION" \
      --delete "$batch" --output text >/dev/null 2>&1 || break
  done
}

if [[ -n "$SITE_BUCKET" && "$SITE_BUCKET" != "None" ]]; then
  echo "==> Emptying $SITE_BUCKET (all versions and delete markers)"
  empty_versioned_bucket "$SITE_BUCKET"
  echo "    done"
fi

echo "==> Deleting stack (CloudFront can take 10-15 minutes)"
aws cloudformation delete-stack --region "$REGION" --stack-name "$STACK_NAME"
aws cloudformation wait stack-delete-complete --region "$REGION" --stack-name "$STACK_NAME"
echo "==> Stack '$STACK_NAME' deleted"

ARTIFACTS="${STACK_NAME}-artifacts-${ACCOUNT_ID}-${REGION}"
echo
echo "The Lambda artifact bucket is kept so redeploys are fast. Remove it with:"
echo "  aws s3 rb s3://${ARTIFACTS} --force --region ${REGION}"
