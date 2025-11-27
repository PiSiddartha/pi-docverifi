-- Document Verification System Database Schema
-- PostgreSQL Database Schema

-- Create database (run this separately)
-- CREATE DATABASE docverifi_db;

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Document Verifications Table
CREATE TABLE document_verifications (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR(255) UNIQUE NOT NULL,
    filename VARCHAR(500) NOT NULL,
    file_path TEXT NOT NULL,
    s3_key VARCHAR(500),
    
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
    
    -- Forensic analysis
    forensic_score FLOAT,
    forensic_penalty FLOAT DEFAULT 0.0,
    forensic_details JSONB,
    exif_data JSONB,
    ela_score FLOAT,
    jpeg_quality FLOAT,
    copy_move_detected VARCHAR(50),
    
    -- Registry lookup
    registry_match_score FLOAT,
    registry_data JSONB,
    
    -- Data comparison
    data_match_score FLOAT,
    provided_data_accuracy FLOAT,
    comparison_details JSONB,
    
    -- Scoring
    ocr_score FLOAT DEFAULT 0.0,
    registry_score FLOAT DEFAULT 0.0,
    provided_score FLOAT DEFAULT 0.0,
    final_score FLOAT DEFAULT 0.0,
    
    -- Status and decision
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'passed', 'failed', 'review', 'manual_review')),
    decision VARCHAR(50) CHECK (decision IN ('PASS', 'FAIL', 'REVIEW')),
    
    -- Manual review
    reviewer_id VARCHAR(255),
    reviewer_action VARCHAR(50) CHECK (reviewer_action IN ('APPROVE', 'REJECT', 'ESCALATE')),
    reviewer_notes TEXT,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP WITH TIME ZONE,
    
    -- Flags
    flags JSONB
);

-- Create indexes for better query performance
CREATE INDEX idx_document_verifications_document_id ON document_verifications(document_id);
CREATE INDEX idx_document_verifications_status ON document_verifications(status);
CREATE INDEX idx_document_verifications_created_at ON document_verifications(created_at DESC);
CREATE INDEX idx_document_verifications_final_score ON document_verifications(final_score);
CREATE INDEX idx_document_verifications_decision ON document_verifications(decision);
CREATE INDEX idx_document_verifications_company_number ON document_verifications(ocr_company_number);
CREATE INDEX idx_document_verifications_merchant_company_number ON document_verifications(merchant_company_number);

-- GIN index for JSONB columns (for faster JSON queries)
CREATE INDEX idx_document_verifications_companies_house_data ON document_verifications USING GIN (companies_house_data);
CREATE INDEX idx_document_verifications_forensic_details ON document_verifications USING GIN (forensic_details);
CREATE INDEX idx_document_verifications_flags ON document_verifications USING GIN (flags);

-- Audit Logs Table
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR(255) NOT NULL,
    action VARCHAR(100) NOT NULL,
    details JSONB,
    user_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (document_id) REFERENCES document_verifications(document_id) ON DELETE CASCADE
);

-- Create indexes for audit logs
CREATE INDEX idx_audit_logs_document_id ON audit_logs(document_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at DESC);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);





-- Comments for documentation
COMMENT ON TABLE document_verifications IS 'Main table storing document verification records with all extracted and analyzed data';
COMMENT ON TABLE audit_logs IS 'Audit trail for all actions performed on documents';
COMMENT ON COLUMN document_verifications.status IS 'Document processing status: pending, processing, passed, failed, review, manual_review';
COMMENT ON COLUMN document_verifications.decision IS 'Final decision: PASS (score >= 75), REVIEW (50-74), FAIL (< 50)';
COMMENT ON COLUMN document_verifications.final_score IS 'Calculated score: OCR(0-30) + Registry(0-40) + Provided(0-30) - Forensic(0-15)';

