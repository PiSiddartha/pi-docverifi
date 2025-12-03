# Document Verification System (PI DocVerifi) - Complete Documentation

## Table of Contents
1. [Project Overview](#project-overview)
2. [System Architecture](#system-architecture)
3. [Document Types and Processing](#document-types-and-processing)
4. [APIs and External Services](#apis-and-external-services)
5. [Technical Stack](#technical-stack)
6. [Workflow and Processing Pipeline](#workflow-and-processing-pipeline)
7. [Scoring System](#scoring-system)
8. [Forensic Analysis](#forensic-analysis)
9. [Database Schema](#database-schema)
10. [API Endpoints](#api-endpoints)
11. [Frontend Architecture](#frontend-architecture)

---

## Project Overview

**PI DocVerifi** is an industry-standard document verification system designed to authenticate and verify UK business documents. The system uses advanced OCR, forensic analysis, and real-time API verification to ensure document authenticity and accuracy.

### Key Features
- **Multi-Document Type Support**: Handles 4 different document types with specialized processing
- **AWS Textract OCR**: High-accuracy text extraction with automatic fallback
- **Advanced Forensic Analysis**: 10+ industry-standard checks for document tampering detection
- **Real-Time API Verification**: Integration with Companies House and HMRC VAT APIs
- **Intelligent Field Extraction**: LLM-powered extraction with regex fallback
- **Comprehensive Scoring System**: Multi-factor scoring (0-100) with decision logic
- **Manual Review Workflow**: Review interface for documents requiring human verification
- **Real-Time Progress Tracking**: Server-Sent Events (SSE) for live progress updates
- **Modern UI**: Next.js frontend with Tailwind CSS

---

## System Architecture

### High-Level Architecture

```
┌─────────────────┐
│   Frontend      │  Next.js 14 + TypeScript + Tailwind CSS
│   (Port 3000)   │
└────────┬────────┘
         │ HTTP/REST API
         │
┌────────▼────────┐
│   Backend API   │  FastAPI (Port 8000)
│                 │
│  ┌───────────┐ │
│  │ Documents │ │  Document Upload & Management
│  └───────────┘ │
│  ┌───────────┐ │
│  │Verification│ │  Processing Pipeline
│  └───────────┘ │
│  ┌───────────┐ │
│  │  Progress │ │  Real-Time Updates (SSE)
│  └───────────┘ │
└────────┬────────┘
         │
    ┌────┴────┬──────────┬──────────────┐
    │         │          │              │
┌───▼───┐ ┌──▼───┐ ┌───▼───┐ ┌────────▼─────┐
│PostgreSQL│ │ AWS S3 │ │ AWS Textract│ │ Companies House│
│Database  │ │Storage │ │    OCR      │ │      API       │
└─────────┘ └───────┘ └──────────────┘ └────────────────┘
                                              │
                                         ┌────▼────┐
                                         │ HMRC VAT│
                                         │   API   │
                                         └─────────┘
```

### Component Breakdown

#### Backend Services
1. **OCR Service** (`ocr_service.py`)
   - AWS Textract integration
   - PDF to image conversion fallback
   - Parallel processing for multi-page documents

2. **Forensic Service** (`forensic_service.py`)
   - EXIF data analysis
   - Error Level Analysis (ELA)
   - Copy-move forgery detection
   - JPEG quality analysis
   - PDF metadata analysis
   - Resolution consistency checks
   - Color histogram analysis
   - Noise pattern analysis
   - File hash verification

3. **LLM Service** (`llm_service.py`)
   - OpenAI GPT-5 nano integration
   - Structured field extraction
   - Fallback to regex patterns

4. **Companies House Service** (`companies_house_service.py`)
   - Company profile lookup
   - Officer/director verification
   - Company search

5. **HMRC VAT Service** (`hmrc_vat_service.py`)
   - OAuth 2.0 authentication
   - VAT number verification
   - Business information lookup

6. **Scoring Service** (`scoring_service.py`)
   - Multi-factor scoring calculation
   - Decision logic (PASS/FAIL/REVIEW)

7. **Pipeline Service** (`pipeline_service.py`)
   - Type-specific processing pipelines
   - Progress tracking integration

---

## Document Types and Processing

The system supports **4 distinct document types**, each with specialized processing:

### 1. Companies House Documents (`companies_house`)
**Purpose**: Verify UK Companies House incorporation certificates

**Fields Extracted**:
- Company Name
- Company Number (6-8 digits, may include letters like SC)
- Registered Office Address
- Date of Incorporation

**Processing Steps**:
1. OCR extraction using AWS Textract
2. LLM field extraction (company_name, company_number, address)
3. Forensic analysis
4. Companies House API lookup using extracted company number
5. Scoring: OCR (0-30) + Registry (0-40) + Provided (0-30) + OCR Comparison (0-30) - Forensic Penalty (0-15)

**API Used**: Companies House API (`https://api.companieshouse.gov.uk`)

**Database Table**: `companies_house_documents`

---

### 2. Company Registration Documents (`company_registration`)
**Purpose**: Verify company registration certificates (similar to Companies House but may have different formats)

**Fields Extracted**: Same as Companies House documents

**Processing Steps**: Identical to Companies House pipeline

**API Used**: Companies House API

**Database Table**: `company_registration_documents`

**Note**: This type uses the same verification logic as Companies House but is stored separately for organizational purposes.

---

### 3. VAT Registration Documents (`vat_registration`)
**Purpose**: Verify UK VAT registration certificates

**Fields Extracted**:
- VAT Number (GB + 9 digits)
- Business Name
- Registered Business Address
- VAT Registration Date

**Processing Steps**:
1. OCR extraction using AWS Textract
2. LLM field extraction (vat_number, business_name, address, registration_date)
3. Forensic analysis
4. HMRC VAT API lookup using extracted VAT number
5. Scoring: OCR (0-40) + Registry (0-30) + Provided (0-30) - Forensic Penalty (0-15)

**API Used**: HMRC VAT API (`https://api.service.hmrc.gov.uk`)

**Authentication**: OAuth 2.0 Client Credentials Flow

**Database Table**: `vat_registration_documents`

---

### 4. Director Verification Documents (`director_verification`)
**Purpose**: Verify director appointment documents

**Fields Extracted**:
- Director Name (Full name)
- Date of Birth
- Residential Address
- Company Name (where director is appointed)
- Company Number (optional, extracted if present)
- Appointment Date

**Processing Steps**:
1. OCR extraction using AWS Textract
2. LLM field extraction (director_name, date_of_birth, address, company_name, company_number, appointment_date)
3. Forensic analysis
4. Companies House Director Verification API lookup
   - Uses company number (from merchant input, OCR LLM extraction, or regex fallback)
   - Verifies director name and DOB against Companies House records
5. Scoring: OCR (0-40) + Registry (0-30) + Provided (0-30) - Forensic Penalty (0-15)

**API Used**: Companies House API (Officers endpoint)

**Database Table**: `director_verification_documents`

---

## APIs and External Services

### 1. AWS Textract (OCR Service)

**Purpose**: Extract text from PDFs and images

**How It's Used**:
- **Synchronous API** (`detect_document_text`): For files ≤ 5MB
  - Direct PDF processing
  - Returns text blocks with confidence scores
- **Asynchronous API** (`start_document_text_detection`): For files > 5MB
  - Requires S3 upload
  - Polls for job completion
  - Handles multi-page documents

**Fallback Mechanism**:
- If Textract rejects PDF format (`UnsupportedDocumentException`):
  1. Convert PDF to images using `pdf2image` (200 DPI, JPEG format)
  2. Process images in parallel (up to 5 concurrent calls)
  3. Combine results maintaining page order

**Performance Optimizations**:
- Parallel image processing (ThreadPoolExecutor, max 5 workers)
- Lower DPI (200 instead of 300) for faster conversion
- JPEG format instead of PNG (3x faster saves)
- Immediate cleanup of temp files

**Configuration**:
- AWS credentials: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
- Region: `AWS_REGION` (default: `us-east-1`)
- S3 bucket: `S3_BUCKET_NAME` (required for async processing)

**Code Location**: `backend/app/services/ocr_service.py`

---

### 2. Companies House API

**Purpose**: Verify UK company information and director details

**Base URL**: `https://api.companieshouse.gov.uk`

**Authentication**: HTTP Basic Auth (API Key)

**Endpoints Used**:

1. **Company Profile** (`GET /company/{company_number}`)
   - Retrieves company name, number, registered address, date of creation
   - Used in: Companies House, Company Registration, Director Verification pipelines

2. **Company Officers** (`GET /company/{company_number}/officers`)
   - Retrieves list of company officers/directors
   - Used in: Director Verification pipeline
   - Includes: name, DOB, appointment date, address

3. **Company Search** (`GET /search/companies`)
   - Search companies by name
   - Used for: Fallback company lookup

**Company Number Normalization**:
- Handles 6-digit (640918 → 00640918), 7-digit (3035678 → 03035678), and 8-digit formats
- Supports 2 letters + 6 digits format (SC555555)
- Automatic padding with leading zeros

**Configuration**:
- API Key: `COMPANIES_HOUSE_API_KEY`

**Code Location**: `backend/app/services/companies_house_service.py`

**Usage Examples**:
```python
# Get company profile
service = CompaniesHouseService()
company_data = service.extract_company_data("01234567")

# Verify director
verification = service.verify_director(
    director_name="John Smith",
    company_number="01234567",
    date_of_birth="1980-01-01"
)
```

---

### 3. HMRC VAT API

**Purpose**: Verify UK VAT registration numbers

**Base URL**: `https://api.service.hmrc.gov.uk`

**Authentication**: OAuth 2.0 Client Credentials Flow

**OAuth Flow**:
1. Request access token using client credentials
2. Token cached and refreshed 5 minutes before expiry
3. Use Bearer token for API requests

**Endpoints Used**:

1. **OAuth Token** (`POST /oauth/token`)
   - Grants: `client_credentials`
   - Scope: `read:vat`
   - Returns: `access_token`, `expires_in`

2. **VAT Verification** (`GET /organisations/vat/check-vat-number/{vat_number}`)
   - Verifies VAT number (9 digits, GB prefix removed for API call)
   - Returns: business name, address, registration date

**VAT Number Normalization**:
- Handles formats: `GB123456789`, `123456789`, `GB 123 456 789`
- Normalizes to: `GB123456789` (GB + 9 digits)

**Configuration**:
- Client ID: `HMRC_CLIENT_ID`
- Client Secret: `HMRC_CLIENT_SECRET`
- Server Token (fallback): `HMRC_SERVER_TOKEN`
- Use OAuth: `HMRC_USE_OAUTH` (default: `True`)

**Code Location**: `backend/app/services/hmrc_vat_service.py`

**Usage Example**:
```python
service = HMRCVATService()
vat_data = service.extract_vat_data("GB123456789")
# Returns: vat_number, business_name, address, registration_date
```

---

### 4. OpenAI API (LLM Service)

**Purpose**: Extract structured fields from OCR text

**Model**: GPT-5 nano (configurable via `OPENAI_MODEL`)

**How It's Used**:
- **Structured Outputs**: Uses Pydantic models for type-safe extraction
- **Field Extraction**:
  - Company fields: `company_name`, `company_number`, `address`
  - VAT fields: `vat_number`, `business_name`, `address`, `registration_date`
  - Director fields: `director_name`, `date_of_birth`, `address`, `company_name`, `company_number`, `appointment_date`

**Text Truncation Strategy**:
- For long documents: Keep first 2000 chars (header) + last 1000 chars (footer)
- Reduces token usage while preserving key information

**Fallback Mechanism**:
- If LLM fails or unavailable: Falls back to regex-based extraction
- Regex patterns match common document formats

**Configuration**:
- API Key: `OPENAI_API_KEY`
- Model: `OPENAI_MODEL` (default: `gpt-5-nano`)

**Code Location**: `backend/app/services/llm_service.py`

**Usage Example**:
```python
# Extract company fields
fields = LLMService.extract_company_fields(raw_ocr_text)
# Returns: {"company_name": "...", "company_number": "...", "address": "..."}

# Extract VAT fields
vat_fields = LLMService.extract_vat_fields(raw_ocr_text)

# Extract director fields
director_fields = LLMService.extract_director_fields(raw_ocr_text)
```

---

### 5. AWS S3 (Optional)

**Purpose**: Document storage and async Textract processing

**How It's Used**:
- **Document Storage**: Backup/archive of uploaded documents
- **Textract Async**: Required for files > 5MB
- **Temporary Storage**: For Textract async jobs (auto-deleted after processing)

**Configuration**:
- Bucket Name: `S3_BUCKET_NAME`
- Region: `AWS_REGION`
- Credentials: Same as Textract

**Code Location**: `backend/app/services/s3_service.py`

---

## Technical Stack

### Backend
- **Framework**: FastAPI 0.109.0
- **Language**: Python 3.11/3.12
- **Database**: PostgreSQL (SQLAlchemy ORM)
- **OCR**: AWS Textract (primary), pdf2image (fallback)
- **Forensic Analysis**: OpenCV, scikit-image, pypdf, exifread
- **LLM**: OpenAI API (GPT-5 nano)
- **Task Queue**: BackgroundTasks (default), SQS (optional)
- **Progress Tracking**: Server-Sent Events (SSE)

### Frontend
- **Framework**: Next.js 14
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **HTTP Client**: Axios
- **File Upload**: React Dropzone
- **Charts**: Recharts

### Infrastructure
- **Database**: PostgreSQL
- **Storage**: AWS S3 (optional)
- **Queue**: AWS SQS (optional)
- **Deployment**: Lambda-compatible (Mangum adapter)

---

## Workflow and Processing Pipeline

### Document Upload Flow

```
1. User uploads document via frontend
   ↓
2. Backend receives file + metadata (document_type, merchant data)
   ↓
3. File saved locally (required) + S3 (optional)
   ↓
4. Database records created:
   - Base document (documents table)
   - Type-specific document (companies_house_documents, etc.)
   ↓
5. Background task started (SQS or BackgroundTasks)
   ↓
6. Processing pipeline begins
```

### Processing Pipeline (Type-Specific)

#### Companies House / Company Registration Pipeline

```
Step 1: OCR Extraction (20% progress)
├── AWS Textract extracts raw text
├── LLM extracts structured fields (company_name, company_number, address)
└── Store OCR data in type_doc

Step 2: Forensic Analysis (50% progress)
├── EXIF data extraction
├── ELA score calculation
├── Copy-move detection
├── JPEG quality analysis
├── PDF metadata analysis
├── Resolution consistency check
├── Color histogram analysis
├── Noise pattern analysis
└── File hash calculation
└── Store forensic data in base_doc

Step 3: Companies House API Lookup (70% progress)
├── Normalize company number (6/7/8 digits → 8 digits)
├── Call Companies House API
├── Retrieve company profile + officers
└── Store API data in type_doc

Step 4: Scoring (90% progress)
├── OCR Score (0-30): Based on Textract confidence
├── Registry Score (0-40): Company number match
├── OCR Comparison Score (0-30): OCR vs Companies House (name, number, address)
├── Provided Score (0-30): Merchant data vs Companies House
├── Forensic Penalty (0-15): Deducted for suspicious findings
├── Final Score: OCR + Registry + OCR Comparison + Provided - Forensic
└── Decision: PASS (≥75), REVIEW (50-74), FAIL (<50)

Step 5: Status Update (100% progress)
├── Update base_doc.status: passed/failed/review
├── Update base_doc.decision: PASS/FAIL/REVIEW
└── Set processed_at timestamp
```

#### VAT Registration Pipeline

```
Step 1: OCR Extraction (20% progress)
├── AWS Textract extracts raw text
├── LLM extracts VAT fields (vat_number, business_name, address, registration_date)
└── Store OCR data in type_doc

Step 2: Forensic Analysis (50% progress)
└── Same as Companies House pipeline

Step 3: HMRC VAT API Lookup (70% progress)
├── Normalize VAT number (GB + 9 digits)
├── Get OAuth token (if not cached)
├── Call HMRC VAT API
└── Store API data in type_doc

Step 4: Scoring (90% progress)
├── OCR Score (0-40): Based on confidence + fields extracted
├── Registry Score (0-30): VAT verification + business name match
├── Provided Score (0-30): Merchant data vs HMRC
├── Forensic Penalty (0-15)
└── Final Score: OCR + Registry + Provided - Forensic

Step 5: Status Update (100% progress)
└── Same as Companies House pipeline
```

#### Director Verification Pipeline

```
Step 1: OCR Extraction (20% progress)
├── AWS Textract extracts raw text
├── LLM extracts director fields (director_name, DOB, address, company_name, company_number, appointment_date)
└── Store OCR data in type_doc

Step 2: Forensic Analysis (50% progress)
└── Same as Companies House pipeline

Step 3: Companies House Director Verification (70% progress)
├── Get company number from:
│   ├── Merchant input (priority 1)
│   ├── OCR LLM extraction (priority 2)
│   └── OCR regex extraction (priority 3)
├── Normalize company number
├── Call Companies House Officers API
├── Match director name + DOB
└── Store verification data in type_doc

Step 4: Scoring (90% progress)
├── OCR Score (0-40): Based on confidence + fields extracted
├── Registry Score (0-30): Director verification + details match
├── Provided Score (0-30): Merchant data vs Companies House
├── Forensic Penalty (0-15)
└── Final Score: OCR + Registry + Provided - Forensic

Step 5: Status Update (100% progress)
└── Same as Companies House pipeline
```

### Progress Tracking

**Real-Time Updates via Server-Sent Events (SSE)**:
- Endpoint: `GET /api/v1/progress/progress/{document_id}`
- Updates include: `step`, `progress` (0-100), `message`, `status`
- Frontend subscribes to progress stream
- Connection closes when status is terminal (passed/failed/review)

**Progress Service**: `backend/app/services/progress_service.py`

---

## Scoring System

### Scoring Components

#### 1. OCR Score (0-30 or 0-40)
**Purpose**: Measures OCR extraction quality

**Calculation**:
- **Companies House/Company Registration**: `(Textract Confidence / 100) * 30`
- **VAT/Director**: `(Textract Confidence / 100) * 40 + Field Bonus`
  - Field Bonus: Up to 5 points based on number of fields extracted

**Factors**:
- AWS Textract confidence score (0-100)
- Number of fields successfully extracted

---

#### 2. Registry Score (0-40 or 0-30)
**Purpose**: Measures match between extracted data and official registry

**Companies House/Company Registration (0-40)**:
- **Company Number Match**: Exact match = 40 points
- **Partial Match**: Similarity ratio * 40 points
- Normalizes company numbers before comparison (handles 6/7/8 digit formats)

**VAT Registration (0-30)**:
- **VAT Verification**: Verified = 20 points
- **Business Name Match**: Similarity * 10 additional points

**Director Verification (0-30)**:
- **Director Verified**: Verified in Companies House = 20 points
- **Name Match**: Similarity * 5 additional points
- **DOB Match**: Similarity * 5 additional points

---

#### 3. OCR Comparison Score (0-30) - Companies House/Company Registration Only
**Purpose**: Compares OCR-extracted fields with Companies House data

**Calculation**:
- **Company Name** (50% weight): Strict validation (similarity < 0.98 applies penalties)
- **Company Number** (30% weight): Normalized comparison
- **Address** (20% weight): Lenient validation (addresses can change over time)

**Strict Name Validation**:
- Similarity < 0.90: Severe penalty (capped score)
- Similarity < 0.98: Moderate penalty
- Similarity ≥ 0.98: Full score

**Lenient Address Validation**:
- Similarity < 0.3: Moderate penalty
- Similarity < 0.5: Small penalty
- Similarity ≥ 0.5: Full score (addresses can change)

---

#### 4. Provided Score (0-30)
**Purpose**: Measures accuracy of merchant-provided data vs official registry

**Companies House/Company Registration**:
- **Company Name** (40% weight): Similarity * 0.4 * 30
- **Company Number** (40% weight): Similarity * 0.4 * 30
- **Address** (20% weight): Similarity * 0.2 * 30

**VAT Registration**:
- **VAT Number** (50% weight): Similarity * 15
- **Business Name** (50% weight): Similarity * 15

**Director Verification**:
- **Director Name** (50% weight): Similarity * 15
- **DOB** (50% weight): Similarity * 15

---

#### 5. Forensic Penalty (0-15)
**Purpose**: Deducts points for suspicious forensic findings

**Penalty Calculation**:
- **High ELA Score** (>50): -5 points
- **Copy-Move Detection**:
  - High confidence (>40%): -7 points (regular docs) / -5 points (scanned docs)
  - Medium confidence (25-40%): -4 points (regular) / -3 points (scanned)
  - Low confidence (<25%): -2 points (regular) / -1.5 points (scanned)
- **Low JPEG Quality** (<30): -3 points
- **PDF Metadata Anomalies** (score <70): -2 points
- **Resolution Inconsistencies** (score <70): -2 points
- **Color Space Anomalies** (score <50): -1.5 points
- **Noise Pattern Inconsistencies** (score <70): -2 points

**Maximum Penalty**: 15 points (capped)

---

### Final Score Calculation

**Formula**:
```
Final Score = OCR Score + Registry Score + OCR Comparison Score + Provided Score - Forensic Penalty
```

**Score Ranges**:
- **Companies House/Company Registration**: 0-130 (30+40+30+30-15)
- **VAT Registration**: 0-100 (40+30+30-15)
- **Director Verification**: 0-100 (40+30+30-15)

**Note**: Final score is capped at 100.0

---

### Decision Logic

**Score-Based Decisions**:
- **PASS**: Final Score ≥ 75
- **REVIEW**: Final Score 50-74
- **FAIL**: Final Score < 50

**Hard Fail Conditions** (override score):
- **Company Name Mismatch**: If OCR company name similarity < 0.85 → FAIL
- **Company Name Low Similarity**: If OCR company name similarity < 0.90 → REVIEW

**Code Location**: `backend/app/services/scoring_service.py`

---

## Forensic Analysis

The system performs **10+ forensic checks** to detect document tampering:

### 1. EXIF Data Analysis
**Purpose**: Extract and analyze image metadata

**Checks**:
- Software used to create/modify document
- Creation/modification dates
- Camera/device information

**Implementation**: `exifread` library

---

### 2. Error Level Analysis (ELA)
**Purpose**: Detect re-saved JPEG artifacts

**How It Works**:
1. Save image at quality 90
2. Reload and compare with original
3. Calculate difference (higher = more suspicious)

**Score**: 0-100 (higher = more suspicious)
**Penalty**: Applied if score > 50

---

### 3. JPEG Quality Analysis
**Purpose**: Identify compression history inconsistencies

**How It Works**:
- Analyzes DCT coefficients
- Multiple saves reduce quality 
- Lower quality suggests editing

**Score**: 0-100 (lower = more suspicious)
**Penalty**: Applied if quality < 30

---

### 4. Copy-Move Forgery Detection
**Purpose**: Find duplicated regions (sign of tampering)

**How It Works**:
1. Divide image into blocks (32x32 pixels)
2. Compare blocks for similarity
3. High similarity = potential copy-move

**Optimizations**:
- Resize large images (max 2000px)
- Sample blocks (max 500 blocks)
- Context-aware thresholds (scanned docs have higher threshold)

**Confidence**: 0-100%
**Penalties**: Graduated based on confidence and document type

---

### 5. PDF Metadata Analysis
**Purpose**: Analyze PDF metadata for suspicious patterns

**Checks**:
- Creation date after modification date (suspicious)
- Suspicious software names (Photoshop, GIMP, etc.)
- Missing expected metadata
- Recent modification dates on old documents

**Score**: 0-100 (lower = more suspicious)
**Penalty**: Applied if score < 70

---

### 6. Resolution/DPI Consistency
**Purpose**: Detect upscaling and inconsistent resolution

**How It Works**:
1. Analyze different regions using FFT
2. Check for consistent high-frequency content
3. Low high-frequency energy = upscaling

**Detects**:
- Upscaling (low resolution → high resolution)
- Inconsistent resolution across regions

**Score**: 0-100 (lower = more suspicious)
**Penalty**: Applied if score < 70

---

### 7. Color Histogram Analysis
**Purpose**: Identify color space inconsistencies and editing artifacts

**How It Works**:
1. Analyze histograms for each color channel (BGR, HSV)
2. Check for unusual spikes (editing artifacts)
3. Check for gaps (missing color values)

**Grayscale-Aware**:
- More lenient for scanned/grayscale documents
- Skips H/S channels for grayscale images

**Score**: 0-100 (lower = more suspicious)
**Penalty**: Applied if score < 50 (very lenient)

---

### 8. Noise Pattern Analysis
**Purpose**: Detect inconsistent noise characteristics

**How It Works**:
1. Divide image into blocks
2. Calculate noise level (Laplacian variance) for each block
3. High variance = inconsistent regions (possible tampering)

**Score**: 0-100 (lower = more suspicious)
**Penalty**: Applied if score < 70

---

### 9. File Hash/Integrity Check
**Purpose**: Verify file integrity

**Calculates**:
- MD5 hash
- SHA256 hash
- File size

**Use Case**: Track document versions, detect modifications

---

### 10. Additional Checks
- **File Format Validation**: Ensures valid PDF/image format
- **PDF Encryption Check**: Detects password-protected PDFs
- **Image Format Support**: PNG, JPEG, TIFF, BMP

**Code Location**: `backend/app/services/forensic_service.py`

---

## Database Schema

### Base Table: `documents`
**Purpose**: Common fields for all document types

**Key Fields**:
- `document_id` (UUID, unique)
- `filename`, `file_path`, `s3_key`
- `document_type` (enum: companies_house, company_registration, vat_registration, director_verification)
- `status` (pending, processing, passed, failed, review, manual_review)
- `decision` (PASS, FAIL, REVIEW)
- `forensic_score`, `forensic_penalty`, `forensic_details`
- `exif_data`, `ela_score`, `jpeg_quality`, `copy_move_detected`
- `created_at`, `updated_at`, `processed_at`
- `reviewer_id`, `reviewer_action`, `reviewer_notes`
- `flags` (JSON)

---

### Type-Specific Tables

#### `companies_house_documents`
**Fields**:
- Merchant data: `merchant_company_name`, `merchant_company_number`, `merchant_address`, `merchant_date`
- OCR data: `ocr_company_name`, `ocr_company_number`, `ocr_address`, `ocr_date`, `ocr_confidence`, `ocr_raw_text`
- Companies House API: `companies_house_company_name`, `companies_house_company_number`, `companies_house_address`, `companies_house_date`, `companies_house_officers`, `companies_house_data`
- Scores: `ocr_score`, `registry_score`, `provided_score`, `data_match_score`, `final_score`
- Comparison: `registry_match_score`, `registry_data`, `comparison_details`, `provided_data_accuracy`

---

#### `company_registration_documents`
**Fields**: Same structure as `companies_house_documents`

---

#### `vat_registration_documents`
**Fields**:
- Merchant data: `merchant_vat_number`, `merchant_business_name`, `merchant_address`
- OCR data: `ocr_vat_number`, `ocr_business_name`, `ocr_vat_address`, `ocr_vat_registration_date`, `ocr_confidence`, `ocr_raw_text`
- HMRC API: `hmrc_vat_number`, `hmrc_business_name`, `hmrc_address`, `hmrc_registration_date`, `hmrc_vat_data`
- Scores: `ocr_score`, `registry_score`, `provided_score`, `data_match_score`, `final_score`
- Comparison: `comparison_details`

---

#### `director_verification_documents`
**Fields**:
- Merchant data: `merchant_director_name`, `merchant_director_dob`, `merchant_company_name`, `merchant_company_number`
- OCR data: `ocr_director_name`, `ocr_director_dob`, `ocr_director_address`, `ocr_director_company_name`, `ocr_appointment_date`, `ocr_confidence`, `ocr_raw_text`
- Companies House API: `companies_house_director_name`, `companies_house_director_dob`, `companies_house_director_address`, `companies_house_appointment_date`, `companies_house_director_data`, `companies_house_company_name`, `companies_house_company_number`
- Scores: `ocr_score`, `registry_score`, `provided_score`, `data_match_score`, `final_score`
- Comparison: `comparison_details` (stores OCR-extracted company_number)

---

### Audit Table: `audit_logs`
**Purpose**: Track document actions

**Fields**:
- `document_id`, `action`, `details` (JSON), `user_id`, `created_at`

**Code Location**: `backend/app/db/models.py`

---

## API Endpoints

### Document Management

#### `POST /api/v1/documents/upload`
**Purpose**: Upload document for verification

**Request**:
- `file`: PDF/image file (multipart/form-data)
- `document_type`: companies_house | company_registration | vat_registration | director_verification
- `company_name`, `company_number`, `address`, `date` (optional, for Companies House/Registration)
- `vat_number`, `business_name` (optional, for VAT)
- `director_name`, `director_dob` (optional, for Director Verification)

**Response**:
```json
{
  "document_id": "uuid",
  "status": "uploaded",
  "message": "Document uploaded successfully. Processing has started."
}
```

**Auto-Processing**: Starts background task automatically

---

#### `GET /api/v1/documents/{document_id}`
**Purpose**: Get document verification details

**Response**: Complete document data including:
- OCR extracted data
- Registry API data (Companies House/HMRC)
- Forensic analysis results
- Score breakdown
- Decision

---

#### `GET /api/v1/documents/`
**Purpose**: List all documents with pagination

**Query Parameters**:
- `skip`: Offset (default: 0)
- `limit`: Page size (default: 100)
- `status`: Filter by status (optional)

**Response**:
```json
{
  "total": 100,
  "documents": [
    {
      "document_id": "uuid",
      "filename": "document.pdf",
      "document_type": "companies_house",
      "status": "passed",
      "final_score": 85.5,
      "decision": "PASS",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

---

### Verification

#### `POST /api/v1/verification/process/{document_id}`
**Purpose**: Manually trigger document processing

**Response**:
```json
{
  "document_id": "uuid",
  "status": "processing",
  "message": "Verification process started"
}
```

**Note**: Usually not needed (upload auto-starts processing)

---

#### `POST /api/v1/verification/review/{document_id}`
**Purpose**: Manual review action

**Query Parameters**:
- `action`: APPROVE | REJECT | ESCALATE
- `reviewer_notes`: Optional notes
- `reviewer_id`: Optional reviewer ID

**Response**:
```json
{
  "document_id": "uuid",
  "action": "APPROVE",
  "status": "passed",
  "message": "Review action 'APPROVE' applied"
}
```

---

### Progress Tracking

#### `GET /api/v1/progress/progress/{document_id}`
**Purpose**: Real-time progress updates (Server-Sent Events)

**Response**: SSE stream with progress updates:
```
data: {"document_id": "uuid", "step": "ocr_extraction", "progress": 20, "message": "Extracting text...", "status": "processing", "timestamp": "2024-01-01T00:00:00Z"}

data: {"document_id": "uuid", "step": "forensic_analysis", "progress": 50, "message": "Analyzing document...", "status": "processing", "timestamp": "2024-01-01T00:00:01Z"}
```

**Connection Closes**: When status is terminal (passed/failed/review)

---

#### `GET /api/v1/progress/progress/{document_id}/current`
**Purpose**: Get current progress (one-time fetch)

**Response**:
```json
{
  "document_id": "uuid",
  "step": "score_calculation",
  "progress": 90,
  "message": "Calculating final scores...",
  "status": "processing",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

---

## Frontend Architecture

### Technology Stack
- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **HTTP Client**: Axios
- **File Upload**: React Dropzone
- **Charts**: Recharts

### Key Components

#### `DocumentUpload.tsx`
**Purpose**: Document upload interface

**Features**:
- Drag-and-drop file upload
- Document type selection
- Dynamic form fields based on document type
- Real-time upload progress

---

#### `DocumentList.tsx`
**Purpose**: List all documents

**Features**:
- Pagination
- Status filtering
- Sort by date
- Quick view of scores and decisions

---

#### `DocumentDetail.tsx`
**Purpose**: Detailed document view

**Features**:
- Complete verification results
- OCR vs Registry comparison
- Forensic analysis details
- Score breakdown visualization
- Manual review interface (for REVIEW status)

---

#### `ProgressBar.tsx`
**Purpose**: Real-time progress indicator

**Features**:
- SSE connection to progress endpoint
- Visual progress bar (0-100%)
- Step-by-step status messages
- Auto-updates during processing

---

### API Client

**Location**: `frontend/lib/api.ts`

**Functions**:
- `uploadDocument()`: Upload document with metadata
- `getDocument()`: Fetch document details
- `listDocuments()`: List documents with pagination
- `processVerification()`: Trigger processing
- `manualReview()`: Submit review action
- `getCurrentProgress()`: Get progress (one-time)

---

## Configuration

### Backend Environment Variables

```env
# Database
DATABASE_URL=postgresql://user:password@host:5432/dbname

# Companies House API
COMPANIES_HOUSE_API_KEY=your_api_key

# HMRC VAT API (OAuth)
HMRC_CLIENT_ID=your_client_id
HMRC_CLIENT_SECRET=your_client_secret
HMRC_USE_OAUTH=true

# AWS (Textract + S3)
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1
S3_BUCKET_NAME=your-bucket-name

# OpenAI (LLM)
OPENAI_API_KEY=your_openai_key
OPENAI_MODEL=gpt-5-nano

# Application
ENVIRONMENT=development
CORS_ORIGINS=http://localhost:3000
MAX_UPLOAD_SIZE=10485760  # 10MB

# Optional: SQS Queue
SQS_QUEUE_URL=https://sqs.region.amazonaws.com/account/queue
USE_SQS=false
```

### Frontend Environment Variables

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Performance Optimizations

### OCR Processing
1. **Parallel Image Processing**: Up to 5 concurrent Textract calls
2. **Optimized PDF Conversion**: 200 DPI, JPEG format, parallel page conversion
3. **Smart Fallback**: Automatic detection and fast fallback when Textract rejects PDF
4. **Immediate Cleanup**: Temp files deleted immediately after processing

**Expected Performance**:
- Multi-page PDFs with image conversion: ~6-12 seconds
- Direct Textract processing: ~2-5 seconds per document

### Forensic Analysis
1. **Image Resizing**: Large images resized to max 2000px for faster processing
2. **Block Sampling**: Limits blocks checked for copy-move detection (max 500)
3. **Grayscale Detection**: Skips unnecessary color analysis for scanned documents

### Database
1. **Separate Tables**: Type-specific tables reduce query complexity
2. **Indexes**: On `document_id`, `document_type`, `status`
3. **JSON Fields**: Efficient storage of complex data (forensic_details, comparison_details)

---

## Error Handling

### OCR Errors
- **Unsupported PDF Format**: Automatic fallback to image conversion
- **File Size Exceeded**: Falls back to async processing (requires S3)
- **Textract API Errors**: Logged with helpful error messages

### API Errors
- **Companies House API**: Returns None if company not found
- **HMRC VAT API**: Handles OAuth token refresh automatically
- **OpenAI API**: Falls back to regex extraction on failure

### Processing Errors
- **Pipeline Failures**: Document status set to "failed"
- **Database Errors**: Rollback and error logging
- **Progress Updates**: Errors don't break main processing

---

## Security Considerations

1. **File Upload Validation**: File size limits, type validation
2. **API Key Management**: Environment variables, never hardcoded
3. **OAuth Token Caching**: Secure token storage and refresh
4. **Database Security**: Parameterized queries (SQLAlchemy ORM)
5. **CORS Configuration**: Configurable allowed origins

---

## Future Enhancements

1. **Additional Document Types**: Bank statements, utility bills, etc.
2. **Multi-Language Support**: Non-UK document verification
3. **Advanced ML Models**: Custom fraud detection models
4. **Batch Processing**: Process multiple documents at once
5. **Webhook Support**: Notify external systems on completion
6. **Enhanced Reporting**: Analytics dashboard, fraud trends

---

## Conclusion

PI DocVerifi is a comprehensive document verification system that combines:
- **Advanced OCR** (AWS Textract with intelligent fallback)
- **Forensic Analysis** (10+ industry-standard checks)
- **Real-Time API Verification** (Companies House, HMRC VAT)
- **LLM-Powered Extraction** (OpenAI GPT-5 nano with structured outputs)
- **Comprehensive Scoring** (Multi-factor scoring with decision logic)
- **Modern UI** (Next.js with real-time progress tracking)

The system is production-ready, scalable, and designed for high accuracy and performance.

---

**Last Updated**: 2024
**Version**: 1.0.0

