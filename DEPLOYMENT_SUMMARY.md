# Document Verification Backend - Deployment Summary

**Deployment Date:** December 3, 2025  
**Region:** ap-south-1  
**Status:** ✅ **OPERATIONAL**

---

## 🏗️ Architecture Overview

The backend is deployed on AWS using a serverless, event-driven architecture:

```
Frontend → ALB → ECS Fargate (FastAPI Backend)
                    ↓
                SQS Queue → Lambda → ECS Backend (Processing)
```

### Components

1. **Application Load Balancer (ALB)**
   - Public-facing entry point
   - Routes traffic to ECS tasks
   - Health checks on `/health` endpoint

2. **ECS Fargate Service**
   - Runs FastAPI backend in containers
   - Auto-scales based on demand
   - Private subnets for security

3. **SQS Queue**
   - Asynchronous document processing
   - Dead Letter Queue (DLQ) for failed messages
   - Triggers Lambda function

4. **Lambda Function**
   - Processes SQS messages
   - Calls ECS backend for document verification
   - Event-driven, cost-effective

5. **ECR Repository**
   - Stores Docker images
   - Versioned container images

---

## 📋 Deployment Details

### ALB Configuration

- **DNS Name:** `document-verification-alb-1580232532.ap-south-1.elb.amazonaws.com`
- **ARN:** `arn:aws:elasticloadbalancing:ap-south-1:177215708218:loadbalancer/app/document-verification-alb/8882d349ae5e3184`
- **Security Group:** `sg-0211ea2fd6126b520`
- **Target Group:** `document-verification-tg`
- **Health Check:** `/health` (30s interval, 5s timeout)

### ECS Configuration

- **Cluster:** `document-verification-cluster`
- **Service:** `document-verification-service`
- **Task Definition:** `document-verification-task`
- **Security Group:** `sg-0c786fb3c4a1dbcb9`
- **Subnets:** 
  - `subnet-0b147e771e6cde399` (ap-south-1b)
  - `subnet-01c946c4ef99f7c58` (ap-south-1a)
- **VPC:** `vpc-02ab30d45a5f5ec3d` (pi-infra-dev-vpc-ap-south-1)
- **CPU:** 1024 (1 vCPU)
- **Memory:** 2048 MB (2 GB)

### SQS Configuration

- **Main Queue:** `document-verification-queue`
  - URL: `https://sqs.ap-south-1.amazonaws.com/177215708218/document-verification-queue`
  - Visibility Timeout: 900 seconds (15 minutes)
  - Message Retention: 1209600 seconds (14 days)
  - Max Receive Count: 3

- **Dead Letter Queue:** `document-verification-dlq`
  - URL: `https://sqs.ap-south-1.amazonaws.com/177215708218/document-verification-dlq`

### Lambda Configuration

- **Function Name:** `document-processor`
- **Runtime:** Python 3.12
- **Timeout:** 300 seconds (5 minutes)
- **Memory:** 512 MB
- **IAM Role:** `lambda-document-processor-role`
- **Event Source:** SQS queue (batch size: 1)

### ECR Configuration

- **Repository:** `document-verification-backend`
- **Image URI:** `177215708218.dkr.ecr.ap-south-1.amazonaws.com/document-verification-backend:latest`
- **Region:** ap-south-1

---

## 🔧 Key Technical Decisions

### Docker Image Optimization

**Base Image:** `python:3.12-slim`

**System Dependencies:**
- `gcc`, `g++` - Build tools for Python packages
- `libpq-dev` - PostgreSQL client (for psycopg2-binary)
- `poppler-utils` - PDF to image conversion (for pdf2image)
- `libmagic1` - File type detection (for python-magic)
- `libglib2.0-0`, `libgomp1` - OpenCV dependencies
- `libjpeg-dev`, `libpng-dev`, `libtiff-dev` - Image processing

