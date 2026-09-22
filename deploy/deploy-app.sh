#!/usr/bin/env bash
# Build and deploy the demo as a single CloudFront URL:
#   - React bundle  -> private S3 bucket, served by CloudFront
#   - FastAPI API   -> Lambda, served by the same distribution under /api/*
#
#   ./deploy/deploy-app.sh [--region us-east-1] [--stack-name agentcore-websearch-app]
#
# Reads AGENTCORE_GATEWAY_URL from .env (or the environment) and derives the
# Gateway ARN so the Lambda's InvokeGateway permission is scoped to that Gateway.
#
# The resulting URL is public. Set API_CONCURRENCY_LIMIT to change the Lambda
# concurrency cap that keeps demo spend bounded (default 5).
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="agentcore-websearch-app"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --region)     REGION="$2"; shift 2 ;;
    --stack-name) STACK_NAME="$2"; shift 2 ;;
    -h|--help)    sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

# ---------------------------------------------------------------- inputs
if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  set -a; . ./.env; set +a
fi

: "${AGENTCORE_GATEWAY_URL:?Set AGENTCORE_GATEWAY_URL (run ./infra/deploy.sh first)}"
MODEL_ID="${BEDROCK_MODEL_ID:-us.anthropic.claude-sonnet-4-6}"
MAX_RESULTS="${MAX_SEARCH_RESULTS:-5}"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"

# Derive the Gateway ARN from its URL host: <id>.gateway.bedrock-agentcore.<region>...
GW_HOST="${AGENTCORE_GATEWAY_URL#https://}"; GW_HOST="${GW_HOST%%/*}"
GW_ID="${GW_HOST%%.*}"
GW_REGION="$(printf '%s' "$GW_HOST" | sed -E 's/.*bedrock-agentcore\.([a-z0-9-]+)\.amazonaws\.com/\1/')"
GATEWAY_ARN="arn:aws:bedrock-agentcore:${GW_REGION}:${ACCOUNT_ID}:gateway/${GW_ID}"

API_CONCURRENCY_LIMIT="${API_CONCURRENCY_LIMIT:-5}"

# Rotated on every deploy. CloudFront injects it; the Lambda refuses requests
# without it, so the public API Gateway endpoint cannot be used directly.
ORIGIN_SECRET="$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))')"

echo "==> Target"
echo "    account     : $ACCOUNT_ID"
echo "    region      : $REGION"
echo "    stack       : $STACK_NAME"
echo "    gateway     : $GW_ID ($GW_REGION)"
echo "    model       : $MODEL_ID"
echo "    concurrency : $API_CONCURRENCY_LIMIT"

# ------------------------------------------------- 1. build the front end
echo
echo "==> Building the React bundle"
( cd web && npm ci --silent && npm run build )

# ------------------------------------------------- 2. build the Lambda zip
echo
echo "==> Packaging the Lambda"
rm -rf build/lambda build/api.zip
mkdir -p build/lambda
python3 -m pip install -q --target build/lambda \
  --platform manylinux2014_x86_64 --python-version 3.13 \
  --implementation cp --only-binary=:all: --upgrade \
  -r deploy/lambda-requirements.txt
find build/lambda -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true
find build/lambda -name "*.pyc" -delete 2>/dev/null || true
find build/lambda -type d -name tests -prune -exec rm -rf {} + 2>/dev/null || true

# The application code itself. demo/ carries all the agent logic.
cp -R api demo build/lambda/
find build/lambda/api build/lambda/demo -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true

( cd build/lambda && zip -qr ../api.zip . )
echo "    zip size    : $(du -h build/api.zip | cut -f1)"

