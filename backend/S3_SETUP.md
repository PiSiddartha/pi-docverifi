# AWS S3 Setup Guide

This guide explains how to set up AWS S3 for document storage in the document verification system.

## Prerequisites

1. **AWS Account**: You need an AWS account with appropriate permissions
2. **AWS CLI**: Install and configure AWS CLI
3. **IAM Credentials**: Access key ID and secret access key

## Quick Setup

### 1. Install AWS CLI

**macOS:**
```bash
brew install awscli
```

**Ubuntu/Debian:**
```bash
sudo apt-get install awscli
```

**Windows:**
Download from: https://aws.amazon.com/cli/

### 2. Configure AWS Credentials

```bash
aws configure
```

You'll be prompted for:
- AWS Access Key ID
- AWS Secret Access Key
- Default region (e.g., `ap-south-1`)
- Default output format (e.g., `json`)

### 3. Create S3 Bucket

Run the automated script:

```bash
cd backend
chmod +x create_s3_bucket.sh
./create_s3_bucket.sh ap-south-1
```

Or manually:

```bash
aws s3api create-bucket \
    --bucket pi-document-verification \
    --region ap-south-1 \
    --create-bucket-configuration LocationConstraint=ap-south-1
```

**Note:** For `us-east-1`, omit the `LocationConstraint` parameter.

### 4. Configure Environment Variables

Update your `.env` file:

```env
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
AWS_REGION=ap-south-1
S3_BUCKET_NAME=pi-document-verification
```

## Bucket Configuration

The `create_s3_bucket.sh` script automatically configures:

- **Versioning**: Enabled to track document versions
- **CORS**: Configured for browser uploads (if needed)
- **Lifecycle Policy**: Deletes old versions after 90 days

## Manual Configuration

### Enable Versioning

```bash
aws s3api put-bucket-versioning \
    --bucket pi-document-verification \
    --versioning-configuration Status=Enabled
```

### Set Up CORS (Optional)

Create `cors-config.json`:

```json
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
```

Apply:

```bash
aws s3api put-bucket-cors \
    --bucket pi-document-verification \
    --cors-configuration file://cors-config.json
```

### Set Up Lifecycle Policy

Create `lifecycle-config.json`:

```json
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
```

Apply:

```bash
aws s3api put-bucket-lifecycle-configuration \
    --bucket pi-document-verification \
    --lifecycle-configuration file://lifecycle-config.json
```

## IAM Permissions

Your IAM user/role needs the following permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject",
                "s3:DeleteObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::pi-document-verification",
                "arn:aws:s3:::pi-document-verification/*"
            ]
        }
    ]
}
```

## Testing S3 Connection

Test the connection from Python:

```python
from app.services.s3_service import s3_service

if s3_service.is_enabled():
    print("✅ S3 is enabled and configured")
else:
    print("❌ S3 is not enabled. Check your .env file.")
```

## Troubleshooting

### Access Denied

- Check IAM permissions
- Verify AWS credentials in `.env`
- Ensure bucket name matches exactly

### Bucket Not Found

- Verify bucket exists: `aws s3 ls`
- Check region matches your configuration
- Ensure bucket name is correct (S3 bucket names are globally unique)

### Upload Fails

- Check file size (default max: 10MB)
- Verify network connectivity
- Check AWS service status
- Review CloudWatch logs for detailed errors

### Download Fails

- Verify S3 key exists in database
- Check file permissions
- Ensure temp directory is writable

## Cost Optimization

- **Lifecycle Policies**: Automatically delete old versions
- **Storage Classes**: Consider using S3 Intelligent-Tiering for cost savings
- **Compression**: Compress documents before upload (if applicable)

## Security Best Practices

1. **Never commit credentials**: Keep `.env` in `.gitignore`
2. **Use IAM roles**: In production, use IAM roles instead of access keys
3. **Enable encryption**: Enable S3 bucket encryption
4. **Restrict access**: Use bucket policies to restrict access
5. **Monitor access**: Enable CloudTrail for audit logs

## Next Steps

1. Create the bucket using the script
2. Update your `.env` file with credentials
3. Test upload: `POST /api/v1/documents/upload`
4. Verify files in S3: `aws s3 ls s3://pi-document-verification/documents/`

## Additional Resources

- [AWS S3 Documentation](https://docs.aws.amazon.com/s3/)
- [AWS CLI Documentation](https://docs.aws.amazon.com/cli/latest/)
- [boto3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)