**Python Package Changes:**
- ✅ `opencv-python-headless` (instead of `opencv-python`)
  - Removes GUI/OpenGL dependencies
  - Perfect for headless containers
  - No `libGL.so.1` errors

**Environment Variables:**
- `QT_QPA_PLATFORM=offscreen` - Headless OpenCV
- `OPENCV_IO_ENABLE_OPENEXR=0` - Disable unnecessary formats

### Security Group Configuration

**Critical Fix:** ECS service initially had empty security groups array, preventing ALB from reaching tasks.

**Final Configuration:**
- ALB Security Group (`sg-0211ea2fd6126b520`):
  - Ingress: HTTP (80) from 0.0.0.0/0
  - Ingress: HTTPS (443) from 0.0.0.0/0

- ECS Security Group (`sg-0c786fb3c4a1dbcb9`):
  - Ingress: TCP 8000 from ALB Security Group
  - Egress: All traffic (default)

---

## 🌐 Endpoints

### Public Endpoints

- **Health Check:** `http://document-verification-alb-1580232532.ap-south-1.elb.amazonaws.com/health`
- **API Documentation:** `http://document-verification-alb-1580232532.ap-south-1.elb.amazonaws.com/api/docs`
- **ReDoc:** `http://document-verification-alb-1580232532.ap-south-1.elb.amazonaws.com/api/redoc`
- **Root:** `http://document-verification-alb-1580232532.ap-south-1.elb.amazonaws.com/`

### API Endpoints

- **Document Upload:** `POST /api/v1/documents/upload`
- **Document Status:** `GET /api/v1/documents/{document_id}`
- **Verification:** `POST /api/v1/verification/{document_id}`
- **Progress:** `GET /api/v1/progress/{task_id}`

---

## 📊 Monitoring & Logs

### View ECS Logs

```bash
aws logs tail /ecs/document-verification --follow --region ap-south-1
```

### View Lambda Logs

```bash
aws logs tail /aws/lambda/document-processor --follow --region ap-south-1
```

### Check Service Status

```bash
# Service status
aws ecs describe-services \
  --cluster document-verification-cluster \
  --services document-verification-service \
  --region ap-south-1

# Task status
aws ecs list-tasks \
  --cluster document-verification-cluster \
  --service-name document-verification-service \
  --region ap-south-1

# Health check script
cd deployment
./check-health.sh
```

### Check ALB Target Health

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

## 🔄 Deployment Scripts

All deployment scripts are in the `deployment/` directory:

### Main Scripts

- **`rebuild-and-deploy.sh`** - Rebuild Docker image and force ECS deployment
- **`sync-env-to-ecs.sh`** - Sync local `.env` variables to ECS task definition
- **`update-ecs-config.sh`** - Update specific environment variables (key=value pairs)

### Usage

```bash
# Rebuild and redeploy
cd deployment
./rebuild-and-deploy.sh

# Sync all variables from .env file
./sync-env-to-ecs.sh ../backend/.env

# Update specific variables
./update-ecs-config.sh OPENAI_API_KEY=sk-new-key COMPANIES_HOUSE_API_KEY=new-key
```

---

## 🔐 Environment Variables

Environment variables are configured in the ECS task definition. Key variables:

- `DATABASE_URL` - PostgreSQL connection string
- `SQS_QUEUE_URL` - SQS queue URL
- `USE_SQS` - `true` (enables SQS processing)
- `AWS_REGION` - `ap-south-1`
- `COMPANIES_HOUSE_API_KEY` - Companies House API key
- `HMRC_CLIENT_ID` - HMRC OAuth client ID
- `HMRC_CLIENT_SECRET` - HMRC OAuth client secret
- `OPENAI_API_KEY` - OpenAI API key
- `S3_BUCKET_NAME` - S3 bucket for document storage
- `SECRET_KEY` - Application secret key
- `CORS_ORIGINS` - Allowed CORS origins

