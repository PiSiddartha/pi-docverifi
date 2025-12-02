# Test Data for Document Verification

This directory contains test datasets and sample documents for testing VAT Registration and Director Verification pipelines.

## Files

- `vat_registration_samples.json` - Sample VAT registration data and test scenarios
- `director_verification_samples.json` - Sample director verification data and test scenarios
- `create_test_documents.py` - Script to generate PDF test documents

## Quick Start

### 1. Install Dependencies

```bash
pip install reportlab
```

### 2. Generate Test Documents

```bash
cd backend/tests/test_data
python create_test_documents.py
```

This will create PDF documents in `generated_documents/` directory.

### 3. Use Test Documents

Upload the generated PDFs through the frontend or API to test the verification pipelines.

## Test Data Structure

### VAT Registration Samples

Each sample includes:
- `vat_number`: UK VAT number (GB prefix optional)
- `business_name`: Registered business name
- `business_address`: Business address
- `registration_date`: Date of VAT registration
- `ocr_text_template`: Expected OCR text content

### Director Verification Samples

Each sample includes:
- `director_name`: Full director name
- `director_dob`: Date of birth (YYYY-MM-DD)
- `company_name`: Company name
- `company_number`: Companies House company number
- `appointment_date`: Date of director appointment
- `director_address`: Director residential address
- `ocr_text_template`: Expected OCR text content

## Test Scenarios

### VAT Registration

1. **Valid VAT Number**: Standard verification flow
2. **Invalid VAT Number**: Test error handling
3. **VAT without GB prefix**: Test normalization
4. **VAT with spaces**: Test normalization

### Director Verification

1. **Valid Director**: Standard verification flow
2. **Director Not Found**: Test error handling
3. **Name Variations**: Test fuzzy matching
4. **DOB Formats**: Test date normalization

## Manual Testing

### Using the API

```bash
# Upload VAT Registration document
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -F "file=@tests/test_data/generated_documents/vat_registration_01_123456789.pdf" \
  -F "document_type=vat_registration" \
  -F "vat_number=GB123456789" \
  -F "business_name=ACME TRADING LIMITED"

# Upload Director Verification document
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -F "file=@tests/test_data/generated_documents/director_verification_01_12345678.pdf" \
  -F "document_type=director_verification" \
  -F "director_name=JOHN MICHAEL SMITH" \
  -F "director_dob=1975-05-15" \
  -F "company_name=TECHNOLOGY SOLUTIONS LIMITED" \
  -F "company_number=12345678"
```

### Using the Frontend

1. Navigate to the upload page
2. Select document type (VAT Registration or Director Verification)
3. Fill in the appropriate fields
4. Upload the generated test PDF
5. Monitor the verification progress

## Expected Results

### VAT Registration

- OCR should extract: VAT number, business name, address, registration date
- HMRC API should verify the VAT number (if OAuth configured)
- Scoring should calculate: OCR score, registry score, provided score, final score

### Director Verification

- OCR should extract: director name, DOB, address, company name, appointment date
- Companies House API should verify the director
- Scoring should calculate: OCR score, registry score, provided score, final score

## Notes

- Generated PDFs are for testing purposes only
- Real API calls require proper authentication (HMRC OAuth, Companies House API key)
- OCR results may vary based on PDF quality and Textract accuracy
- Some test scenarios may return "not_found" if using real APIs with test data

## Custom Test Data

To add custom test data:

1. Edit the JSON files (`vat_registration_samples.json` or `director_verification_samples.json`)
2. Add your test case to the appropriate array
3. Run `create_test_documents.py` to generate new PDFs

Example:

```json
{
  "description": "My Custom Test Case",
  "vat_number": "GB999888777",
  "business_name": "MY TEST COMPANY LTD",
  "business_address": "123 Test Street, Test City, TE1 1ST",
  "registration_date": "2023-01-01",
  "ocr_text_template": "Your OCR text here..."
}
```

