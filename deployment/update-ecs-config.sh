#!/bin/bash
set -e

# Update specific environment variables in ECS task definition
# Usage: ./update-ecs-config.sh KEY1=value1 KEY2=value2 ...
# Example: ./update-ecs-config.sh OPENAI_API_KEY=sk-new-key COMPANIES_HOUSE_API_KEY=new-key

REGION=${REGION:-"ap-south-1"}
ACCOUNT_ID=${ACCOUNT_ID:-"177215708218"}
TASK_FAMILY="document-verification-task"
CLUSTER_NAME="document-verification-cluster"
SERVICE_NAME="document-verification-service"

if [ $# -eq 0 ]; then
    echo "❌ No environment variables provided"
    echo ""
    echo "Usage: ./update-ecs-config.sh KEY1=value1 KEY2=value2 ..."
    echo ""
    echo "Examples:"
    echo "  ./update-ecs-config.sh OPENAI_API_KEY=sk-new-key"
    echo "  ./update-ecs-config.sh COMPANIES_HOUSE_API_KEY=new-key S3_BUCKET_NAME=new-bucket"
    echo ""
    echo "Available variables:"
    echo "  DATABASE_URL, COMPANIES_HOUSE_API_KEY, HMRC_CLIENT_ID, HMRC_CLIENT_SECRET"
    echo "  OPENAI_API_KEY, S3_BUCKET_NAME, SECRET_KEY, ENVIRONMENT, CORS_ORIGINS"
    echo "  MAX_UPLOAD_SIZE, REDIS_URL, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY"
    exit 1
fi

echo "🔄 Updating ECS environment variables..."
echo "Region: $REGION"
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

# Parse arguments and build environment variables array
echo "📝 Parsing environment variables..."
ENV_ARRAY="[]"

for arg in "$@"; do
    if [[ "$arg" =~ ^([^=]+)=(.*)$ ]]; then
        KEY="${BASH_REMATCH[1]}"
        VALUE="${BASH_REMATCH[2]}"
        
        # Remove quotes if present
        VALUE=$(echo "$VALUE" | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")
        
        if [ -z "$VALUE" ]; then
            echo "   ⚠️  Skipping empty value for $KEY"
            continue
        fi
        
        echo "   Adding/Updating: $KEY"
        ENV_ARRAY=$(echo $ENV_ARRAY | jq --arg k "$KEY" --arg v "$VALUE" '. + [{"name": $k, "value": $v}]')
    else
        echo "   ⚠️  Invalid format: $arg (expected KEY=value)"
    fi
done

if [ "$ENV_ARRAY" == "[]" ]; then
    echo "❌ No valid environment variables to update"
    exit 1
fi

echo ""
echo "🔄 Merging with existing environment variables..."

# Start with existing environment variables
FINAL_ENV="$CURRENT_ENV"

# Update/add new variables
for var_obj in $(echo $ENV_ARRAY | jq -c '.[]'); do
    VAR_NAME=$(echo $var_obj | jq -r '.name')
    VAR_VALUE=$(echo $var_obj | jq -r '.value')
    
    # Remove existing entry with same name (if any)
    FINAL_ENV=$(echo $FINAL_ENV | jq --arg name "$VAR_NAME" '[.[] | select(.name != $name)]')
    
    # Add new/updated entry
    FINAL_ENV=$(echo $FINAL_ENV | jq --argjson new "$var_obj" '. + [$new]')
done

# Remove duplicates (keep last occurrence)
FINAL_ENV=$(echo $FINAL_ENV | jq 'reverse | unique_by(.name) | reverse')

echo "   ✅ Environment variables prepared"
echo ""

# Show what will be updated (without sensitive values)
echo "📋 Environment variables to be set:"
echo $FINAL_ENV | jq -r '.[] | "   \(.name) = \(if (.value | length) > 30 then (.value[0:30] + "...") else .value end)"'
echo ""

# Ask for confirmation
read -p "Continue with update? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 1
fi

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
echo "✅ Environment Variables Updated!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 Summary:"
echo "   Task Definition: $TASK_FAMILY:$NEW_REVISION"
echo "   Variables updated: $# variable(s)"
echo ""
echo "⏳ New tasks are being deployed with updated environment variables"
echo "   Monitor with:"
echo "   aws ecs describe-services --cluster $CLUSTER_NAME --services $SERVICE_NAME --region $REGION"
echo ""
echo "📊 View logs:"
echo "   aws logs tail /ecs/document-verification --follow --region $REGION"

