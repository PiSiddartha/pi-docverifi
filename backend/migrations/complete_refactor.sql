-- Complete Refactoring Migration: Separate Tables per Document Type
-- This script:
-- 1. Creates new table structure
-- 2. Optionally migrates existing data
-- 3. Drops old table

BEGIN;

-- ============================================================================
-- STEP 0: Drop existing new tables if they exist (from previous failed migration)
-- ============================================================================

DROP TABLE IF EXISTS director_verification_documents CASCADE;
DROP TABLE IF EXISTS vat_registration_documents CASCADE;
DROP TABLE IF EXISTS company_registration_documents CASCADE;
DROP TABLE IF EXISTS companies_house_documents CASCADE;
DROP TABLE IF EXISTS documents CASCADE;

-- ============================================================================
-- STEP 1: Create new table structure
-- ============================================================================

-- Base document table (common fields for all document types)
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR UNIQUE NOT NULL,
    filename VARCHAR NOT NULL,
    file_path VARCHAR NOT NULL,
    s3_key VARCHAR,
    document_type VARCHAR NOT NULL,
    
    -- Common status fields
    status VARCHAR DEFAULT 'pending',
    decision VARCHAR,
    
    -- Common scoring fields
    forensic_score FLOAT,
    forensic_penalty FLOAT DEFAULT 0.0,
    forensic_details JSONB,
    exif_data JSONB,
    ela_score FLOAT,
    jpeg_quality FLOAT,
    copy_move_detected VARCHAR,
    
    -- Common metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,
    processed_at TIMESTAMP WITH TIME ZONE,
    
    -- Manual review
    reviewer_id VARCHAR,
    reviewer_action VARCHAR,
    reviewer_notes TEXT,
    
    -- Flags
    flags JSONB
);

CREATE INDEX IF NOT EXISTS idx_documents_document_id ON documents(document_id);
CREATE INDEX IF NOT EXISTS idx_documents_document_type ON documents(document_type);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);

-- Companies House Documents table
CREATE TABLE IF NOT EXISTS companies_house_documents (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR UNIQUE NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    
    merchant_company_name TEXT,
    merchant_company_number VARCHAR(50),
    merchant_address TEXT,
    merchant_date VARCHAR(50),
    
    ocr_company_name TEXT,
    ocr_company_number VARCHAR(50),
    ocr_address TEXT,
    ocr_date VARCHAR(50),
    ocr_confidence FLOAT,
    ocr_raw_text TEXT,
    
    companies_house_company_name TEXT,
    companies_house_company_number VARCHAR(50),
    companies_house_address TEXT,
    companies_house_date VARCHAR(50),
    companies_house_officers JSONB,
    companies_house_data JSONB,
    
    ocr_score FLOAT DEFAULT 0.0,
    registry_score FLOAT DEFAULT 0.0,
    provided_score FLOAT DEFAULT 0.0,
    data_match_score FLOAT DEFAULT 0.0,
    final_score FLOAT DEFAULT 0.0,
    
    registry_match_score FLOAT,
    registry_data JSONB,
    comparison_details JSONB,
    provided_data_accuracy FLOAT
);

CREATE INDEX IF NOT EXISTS idx_ch_docs_document_id ON companies_house_documents(document_id);

-- Company Registration Documents table
CREATE TABLE IF NOT EXISTS company_registration_documents (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR UNIQUE NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    
    merchant_company_name TEXT,
    merchant_company_number VARCHAR(50),
    merchant_address TEXT,
    merchant_date VARCHAR(50),
    
    ocr_company_name TEXT,
    ocr_company_number VARCHAR(50),
    ocr_address TEXT,
    ocr_date VARCHAR(50),
    ocr_confidence FLOAT,
    ocr_raw_text TEXT,
    
    companies_house_company_name TEXT,
    companies_house_company_number VARCHAR(50),
    companies_house_address TEXT,
    companies_house_date VARCHAR(50),
    companies_house_officers JSONB,
    companies_house_data JSONB,
    
    ocr_score FLOAT DEFAULT 0.0,
    registry_score FLOAT DEFAULT 0.0,
    provided_score FLOAT DEFAULT 0.0,
    data_match_score FLOAT DEFAULT 0.0,
    final_score FLOAT DEFAULT 0.0,
    
    registry_match_score FLOAT,
    registry_data JSONB,
    comparison_details JSONB,
    provided_data_accuracy FLOAT
);

CREATE INDEX IF NOT EXISTS idx_cr_docs_document_id ON company_registration_documents(document_id);

