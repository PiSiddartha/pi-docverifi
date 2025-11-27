# Deployment Guide

This guide covers deployment options for both the backend and frontend of the Document Verification System.

## Table of Contents

1. [Backend Deployment Options](#backend-deployment-options)
2. [Frontend Deployment (AWS Amplify)](#frontend-deployment-aws-amplify)
3. [Environment Configuration](#environment-configuration)
4. [Database Setup](#database-setup)
5. [S3 Setup](#s3-setup)

---

## Backend Deployment Options

### Option 1: AWS Lambda (Serverless) - Recommended for Cost Efficiency

**Pros:**
- Pay only for what you use
- Auto-scaling
- No server management
- Good for variable workloads

**Cons:**
- 15-minute timeout limit (may need to refactor long-running tasks)
- Cold starts
- Limited to 10GB memory
- OCR dependencies may be challenging

**Implementation:**

1. **Use AWS Lambda with Container Image:**
   ```bash
   # Create Dockerfile for Lambda
   FROM public.ecr.aws/lambda/python:3.12
   
   # Install system dependencies
   RUN yum install -y tesseract poppler-utils
   
   # Copy requirements and install
   COPY requirements.txt ${LAMBDA_TASK_ROOT}
   RUN pip install -r requirements.txt
   
   # Copy application code
   COPY app ${LAMBDA_TASK_ROOT}/app
   COPY run.py ${LAMBDA_TASK_ROOT}
   
   # Set handler
   CMD ["app.handler.lambda_handler"]
   ```

2. **Create Lambda Handler:**
   ```python
   # app/handler.py
   from mangum import Mangum
   from app.main import app
   
   handler = Mangum(app, lifespan="off")
   ```

3. **For Long-Running Tasks:**
   - Use AWS Step Functions or SQS + Lambda
   - Or use ECS Fargate for processing tasks

### Option 2: AWS ECS Fargate (Container) - Recommended for Reliability

**Pros:**
- No timeout limits
- Full control over environment
- Easy OCR dependency installation
- Better for long-running tasks

**Cons:**
- Higher cost (always running)
- More complex setup

**Implementation:**

1. **Create Dockerfile:**
   ```dockerfile
   FROM python:3.12-slim
   
   # Install system dependencies
   RUN apt-get update && apt-get install -y \
       tesseract-ocr \
       poppler-utils \
       libopencv-dev \
       python3-opencv \
       && rm -rf /var/lib/apt/lists/*
   
   WORKDIR /app
   
   # Install Python dependencies
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   
   # Copy application
   COPY . .
   
   # Expose port
   EXPOSE 8000
   
   # Run with uvicorn
   CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
   ```

2. **Create ECS Task Definition:**
   ```json
   {
     "family": "docverifi-backend",
     "networkMode": "awsvpc",
     "requiresCompatibilities": ["FARGATE"],
     "cpu": "2048",
     "memory": "4096",
     "containerDefinitions": [{
       "name": "backend",
       "image": "your-ecr-repo/docverifi-backend:latest",
       "portMappings": [{
         "containerPort": 8000,
         "protocol": "tcp"
       }],
       "environment": [
         {"name": "DATABASE_URL", "value": "..."},
         {"name": "ENVIRONMENT", "value": "production"}
       ],
       "logConfiguration": {
         "logDriver": "awslogs",
         "options": {
           "awslogs-group": "/ecs/docverifi-backend",
           "awslogs-region": "ap-south-1",
           "awslogs-stream-prefix": "ecs"
         }
       }
     }]
   }
   ```

3. **Create ECS Service with Application Load Balancer**

### Option 3: EC2 Instance (Traditional)

**Pros:**
- Full control
- Easy setup
- Good for development/testing

**Cons:**
- Manual scaling
- Server management required
- Higher operational overhead

**Implementation:**

1. Launch EC2 instance (Ubuntu 22.04 LTS recommended)
2. Install dependencies:
   ```bash
   sudo apt-get update
   sudo apt-get install -y python3.12 python3.12-venv tesseract-ocr poppler-utils
   ```
3. Deploy application
4. Use systemd service or PM2 for process management

---

## Frontend Deployment (AWS Amplify)

### Prerequisites

1. AWS Account
2. Amplify CLI installed: `npm install -g @aws-amplify/cli`
3. Git repository with frontend code

### Steps

1. **Initialize Amplify:**
   ```bash
   cd frontend
   amplify init
   ```

2. **Add Hosting:**
   ```bash
   amplify add hosting
   # Select: Hosting with Amplify Console
   ```

3. **Configure Build Settings:**
   
   Create `amplify.yml` in frontend root:
   ```yaml
   version: 1
   frontend:
     phases:
       preBuild:
         commands:
           - npm ci
       build:
         commands:
           - npm run build
     artifacts:
       baseDirectory: .next
       files:
         - '**/*'
     cache:
       paths:
         - node_modules/**/*
   ```

4. **Set Environment Variables:**
   - In Amplify Console → App Settings → Environment Variables
   - Add: `NEXT_PUBLIC_API_URL` = your backend API URL

5. **Deploy:**
   ```bash
   amplify publish
   ```

   Or connect to Git repository for automatic deployments

### Alternative: Vercel (Easier Setup)

1. Push code to GitHub
2. Import project in Vercel
3. Set environment variables
4. Deploy

---

## Environment Configuration

### Backend Environment Variables

Create `.env` file or set in deployment platform:

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Companies House API
COMPANIES_HOUSE_API_KEY=your_key_here

# AWS S3
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=ap-south-1
S3_BUCKET_NAME=your-bucket-name

# Application
ENVIRONMENT=production
SECRET_KEY=generate-secure-random-key
CORS_ORIGINS=https://your-frontend-domain.com

# File Upload
MAX_UPLOAD_SIZE=10485760  # 10MB
UPLOAD_DIR=/tmp/uploads  # For Lambda, use /tmp
```

### Frontend Environment Variables

```bash
NEXT_PUBLIC_API_URL=https://your-backend-api.com
```

---

## Database Setup

### RDS PostgreSQL

1. **Create RDS Instance:**
   - Engine: PostgreSQL 15+
   - Instance class: db.t3.medium (or larger for production)
   - Storage: 20GB+ (auto-scaling enabled)
   - Multi-AZ: Enable for production
   - Backup retention: 7 days

2. **Security:**
   - VPC: Use private subnet
   - Security Group: Allow access from backend only
   - Enable encryption at rest

3. **Run Migrations:**
   ```bash
   # Connect to RDS and run
   psql -h your-rds-endpoint -U postgres -d your_db < database_schema.sql
   psql -h your-rds-endpoint -U postgres -d your_db < alter_column_sizes.sql
   ```

---

## S3 Setup

1. **Create S3 Bucket:**
   ```bash
   aws s3 mb s3://your-docverifi-bucket --region ap-south-1
   ```

2. **Configure CORS:**
   ```json
   [
     {
       "AllowedHeaders": ["*"],
       "AllowedMethods": ["GET", "PUT", "POST", "DELETE"],
       "AllowedOrigins": ["https://your-frontend-domain.com"],
       "ExposeHeaders": []
     }
   ]
   ```

3. **Bucket Policy (if needed):**
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [{
       "Effect": "Allow",
       "Principal": {"AWS": "arn:aws:iam::account-id:role/your-role"},
       "Action": ["s3:GetObject", "s3:PutObject"],
       "Resource": "arn:aws:s3:::your-bucket/*"
     }]
   }
   ```

---

## Deployment Checklist

### Backend
- [ ] Database migrations run
- [ ] Environment variables configured
- [ ] S3 bucket created and configured
- [ ] CORS settings updated
- [ ] Health check endpoint working
- [ ] Logging configured (CloudWatch)
- [ ] Monitoring/alerts set up

### Frontend
- [ ] Environment variables set
- [ ] API URL configured
- [ ] Build succeeds
- [ ] CORS allows frontend domain
- [ ] SSL certificate configured
- [ ] Custom domain (optional)

---

## Monitoring & Logging

### CloudWatch Logs

For ECS/Lambda:
- Log groups automatically created
- View logs in CloudWatch Console

### Application Monitoring

Consider:
- AWS X-Ray for tracing
- CloudWatch Metrics for custom metrics
- SNS for alerts

---

## Cost Estimation (Monthly)

### ECS Fargate (2 vCPU, 4GB RAM, 24/7):
- ~$150-200/month

### Lambda (1000 requests/day, 5s avg):
- ~$10-20/month

### RDS (db.t3.medium):
- ~$100-150/month

### S3 Storage (100GB):
- ~$2-3/month

### Amplify Hosting:
- Free tier available, then ~$15/month

---

## Security Best Practices

1. **Secrets Management:**
   - Use AWS Secrets Manager or Parameter Store
   - Never commit `.env` files

2. **Network Security:**
   - Use VPC for backend
   - Security groups with least privilege
   - WAF for API protection

3. **Data Encryption:**
   - Encrypt RDS at rest
   - Use HTTPS everywhere
   - Encrypt S3 objects

4. **Access Control:**
   - IAM roles with least privilege
   - API authentication (JWT tokens)

---

## Troubleshooting

### Common Issues

1. **OCR not working in Lambda:**
   - Use container image with dependencies pre-installed
   - Or use ECS instead

2. **Timeout errors:**
   - Use ECS for long-running tasks
   - Or implement async processing with SQS

3. **CORS errors:**
   - Check CORS_ORIGINS in backend
   - Verify frontend domain matches

4. **Database connection errors:**
   - Check security group rules
   - Verify VPC configuration

---

## Support

For deployment issues, check:
- AWS CloudWatch Logs
- Application logs
- Network connectivity
- IAM permissions

