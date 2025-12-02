# Database Refactoring: Separate Tables per Document Type

## Overview
This migration refactors the database from a single large `document_verifications` table to separate tables for each document type. This provides:

✅ **Better organization** - Each document type has its own table with only relevant columns
✅ **Better performance** - Smaller tables, faster queries
✅ **Easier maintenance** - Clear separation of concerns
✅ **Type safety** - Database enforces document type structure

## New Schema Structure

### 1. `documents` (Base Table)
Common fields shared by all document types:
- Basic info: `document_id`, `filename`, `file_path`, `s3_key`, `document_type`
- Status: `status`, `decision`
- Forensic analysis: `forensic_score`, `forensic_penalty`, `forensic_details`, etc.
- Metadata: `created_at`, `updated_at`, `processed_at`
- Review: `reviewer_id`, `reviewer_action`, `reviewer_notes`

### 2. `companies_house_documents`
Fields specific to Companies House documents:
- Merchant data: `merchant_company_name`, `merchant_company_number`, etc.
- OCR data: `ocr_company_name`, `ocr_company_number`, etc.
- Companies House API: `companies_house_company_name`, etc.
- Scoring: `ocr_score`, `registry_score`, `final_score`, etc.

### 3. `company_registration_documents`
Similar to Companies House (same structure)

### 4. `vat_registration_documents`
Fields specific to VAT documents:
- Merchant data: `merchant_vat_number`, `merchant_business_name`
- OCR data: `ocr_vat_number`, `ocr_business_name`, etc.
- HMRC API: `hmrc_vat_number`, `hmrc_business_name`, etc.
- Scoring fields

### 5. `director_verification_documents`
Fields specific to Director verification:
- Merchant data: `merchant_director_name`, `merchant_director_dob`
- OCR data: `ocr_director_name`, `ocr_director_dob`, etc.
- Companies House API: `companies_house_director_name`, etc.
- Scoring fields

## Migration Steps

### Option 1: Fresh Start (No Data Migration)
If you don't need to preserve existing data:

```bash
psql -U your_username -d your_database -f migrations/refactor_to_separate_tables.sql
```

Then uncomment the `DROP TABLE` line in the SQL file and run again.

### Option 2: With Data Migration
If you want to preserve existing data, we'll need to:
1. Create new tables
2. Migrate data from old table to new tables based on `document_type`
3. Drop old table

## Benefits

1. **Cleaner Schema**: Each table only has columns relevant to that document type
2. **Better Queries**: No need to filter by document_type and handle NULL columns
3. **Type Safety**: Database enforces correct structure per document type
4. **Easier Extensions**: Adding new document types is just creating a new table
5. **Performance**: Smaller tables = faster queries and indexes

## Application Code Changes Needed

After this migration, you'll need to update:

1. **Models** (`app/db/models.py`):
   - Create separate SQLAlchemy models for each table
   - Update `DocumentVerification` to use the new structure

2. **Pipelines** (`app/services/pipeline_service.py`):
   - Update to insert into correct table based on document type

3. **API Endpoints** (`app/api/v1/documents.py`):
   - Update queries to join `documents` with type-specific table

## Rollback

If you need to rollback, you can recreate the old `document_verifications` table structure, but data migration back would be complex.

