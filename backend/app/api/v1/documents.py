"""
Document upload and management endpoints
"""
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional
import os
import uuid
import shutil
from pathlib import Path
import io
import json
import logging
import boto3

from app.db.database import get_db
from app.db.models import Document, DocumentType
from app.db.document_helper import create_document_record
from app.core.config import settings
from app.api.v1.verification import process_document_verification
from app.services.s3_service import s3_service

logger = logging.getLogger(__name__)
router = APIRouter()


def truncate_string(value: str, max_length: int) -> str:
    """
    Truncate a string to fit within the specified max length.
    Returns the truncated string with '...' appended if truncated.
    """
    if not value:
        return value
    if len(value) <= max_length:
        return value
    # Truncate and add ellipsis, but ensure total length doesn't exceed max_length
    return value[:max_length - 3] + "..."


@router.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    document_type: str = Form("companies_house"),  # Use Form() for multipart form data
    # Company/Registration fields
    company_name: Optional[str] = Form(None),
    company_number: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    date: Optional[str] = Form(None),
    # VAT Registration fields
    vat_number: Optional[str] = Form(None),
    business_name: Optional[str] = Form(None),
    # Director Verification fields
    director_name: Optional[str] = Form(None),
    director_dob: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Upload a document for verification
    """
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    # Check file size
    file_content = await file.read()
    if len(file_content) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max size: {settings.MAX_UPLOAD_SIZE} bytes"
        )
    
    # Generate unique document ID
    document_id = str(uuid.uuid4())
    file_extension = Path(file.filename).suffix
    filename = f"{document_id}{file_extension}"
    
    # Prepare file for upload
    await file.seek(0)
    file_obj = io.BytesIO(file_content)
    
    # Always save locally first (required for processing and satisfies NOT NULL constraint)
    # Use /tmp in Lambda environment, otherwise use configured UPLOAD_DIR
    if os.getenv("LAMBDA_TASK_ROOT"):
        upload_dir = Path("/tmp/uploads")
    else:
        upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / filename
    await file.seek(0)
    with open(file_path, "wb") as buffer:
        buffer.write(file_content)
    
    # Upload to S3 if enabled (as backup/archive)
    s3_key = None
    if s3_service.is_enabled():
        # Upload to S3
        s3_key = f"documents/{document_id}/{filename}"
        await file.seek(0)
        file_obj.seek(0)
        s3_url = s3_service.upload_fileobj(
            file_obj,
            s3_key,
            content_type=file.content_type or "application/octet-stream"
        )
        
        if not s3_url:
            # S3 upload failed, but we still have local copy
            # Clear s3_key to indicate S3 upload failed
            s3_key = None
    
    # Validate document type
    valid_types = [dt.value for dt in DocumentType]
    logger.info(f"[UPLOAD] Received document_type: {document_type}")
    logger.info(f"[UPLOAD] Valid document types: {valid_types}")
    if document_type not in valid_types:
        logger.warning(f"Invalid document type: {document_type}, defaulting to companies_house")
        document_type = DocumentType.COMPANIES_HOUSE.value
    else:
        logger.info(f"[UPLOAD] Document type validated: {document_type}")
    
    # Prepare merchant data (no truncation needed - using TEXT columns)
    merchant_data = {
        'merchant_company_name': company_name,
        'merchant_company_number': company_number,
        'merchant_address': address,
        'merchant_date': date,
        'merchant_vat_number': vat_number,
        'merchant_business_name': business_name,
        'merchant_director_name': director_name,
        'merchant_director_dob': director_dob,
    }
    
    # Create database records (base document + type-specific document)
    base_doc, type_doc = create_document_record(
        db=db,
        document_id=document_id,
        filename=file.filename,
        file_path=str(file_path),
        document_type=document_type,
        s3_key=s3_key,
        **merchant_data
    )
    
    db.commit()
    db.refresh(base_doc)
    db.refresh(type_doc)
    
    # Auto-start processing - use SQS if configured, otherwise BackgroundTasks
    logger.info(f"[UPLOAD] Document uploaded successfully. document_id: {document_id}, filename: {file.filename}, file_path: {file_path}, s3_key: {s3_key}")
    
    if settings.USE_SQS and settings.SQS_QUEUE_URL:
        # Send to SQS queue for async processing
        try:
            sqs = boto3.client('sqs', region_name=settings.AWS_REGION)
            sqs.send_message(
                QueueUrl=settings.SQS_QUEUE_URL,
                MessageBody=json.dumps({
                    "document_id": document_id,
                    "action": "process"
                })
            )
            logger.info(f"[UPLOAD] Message sent to SQS queue for document_id: {document_id}")
        except Exception as e:
            logger.error(f"[UPLOAD] Failed to send message to SQS: {e}")
            # Fallback to BackgroundTasks
            background_tasks.add_task(process_document_verification, document_id)
            logger.info(f"[UPLOAD] Falling back to BackgroundTasks for document_id: {document_id}")
    else:
        # Use BackgroundTasks (default for local development)
        logger.info(f"[UPLOAD] Starting background processing task for document_id: {document_id}")
        background_tasks.add_task(process_document_verification, document_id)
    
    return {
        "document_id": document_id,
        "status": "uploaded",
        "message": "Document uploaded successfully. Processing has started."
    }


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    db: Session = Depends(get_db)
):
    """
    Get document verification details
    """
    from app.db.document_helper import get_document_with_type
    from app.db.models import (
        CompaniesHouseDocument,
        CompanyRegistrationDocument,
        VATRegistrationDocument,
        DirectorVerificationDocument
    )
    
    result = get_document_with_type(db, document_id)
    if not result:
        raise HTTPException(status_code=404, detail="Document not found")
    
    base_doc, type_doc = result
    
    # Build response based on document type
    # Get final_score from type_doc if available, otherwise 0.0
    final_score = type_doc.final_score if type_doc and type_doc.final_score is not None else None
    
    response = {
        "document_id": base_doc.document_id,
        "filename": base_doc.filename,
        "document_type": base_doc.document_type,
        "status": base_doc.status,
        "decision": base_doc.decision,
        "final_score": final_score,  # Add at top level for backward compatibility
        "created_at": base_doc.created_at.isoformat() if base_doc.created_at else None,
        "processed_at": base_doc.processed_at.isoformat() if base_doc.processed_at else None,
        "forensic_analysis": {
            "forensic_score": base_doc.forensic_score,
            "forensic_penalty": base_doc.forensic_penalty or 0.0,
            "ela_score": base_doc.ela_score,
            "jpeg_quality": base_doc.jpeg_quality,
            "copy_move_detected": base_doc.copy_move_detected,
            "details": base_doc.forensic_details
        },
        "flags": base_doc.flags
    }
    
    # Add type-specific data
    if isinstance(type_doc, (CompaniesHouseDocument, CompanyRegistrationDocument)):
        response["ocr_data"] = {
            "company_name": type_doc.ocr_company_name,
            "company_number": type_doc.ocr_company_number,
            "address": type_doc.ocr_address,
            "date": type_doc.ocr_date,
            "confidence": type_doc.ocr_confidence
        }
        response["companies_house_data"] = {
            "company_name": type_doc.companies_house_company_name,
            "company_number": type_doc.companies_house_company_number,
            "address": type_doc.companies_house_address,
            "date": type_doc.companies_house_date
        }
        response["scores"] = {
            "ocr_score": type_doc.ocr_score or 0.0,
            "registry_score": type_doc.registry_score or 0.0,
            "provided_score": type_doc.provided_score or 0.0,
            "final_score": type_doc.final_score or 0.0
        }
    elif isinstance(type_doc, VATRegistrationDocument):
        response["ocr_data"] = {
            "vat_number": type_doc.ocr_vat_number,
            "business_name": type_doc.ocr_business_name,
            "address": type_doc.ocr_vat_address,
            "registration_date": type_doc.ocr_vat_registration_date,
            "confidence": type_doc.ocr_confidence
        }
        response["hmrc_data"] = {
            "vat_number": type_doc.hmrc_vat_number,
            "business_name": type_doc.hmrc_business_name,
            "address": type_doc.hmrc_address,
            "registration_date": type_doc.hmrc_registration_date
        }
        response["scores"] = {
            "ocr_score": type_doc.ocr_score or 0.0,
            "registry_score": type_doc.registry_score or 0.0,
            "provided_score": type_doc.provided_score or 0.0,
            "final_score": type_doc.final_score or 0.0
        }
    elif isinstance(type_doc, DirectorVerificationDocument):
        # Get OCR company number from comparison_details if stored there
        ocr_company_number = None
        if type_doc.comparison_details and isinstance(type_doc.comparison_details, dict):
            ocr_company_number = type_doc.comparison_details.get("ocr_company_number")
        
        response["ocr_data"] = {
            "director_name": type_doc.ocr_director_name,
            "date_of_birth": type_doc.ocr_director_dob,
            "address": type_doc.ocr_director_address,
            "company_name": type_doc.ocr_director_company_name,
            "company_number": ocr_company_number,  # Add OCR-extracted company number
            "appointment_date": type_doc.ocr_appointment_date,
            "confidence": type_doc.ocr_confidence
        }
        response["companies_house_data"] = {
            "director_name": type_doc.companies_house_director_name,
            "date_of_birth": type_doc.companies_house_director_dob,
            "address": type_doc.companies_house_director_address,
            "appointment_date": type_doc.companies_house_appointment_date,
            "company_name": type_doc.companies_house_company_name,
            "company_number": type_doc.companies_house_company_number
        }
        response["scores"] = {
            "ocr_score": type_doc.ocr_score or 0.0,
            "registry_score": type_doc.registry_score or 0.0,
            "provided_score": type_doc.provided_score or 0.0,
            "final_score": type_doc.final_score or 0.0
        }
    else:
        # No type_doc or unknown type - provide defaults
        response["ocr_data"] = {
            "company_name": None,
            "company_number": None,
            "address": None,
            "date": None,
            "confidence": None
        }
        response["companies_house_data"] = {
            "company_name": None,
            "company_number": None,
            "address": None,
            "date": None
        }
        response["scores"] = {
            "ocr_score": 0.0,
            "registry_score": 0.0,
            "provided_score": 0.0,
            "final_score": 0.0
        }
    
    return response


@router.get("/")
async def list_documents(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    List all documents with pagination
    """
    from app.db.models import (
        Document,
        CompaniesHouseDocument,
        CompanyRegistrationDocument,
        VATRegistrationDocument,
        DirectorVerificationDocument
    )
    
    query = db.query(Document)
    
    if status:
        # Validate status against allowed values
        allowed_statuses = ["pending", "processing", "passed", "failed", "review", "manual_review"]
        if status not in allowed_statuses:
            raise HTTPException(status_code=400, detail="Invalid status")
        query = query.filter(Document.status == status)
    
    documents = query.order_by(
        Document.created_at.desc()
    ).offset(skip).limit(limit).all()
    
    # Get final scores from type-specific tables
    document_list = []
    for doc in documents:
        # Get final score from type-specific table
        final_score = 0.0
        if doc.document_type == DocumentType.COMPANIES_HOUSE.value:
            type_doc = db.query(CompaniesHouseDocument).filter(
                CompaniesHouseDocument.document_id == doc.document_id
            ).first()
            final_score = type_doc.final_score if type_doc else 0.0
        elif doc.document_type == DocumentType.COMPANY_REGISTRATION.value:
            type_doc = db.query(CompanyRegistrationDocument).filter(
                CompanyRegistrationDocument.document_id == doc.document_id
            ).first()
            final_score = type_doc.final_score if type_doc else 0.0
        elif doc.document_type == DocumentType.VAT_REGISTRATION.value:
            type_doc = db.query(VATRegistrationDocument).filter(
                VATRegistrationDocument.document_id == doc.document_id
            ).first()
            final_score = type_doc.final_score if type_doc else 0.0
        elif doc.document_type == DocumentType.DIRECTOR_VERIFICATION.value:
            type_doc = db.query(DirectorVerificationDocument).filter(
                DirectorVerificationDocument.document_id == doc.document_id
            ).first()
            final_score = type_doc.final_score if type_doc else 0.0
        
        document_list.append({
                "document_id": doc.document_id,
                "filename": doc.filename,
            "document_type": doc.document_type,
                "status": doc.status,
            "final_score": final_score,
                "decision": doc.decision,
                "created_at": doc.created_at.isoformat() if doc.created_at else None
        })
    
    return {
        "total": len(document_list),
        "documents": document_list
    }

