# Backend - Document Verification API

FastAPI backend for document verification system with OCR, forensic analysis, and Companies House integration.

## Quick Start

1. **Create and activate virtual environment:**
```bash
python3.12 -m venv venv  # Use Python 3.12 (recommended) or 3.11
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate  # Windows
```

2. **Install Python dependencies:**
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

3. **Install OCR system dependencies:**
```bash
# Automated installation (recommended)
chmod +x install_ocr_dependencies.sh
./install_ocr_dependencies.sh

# Or manually (see OCR_SETUP.md for details)
```

4. **Set up AWS S3 (for document storage):**
```bash
# Configure AWS CLI first: aws configure
chmod +x create_s3_bucket.sh
./create_s3_bucket.sh ap-south-1
```

5. **Configure environment:**
```bash
cp ENV_EXAMPLE.txt .env
# Edit .env with your:
# - Database URL
# - Companies House API key
# - AWS S3 credentials (if using S3)
```

6. **Run the server:**
```bash
python run.py
```

API available at `http://localhost:8000`  
API docs at `http://localhost:8000/api/docs`

## Setup Documentation

- **OCR Dependencies**: See [OCR_SETUP.md](OCR_SETUP.md) for detailed OCR installation instructions
- **AWS S3 Setup**: See [S3_SETUP.md](S3_SETUP.md) for S3 bucket configuration

## Database

The system uses the existing PostgreSQL database. Tables `document_verifications` and `audit_logs` are already created.

To test connection:
```bash
python test_connection.py
```

## API Endpoints

- `POST /api/v1/documents/upload` - Upload document for verification
- `GET /api/v1/documents/{document_id}` - Get document details
- `GET /api/v1/documents/` - List all documents
- `POST /api/v1/verification/process/{document_id}` - Start processing
- `POST /api/v1/verification/review/{document_id}` - Manual review action

## Project Structure

```
backend/
├── app/
│   ├── api/v1/          # API endpoints
│   ├── core/             # Configuration
│   ├── db/               # Database models and connection
│   └── services/         # Business logic (OCR, Forensic, Scoring)
├── migrations/           # SQL migration scripts
├── requirements.txt      # Python dependencies
├── ENV_EXAMPLE.txt      # Environment variables template
└── run.py               # Application entry point
```

## Requirements

- Python 3.11 or 3.12 (3.13 has compatibility issues)
- PostgreSQL database
- Poppler (for PDF processing - only needed for PDF fallback conversion)
- AWS Textract (for OCR - primary method)