-- VAT Registration Documents table
CREATE TABLE IF NOT EXISTS vat_registration_documents (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR UNIQUE NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    
    merchant_vat_number VARCHAR(50),
    merchant_business_name TEXT,
    merchant_address TEXT,
    
    ocr_vat_number VARCHAR(50),
    ocr_business_name TEXT,
    ocr_vat_address TEXT,
    ocr_vat_registration_date VARCHAR(50),
    ocr_confidence FLOAT,
    ocr_raw_text TEXT,
    
    hmrc_vat_number VARCHAR(50),
    hmrc_business_name TEXT,
    hmrc_address TEXT,
    hmrc_registration_date VARCHAR(50),
    hmrc_vat_data JSONB,
    
    ocr_score FLOAT DEFAULT 0.0,
    registry_score FLOAT DEFAULT 0.0,
    provided_score FLOAT DEFAULT 0.0,
    data_match_score FLOAT DEFAULT 0.0,
    final_score FLOAT DEFAULT 0.0,
    
    comparison_details JSONB
);

CREATE INDEX IF NOT EXISTS idx_vat_docs_document_id ON vat_registration_documents(document_id);

-- Director Verification Documents table
CREATE TABLE IF NOT EXISTS director_verification_documents (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR UNIQUE NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    
    merchant_director_name VARCHAR(200),
    merchant_director_dob VARCHAR(50),
    merchant_company_name TEXT,
    merchant_company_number VARCHAR(50),
    
    ocr_director_name VARCHAR(200),
    ocr_director_dob VARCHAR(50),
    ocr_director_address TEXT,
    ocr_director_company_name TEXT,
    ocr_appointment_date VARCHAR(50),
    ocr_confidence FLOAT,
    ocr_raw_text TEXT,
    
    companies_house_director_name VARCHAR(200),
    companies_house_director_dob VARCHAR(50),
    companies_house_director_address TEXT,
    companies_house_appointment_date VARCHAR(50),
    companies_house_director_data JSONB,
    companies_house_company_name TEXT,
    companies_house_company_number VARCHAR(50),
    
    ocr_score FLOAT DEFAULT 0.0,
    registry_score FLOAT DEFAULT 0.0,
    provided_score FLOAT DEFAULT 0.0,
    data_match_score FLOAT DEFAULT 0.0,
    final_score FLOAT DEFAULT 0.0,
    
    comparison_details JSONB
);

CREATE INDEX IF NOT EXISTS idx_dir_docs_document_id ON director_verification_documents(document_id);

-- ============================================================================
-- STEP 2: Migrate existing data (if any)
-- ============================================================================

-- Migrate base document data
INSERT INTO documents (
    document_id, filename, file_path, s3_key, document_type,
    status, decision,
    forensic_score, forensic_penalty, forensic_details, exif_data,
    ela_score, jpeg_quality, copy_move_detected,
    created_at, updated_at, processed_at,
    reviewer_id, reviewer_action, reviewer_notes, flags
)
SELECT 
    document_id, filename, file_path, s3_key, document_type,
    status, decision,
    forensic_score, forensic_penalty, forensic_details, exif_data,
    ela_score, jpeg_quality, copy_move_detected,
    created_at, updated_at, processed_at,
    reviewer_id, reviewer_action, reviewer_notes, flags
FROM document_verifications
ON CONFLICT (document_id) DO NOTHING;

-- Migrate Companies House documents
-- Note: All TEXT fields will preserve full data, no truncation
INSERT INTO companies_house_documents (
    document_id,
    merchant_company_name, merchant_company_number, merchant_address, merchant_date,
    ocr_company_name, ocr_company_number, ocr_address, ocr_date, ocr_confidence, ocr_raw_text,
    companies_house_company_name, companies_house_company_number, companies_house_address,
    companies_house_date, companies_house_officers, companies_house_data,
    ocr_score, registry_score, provided_score, data_match_score, final_score,
    registry_match_score, registry_data, comparison_details, provided_data_accuracy
)
SELECT 
    document_id,
    merchant_company_name::TEXT, merchant_company_number, merchant_address::TEXT, merchant_date,
    ocr_company_name::TEXT, ocr_company_number, ocr_address::TEXT, ocr_date, ocr_confidence, ocr_raw_text::TEXT,
    companies_house_company_name::TEXT, companies_house_company_number, companies_house_address::TEXT,
    companies_house_date, companies_house_officers, companies_house_data,
    ocr_score, registry_score, provided_score, data_match_score, final_score,
    registry_match_score, registry_data, comparison_details, provided_data_accuracy
