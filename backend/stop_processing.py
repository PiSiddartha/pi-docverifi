#!/usr/bin/env python3
"""
Script to stop all ongoing document verification processes
"""
import sys
import os
from pathlib import Path

# Add the backend directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from app.db.database import SessionLocal
from app.db.models import DocumentVerification
from sqlalchemy import update
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def stop_all_processing():
    """Stop all documents that are currently in 'processing' status"""
    db = SessionLocal()
    
    try:
        # Find all documents in processing status
        processing_docs = db.query(DocumentVerification).filter(
            DocumentVerification.status == "processing"
        ).all()
        
        if not processing_docs:
            logger.info("No documents currently in processing status")
            return
        
        logger.info(f"Found {len(processing_docs)} document(s) in processing status")
        
        # Update status to failed
        result = db.execute(
            update(DocumentVerification)
            .where(DocumentVerification.status == "processing")
            .values(status="failed", decision="FAIL")
        )
        db.commit()
        
        logger.info(f"Stopped {result.rowcount} document verification process(es)")
        logger.info("All processing documents have been set to 'failed' status")
        
        # List the stopped documents
        for doc in processing_docs:
            logger.info(f"  - Document ID: {doc.document_id}, Filename: {doc.filename}")
            
    except Exception as e:
        logger.error(f"Error stopping processes: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def stop_specific_document(document_id: str):
    """Stop processing for a specific document"""
    db = SessionLocal()
    
    try:
        document = db.query(DocumentVerification).filter(
            DocumentVerification.document_id == document_id
        ).first()
        
        if not document:
            logger.error(f"Document not found: {document_id}")
            return False
        
        if document.status != "processing":
            logger.warning(f"Document {document_id} is not in processing status (current: {document.status})")
            return False
        
        document.status = "failed"
        document.decision = "FAIL"
        db.commit()
        
        logger.info(f"Stopped processing for document: {document_id} ({document.filename})")
        return True
        
    except Exception as e:
        logger.error(f"Error stopping document: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Stop document verification processes")
    parser.add_argument(
        "--document-id",
        type=str,
        help="Stop processing for a specific document ID"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Stop all ongoing processes"
    )
    
    args = parser.parse_args()
    
    if args.document_id:
        stop_specific_document(args.document_id)
    elif args.all:
        stop_all_processing()
    else:
        parser.print_help()
        sys.exit(1)

