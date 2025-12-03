#!/bin/bash
set -e

# Sync environment variables from .env file to ECS task definition
# This script reads your local .env file and updates the ECS task definition
# Usage: ./sync-env-to-ecs.sh [.env-file-path] [region]

ENV_FILE=${1:-"../backend/.env"}
REGION=${2:-"ap-south-1"}
ACCOUNT_ID=${3:-"177215708218"}
TASK_FAMILY="document-verification-task"

echo "🔄 Syncing environment variables from .env to ECS..."
echo "Env file: $ENV_FILE"
echo "Region: $REGION"
echo ""

# Check if .env file exists
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ .env file not found: $ENV_FILE"
    echo ""
    echo "Please provide the path to your .env file:"
    echo "   Usage: ./sync-env-to-ecs.sh <path-to-.env-file>"
    echo ""
    echo "Or create one with these variables:"
    echo "   DATABASE_URL=..."
    echo "   COMPANIES_HOUSE_API_KEY=..."
    echo "   OPENAI_API_KEY=..."
    echo "   S3_BUCKET_NAME=..."
    echo "   HMRC_CLIENT_ID=..."
    echo "   HMRC_CLIENT_SECRET=..."
    exit 1
fi

echo "✅ Found .env file"
echo ""

# Get current task definition
echo "📥 Getting current task definition..."
CURRENT_TASK_DEF=$(aws ecs describe-task-definition \
    --task-definition $TASK_FAMILY \
    --region $REGION \
    --query 'taskDefinition')

CURRENT_IMAGE=$(echo $CURRENT_TASK_DEF | jq -r '.containerDefinitions[0].image')
CURRENT_ENV=$(echo $CURRENT_TASK_DEF | jq '.containerDefinitions[0].environment // []')

echo "   Current image: $CURRENT_IMAGE"
echo ""

# Read .env file and build environment variables array
echo "📖 Reading .env file..."
ENV_ARRAY="[]"

# List of environment variables to sync (from config.py)
ENV_VARS=(
    "DATABASE_URL"
    "COMPANIES_HOUSE_API_KEY"
    "HMRC_CLIENT_ID"
    "HMRC_CLIENT_SECRET"
    "HMRC_SERVER_TOKEN"
    "HMRC_USE_OAUTH"
    "AWS_ACCESS_KEY_ID"
    "AWS_SECRET_ACCESS_KEY"
    "AWS_REGION"
    "S3_BUCKET_NAME"
    "OPENAI_API_KEY"
    "OPENAI_MODEL"
    "SQS_QUEUE_URL"
    "USE_SQS"
    "SECRET_KEY"
    "ENVIRONMENT"
    "CORS_ORIGINS"
    "MAX_UPLOAD_SIZE"
    "UPLOAD_DIR"
    "REDIS_URL"
)

# Read .env file line by line
while IFS='=' read -r key value || [ -n "$key" ]; do
    # Skip comments and empty lines
    [[ "$key" =~ ^#.*$ ]] && continue
    [[ -z "$key" ]] && continue
    
    # Remove quotes from value if present
    value=$(echo "$value" | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")
    
    # Check if this is a variable we want to sync
    for env_var in "${ENV_VARS[@]}"; do
        if [ "$key" == "$env_var" ]; then
            # Skip empty values
            if [ -n "$value" ]; then
                echo "   Adding: $key"
                ENV_ARRAY=$(echo $ENV_ARRAY | jq --arg k "$key" --arg v "$value" '. + [{"name": $k, "value": $v}]')
            fi
            break
        fi
    done
done < "$ENV_FILE"

# Merge with existing environment variables (ECS-specific ones take precedence)
echo ""
echo "🔄 Merging with existing ECS environment variables..."

# Keep ECS-specific vars that shouldn't be overridden
ECS_SPECIFIC_VARS=("USE_SQS" "SQS_QUEUE_URL" "AWS_REGION")

# Start with ECS-specific vars
FINAL_ENV="[]"
for var in "${ECS_SPECIFIC_VARS[@]}"; do
    EXISTING=$(echo $CURRENT_ENV | jq --arg v "$var" '.[] | select(.name == $v)')
    if [ -n "$EXISTING" ] && [ "$EXISTING" != "null" ]; then
        FINAL_ENV=$(echo $FINAL_ENV | jq ". + [$EXISTING]")
    fi
done

# Add all other vars from .env
FINAL_ENV=$(echo $FINAL_ENV | jq --argjson new "$ENV_ARRAY" '. + $new')

# Remove duplicates (keep last occurrence)
FINAL_ENV=$(echo $FINAL_ENV | jq 'reverse | unique_by(.name) | reverse')

echo "   ✅ Environment variables prepared"
echo ""

# Create new task definition JSON
echo "📝 Creating new task definition..."
cat > /tmp/new-task-def.json <<EOF
{
  "family": "$TASK_FAMILY",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "executionRoleArn": "arn:aws:iam::${ACCOUNT_ID}:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::${ACCOUNT_ID}:role/ecsTaskRole",
  "containerDefinitions": [
    {
      "name": "backend-container",
      "image": "$CURRENT_IMAGE",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": $(echo $FINAL_ENV | jq -c .),
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/document-verification",
          "awslogs-region": "$REGION",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
EOF

# Show what will be set (without sensitive values)
echo "📋 Environment variables to be set:"
echo $FINAL_ENV | jq -r '.[] | "   \(.name) = \(if (.value | length) > 20 then (.value[0:20] + "...") else .value end)"'
echo ""

# Ask for confirmation
read -p "Continue with update? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    rm -f /tmp/new-task-def.json
    exit 1
fi

# Register new task definition
echo "🚀 Registering new task definition..."
NEW_TASK_DEF_ARN=$(aws ecs register-task-definition \
    --cli-input-json file:///tmp/new-task-def.json \
    --region $REGION \
    --query 'taskDefinition.taskDefinitionArn' \
    --output text)

NEW_REVISION=$(echo $NEW_TASK_DEF_ARN | awk -F: '{print $NF}')
echo "   ✅ New revision registered: $NEW_REVISION"
echo ""

# Update ECS service
echo "🔄 Updating ECS service..."
CLUSTER_NAME="document-verification-cluster"
SERVICE_NAME="document-verification-service"

aws ecs update-service \
    --cluster $CLUSTER_NAME \
    --service $SERVICE_NAME \
    --task-definition $TASK_FAMILY:$NEW_REVISION \
    --force-new-deployment \
    --region $REGION > /dev/null

echo "   ✅ Service update initiated"
echo ""

# Cleanup
rm -f /tmp/new-task-def.json

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Environment Variables Synced!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 Summary:"
echo "   Task Definition: $TASK_FAMILY:$NEW_REVISION"
echo "   Environment variables: $(echo $FINAL_ENV | jq 'length') variables set"
echo ""
echo "⏳ New tasks are being deployed with updated environment variables"
echo "   Monitor with:"
echo "   aws ecs describe-services --cluster $CLUSTER_NAME --services $SERVICE_NAME --region $REGION"
echo ""
echo "📊 View logs:"
echo "   aws logs tail /ecs/document-verification --follow --region $REGION"