**Note:** Environment variables can be updated after deployment:
- **All variables:** Use `sync-env-to-ecs.sh` to sync from `.env` file
- **Specific variables:** Use `update-ecs-config.sh KEY=value` for quick updates

---

## 🐛 Issues Resolved During Deployment

### 1. OpenCV Import Error (`libGL.so.1`)

**Problem:** `ImportError: libGL.so.1: cannot open shared object file`

**Solution:** 
- Switched from `opencv-python` to `opencv-python-headless`
- Removed unnecessary X11/OpenGL libraries from Dockerfile
- Added environment variables for headless operation

### 2. PostgreSQL Dialect Error

**Problem:** `sqlalchemy.exc.NoSuchModuleError: Can't load plugin: sqlalchemy.dialects:postgres`

**Solution:**
- Added `libpq-dev` to Dockerfile (required by `psycopg2-binary`)

### 3. ECS Security Group Not Configured

**Problem:** ALB couldn't reach ECS tasks (504 Gateway Timeout)

**Solution:**
- Updated ECS service to use security group `sg-0c786fb3c4a1dbcb9`
- Verified ingress rule allows ALB → ECS on port 8000

### 4. Package Availability Issues

**Problem:** `E: Package 'libgl1-mesa-glx' has no installation candidate`

**Solution:**
- Updated package names for Debian Trixie (Python 3.12-slim base image)
- Used `libgl1` instead of `libgl1-mesa-glx`

---

## 📦 Docker Image Details

### Build Command

```bash
cd backend
docker build -t document-verification-backend:latest .
```

### Push to ECR

```bash
# Login to ECR
aws ecr get-login-password --region ap-south-1 | \
  docker login --username AWS --password-stdin \
  177215708218.dkr.ecr.ap-south-1.amazonaws.com

# Tag and push
docker tag document-verification-backend:latest \
  177215708218.dkr.ecr.ap-south-1.amazonaws.com/document-verification-backend:latest

docker push \
  177215708218.dkr.ecr.ap-south-1.amazonaws.com/document-verification-backend:latest
```

### Image Size Optimization

- Base image: `python:3.12-slim` (~45 MB)
- Final image: ~500-600 MB (includes all dependencies)
- Multi-stage build not used (single stage is sufficient for this use case)

---

## 🔄 Update Process

### Update Application Code

1. **Make code changes**
2. **Rebuild and push image:**
   ```bash
   cd deployment
   ./rebuild-and-deploy.sh
   ```
3. **Monitor deployment:**
   ```bash
   aws ecs describe-services \
     --cluster document-verification-cluster \
     --services document-verification-service \
     --region ap-south-1
   ```

### Update Environment Variables

```bash
cd deployment
./sync-env-to-ecs.sh
```

Or update specific variables:
```bash
./update-ecs-config.sh KEY1=value1 KEY2=value2
```

### Update Lambda Function

```bash
cd deployment
./deploy-lambda.sh
```

---

## 🎯 Performance & Scaling

### Current Configuration

- **ECS Tasks:** 1 (can be scaled up)
- **CPU:** 1024 (1 vCPU) per task
- **Memory:** 2048 MB (2 GB) per task
- **ALB:** Application Load Balancer (handles auto-scaling)

### Scaling Recommendations

- **Horizontal Scaling:** Increase `desiredCount` in ECS service
- **Auto Scaling:** Configure ECS Auto Scaling based on CPU/memory metrics
- **Lambda Concurrency:** Adjust Lambda reserved concurrency if needed

### Cost Optimization

- **ECS Fargate:** Pay only for running tasks
- **Lambda:** Pay per invocation (very cost-effective)
- **SQS:** First 1M requests/month free
- **ALB:** ~$0.0225/hour + data transfer

---

## 🔒 Security Best Practices

✅ **Implemented:**
- ECS tasks in private subnets (no public IP)
- Security groups restrict traffic (ALB → ECS only)
- Environment variables stored in ECS task definition (not in code)
- IAM roles with least privilege
- Dead Letter Queue for failed messages

