"""
Helper functions for working with the new document table structure
"""
from sqlalchemy.orm import Session
from typing import Optional, Tuple, Union
from app.db.models import (
    Document,
    DocumentType,
    CompaniesHouseDocument,
    CompanyRegistrationDocument,
    VATRegistrationDocument,
    DirectorVerificationDocument
)


def get_document_with_type(db: Session, document_id: str) -> Optional[Tuple[Document, Union[
    CompaniesHouseDocument,
    CompanyRegistrationDocument,
    VATRegistrationDocument,
    DirectorVerificationDocument
]]]:
    """
    Get document and its type-specific data
    
    Returns:
        Tuple of (Document, type_specific_document) or None if not found
    """
    # Get base document
    base_doc = db.query(Document).filter(Document.document_id == document_id).first()
    
    if not base_doc:
        return None
    
    # Get type-specific document
    doc_type = base_doc.document_type
    
    if doc_type == DocumentType.COMPANIES_HOUSE.value:
        type_doc = db.query(CompaniesHouseDocument).filter(
            CompaniesHouseDocument.document_id == document_id
        ).first()
    elif doc_type == DocumentType.COMPANY_REGISTRATION.value:
        type_doc = db.query(CompanyRegistrationDocument).filter(
            CompanyRegistrationDocument.document_id == document_id
        ).first()
    elif doc_type == DocumentType.VAT_REGISTRATION.value:
        type_doc = db.query(VATRegistrationDocument).filter(
            VATRegistrationDocument.document_id == document_id
        ).first()
    elif doc_type == DocumentType.DIRECTOR_VERIFICATION.value:
        type_doc = db.query(DirectorVerificationDocument).filter(
            DirectorVerificationDocument.document_id == document_id
        ).first()
    else:
        type_doc = None
    
    return (base_doc, type_doc) if type_doc else (base_doc, None)


def create_document_record(
    db: Session,
    document_id: str,
    filename: str,
    file_path: str,
    document_type: str,
    s3_key: Optional[str] = None,
    **kwargs
) -> Tuple[Document, Union[
    CompaniesHouseDocument,
    CompanyRegistrationDocument,
    VATRegistrationDocument,
    DirectorVerificationDocument
]]:
    """
    Create both base document and type-specific document records
    
    Returns:
        Tuple of (Document, type_specific_document)
    """
    # Create base document
    base_doc = Document(
        document_id=document_id,
        filename=filename,
        file_path=file_path,
        s3_key=s3_key,
        document_type=document_type,
        status="pending"
    )
    db.add(base_doc)
    db.flush()  # Flush to get the ID
    
    # Create type-specific document
    if document_type == DocumentType.COMPANIES_HOUSE.value:
        type_doc = CompaniesHouseDocument(
            document_id=document_id,
            merchant_company_name=kwargs.get('merchant_company_name'),
            merchant_company_number=kwargs.get('merchant_company_number'),
            merchant_address=kwargs.get('merchant_address'),
            merchant_date=kwargs.get('merchant_date'),
        )
    elif document_type == DocumentType.COMPANY_REGISTRATION.value:
        type_doc = CompanyRegistrationDocument(
            document_id=document_id,
            merchant_company_name=kwargs.get('merchant_company_name'),
            merchant_company_number=kwargs.get('merchant_company_number'),
            merchant_address=kwargs.get('merchant_address'),
            merchant_date=kwargs.get('merchant_date'),
        )
    elif document_type == DocumentType.VAT_REGISTRATION.value:
        type_doc = VATRegistrationDocument(
            document_id=document_id,
            merchant_vat_number=kwargs.get('merchant_vat_number'),
            merchant_business_name=kwargs.get('merchant_business_name'),
            merchant_address=kwargs.get('merchant_address'),
        )
    elif document_type == DocumentType.DIRECTOR_VERIFICATION.value:
        type_doc = DirectorVerificationDocument(
            document_id=document_id,
            merchant_director_name=kwargs.get('merchant_director_name'),
            merchant_director_dob=kwargs.get('merchant_director_dob'),
            merchant_company_name=kwargs.get('merchant_company_name'),
            merchant_company_number=kwargs.get('merchant_company_number'),
        )
    else:
        # Default to Companies House
        type_doc = CompaniesHouseDocument(
            document_id=document_id,
            merchant_company_name=kwargs.get('merchant_company_name'),
            merchant_company_number=kwargs.get('merchant_company_number'),
            merchant_address=kwargs.get('merchant_address'),
            merchant_date=kwargs.get('merchant_date'),
        )
    
    db.add(type_doc)
    db.flush()
    
    return (base_doc, type_doc)

