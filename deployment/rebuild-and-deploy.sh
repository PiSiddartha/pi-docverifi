#!/bin/bash
set -e

# Rebuild Docker image and redeploy to ECS
# Usage: ./rebuild-and-deploy.sh [ecr-uri] [region] [account-id]

ECR_URI=${1:-"177215708218.dkr.ecr.ap-south-1.amazonaws.com/document-verification-backend"}
REGION=${2:-"ap-south-1"}
ACCOUNT_ID=${3:-"177215708218"}

echo "🔨 Rebuilding and deploying Docker image..."
echo "ECR URI: $ECR_URI"
echo "Region: $REGION"
echo ""

# Navigate to backend directory
cd "$(dirname "$0")/../backend"

# Build Docker image
echo "📦 Building Docker image..."
docker build -t document-verification-backend:latest .

# Login to ECR
echo "🔐 Logging in to ECR..."
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_URI

# Tag image
echo "🏷️  Tagging image..."
docker tag document-verification-backend:latest $ECR_URI:latest

# Push to ECR
echo "📤 Pushing image to ECR..."
docker push $ECR_URI:latest

echo ""
echo "✅ Image pushed successfully!"
echo ""

# Force ECS service to pull new image
echo "🔄 Forcing ECS service to pull new image..."
CLUSTER_NAME="document-verification-cluster"
SERVICE_NAME="document-verification-service"

aws ecs update-service \
    --cluster $CLUSTER_NAME \
    --service $SERVICE_NAME \
    --force-new-deployment \
    --region $REGION > /dev/null

echo "✅ Service update initiated"
echo ""
echo "📊 Monitor deployment:"
echo "   aws ecs describe-services --cluster $CLUSTER_NAME --services $SERVICE_NAME --region $REGION"
echo ""
echo "📋 View logs:"
echo "   aws logs tail /ecs/document-verification --follow --region $REGION"