⚠️ **Recommendations:**
- Enable HTTPS on ALB (add SSL certificate)
- Use AWS Secrets Manager for sensitive credentials
- Enable CloudWatch alarms for monitoring
- Set up VPC Flow Logs for network monitoring
- Regular security group reviews

---

## 📝 Quick Reference

### Important URLs

- **ALB DNS:** `document-verification-alb-1580232532.ap-south-1.elb.amazonaws.com`
- **Health Check:** `http://document-verification-alb-1580232532.ap-south-1.elb.amazonaws.com/health`
- **API Docs:** `http://document-verification-alb-1580232532.ap-south-1.elb.amazonaws.com/api/docs`

### Important Commands

```bash
# Check health
curl http://document-verification-alb-1580232532.ap-south-1.elb.amazonaws.com/health

# View logs
aws logs tail /ecs/document-verification --follow --region ap-south-1

# Rebuild and deploy
cd deployment && ./rebuild-and-deploy.sh

# Check service status
cd deployment && ./check-health.sh
```

### AWS Console Links

- **ECS Cluster:** [Console](https://ap-south-1.console.aws.amazon.com/ecs/v2/clusters/document-verification-cluster)
- **ECR Repository:** [Console](https://ap-south-1.console.aws.amazon.com/ecr/repositories/document-verification-backend)
- **ALB:** [Console](https://ap-south-1.console.aws.amazon.com/ec2/v2/home?region=ap-south-1#LoadBalancers:)
- **SQS Queue:** [Console](https://ap-south-1.console.aws.amazon.com/sqs/v2/home?region=ap-south-1#/queues)
- **Lambda:** [Console](https://ap-south-1.console.aws.amazon.com/lambda/home?region=ap-south-1#/functions)

---

## ✅ Deployment Checklist

- [x] ECR repository created
- [x] Docker image built and pushed
- [x] ECS cluster created
- [x] IAM roles configured (Task Execution & Task Role)
- [x] Task definition registered
- [x] ALB created with target group
- [x] Security groups configured correctly
- [x] ECS service created and running
- [x] Health checks passing
- [x] SQS queues created (main + DLQ)
- [x] Lambda function deployed
- [x] Lambda connected to SQS
- [x] Environment variables configured
- [x] Logs accessible in CloudWatch
- [x] API endpoints responding

---

## 📞 Support & Troubleshooting

### Common Issues

1. **503 Service Unavailable**
   - Check ECS service has running tasks
   - Verify security groups allow ALB → ECS traffic
   - Check task logs for errors

2. **504 Gateway Timeout**
   - Verify health check endpoint responds quickly
   - Check security group rules
   - Ensure tasks are in correct subnets

3. **Tasks Failing to Start**
   - Check task definition for errors
   - Verify ECR image exists and is accessible
   - Check IAM role permissions
   - Review CloudWatch logs

### Useful Debugging Commands

```bash
# Check task status
aws ecs describe-tasks \
  --cluster document-verification-cluster \
  --tasks $(aws ecs list-tasks --cluster document-verification-cluster --service-name document-verification-service --region ap-south-1 --query 'taskArns[0]' --output text) \
  --region ap-south-1

# Check target health
aws elbv2 describe-target-health \
  --target-group-arn $(aws elbv2 describe-target-groups --names document-verification-tg --region ap-south-1 --query 'TargetGroups[0].TargetGroupArn' --output text) \
  --region ap-south-1

# View recent service events
aws ecs describe-services \
  --cluster document-verification-cluster \
  --services document-verification-service \
  --region ap-south-1 \
  --query 'services[0].events[0:5]' \
  --output table
```

---

## 🎉 Deployment Complete!

The Document Verification backend is now fully deployed and operational on AWS. All components are connected and working correctly.

**Last Verified:** December 3, 2025, 13:29 IST  
**Status:** ✅ Healthy and responding to requests

---

*For detailed deployment instructions, see [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)*

