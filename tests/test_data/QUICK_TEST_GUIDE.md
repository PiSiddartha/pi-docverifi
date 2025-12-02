# Quick Test Guide - VAT & Director Verification

## Prerequisites

1. Backend server running on `http://localhost:8000`
2. Frontend running (optional, can use API directly)
3. Test documents generated (see below)

## Generate Test Documents

### Option 1: Using Python (Recommended)

```bash
cd backend/tests/test_data
pip install reportlab
python create_test_documents.py
```

This creates PDFs in `generated_documents/` directory.

### Option 2: Using Simple Script

```bash
cd backend/tests/test_data
./generate_simple_test_docs.sh
# Then convert .txt files to PDF using any tool
```

## Test VAT Registration

### Test Case 1: Standard VAT Registration

**Document**: `vat_registration_01_123456789.pdf`

**Upload via API**:
```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -F "file=@backend/tests/test_data/generated_documents/vat_registration_01_123456789.pdf" \
  -F "document_type=vat_registration" \
  -F "vat_number=GB123456789" \
  -F "business_name=ACME TRADING LIMITED"
```

**Upload via Frontend**:
1. Select "VAT Registration" document type
2. Enter VAT Number: `GB123456789`
3. Enter Business Name: `ACME TRADING LIMITED`
4. Upload the PDF
5. Monitor progress

**Expected Results**:
- OCR extracts: VAT number, business name, address
- HMRC API verification (if OAuth configured)
- Scores calculated: OCR, Registry, Provided, Final
- Status: `passed`, `review`, or `failed` based on scores

### Test Case 2: VAT Number Normalization

Test that VAT numbers are normalized correctly:
- `123456789` → `GB123456789`
- `GB 123 456 789` → `GB123456789`

## Test Director Verification

### Test Case 1: Standard Director Verification

**Document**: `director_verification_01_12345678.pdf`

**Upload via API**:
```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -F "file=@backend/tests/test_data/generated_documents/director_verification_01_12345678.pdf" \
  -F "document_type=director_verification" \
  -F "director_name=JOHN MICHAEL SMITH" \
  -F "director_dob=1975-05-15" \
  -F "company_name=TECHNOLOGY SOLUTIONS LIMITED" \
  -F "company_number=12345678"
```

**Upload via Frontend**:
1. Select "Director Verification" document type
2. Enter Director Name: `JOHN MICHAEL SMITH`
3. Enter Date of Birth: `1975-05-15`
4. Enter Company Name: `TECHNOLOGY SOLUTIONS LIMITED`
5. Enter Company Number: `12345678`
6. Upload the PDF
7. Monitor progress

**Expected Results**:
- OCR extracts: director name, DOB, address, company details
- Companies House API verification
- Scores calculated: OCR, Registry, Provided, Final
- Status: `passed`, `review`, or `failed` based on scores

### Test Case 2: Director Name Variations

Test fuzzy matching with name variations:
- `JOHN M SMITH` vs `JOHN MICHAEL SMITH`
- `J. M. SMITH` vs `JOHN MICHAEL SMITH`

## Verify Results

### Check Document Status

```bash
# Get document details
curl "http://localhost:8000/api/v1/documents/{document_id}"

# List all documents
curl "http://localhost:8000/api/v1/documents/?limit=10"
```

### Check Progress

```bash
# Get current progress
curl "http://localhost:8000/api/v1/progress/progress/{document_id}/current"
```

## Troubleshooting

### OCR Not Extracting Data

- Check PDF quality (should be text-based, not scanned image)
- Verify Textract is configured correctly
- Check logs for OCR errors

### API Verification Failing

**HMRC VAT API**:
- Verify OAuth credentials are set: `HMRC_CLIENT_ID`, `HMRC_CLIENT_SECRET`
- Check OAuth token is being obtained (check logs)
- Verify VAT number format is correct

**Companies House API**:
- Verify API key is set: `COMPANIES_HOUSE_API_KEY`
- Check API key is valid
- Verify company number format

### Low Scores

- Check OCR confidence scores
- Verify merchant-provided data matches OCR data
- Check API verification results
- Review forensic analysis scores

## Test Data Files

All test data is in JSON format:
- `vat_registration_samples.json` - VAT test cases
- `director_verification_samples.json` - Director test cases

Each file contains:
- Sample documents with expected OCR text
- Test scenarios for different edge cases
- Expected results for validation

## Next Steps

1. Generate test documents
2. Upload via frontend or API
3. Monitor verification progress
4. Review scores and results
5. Adjust test data as needed

For more details, see `README.md` in this directory.

