# Document Verification System

Industry-standard document verification system with AWS Textract OCR, advanced forensic analysis, and Companies House API integration.

## Features

- **AWS Textract OCR**: High-accuracy text extraction from PDFs and images using AWS Textract
  - Automatic fallback to image conversion for unsupported PDF formats
  - Parallel processing for multi-page documents (up to 5x faster)
  - Optimized performance with JPEG conversion and lower DPI processing
  - Support for both synchronous (≤5MB) and asynchronous (>5MB) processing
- **Advanced Forensic Analysis**: 10+ industry-standard checks to detect document tampering:
  - **EXIF Data Analysis**: Metadata extraction and anomaly detection
  - **ELA (Error Level Analysis)**: Detects re-saved JPEG artifacts
  - **JPEG Quality Analysis**: Identifies compression history inconsistencies
  - **Copy-Move Forgery Detection**: Finds duplicated regions with context-aware thresholds
  - **PDF Metadata Analysis**: Analyzes PDF metadata for suspicious patterns
  - **Resolution/DPI Consistency**: Detects upscaling and inconsistent resolution
  - **Color Histogram Analysis**: Identifies unusual color patterns (grayscale-aware)
  - **Noise Pattern Analysis**: Detects inconsistent noise characteristics
  - **File Hash/Integrity Check**: MD5 and SHA256 verification
- **Companies House Integration**: Real-time verification against UK Companies House API
- **Intelligent Field Extraction**: Advanced pattern matching for company names, numbers, and addresses
  - Handles complex formats (parentheses, ampersands, single-letter prefixes)
  - Automatic company number normalization (7-digit to 8-digit padding)
- **Scoring System**: Comprehensive scoring (0-100) based on OCR, registry matching, provided data accuracy, and forensic penalties
- **Manual Review**: Review interface for documents requiring human verification
- **Modern UI**: Beautiful Next.js frontend with Tailwind CSS

## Architecture

