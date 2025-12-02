-- Migration: Refactor to separate tables per document type
-- This creates dedicated tables for each document type instead of one large table
-- WARNING: This will DELETE all existing data in document_verifications table!

BEGIN;

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
    document_type VARCHAR NOT NULL, -- companies_house, company_registration, vat_registration, director_verification
    
    -- Common status fields
    status VARCHAR DEFAULT 'pending', -- pending, processing, passed, failed, review, manual_review
    decision VARCHAR, -- PASS, FAIL, REVIEW
    
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
    reviewer_action VARCHAR, -- APPROVE, REJECT, ESCALATE
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
    
    -- Merchant provided data
    merchant_company_name VARCHAR(500),
    merchant_company_number VARCHAR(50),
    merchant_address TEXT,
    merchant_date VARCHAR(50),
    
    -- OCR extracted data
    ocr_company_name VARCHAR(500),
    ocr_company_number VARCHAR(50),
    ocr_address TEXT,
    ocr_date VARCHAR(50),
    ocr_confidence FLOAT,
    ocr_raw_text TEXT,
    
    -- Companies House API data
    companies_house_company_name VARCHAR(500),
    companies_house_company_number VARCHAR(50),
    companies_house_address TEXT,
    companies_house_date VARCHAR(50),
    companies_house_officers JSONB,
    companies_house_data JSONB,
    
    -- Scoring
    ocr_score FLOAT DEFAULT 0.0,
    registry_score FLOAT DEFAULT 0.0,
    provided_score FLOAT DEFAULT 0.0,
    data_match_score FLOAT DEFAULT 0.0,
    final_score FLOAT DEFAULT 0.0,
    
    -- Comparison
    registry_match_score FLOAT,
    registry_data JSONB,
    comparison_details JSONB,
    provided_data_accuracy FLOAT
);

CREATE INDEX IF NOT EXISTS idx_ch_docs_document_id ON companies_house_documents(document_id);

-- Company Registration Documents table (similar to Companies House)
CREATE TABLE IF NOT EXISTS company_registration_documents (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR UNIQUE NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    
    -- Merchant provided data
    merchant_company_name VARCHAR(500),
    merchant_company_number VARCHAR(50),
    merchant_address TEXT,
    merchant_date VARCHAR(50),
    
    -- OCR extracted data
    ocr_company_name VARCHAR(500),
    ocr_company_number VARCHAR(50),
    ocr_address TEXT,
    ocr_date VARCHAR(50),
    ocr_confidence FLOAT,
    ocr_raw_text TEXT,
    
    -- Companies House API data
    companies_house_company_name VARCHAR(500),
    companies_house_company_number VARCHAR(50),
    companies_house_address TEXT,
    companies_house_date VARCHAR(50),
    companies_house_officers JSONB,
    companies_house_data JSONB,
    
    -- Scoring
    ocr_score FLOAT DEFAULT 0.0,
    registry_score FLOAT DEFAULT 0.0,
    provided_score FLOAT DEFAULT 0.0,
    data_match_score FLOAT DEFAULT 0.0,
    final_score FLOAT DEFAULT 0.0,
    
    -- Comparison
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
    
    -- Merchant provided data
    merchant_vat_number VARCHAR(50),
    merchant_business_name VARCHAR(500),
    merchant_address TEXT,
    
    -- OCR extracted data
    ocr_vat_number VARCHAR(50),
    ocr_business_name VARCHAR(500),
    ocr_vat_address TEXT,
    ocr_vat_registration_date VARCHAR(50),
    ocr_confidence FLOAT,
    ocr_raw_text TEXT,
    
    -- HMRC API data
    hmrc_vat_number VARCHAR(50),
    hmrc_business_name VARCHAR(500),
    hmrc_address TEXT,
    hmrc_registration_date VARCHAR(50),
    hmrc_vat_data JSONB,
    
    -- Scoring
    ocr_score FLOAT DEFAULT 0.0,
    registry_score FLOAT DEFAULT 0.0,
    provided_score FLOAT DEFAULT 0.0,
    data_match_score FLOAT DEFAULT 0.0,
    final_score FLOAT DEFAULT 0.0,
    
    -- Comparison
    comparison_details JSONB
);

CREATE INDEX IF NOT EXISTS idx_vat_docs_document_id ON vat_registration_documents(document_id);

-- Director Verification Documents table
CREATE TABLE IF NOT EXISTS director_verification_documents (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR UNIQUE NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    
    -- Merchant provided data
    merchant_director_name VARCHAR(200),
    merchant_director_dob VARCHAR(50),
    merchant_company_name VARCHAR(500),
    merchant_company_number VARCHAR(50),
    
    -- OCR extracted data
    ocr_director_name VARCHAR(200),
    ocr_director_dob VARCHAR(50),
    ocr_director_address TEXT,
    ocr_director_company_name VARCHAR(500),
    ocr_appointment_date VARCHAR(50),
    ocr_confidence FLOAT,
    ocr_raw_text TEXT,
    
    -- Companies House API data
    companies_house_director_name VARCHAR(200),
    companies_house_director_dob VARCHAR(50),
    companies_house_director_address TEXT,
    companies_house_appointment_date VARCHAR(50),
    companies_house_director_data JSONB,
    companies_house_company_name VARCHAR(500),
    companies_house_company_number VARCHAR(50),
    
    -- Scoring
    ocr_score FLOAT DEFAULT 0.0,
    registry_score FLOAT DEFAULT 0.0,
    provided_score FLOAT DEFAULT 0.0,
    data_match_score FLOAT DEFAULT 0.0,
    final_score FLOAT DEFAULT 0.0,
    
    -- Comparison
    comparison_details JSONB
);

CREATE INDEX IF NOT EXISTS idx_dir_docs_document_id ON director_verification_documents(document_id);

-- ============================================================================
-- STEP 2: Drop old table (WARNING: This deletes all data!)
-- ============================================================================

-- Uncomment the line below to drop the old table
-- DROP TABLE IF EXISTS document_verifications CASCADE;

COMMIT;

