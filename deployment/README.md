# Deployment Guide

This directory contains scripts for managing the deployed Document Verification backend on AWS.

## Quick Start

### Rebuild and Deploy

Rebuild the Docker image and deploy to ECS:

```bash
./rebuild-and-deploy.sh
```

This script:
1. Builds the Docker image
2. Pushes to ECR
3. Forces ECS service to pull the new image

### Sync Environment Variables

Sync environment variables from your local `.env` file to ECS:

```bash
./sync-env-to-ecs.sh ../backend/.env
```

This script:
1. Reads your `.env` file
2. Extracts relevant environment variables
3. Updates the ECS task definition
4. Deploys the new configuration

---

## Scripts

### `rebuild-and-deploy.sh`

Rebuilds the Docker image and forces ECS deployment.

**Usage:**
```bash
./rebuild-and-deploy.sh
```

**What it does:**
- Builds Docker image from `../backend/Dockerfile`
- Tags and pushes to ECR
- Forces ECS service to pull new image
- Monitors deployment status

### `sync-env-to-ecs.sh`

Syncs environment variables from `.env` file to ECS task definition.

**Usage:**
```bash
./sync-env-to-ecs.sh [path-to-env-file]
```

**Example:**
```bash
./sync-env-to-ecs.sh ../backend/.env
```

**What it does:**
- Reads `.env` file
- Extracts environment variables
- Updates ECS task definition
- Deploys new task definition
- Forces service update

### `update-ecs-config.sh`

Updates specific environment variables without reading from `.env` file.

**Usage:**
```bash
./update-ecs-config.sh KEY1=value1 KEY2=value2 ...
```

**Examples:**
```bash
# Update a single variable
./update-ecs-config.sh OPENAI_API_KEY=sk-new-key

# Update multiple variables
./update-ecs-config.sh COMPANIES_HOUSE_API_KEY=new-key S3_BUCKET_NAME=new-bucket

# Update with quotes (optional)
./update-ecs-config.sh CORS_ORIGINS="http://localhost:3000,https://example.com"
```

**What it does:**
- Takes key=value pairs as arguments
- Updates/adds environment variables in ECS task definition
- Merges with existing variables (updates if key exists, adds if new)
- Deploys new task definition
- Forces service update

**Use cases:**
- Quick updates to single variables
- Updating API keys without modifying `.env` file
- Testing different configurations
- Updating variables from CI/CD pipelines

**Environment Variables Synced:**
- `DATABASE_URL`
- `COMPANIES_HOUSE_API_KEY`
- `HMRC_CLIENT_ID`
- `HMRC_CLIENT_SECRET`
- `OPENAI_API_KEY`
- `S3_BUCKET_NAME`
- `AWS_ACCESS_KEY_ID` (if not using IAM role)
- `AWS_SECRET_ACCESS_KEY` (if not using IAM role)
- `SECRET_KEY`
- `ENVIRONMENT`
- `CORS_ORIGINS`
- `MAX_UPLOAD_SIZE`
- `REDIS_URL` (if set)

---

## Environment Variables

### Required Variables

- `DATABASE_URL` - PostgreSQL connection string
- `SQS_QUEUE_URL` - SQS queue URL (auto-set during deployment)
- `USE_SQS` - Set to "true" (auto-set during deployment)
- `AWS_REGION` - AWS region (default: ap-south-1)

### Optional but Recommended

- `S3_BUCKET_NAME` - S3 bucket for document storage
- `COMPANIES_HOUSE_API_KEY` - Companies House API key
- `OPENAI_API_KEY` - OpenAI API key
- `HMRC_CLIENT_ID` - HMRC OAuth client ID
- `HMRC_CLIENT_SECRET` - HMRC OAuth client secret

### Security Best Practices

1. ✅ **Never commit `.env` to git** (should be in `.gitignore`)
2. ✅ **Never include `.env` in Docker image** (already done via `.dockerignore`)
3. ✅ **Use IAM roles instead of access keys** (ECS task role is already configured)
4. ⚠️ **For production, use AWS Secrets Manager** instead of environment variables
5. ⚠️ **Rotate secrets regularly**

---

## Deployment Architecture

The backend is deployed on AWS with the following components:

- **ECS Fargate**: Runs FastAPI backend in containers
- **Application Load Balancer (ALB)**: Public-facing entry point
- **SQS Queue**: Asynchronous document processing
- **Lambda Function**: Processes SQS messages
- **ECR Repository**: Stores Docker images

For detailed deployment information, see [../DEPLOYMENT_SUMMARY.md](../DEPLOYMENT_SUMMARY.md).

---

## Troubleshooting

### Variables not appearing in container

- Check task definition revision:
  ```bash
  aws ecs describe-task-definition --task-definition document-verification-task --region ap-south-1
  ```
- Verify service is using latest revision
- Check container logs:
  ```bash
  aws logs tail /ecs/document-verification --follow --region ap-south-1
  ```

### Service not updating

- Check ECS service status:
  ```bash
  aws ecs describe-services \
    --cluster document-verification-cluster \
    --services document-verification-service \
    --region ap-south-1
  ```
- Verify new task definition was created
- Check for deployment errors in service events

### Health check failures

- Verify security groups allow ALB → ECS traffic
- Check application logs for startup errors
- Ensure `/health` endpoint responds quickly

---

## Monitoring

### View Logs

```bash
# ECS logs
aws logs tail /ecs/document-verification --follow --region ap-south-1

# Lambda logs
aws logs tail /aws/lambda/document-processor --follow --region ap-south-1
```

### Check Service Status

```bash
aws ecs describe-services \
  --cluster document-verification-cluster \
  --services document-verification-service \
  --region ap-south-1
```

### Check ALB Health

```bash
aws elbv2 describe-target-health \
  --target-group-arn $(aws elbv2 describe-target-groups \
    --names document-verification-tg \
    --region ap-south-1 \
    --query 'TargetGroups[0].TargetGroupArn' \
    --output text) \
  --region ap-south-1
```

---

## Quick Reference

**ALB DNS:** `document-verification-alb-1580232532.ap-south-1.elb.amazonaws.com`

**Health Check:** `http://document-verification-alb-1580232532.ap-south-1.elb.amazonaws.com/health`

**API Docs:** `http://document-verification-alb-1580232532.ap-south-1.elb.amazonaws.com/api/docs`

**Region:** `ap-south-1`

**Cluster:** `document-verification-cluster`

**Service:** `document-verification-service`

**Task Definition:** `document-verification-task`
