"""
Document verification processing endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from app.db.database import get_db
from app.db.models import DocumentVerification
from app.services.ocr_service import OCRService
from app.services.forensic_service import ForensicService
from app.services.companies_house_service import CompaniesHouseService
from app.services.scoring_service import ScoringService
from app.services.s3_service import s3_service
from app.services.progress_service import progress_service
from app.core.config import settings
from pathlib import Path
import os
import asyncio

logger = logging.getLogger(__name__)
router = APIRouter()


def process_document_verification(document_id: str):
    """
    Background task to process document verification
    """
    logger.info(f"[PROCESS START] Starting verification for document_id: {document_id}")
    from app.db.database import SessionLocal
    db = SessionLocal()
    
    # Helper to run async progress updates
    def update_progress_sync(step: str, progress: int, message: str, status: str = None):
        try:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            loop.run_until_complete(
                progress_service.update_progress(document_id, step, progress, message, status)
            )
        except Exception as e:
            # Don't let progress update errors break the main process
            logger.warning(f"Failed to update progress: {e}")
    
    try:
        logger.info(f"[STEP 0] Looking up document in database: {document_id}")
        document = db.query(DocumentVerification).filter(
            DocumentVerification.document_id == document_id
        ).first()
        
        if not document:
            logger.warning(f"[STEP 0] Document not found: {document_id}")
            return
        
        logger.info(f"[STEP 0] Document found. Current status: {document.status}, filename: {document.filename}")
        
        # Update status to processing
        logger.info(f"[STEP 0] Updating status to 'processing'")
        document.status = "processing"
        db.commit()
        logger.info(f"[STEP 0] Status updated to 'processing'")
        
        # Emit progress update
        update_progress_sync("initializing", 5, "Starting document verification process", "processing")
        
        # Get file path - file_path should always be a local file path
        file_path = document.file_path
        logger.info(f"[STEP 0] File path: {file_path}")
        logger.info(f"[STEP 0] S3 key: {document.s3_key}")
        
        # Verify file exists locally
        if not file_path or not os.path.exists(file_path):
            logger.error(f"[STEP 0] File not found at path: {file_path}")
            document.status = "failed"
            db.commit()
            return
        
        logger.info(f"[STEP 0] File exists. File size: {os.path.getsize(file_path)} bytes")
        
        update_progress_sync("file_validation", 10, "File validated successfully", "processing")
        
        # Step 1: OCR Extraction
        logger.info(f"[STEP 1] Starting OCR extraction...")
        update_progress_sync("ocr_extraction", 20, "Extracting text and data from document using OCR", "processing")
        ocr_result = OCRService.process_document(file_path)
        logger.info(f"[STEP 1] OCR extraction completed. Company name: {ocr_result.get('company_name')}, Company number: {ocr_result.get('company_number')}")
        document.ocr_company_name = ocr_result.get("company_name")
        document.ocr_company_number = ocr_result.get("company_number")
        document.ocr_address = ocr_result.get("address")
        document.ocr_date = ocr_result.get("date")
        document.ocr_confidence = ocr_result.get("confidence")
        document.ocr_raw_text = ocr_result.get("raw_text")
        db.commit()
        logger.info(f"[STEP 1] OCR data saved to database")
        
        update_progress_sync("ocr_complete", 40, f"OCR completed. Company: {ocr_result.get('company_name', 'N/A')}", "processing")
        
        # Step 2: Forensic Analysis
        logger.info(f"[STEP 2] Starting forensic analysis...")
        update_progress_sync("forensic_analysis", 50, "Analyzing document for tampering and authenticity", "processing")
        forensic_result = ForensicService.process_document(file_path)
        logger.info(f"[STEP 2] Forensic analysis completed. Score: {forensic_result.get('forensic_score')}, Penalty: {forensic_result.get('forensic_penalty')}")
        document.forensic_score = forensic_result.get("forensic_score")
        document.forensic_penalty = forensic_result.get("forensic_penalty")
        document.forensic_details = forensic_result.get("details")
        document.exif_data = forensic_result.get("exif_data")
        document.ela_score = forensic_result.get("ela_score")
        document.jpeg_quality = forensic_result.get("jpeg_quality")
        document.copy_move_detected = forensic_result.get("copy_move_detected")
        db.commit()
        logger.info(f"[STEP 2] Forensic data saved to database")
        
        update_progress_sync("forensic_complete", 60, f"Forensic analysis complete. Score: {forensic_result.get('forensic_score', 'N/A')}", "processing")
        
        # Step 3: Companies House API Lookup
        logger.info(f"[STEP 3] Starting Companies House lookup...")
        update_progress_sync("companies_house_lookup", 70, "Looking up company information in Companies House registry", "processing")
        companies_house_service = CompaniesHouseService()
        company_number = None
        
        # Try to get company number from OCR or merchant input
        if document.ocr_company_number:
            company_number = document.ocr_company_number
            logger.info(f"[STEP 3] Using company number from OCR: {company_number}")
        elif document.merchant_company_number:
            company_number = document.merchant_company_number
            logger.info(f"[STEP 3] Using company number from merchant input: {company_number}")
        else:
            logger.info(f"[STEP 3] No company number found, skipping Companies House lookup")
        
        if company_number:
            # Normalize company number for API call (pad 7-digit to 8-digit if needed)
            # But keep original in database
            normalized_number = company_number
            if normalized_number.isdigit() and len(normalized_number) == 7:
                normalized_number = '0' + normalized_number
                logger.info(f"[STEP 3] Normalized company number for API: {company_number} -> {normalized_number}")
            
            logger.info(f"[STEP 3] Fetching data from Companies House API for: {normalized_number} (original: {company_number})")
            ch_data = companies_house_service.extract_company_data(normalized_number)
            logger.info(f"[STEP 3] Companies House data retrieved. Company name: {ch_data.get('company_name')}")
            document.companies_house_company_name = ch_data.get("company_name")
            document.companies_house_company_number = ch_data.get("company_number")
            document.companies_house_address = ch_data.get("address")
            document.companies_house_date = ch_data.get("date")
            document.companies_house_officers = ch_data.get("officers")
            document.companies_house_data = ch_data.get("data")
            db.commit()
            logger.info(f"[STEP 3] Companies House data saved to database")
            update_progress_sync("companies_house_complete", 80, f"Companies House lookup complete. Company: {ch_data.get('company_name', 'N/A')}", "processing")
        else:
            logger.info(f"[STEP 3] Companies House lookup skipped (no company number)")
            update_progress_sync("companies_house_skipped", 80, "Companies House lookup skipped (no company number found)", "processing")
        
        # Step 4: Calculate Scores
        logger.info(f"[STEP 4] Starting score calculation...")
        update_progress_sync("score_calculation", 90, "Calculating final verification scores", "processing")
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
        
        logger.info(f"[STEP 4] Calculating scores with forensic penalty: {document.forensic_penalty}")
        try:
            scoring_result = ScoringService.process_scoring(
                ocr_data,
                merchant_data,
                companies_house_data,
                document.forensic_penalty
            )
            
            if not scoring_result:
                logger.error("[STEP 4] Scoring service returned None")
                raise ValueError("Scoring service returned None")
            
            document.ocr_score = scoring_result.get("ocr_score", 0.0)
            document.registry_score = scoring_result.get("registry_score", 0.0)
            document.provided_score = scoring_result.get("provided_score", 0.0)
            document.data_match_score = scoring_result.get("data_match_score", 0.0)
            document.final_score = scoring_result.get("final_score", 0.0)
            document.decision = scoring_result.get("decision", "FAIL")
            db.commit()
            logger.info(f"[STEP 4] Scores calculated. OCR: {document.ocr_score}, Registry: {document.registry_score}, Provided: {document.provided_score}, Final: {document.final_score}, Decision: {document.decision}")
        except Exception as scoring_error:
            logger.error(f"[STEP 4] Error in scoring calculation: {scoring_error}", exc_info=True)
            # Set default scores if scoring fails
            document.ocr_score = 0.0
            document.registry_score = 0.0
            document.provided_score = 0.0
            document.data_match_score = 0.0
            document.final_score = 0.0
            document.decision = "FAIL"
            db.commit()
            raise  # Re-raise to be caught by outer exception handler
        
        # Step 5: Update Status
        logger.info(f"[STEP 5] Updating final status...")
        if document.decision == "PASS":
            document.status = "passed"
            logger.info(f"[STEP 5] Status set to 'passed'")
        elif document.decision == "FAIL":
            document.status = "failed"
            logger.info(f"[STEP 5] Status set to 'failed'")
        elif document.decision == "REVIEW":
            document.status = "review"
            logger.info(f"[STEP 5] Status set to 'review'")
        
        document.processed_at = datetime.utcnow()
        db.commit()
        logger.info(f"[PROCESS COMPLETE] Verification completed successfully. Final status: {document.status}, Decision: {document.decision}, Final Score: {document.final_score}")
        logger.info(f"[PROCESS COMPLETE] Breakdown - OCR: {document.ocr_score}, Registry: {document.registry_score}, Provided: {document.provided_score}, Forensic Penalty: {document.forensic_penalty}")
        
        # Emit final progress update
        try:
            final_message = f"Verification complete. Status: {document.status}, Score: {document.final_score:.1f}, Decision: {document.decision}"
            update_progress_sync("complete", 100, final_message, document.status)
            logger.info(f"[PROCESS COMPLETE] Final progress update sent")
        except Exception as progress_error:
            logger.warning(f"[PROCESS COMPLETE] Failed to send final progress update: {progress_error}")
        
    except Exception as e:
        logger.error(f"[ERROR] Error processing document {document_id}: {e}", exc_info=True)
        import traceback
        logger.error(f"[ERROR] Full traceback:\n{traceback.format_exc()}")
        
        if 'document' in locals() and document:
            try:
                logger.error(f"[ERROR] Setting document status to 'failed' due to error")
                # Refresh document to get latest state
                db.refresh(document)
                document.status = "failed"
                document.decision = "FAIL"
                db.commit()
                logger.info(f"[ERROR] Document status updated to 'failed'")
            except Exception as db_error:
                logger.error(f"[ERROR] Failed to update document status: {db_error}")
                db.rollback()
            
            # Emit error progress update
            try:
                update_progress_sync("error", 0, f"Verification failed: {str(e)}", "failed")
            except Exception as progress_error:
                logger.warning(f"[ERROR] Failed to send error progress update: {progress_error}")
    finally:
        try:
            db.close()
            logger.info(f"[CLEANUP] Database connection closed for document_id: {document_id}")
        except:
            pass


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
    
    # If already processing, return success (upload endpoint already started processing)
    if document.status == "processing":
        return {
            "document_id": document_id,
            "status": "processing",
            "message": "Document is already being processed"
        }
    
    # If already completed, don't allow reprocessing unless explicitly needed
    if document.status in ["passed", "failed"]:
        return {
            "document_id": document_id,
            "status": document.status,
            "message": f"Document has already been processed with status: {document.status}"
        }
    
    # Add background task
    logger.info(f"[PROCESS ENDPOINT] Starting background processing task for document_id: {document_id}")
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

