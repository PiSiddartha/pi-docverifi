"""
Document verification processing endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.database import get_db
from app.db.models import DocumentVerification
from app.services.ocr_service import OCRService
from app.services.forensic_service import ForensicService
from app.services.companies_house_service import CompaniesHouseService
from app.services.scoring_service import ScoringService
from app.services.s3_service import s3_service
from app.core.config import settings
from pathlib import Path
import tempfile
import os

router = APIRouter()


def process_document_verification(document_id: str):
    """
    Background task to process document verification
    """
    from app.db.database import SessionLocal
    db = SessionLocal()
    
    try:
        document = db.query(DocumentVerification).filter(
            DocumentVerification.document_id == document_id
        ).first()
        
        if not document:
            return
        
        # Update status to processing
        document.status = "processing"
        db.commit()
        
        # Get file path - download from S3 if needed
        file_path = document.file_path
        temp_file = None
        
        if document.s3_key and s3_service.is_enabled():
            # Download from S3 to temp file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=Path(document.filename).suffix)
            temp_file.close()
            
            if s3_service.download_file(document.s3_key, temp_file.name):
                file_path = temp_file.name
            else:
                # Fallback to local file if S3 download fails
                if not document.file_path or not os.path.exists(document.file_path):
                    document.status = "failed"
                    db.commit()
                    return
        
        # Step 1: OCR Extraction
        ocr_result = OCRService.process_document(file_path)
        document.ocr_company_name = ocr_result.get("company_name")
        document.ocr_company_number = ocr_result.get("company_number")
        document.ocr_address = ocr_result.get("address")
        document.ocr_date = ocr_result.get("date")
        document.ocr_confidence = ocr_result.get("confidence")
        document.ocr_raw_text = ocr_result.get("raw_text")
        db.commit()
        
        # Step 2: Forensic Analysis
        forensic_result = ForensicService.process_document(file_path)
        document.forensic_score = forensic_result.get("forensic_score")
        document.forensic_penalty = forensic_result.get("forensic_penalty")
        document.forensic_details = forensic_result.get("details")
        document.exif_data = forensic_result.get("exif_data")
        document.ela_score = forensic_result.get("ela_score")
        document.jpeg_quality = forensic_result.get("jpeg_quality")
        document.copy_move_detected = forensic_result.get("copy_move_detected")
        db.commit()
        
        # Step 3: Companies House API Lookup
        companies_house_service = CompaniesHouseService()
        company_number = None
        
        # Try to get company number from OCR or merchant input
        if document.ocr_company_number:
            company_number = document.ocr_company_number
        elif document.merchant_company_number:
            company_number = document.merchant_company_number
        
        if company_number:
            ch_data = companies_house_service.extract_company_data(company_number)
            document.companies_house_company_name = ch_data.get("company_name")
            document.companies_house_company_number = ch_data.get("company_number")
            document.companies_house_address = ch_data.get("address")
            document.companies_house_date = ch_data.get("date")
            document.companies_house_officers = ch_data.get("officers")
            document.companies_house_data = ch_data.get("data")
            db.commit()
        
        # Step 4: Calculate Scores
        ocr_data = {
            "company_name": document.ocr_company_name,
            "company_number": document.ocr_company_number,
            "address": document.ocr_address,
            "date": document.ocr_date,
            "confidence": document.ocr_confidence
        }
        
        merchant_data = {
            "company_name": document.merchant_company_name,
            "company_number": document.merchant_company_number,
            "address": document.merchant_address,
            "date": document.merchant_date
        }
        
        companies_house_data = {
            "company_name": document.companies_house_company_name,
            "company_number": document.companies_house_company_number,
            "address": document.companies_house_address,
            "date": document.companies_house_date
        }
        
        scoring_result = ScoringService.process_scoring(
            ocr_data,
            merchant_data,
            companies_house_data,
            document.forensic_penalty
        )
        
        document.ocr_score = scoring_result.get("ocr_score")
        document.registry_score = scoring_result.get("registry_score")
        document.provided_score = scoring_result.get("provided_score")
        document.data_match_score = scoring_result.get("data_match_score")
        document.final_score = scoring_result.get("final_score")
        document.decision = scoring_result.get("decision")
        db.commit()
        
        # Step 5: Update Status
        if document.decision == "PASS":
            document.status = "passed"
        elif document.decision == "FAIL":
            document.status = "failed"
        elif document.decision == "REVIEW":
            document.status = "review"
        
        document.processed_at = datetime.utcnow()
        db.commit()
        
        # Cleanup temp file if downloaded from S3
        if temp_file and os.path.exists(temp_file.name):
            os.remove(temp_file.name)
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error processing document {document_id}: {e}")
        
        if 'document' in locals() and document:
            document.status = "failed"
            document.decision = "FAIL"
            db.commit()
        
        # Cleanup temp file on error
        if 'temp_file' in locals() and temp_file and os.path.exists(temp_file.name):
            try:
                os.remove(temp_file.name)
            except:
                pass
    finally:
        db.close()


@router.post("/process/{document_id}")
async def process_verification(
    document_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Trigger document verification processing
    """
    document = db.query(DocumentVerification).filter(
        DocumentVerification.document_id == document_id
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.status == "processing":
        raise HTTPException(status_code=400, detail="Document is already being processed")
    
    # Add background task
    background_tasks.add_task(process_document_verification, document_id)
    
    return {
        "document_id": document_id,
        "status": "processing",
        "message": "Verification process started"
    }


@router.post("/review/{document_id}")
async def manual_review(
    document_id: str,
    action: str,  # "APPROVE", "REJECT", "ESCALATE"
    reviewer_notes: str = None,
    reviewer_id: str = None,
    db: Session = Depends(get_db)
):
    """
    Manual review action for documents in review status
    """
    document = db.query(DocumentVerification).filter(
        DocumentVerification.document_id == document_id
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.status != "review":
        raise HTTPException(
            status_code=400,
            detail="Document is not in review status"
        )
    
    if action not in ["APPROVE", "REJECT", "ESCALATE"]:
        raise HTTPException(status_code=400, detail="Invalid action")
    
    document.reviewer_action = action
    document.reviewer_notes = reviewer_notes
    document.reviewer_id = reviewer_id
    
    if action == "APPROVE":
        document.status = "passed"
        document.decision = "PASS"
    elif action == "REJECT":
        document.status = "failed"
        document.decision = "FAIL"
    elif action == "ESCALATE":
        document.status = "manual_review"
    
    db.commit()
    
    return {
        "document_id": document_id,
        "action": action,
        "status": document.status,
        "message": f"Review action '{action}' applied"
    }

