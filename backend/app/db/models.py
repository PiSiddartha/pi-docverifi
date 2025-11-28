"""
Database models
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON, Enum as SQLEnum
from sqlalchemy.sql import func
from app.db.database import Base
import enum


class VerificationStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PASSED = "passed"
    FAILED = "failed"
    REVIEW = "review"
    MANUAL_REVIEW = "manual_review"


class DocumentType(str, enum.Enum):
    COMPANIES_HOUSE = "companies_house"
    # Future types can be added here:
    # ID_DOCUMENT = "id_document"
    # PASSPORT = "passport"
    # DRIVER_LICENSE = "driver_license"


class DocumentVerification(Base):
    __tablename__ = "document_verifications"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(String, unique=True, index=True)
    filename = Column(String)
    file_path = Column(String)
    s3_key = Column(String, nullable=True)
    
    # Document type - determines which verification pipeline to use
    document_type = Column(String, default="companies_house", index=True)  # companies_house, id_document, passport, etc.
    
    # Merchant provided data
    merchant_company_name = Column(String, nullable=True)
    merchant_company_number = Column(String, nullable=True)
    merchant_address = Column(Text, nullable=True)
    merchant_date = Column(String, nullable=True)
    
    # OCR extracted data
    ocr_company_name = Column(String, nullable=True)
    ocr_company_number = Column(String, nullable=True)
    ocr_address = Column(Text, nullable=True)
    ocr_date = Column(String, nullable=True)
    ocr_confidence = Column(Float, nullable=True)
    ocr_raw_text = Column(Text, nullable=True)
    
    # Companies House API data
    companies_house_company_name = Column(String, nullable=True)
    companies_house_company_number = Column(String, nullable=True)
    companies_house_address = Column(Text, nullable=True)
    companies_house_date = Column(String, nullable=True)
    companies_house_officers = Column(JSON, nullable=True)
    companies_house_data = Column(JSON, nullable=True)
    
    # Forensic analysis
    forensic_score = Column(Float, nullable=True)
    forensic_penalty = Column(Float, default=0.0)
    forensic_details = Column(JSON, nullable=True)
    exif_data = Column(JSON, nullable=True)
    ela_score = Column(Float, nullable=True)
    jpeg_quality = Column(Float, nullable=True)
    copy_move_detected = Column(String, nullable=True)
    
    # Registry lookup
    registry_match_score = Column(Float, nullable=True)
    registry_data = Column(JSON, nullable=True)
    
    # Data comparison
    data_match_score = Column(Float, nullable=True)
    provided_data_accuracy = Column(Float, nullable=True)
    comparison_details = Column(JSON, nullable=True)
    
    # Scoring
    ocr_score = Column(Float, default=0.0)
    registry_score = Column(Float, default=0.0)
    provided_score = Column(Float, default=0.0)
    final_score = Column(Float, default=0.0)
    
    # Status and decision
    # Note: Using String instead of Enum to match existing database structure
    status = Column(String, default="pending")  # pending, processing, passed, failed, review, manual_review
    decision = Column(String, nullable=True)  # "PASS", "FAIL", "REVIEW"
    
    # Manual review
    reviewer_id = Column(String, nullable=True)
    reviewer_action = Column(String, nullable=True)  # "APPROVE", "REJECT", "ESCALATE"
    reviewer_notes = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Flags
    flags = Column(JSON, nullable=True)  # Array of flag strings
    
    def __repr__(self):
        return f"<DocumentVerification(id={self.id}, document_id={self.document_id}, status={self.status}, score={self.final_score})>"


class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(String, index=True)
    action = Column(String)
    details = Column(JSON, nullable=True)
    user_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