The system follows the workflow diagram:
1. Document Upload → Store in S3/File System → Create DB Record
2. OCR Processing → Extract Fields (Name, DOB, Company#, Address)
3. Forensic Analysis → EXIF, ELA, JPEG, Copy-Move Detection
4. Companies House API → Fetch Real Data
5. Data Comparison → OCR vs Provided vs Real Data
6. Scoring → OCR(0-30) + Registry(0-40) + Provided(0-30) - Forensic(0-15)
7. Decision → PASS (≥75), REVIEW (50-74), FAIL (<50)
8. Manual Review → For documents in review status

## Setup

### Backend Setup

1. Navigate to backend directory:
```bash
cd backend
```

2. Create and activate virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Install system dependencies (for PDF to image conversion fallback):
```bash
# macOS
brew install poppler

# Ubuntu/Debian
sudo apt-get install poppler-utils

# Windows
# Download and install Poppler from:
# https://github.com/oschwartz10612/poppler-windows/releases
```

**Note**: AWS Textract is used for OCR, so Tesseract is no longer required. Poppler is only needed for the fallback PDF-to-image conversion when Textract rejects certain PDF formats.

5. Create `.env` file:
```bash
cp .env.example .env
```

6. Update `.env` with your configuration:
```env
DATABASE_URL=postgresql://user:password@localhost:5432/docverifi_db
COMPANIES_HOUSE_API_KEY=your_api_key_here

# AWS Textract Configuration (required for OCR)
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=us-east-1  # or your preferred region

# Optional: S3 Configuration (required for files >5MB)
AWS_S3_BUCKET=your-s3-bucket-name
```

7. Create database:
```bash
# Using PostgreSQL
createdb docverifi_db
```

8. Run database migrations:
```bash
# Apply SQL migrations from the migrations/ directory
psql -d docverifi_db -f migrations/add_document_type.sql
```

9. Start the server:
```bash
python run.py
```

The API will be available at `http://localhost:8000`
API docs at `http://localhost:8000/api/docs`

### Frontend Setup

1. Navigate to frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Create `.env.local` file:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

4. Start development server:
```bash
npm run dev
```

The frontend will be available at `http://localhost:3000`

## Usage

### Upload Document

1. Go to the Upload Document tab
2. Drag and drop or select a PDF file
3. Optionally provide company information (name, number, address, date)
4. Click "Upload & Verify Document"
5. The system will automatically start processing

### View Results

1. Go to the View Documents tab
2. See list of all uploaded documents
3. Click "View" to see detailed results including:
   - OCR extracted data
   - Companies House data
   - Forensic analysis results
   - Score breakdown
   - Decision (PASS/FAIL/REVIEW)

### Manual Review

For documents with status "review" (score 50-74):
1. Open document details
2. Review all extracted data and scores
3. Enter review notes
4. Choose action: Approve, Reject, or Escalate

## API Endpoints

### Documents
- `POST /api/v1/documents/upload` - Upload document
- `GET /api/v1/documents/{document_id}` - Get document details
- `GET /api/v1/documents/` - List documents

### Verification
- `POST /api/v1/verification/process/{document_id}` - Start processing
- `POST /api/v1/verification/review/{document_id}` - Manual review action

## Scoring Breakdown

- **OCR Score (0-30)**: Based on AWS Textract confidence and field extraction accuracy
- **Registry Score (0-40)**: Match between OCR company number and Companies House data
- **Provided Score (0-30)**: Accuracy of merchant-provided data vs Companies House data
- **Forensic Penalty (0-15)**: Deducted for suspicious forensic findings:
  - Copy-move detection (graduated penalties: -2 to -7)
  - Resolution inconsistencies
  - Color space anomalies (grayscale-aware)
  - Noise pattern inconsistencies
  - Metadata anomalies
- **Final Score**: OCR + Registry + Provided - Forensic Penalty

### Decision Thresholds
- **PASS**: Score ≥ 75
- **REVIEW**: Score 50-74
- **FAIL**: Score < 50

## Technologies

### Backend
- **FastAPI** (Python web framework)
- **SQLAlchemy** (ORM)
- **PostgreSQL** (Database)
- **AWS Textract** (OCR - primary)
- **pdf2image** (PDF to image conversion fallback)
- **boto3** (AWS SDK for Textract and S3)
- **OpenCV, scikit-image** (Forensic analysis)
- **pypdf** (PDF metadata analysis)
- **Companies House API** (UK company data verification)

### Frontend
- **Next.js 14** (React framework)
- **TypeScript**
- **Tailwind CSS**
- **Axios** (HTTP client)
- **React Dropzone** (File upload)

## Performance Optimizations

The system includes several performance optimizations for fast OCR processing:

1. **Parallel Image Processing**: Up to 5 images processed concurrently using ThreadPoolExecutor
2. **Optimized PDF Conversion**: 
   - Lower DPI (200 instead of 300) for faster conversion
   - JPEG format instead of PNG (3x faster saves)
   - Parallel page conversion with thread_count=4
3. **Immediate File Cleanup**: Temp files deleted immediately after processing
4. **Smart Fallback**: Automatic detection and fast fallback when Textract rejects PDF format
5. **Performance Logging**: Detailed timing information for monitoring

**Expected Performance**: 
- Multi-page PDFs with image conversion: ~6-12 seconds (previously 30-60 seconds)
- Direct Textract processing: ~2-5 seconds per document

## Development

### Backend Development
```bash
cd backend
source venv/bin/activate
python run.py
```

### Frontend Development
```bash
cd frontend
npm run dev
```

## Production Deployment

The backend is deployed on AWS using ECS Fargate, ALB, SQS, and Lambda.

### AWS Deployment

For detailed deployment information, see:
- **[DEPLOYMENT_SUMMARY.md](./DEPLOYMENT_SUMMARY.md)** - Complete deployment reference
- **[deployment/README.md](./deployment/README.md)** - Deployment scripts and management

**Quick Commands:**
```bash
# Rebuild and deploy
cd deployment
./rebuild-and-deploy.sh

# Sync environment variables
./sync-env-to-ecs.sh ../backend/.env
```

**Production Endpoints:**
- Health: `http://document-verification-alb-1580232532.ap-south-1.elb.amazonaws.com/health`
- API Docs: `http://document-verification-alb-1580232532.ap-south-1.elb.amazonaws.com/api/docs`

### Local Production Setup

1. Set `ENVIRONMENT=production` in backend `.env`
2. Configure proper database and S3 credentials
3. Build frontend: `npm run build`
4. Use production WSGI server (e.g., Gunicorn) for backend
5. Deploy frontend to Vercel, Netlify, or similar

## Recent Improvements

### OCR Engine Upgrade (Latest)
- **Migrated from Tesseract to AWS Textract** for higher accuracy and better performance
- **Parallel processing** for multi-page documents (5x speed improvement)
- **Optimized fallback** when Textract rejects PDF format (JPEG conversion, lower DPI)
- **Enhanced field extraction** with improved patterns for company names (handles parentheses, ampersands, single letters)
- **Automatic company number normalization** (7-digit to 8-digit padding)

### Forensic Analysis Enhancements
- **5 new industry-standard checks** added:
  - PDF metadata analysis
  - Resolution/DPI consistency detection
  - Color histogram analysis (grayscale-aware)
  - Noise pattern analysis
  - File hash/integrity verification
- **Improved copy-move detection** with context-aware thresholds and graduated penalties
- **Better handling of scanned documents** to reduce false positives

### Performance Optimizations
- **Parallel image processing** (up to 5 concurrent Textract calls)
- **Optimized PDF conversion** (200 DPI, JPEG format, parallel processing)
- **Immediate file cleanup** to reduce disk I/O
- **Performance logging** for monitoring and optimization

## License

MIT