FROM document_verifications
WHERE document_type = 'companies_house'
ON CONFLICT (document_id) DO NOTHING;

-- Migrate Company Registration documents
-- Note: All TEXT fields will preserve full data, no truncation
INSERT INTO company_registration_documents (
    document_id,
    merchant_company_name, merchant_company_number, merchant_address, merchant_date,
    ocr_company_name, ocr_company_number, ocr_address, ocr_date, ocr_confidence, ocr_raw_text,
    companies_house_company_name, companies_house_company_number, companies_house_address,
    companies_house_date, companies_house_officers, companies_house_data,
    ocr_score, registry_score, provided_score, data_match_score, final_score,
    registry_match_score, registry_data, comparison_details, provided_data_accuracy
)
SELECT 
    document_id,
    merchant_company_name::TEXT, merchant_company_number, merchant_address::TEXT, merchant_date,
    ocr_company_name::TEXT, ocr_company_number, ocr_address::TEXT, ocr_date, ocr_confidence, ocr_raw_text::TEXT,
    companies_house_company_name::TEXT, companies_house_company_number, companies_house_address::TEXT,
    companies_house_date, companies_house_officers, companies_house_data,
    ocr_score, registry_score, provided_score, data_match_score, final_score,
    registry_match_score, registry_data, comparison_details, provided_data_accuracy
FROM document_verifications
WHERE document_type = 'company_registration'
ON CONFLICT (document_id) DO NOTHING;

-- Migrate VAT Registration documents
-- Note: All TEXT fields will preserve full data, no truncation
INSERT INTO vat_registration_documents (
    document_id,
    merchant_vat_number, merchant_business_name, merchant_address,
    ocr_vat_number, ocr_business_name, ocr_vat_address, ocr_vat_registration_date,
    ocr_confidence, ocr_raw_text,
    hmrc_vat_number, hmrc_business_name, hmrc_address, hmrc_registration_date, hmrc_vat_data,
    ocr_score, registry_score, provided_score, data_match_score, final_score,
    comparison_details
)
SELECT 
    document_id,
    merchant_vat_number, merchant_business_name::TEXT, merchant_address::TEXT,
    ocr_vat_number, ocr_business_name::TEXT, ocr_vat_address::TEXT, ocr_vat_registration_date,
    ocr_confidence, ocr_raw_text::TEXT,
    hmrc_vat_number, hmrc_business_name::TEXT, hmrc_address::TEXT, hmrc_registration_date, hmrc_vat_data,
    ocr_score, registry_score, provided_score, data_match_score, final_score,
    comparison_details
FROM document_verifications
WHERE document_type = 'vat_registration'
ON CONFLICT (document_id) DO NOTHING;

-- Migrate Director Verification documents
-- Note: All TEXT fields will preserve full data, no truncation
INSERT INTO director_verification_documents (
    document_id,
    merchant_director_name, merchant_director_dob, merchant_company_name, merchant_company_number,
    ocr_director_name, ocr_director_dob, ocr_director_address, ocr_director_company_name,
    ocr_appointment_date, ocr_confidence, ocr_raw_text,
    companies_house_director_name, companies_house_director_dob, companies_house_director_address,
    companies_house_appointment_date, companies_house_director_data,
    companies_house_company_name, companies_house_company_number,
    ocr_score, registry_score, provided_score, data_match_score, final_score,
    comparison_details
)
SELECT 
    document_id,
    merchant_director_name, merchant_director_dob, merchant_company_name::TEXT, merchant_company_number,
    ocr_director_name, ocr_director_dob, ocr_director_address::TEXT, ocr_director_company_name::TEXT,
    ocr_appointment_date, ocr_confidence, ocr_raw_text::TEXT,
    companies_house_director_name, companies_house_director_dob, companies_house_director_address::TEXT,
    companies_house_appointment_date, companies_house_director_data,
    ocr_company_name::TEXT, ocr_company_number, -- Use OCR company fields for CH company fields
    ocr_score, registry_score, provided_score, data_match_score, final_score,
    comparison_details
FROM document_verifications
WHERE document_type = 'director_verification'
ON CONFLICT (document_id) DO NOTHING;

-- ============================================================================
-- STEP 3: Drop old table (WARNING: This deletes the old table!)
-- ============================================================================

-- Uncomment the line below when you're ready to drop the old table
-- DROP TABLE IF EXISTS document_verifications CASCADE;

COMMIT;

