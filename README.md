# Document Verification System

Industry-standard document verification system with OCR, forensic analysis, and Companies House API integration.

## Features

- **OCR Extraction**: Extract text and structured data from PDFs using Tesseract
- **Forensic Analysis**: Detect document tampering using EXIF, ELA, JPEG quality analysis, and copy-move detection
- **Companies House Integration**: Verify company data against UK Companies House API
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

4. Install system dependencies (for OCR):
```bash
# macOS
brew install tesseract poppler

# Ubuntu/Debian
sudo apt-get install tesseract-ocr poppler-utils

# Windows
# Download and install from:
# - Tesseract: https://github.com/UB-Mannheim/tesseract/wiki
# - Poppler: https://github.com/oschwartz10612/poppler-windows/releases
```

5. Create `.env` file:
```bash
cp .env.example .env
```

6. Update `.env` with your configuration:
```env
DATABASE_URL=postgresql://user:password@localhost:5432/docverifi_db
COMPANIES_HOUSE_API_KEY=your_api_key_here
```

7. Create database:
```bash
# Using PostgreSQL
createdb docverifi_db
```

8. Run migrations (if using Alembic):
```bash
alembic upgrade head
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

- **OCR Score (0-30)**: Based on OCR confidence
- **Registry Score (0-40)**: Match between OCR company number and Companies House
- **Provided Score (0-30)**: Accuracy of merchant-provided data vs Companies House
- **Forensic Penalty (0-15)**: Deducted for suspicious forensic findings
- **Final Score**: OCR + Registry + Provided - Forensic Penalty

### Decision Thresholds
- **PASS**: Score ≥ 75
- **REVIEW**: Score 50-74
- **FAIL**: Score < 50

## Technologies

### Backend
- FastAPI (Python web framework)
- SQLAlchemy (ORM)
- PostgreSQL (Database)
- Tesseract (OCR)
- OpenCV, scikit-image (Forensic analysis)
- Companies House API

### Frontend
- Next.js 14 (React framework)
- TypeScript
- Tailwind CSS
- Axios (HTTP client)
- React Dropzone (File upload)

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

1. Set `ENVIRONMENT=production` in backend `.env`
2. Configure proper database and S3 credentials
3. Build frontend: `npm run build`
4. Use production WSGI server (e.g., Gunicorn) for backend
5. Deploy frontend to Vercel, Netlify, or similar

## License

MIT

