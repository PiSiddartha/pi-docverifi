#!/bin/bash

# Script to create S3 bucket for document verification
# Usage: ./create_s3_bucket.sh [region]
# Default region: ap-south-1

REGION=${1:-ap-south-1}
BUCKET_NAME="pi-document-verification"

echo "Creating S3 bucket: $BUCKET_NAME in region: $REGION"

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI is not installed. Please install it first:"
    echo "   macOS: brew install awscli"
    echo "   Linux: sudo apt-get install awscli"
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS credentials not configured. Please run 'aws configure' first."
    exit 1
fi

# Create bucket
echo "Creating bucket..."
if aws s3api create-bucket \
    --bucket "$BUCKET_NAME" \
    --region "$REGION" \
    --create-bucket-configuration LocationConstraint="$REGION" 2>/dev/null; then
    echo "✅ Bucket created successfully!"
elif aws s3api create-bucket \
    --bucket "$BUCKET_NAME" \
    --region us-east-1 2>/dev/null; then
    echo "✅ Bucket created successfully (us-east-1 doesn't need LocationConstraint)!"
else
    # Check if bucket already exists
    if aws s3api head-bucket --bucket "$BUCKET_NAME" 2>/dev/null; then
        echo "⚠️  Bucket already exists. Continuing..."
    else
        echo "❌ Failed to create bucket. Please check your AWS permissions."
        exit 1
    fi
fi

# Enable versioning
echo "Enabling versioning..."
aws s3api put-bucket-versioning \
    --bucket "$BUCKET_NAME" \
    --versioning-configuration Status=Enabled

# Set up CORS (if needed for direct browser uploads)
echo "Setting up CORS configuration..."
cat > /tmp/s3-cors.json << 'EOF'
{
    "CORSRules": [
        {
            "AllowedOrigins": ["*"],
            "AllowedMethods": ["GET", "PUT", "POST", "DELETE"],
            "AllowedHeaders": ["*"],
            "ExposeHeaders": ["ETag"],
            "MaxAgeSeconds": 3000
        }
    ]
}
EOF

aws s3api put-bucket-cors \
    --bucket "$BUCKET_NAME" \
    --cors-configuration file:///tmp/s3-cors.json

# Set up lifecycle policy (optional - delete old versions after 90 days)
echo "Setting up lifecycle policy..."
cat > /tmp/s3-lifecycle.json << 'EOF'
{
    "Rules": [
        {
            "Id": "DeleteOldVersions",
            "Status": "Enabled",
            "NoncurrentVersionExpiration": {
                "NoncurrentDays": 90
            }
        }
    ]
}
EOF

aws s3api put-bucket-lifecycle-configuration \
    --bucket "$BUCKET_NAME" \
    --lifecycle-configuration file:///tmp/s3-lifecycle.json

# Cleanup temp files
rm -f /tmp/s3-cors.json /tmp/s3-lifecycle.json

echo ""
echo "✅ S3 bucket setup complete!"
echo ""
echo "Bucket Name: $BUCKET_NAME"
echo "Region: $REGION"
echo ""
echo "Update your .env file with:"
echo "S3_BUCKET_NAME=$BUCKET_NAME"
echo "AWS_REGION=$REGION"
echo ""

