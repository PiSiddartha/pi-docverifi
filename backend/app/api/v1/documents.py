"""
Document upload and management endpoints
"""
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
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
from app.db.models import DocumentVerification
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
    document_type: str = "companies_house",  # Default to companies_house
    company_name: Optional[str] = None,
    company_number: Optional[str] = None,
    address: Optional[str] = None,
    date: Optional[str] = None,
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
    
    # Truncate merchant data to fit database column limits
    merchant_company_name = truncate_string(company_name, 500) if company_name else None
    merchant_company_number = truncate_string(company_number, 50) if company_number else None
    merchant_date = truncate_string(date, 50) if date else None
    
    # Validate document type
    from app.db.models import DocumentType
    valid_types = [dt.value for dt in DocumentType]
    if document_type not in valid_types:
        logger.warning(f"Invalid document type: {document_type}, defaulting to companies_house")
        document_type = DocumentType.COMPANIES_HOUSE.value
    
    # Create database record
    db_record = DocumentVerification(
        document_id=document_id,
        filename=file.filename,
        file_path=str(file_path),
        s3_key=s3_key,
        document_type=document_type,
        merchant_company_name=merchant_company_name,
        merchant_company_number=merchant_company_number,
        merchant_address=address,  # TEXT column, no truncation needed
        merchant_date=merchant_date,
        status="pending"
    )
    
    db.add(db_record)
    db.commit()
    db.refresh(db_record)
    
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
    document = db.query(DocumentVerification).filter(
        DocumentVerification.document_id == document_id
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {
        "document_id": document.document_id,
        "filename": document.filename,
        "status": document.status,
        "final_score": document.final_score,
        "decision": document.decision,
        "created_at": document.created_at.isoformat() if document.created_at else None,
        "processed_at": document.processed_at.isoformat() if document.processed_at else None,
        "ocr_data": {
            "company_name": document.ocr_company_name,
            "company_number": document.ocr_company_number,
            "address": document.ocr_address,
            "date": document.ocr_date,
            "confidence": document.ocr_confidence
        },
        "companies_house_data": {
            "company_name": document.companies_house_company_name,
            "company_number": document.companies_house_company_number,
            "address": document.companies_house_address,
            "date": document.companies_house_date
        },
        "forensic_analysis": {
            "forensic_score": document.forensic_score,
            "forensic_penalty": document.forensic_penalty,
            "ela_score": document.ela_score,
            "jpeg_quality": document.jpeg_quality,
            "copy_move_detected": document.copy_move_detected,
            "details": document.forensic_details
        },
        "scores": {
            "ocr_score": document.ocr_score,
            "registry_score": document.registry_score,
            "provided_score": document.provided_score,
            "final_score": document.final_score
        },
        "flags": document.flags
    }


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
    query = db.query(DocumentVerification)
    
    if status:
        # Validate status against allowed values
        allowed_statuses = ["pending", "processing", "passed", "failed", "review", "manual_review"]
        if status not in allowed_statuses:
            raise HTTPException(status_code=400, detail="Invalid status")
        query = query.filter(DocumentVerification.status == status)
    
    documents = query.order_by(
        DocumentVerification.created_at.desc()
    ).offset(skip).limit(limit).all()
    
    return {
        "total": len(documents),
        "documents": [
            {
                "document_id": doc.document_id,
                "filename": doc.filename,
                "status": doc.status,
                "final_score": doc.final_score,
                "decision": doc.decision,
                "created_at": doc.created_at.isoformat() if doc.created_at else None
            }
            for doc in documents
        ]
    }

