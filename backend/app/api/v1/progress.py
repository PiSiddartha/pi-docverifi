"""
Progress tracking endpoints for real-time updates
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.services.progress_service import progress_service
import asyncio
import json
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/progress/{document_id}")
async def stream_progress(document_id: str):
    """
    Server-Sent Events (SSE) endpoint for real-time progress updates
    """
    async def event_generator():
        queue = await progress_service.subscribe(document_id)
        
        try:
            while True:
                try:
                    # Wait for progress update with timeout
                    progress_data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    
                    # Format as SSE
                    data = json.dumps(progress_data)
                    yield f"data: {data}\n\n"
                    
                    # If status is terminal (passed, failed, review), close connection
                    if progress_data.get("status") in ["passed", "failed", "review", "manual_review"]:
                        logger.info(f"Progress complete for {document_id}, closing connection")
                        break
                        
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield ": keepalive\n\n"
                except Exception as e:
                    logger.error(f"Error in progress stream: {e}")
                    break
        finally:
            await progress_service.unsubscribe(document_id, queue)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/progress/{document_id}/current")
async def get_current_progress(document_id: str):
    """
    Get current progress for a document (one-time fetch)
    """
    progress = await progress_service.get_progress(document_id)
    
    if not progress:
        raise HTTPException(status_code=404, detail="No progress data found for this document")
    
    return progress

