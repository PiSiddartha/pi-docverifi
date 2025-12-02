"""
New Database models for refactored table structure
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
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
    COMPANY_REGISTRATION = "company_registration"
    VAT_REGISTRATION = "vat_registration"
    DIRECTOR_VERIFICATION = "director_verification"


class Document(Base):
    """Base document table with common fields"""
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(String, unique=True, index=True, nullable=False)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    s3_key = Column(String, nullable=True)
    document_type = Column(String, nullable=False, index=True)
    
    # Status fields
    status = Column(String, default="pending", index=True)
    decision = Column(String, nullable=True)
    
    # Forensic analysis (common to all)
    forensic_score = Column(Float, nullable=True)
    forensic_penalty = Column(Float, default=0.0)
    forensic_details = Column(JSON, nullable=True)
    exif_data = Column(JSON, nullable=True)
    ela_score = Column(Float, nullable=True)
    jpeg_quality = Column(Float, nullable=True)
    copy_move_detected = Column(String, nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Manual review
    reviewer_id = Column(String, nullable=True)
    reviewer_action = Column(String, nullable=True)
    reviewer_notes = Column(Text, nullable=True)
    
    # Flags
    flags = Column(JSON, nullable=True)
    
    def __repr__(self):
        return f"<Document(id={self.id}, document_id={self.document_id}, type={self.document_type}, status={self.status})>"


class CompaniesHouseDocument(Base):
    """Companies House specific document data"""
    __tablename__ = "companies_house_documents"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(String, unique=True, nullable=False, index=True)
    
    # Merchant provided data
    merchant_company_name = Column(Text, nullable=True)
    merchant_company_number = Column(String(50), nullable=True)
    merchant_address = Column(Text, nullable=True)
    merchant_date = Column(String(50), nullable=True)
    
    # OCR extracted data
    ocr_company_name = Column(Text, nullable=True)
    ocr_company_number = Column(String(50), nullable=True)
    ocr_address = Column(Text, nullable=True)
    ocr_date = Column(String(50), nullable=True)
    ocr_confidence = Column(Float, nullable=True)
    ocr_raw_text = Column(Text, nullable=True)
    
    # Companies House API data
    companies_house_company_name = Column(Text, nullable=True)
    companies_house_company_number = Column(String(50), nullable=True)
    companies_house_address = Column(Text, nullable=True)
    companies_house_date = Column(String(50), nullable=True)
    companies_house_officers = Column(JSON, nullable=True)
    companies_house_data = Column(JSON, nullable=True)
    
    # Scoring
    ocr_score = Column(Float, default=0.0)
    registry_score = Column(Float, default=0.0)
    provided_score = Column(Float, default=0.0)
    data_match_score = Column(Float, default=0.0)
    final_score = Column(Float, default=0.0)
    
    # Comparison
    registry_match_score = Column(Float, nullable=True)
    registry_data = Column(JSON, nullable=True)
    comparison_details = Column(JSON, nullable=True)
    provided_data_accuracy = Column(Float, nullable=True)
    
    def __repr__(self):
        return f"<CompaniesHouseDocument(document_id={self.document_id}, company={self.ocr_company_name})>"


class CompanyRegistrationDocument(Base):
    """Company Registration specific document data"""
    __tablename__ = "company_registration_documents"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(String, unique=True, nullable=False, index=True)
    
    # Merchant provided data
    merchant_company_name = Column(Text, nullable=True)
    merchant_company_number = Column(String(50), nullable=True)
    merchant_address = Column(Text, nullable=True)
    merchant_date = Column(String(50), nullable=True)
    
    # OCR extracted data
    ocr_company_name = Column(Text, nullable=True)
    ocr_company_number = Column(String(50), nullable=True)
    ocr_address = Column(Text, nullable=True)
    ocr_date = Column(String(50), nullable=True)
    ocr_confidence = Column(Float, nullable=True)
    ocr_raw_text = Column(Text, nullable=True)
    
    # Companies House API data
    companies_house_company_name = Column(Text, nullable=True)
    companies_house_company_number = Column(String(50), nullable=True)
    companies_house_address = Column(Text, nullable=True)
    companies_house_date = Column(String(50), nullable=True)
    companies_house_officers = Column(JSON, nullable=True)
    companies_house_data = Column(JSON, nullable=True)
    
    # Scoring
    ocr_score = Column(Float, default=0.0)
    registry_score = Column(Float, default=0.0)
    provided_score = Column(Float, default=0.0)
    data_match_score = Column(Float, default=0.0)
    final_score = Column(Float, default=0.0)
    
    # Comparison
    registry_match_score = Column(Float, nullable=True)
    registry_data = Column(JSON, nullable=True)
    comparison_details = Column(JSON, nullable=True)
    provided_data_accuracy = Column(Float, nullable=True)
    
    def __repr__(self):
        return f"<CompanyRegistrationDocument(document_id={self.document_id}, company={self.ocr_company_name})>"


class VATRegistrationDocument(Base):
    """VAT Registration specific document data"""
    __tablename__ = "vat_registration_documents"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(String, unique=True, nullable=False, index=True)
    
    # Merchant provided data
    merchant_vat_number = Column(String(50), nullable=True)
    merchant_business_name = Column(Text, nullable=True)
    merchant_address = Column(Text, nullable=True)
    
    # OCR extracted data
    ocr_vat_number = Column(String(50), nullable=True)
    ocr_business_name = Column(Text, nullable=True)
    ocr_vat_address = Column(Text, nullable=True)
    ocr_vat_registration_date = Column(String(50), nullable=True)
    ocr_confidence = Column(Float, nullable=True)
    ocr_raw_text = Column(Text, nullable=True)
    
    # HMRC API data
    hmrc_vat_number = Column(String(50), nullable=True)
    hmrc_business_name = Column(Text, nullable=True)
    hmrc_address = Column(Text, nullable=True)
    hmrc_registration_date = Column(String(50), nullable=True)
    hmrc_vat_data = Column(JSON, nullable=True)
    
    # Scoring
    ocr_score = Column(Float, default=0.0)
    registry_score = Column(Float, default=0.0)
    provided_score = Column(Float, default=0.0)
    data_match_score = Column(Float, default=0.0)
    final_score = Column(Float, default=0.0)
    
    # Comparison
    comparison_details = Column(JSON, nullable=True)
    
    def __repr__(self):
        return f"<VATRegistrationDocument(document_id={self.document_id}, vat={self.ocr_vat_number})>"


class DirectorVerificationDocument(Base):
    """Director Verification specific document data"""
    __tablename__ = "director_verification_documents"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(String, unique=True, nullable=False, index=True)
    
    # Merchant provided data
    merchant_director_name = Column(String(200), nullable=True)
    merchant_director_dob = Column(String(50), nullable=True)
    merchant_company_name = Column(Text, nullable=True)
    merchant_company_number = Column(String(50), nullable=True)
    
    # OCR extracted data
    ocr_director_name = Column(String(200), nullable=True)
    ocr_director_dob = Column(String(50), nullable=True)
    ocr_director_address = Column(Text, nullable=True)
    ocr_director_company_name = Column(Text, nullable=True)
    ocr_appointment_date = Column(String(50), nullable=True)
    ocr_confidence = Column(Float, nullable=True)
    ocr_raw_text = Column(Text, nullable=True)
    
    # Companies House API data
    companies_house_director_name = Column(String(200), nullable=True)
    companies_house_director_dob = Column(String(50), nullable=True)
    companies_house_director_address = Column(Text, nullable=True)
    companies_house_appointment_date = Column(String(50), nullable=True)
    companies_house_director_data = Column(JSON, nullable=True)
    companies_house_company_name = Column(Text, nullable=True)
    companies_house_company_number = Column(String(50), nullable=True)
    
    # Scoring
    ocr_score = Column(Float, default=0.0)
    registry_score = Column(Float, default=0.0)
    provided_score = Column(Float, default=0.0)
    data_match_score = Column(Float, default=0.0)
    final_score = Column(Float, default=0.0)
    
    # Comparison
    comparison_details = Column(JSON, nullable=True)
    
    def __repr__(self):
        return f"<DirectorVerificationDocument(document_id={self.document_id}, director={self.ocr_director_name})>"


class AuditLog(Base):
    """Audit log for document actions"""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(String, index=True)
    action = Column(String)
    details = Column(JSON, nullable=True)
    user_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