# ------------------------------------------- 3. staging bucket for the zip
STAGING_BUCKET="${STACK_NAME}-artifacts-${ACCOUNT_ID}-${REGION}"
if ! aws s3api head-bucket --bucket "$STAGING_BUCKET" --region "$REGION" 2>/dev/null; then
  echo
  echo "==> Creating artifact bucket $STAGING_BUCKET"
  if [[ "$REGION" == "us-east-1" ]]; then
    aws s3api create-bucket --bucket "$STAGING_BUCKET" --region "$REGION" >/dev/null
  else
    aws s3api create-bucket --bucket "$STAGING_BUCKET" --region "$REGION" \
      --create-bucket-configuration "LocationConstraint=$REGION" >/dev/null
  fi
  aws s3api put-public-access-block --bucket "$STAGING_BUCKET" \
    --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
  aws s3api put-bucket-encryption --bucket "$STAGING_BUCKET" \
    --server-side-encryption-configuration \
    '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
fi

# Content-addressed key so Lambda always picks up a changed package.
CODE_HASH="$(python3 -c "
import hashlib,sys
h=hashlib.sha256()
with open('build/api.zip','rb') as f:
    for chunk in iter(lambda: f.read(1<<20), b''): h.update(chunk)
print(h.hexdigest()[:16])
")"
CODE_KEY="lambda/api-${CODE_HASH}.zip"
echo
echo "==> Uploading the Lambda package"
aws s3 cp build/api.zip "s3://${STAGING_BUCKET}/${CODE_KEY}" --region "$REGION" --only-show-errors

# ------------------------------------------------------- 4. deploy the stack
echo
echo "==> Deploying stack $STACK_NAME"
aws cloudformation deploy \
  --region "$REGION" \
  --stack-name "$STACK_NAME" \
  --template-file deploy/app-hosting.yaml \
  --capabilities CAPABILITY_IAM \
  --no-fail-on-empty-changeset \
  --parameter-overrides \
    "GatewayUrl=${AGENTCORE_GATEWAY_URL}" \
    "GatewayArn=${GATEWAY_ARN}" \
    "ModelId=${MODEL_ID}" \
    "LambdaCodeBucket=${STAGING_BUCKET}" \
    "LambdaCodeKey=${CODE_KEY}" \
    "OriginSecret=${ORIGIN_SECRET}" \
    "MaxSearchResults=${MAX_RESULTS}" \
    "ApiConcurrencyLimit=${API_CONCURRENCY_LIMIT}" \
  --tags Project=AgentCoreWebSearchDemo Purpose=CustomerDemo

get_output() {
  aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}

APP_URL="$(get_output AppUrl)"
SITE_BUCKET="$(get_output SiteBucketName)"
DIST_ID="$(get_output DistributionId)"

# --------------------------------------------- 5. publish the static bundle
echo
echo "==> Uploading the React bundle to $SITE_BUCKET"
# Hashed assets can be cached hard; index.html must not be.
aws s3 sync web/dist "s3://${SITE_BUCKET}" --region "$REGION" --delete \
  --exclude index.html --cache-control "public,max-age=31536000,immutable" --only-show-errors
aws s3 cp web/dist/index.html "s3://${SITE_BUCKET}/index.html" --region "$REGION" \
  --cache-control "no-cache,no-store,must-revalidate" --content-type "text/html" --only-show-errors

echo
echo "==> Invalidating the CloudFront cache"
aws cloudfront create-invalidation --distribution-id "$DIST_ID" \
  --paths "/*" --query 'Invalidation.Id' --output text

cat <<EOF

========================================================================
  Application URL : $APP_URL
  Sign-in         : none, the link is public
========================================================================

CloudFront takes a few minutes to finish deploying the first time.

Anyone with the link can run the demo, and each grounded run costs about
\$0.03. The API Lambda is capped at $API_CONCURRENCY_LIMIT concurrent executions to bound
that; raise it with API_CONCURRENCY_LIMIT=... if a demo needs more headroom.
Tear the stack down when the demo season is over.

Teardown: ./deploy/teardown-app.sh --region $REGION --stack-name $STACK_NAME
EOF
