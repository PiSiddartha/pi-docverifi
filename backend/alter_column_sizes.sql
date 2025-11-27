-- Alter table columns to support longer text values
-- Run this script to update the database schema

-- Change VARCHAR columns to TEXT for fields that may contain long text
-- This allows unlimited length (up to ~1GB in PostgreSQL)

-- OCR extracted data columns
ALTER TABLE document_verifications 
    ALTER COLUMN ocr_company_name TYPE TEXT,
    ALTER COLUMN ocr_company_number TYPE VARCHAR(100),
    ALTER COLUMN ocr_date TYPE VARCHAR(100);

-- Merchant provided data columns  
ALTER TABLE document_verifications
    ALTER COLUMN merchant_company_name TYPE TEXT,
    ALTER COLUMN merchant_company_number TYPE VARCHAR(100),
    ALTER COLUMN merchant_date TYPE VARCHAR(100);

-- Companies House API data columns
ALTER TABLE document_verifications
    ALTER COLUMN companies_house_company_name TYPE TEXT,
    ALTER COLUMN companies_house_company_number TYPE VARCHAR(100),
    ALTER COLUMN companies_house_date TYPE VARCHAR(100);

-- Other VARCHAR columns that might need more space
ALTER TABLE document_verifications
    ALTER COLUMN filename TYPE TEXT,
    ALTER COLUMN s3_key TYPE TEXT,
    ALTER COLUMN copy_move_detected TYPE VARCHAR(100);

-- Verify the changes
SELECT 
    column_name, 
    data_type, 
    character_maximum_length
FROM information_schema.columns 
WHERE table_name = 'document_verifications' 
    AND column_name IN (
        'ocr_company_name', 
        'ocr_company_number', 
        'ocr_date',
        'merchant_company_name',
        'merchant_company_number',
        'merchant_date',
        'companies_house_company_name',
        'companies_house_company_number',
        'companies_house_date',
        'filename',
        's3_key',
        'copy_move_detected'
    )
ORDER BY column_name;

