"""
Document verification processing endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from app.db.database import get_db
from app.db.models import Document, DocumentType
from app.db.document_helper import get_document_with_type
from app.services.pipeline_service import PipelineFactory
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
        result = get_document_with_type(db, document_id)
        
        if not result:
            logger.warning(f"[STEP 0] Document not found: {document_id}")
            return
        
        base_doc, type_doc = result
        
        if not base_doc:
            logger.warning(f"[STEP 0] Base document not found: {document_id}")
            return
        
        logger.info(f"[STEP 0] Document found. Current status: {base_doc.status}, filename: {base_doc.filename}")
        
        # Update status to processing
        logger.info(f"[STEP 0] Updating status to 'processing'")
        base_doc.status = "processing"
        db.commit()
        logger.info(f"[STEP 0] Status updated to 'processing'")
        
        # Emit progress update
        update_progress_sync("initializing", 5, "Starting document verification process", "processing")
        
        # Get file path - file_path should always be a local file path
        file_path = base_doc.file_path
        logger.info(f"[STEP 0] File path: {file_path}")
        logger.info(f"[STEP 0] S3 key: {base_doc.s3_key}")
        
        # Verify file exists locally
        if not file_path or not os.path.exists(file_path):
            logger.error(f"[STEP 0] File not found at path: {file_path}")
            base_doc.status = "failed"
            db.commit()
            return
        
        logger.info(f"[STEP 0] File exists. File size: {os.path.getsize(file_path)} bytes")
        
        update_progress_sync("file_validation", 10, "File validated successfully", "processing")
        
        # Determine document type and get appropriate pipeline
        document_type = base_doc.document_type or DocumentType.COMPANIES_HOUSE.value
        logger.info(f"[PIPELINE] Processing document type: {document_type}")
        update_progress_sync("pipeline_init", 15, f"Initializing {document_type} verification pipeline", "processing")
        
        # Create pipeline with progress callback
        # Pass both base_doc and type_doc to pipeline
        pipeline = PipelineFactory.create_pipeline(base_doc, type_doc, update_progress_sync)
        
        # Run the pipeline (progress updates happen inside the pipeline)
        try:
            pipeline_results = pipeline.process()
            # Commit both base_doc and type_doc changes
            db.commit()
            if type_doc:
                db.refresh(type_doc)
            db.refresh(base_doc)
            
            # Log results
            ocr_result = pipeline_results.get("ocr_result", {})
            forensic_result = pipeline_results.get("forensic_result", {})
            scoring_result = pipeline_results.get("scoring_result", {})
            
            # Log OCR extraction results based on document type
            document_type = base_doc.document_type or DocumentType.COMPANIES_HOUSE.value
            if document_type == DocumentType.DIRECTOR_VERIFICATION.value:
                logger.info(f"[STEP 1] OCR extraction completed. Director name: {ocr_result.get('director_name')}, Company name: {ocr_result.get('company_name')}, Company number: {ocr_result.get('company_number')}")
            elif document_type == DocumentType.VAT_REGISTRATION.value:
                logger.info(f"[STEP 1] OCR extraction completed. VAT number: {ocr_result.get('vat_number')}, Business name: {ocr_result.get('business_name')}")
            else:
                logger.info(f"[STEP 1] OCR extraction completed. Company name: {ocr_result.get('company_name')}, Company number: {ocr_result.get('company_number')}")
            logger.info(f"[STEP 2] Forensic analysis completed. Score: {forensic_result.get('forensic_score')}, Penalty: {forensic_result.get('forensic_penalty')}")
            
            # Refresh to get updated scores from type_doc
            if type_doc:
                db.refresh(type_doc)
            db.refresh(base_doc)
            
            final_score = type_doc.final_score if type_doc else 0.0
            logger.info(f"[STEP 4] Scores calculated. OCR: {type_doc.ocr_score if type_doc else 0.0}, Registry: {type_doc.registry_score if type_doc else 0.0}, Provided: {type_doc.provided_score if type_doc else 0.0}, Final: {final_score}, Decision: {base_doc.decision}")
                
        except Exception as pipeline_error:
            logger.error(f"[PIPELINE] Error in pipeline processing: {pipeline_error}", exc_info=True)
            # Set default scores if pipeline fails
            if type_doc:
                type_doc.ocr_score = 0.0
                type_doc.registry_score = 0.0
                type_doc.provided_score = 0.0
                type_doc.data_match_score = 0.0
                type_doc.final_score = 0.0
            base_doc.decision = "FAIL"
            db.commit()
            raise  # Re-raise to be caught by outer exception handler
        
        # Step 5: Update Status
        logger.info(f"[STEP 5] Updating final status...")
        if base_doc.decision == "PASS":
            base_doc.status = "passed"
            logger.info(f"[STEP 5] Status set to 'passed'")
        elif base_doc.decision == "FAIL":
            base_doc.status = "failed"
            logger.info(f"[STEP 5] Status set to 'failed'")
        elif base_doc.decision == "REVIEW":
            base_doc.status = "review"
            logger.info(f"[STEP 5] Status set to 'review'")
        
        base_doc.processed_at = datetime.utcnow()
        db.commit()
        
        # Refresh to get latest values
        db.refresh(base_doc)
        if type_doc:
            db.refresh(type_doc)
        
        # Get final values for logging
        final_score = type_doc.final_score if type_doc else 0.0
        ocr_score = type_doc.ocr_score if type_doc else 0.0
        registry_score = type_doc.registry_score if type_doc else 0.0
        provided_score = type_doc.provided_score if type_doc else 0.0
        data_match_score = type_doc.data_match_score if type_doc else 0.0
        forensic_penalty = base_doc.forensic_penalty or 0.0
        
        logger.info("")
        logger.info("╔" + "═" * 78 + "╗")
        logger.info("║" + " " * 15 + "VERIFICATION COMPLETE" + " " * 43 + "║")
        logger.info("╠" + "═" * 78 + "╣")
        logger.info(f"║ Document ID: {document_id:<66} ║")
        logger.info(f"║ Final Status: {base_doc.status:<66} ║")
        logger.info(f"║ Decision: {base_doc.decision:<66} ║")
        logger.info(f"║ Final Score: {final_score:.2f}{' ' * (66 - len(str(round(final_score, 2))))} ║")
        logger.info("╠" + "═" * 78 + "╣")
        logger.info("║" + " " * 25 + "SCORE BREAKDOWN" + " " * 38 + "║")
        logger.info("╠" + "─" * 78 + "╣")
        logger.info(f"║   OCR Score: {ocr_score:>10.2f}{' ' * 60} ║")
        logger.info(f"║   Registry Score: {registry_score:>10.2f}{' ' * 60} ║")
        logger.info(f"║   Provided Score: {provided_score:>10.2f}{' ' * 60} ║")
        logger.info(f"║   Data Match Score: {data_match_score:>10.2f}{' ' * 60} ║")
        logger.info(f"║   Forensic Penalty: {forensic_penalty:>10.2f}{' ' * 60} ║")
        logger.info("╠" + "═" * 78 + "╣")
        logger.info("║ NOTE: LLM token usage metrics are logged above during LLM extraction ║")
        logger.info("║       Look for 'LLM TOKEN USAGE METRICS' section in the logs above.  ║")
        logger.info("╚" + "═" * 78 + "╝")
        logger.info("")
        
        # Emit final progress update
        try:
            final_message = f"Verification complete. Status: {base_doc.status}, Score: {final_score:.1f}, Decision: {base_doc.decision}"
            update_progress_sync("complete", 100, final_message, base_doc.status)
            logger.info(f"[PROCESS COMPLETE] Final progress update sent")
        except Exception as progress_error:
            logger.warning(f"[PROCESS COMPLETE] Failed to send final progress update: {progress_error}")
        
    except Exception as e:
        logger.error(f"[ERROR] Error processing document {document_id}: {e}", exc_info=True)
        import traceback
        logger.error(f"[ERROR] Full traceback:\n{traceback.format_exc()}")
        
        if 'base_doc' in locals() and base_doc:
            try:
                logger.error(f"[ERROR] Setting document status to 'failed' due to error")
                # Refresh document to get latest state
                db.refresh(base_doc)
                base_doc.status = "failed"
                base_doc.decision = "FAIL"
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
    result = get_document_with_type(db, document_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Document not found")
    
    base_doc, _ = result
    
    if not base_doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # If already processing, return success (upload endpoint already started processing)
    if base_doc.status == "processing":
        return {
            "document_id": document_id,
            "status": "processing",
            "message": "Document is already being processed"
        }
    
    # If already completed, don't allow reprocessing unless explicitly needed
    if base_doc.status in ["passed", "failed"]:
        return {
            "document_id": document_id,
            "status": base_doc.status,
            "message": f"Document has already been processed with status: {base_doc.status}"
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
    result = get_document_with_type(db, document_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Document not found")
    
    base_doc, _ = result
    
    if not base_doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if base_doc.status != "review":
        raise HTTPException(
            status_code=400,
            detail="Document is not in review status"
        )
    
    if action not in ["APPROVE", "REJECT", "ESCALATE"]:
        raise HTTPException(status_code=400, detail="Invalid action")
    
    base_doc.reviewer_action = action
    base_doc.reviewer_notes = reviewer_notes
    base_doc.reviewer_id = reviewer_id
    
    if action == "APPROVE":
        base_doc.status = "passed"
        base_doc.decision = "PASS"
    elif action == "REJECT":
        base_doc.status = "failed"
        base_doc.decision = "FAIL"
    elif action == "ESCALATE":
        base_doc.status = "manual_review"
    
    db.commit()
    
    return {
        "document_id": document_id,
        "action": action,
        "status": base_doc.status,
        "message": f"Review action '{action}' applied"
    }

