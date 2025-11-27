"""
Progress tracking service for document verification
"""
import asyncio
from typing import Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ProgressService:
    """Service for tracking and broadcasting progress updates"""
    
    def __init__(self):
        # Store active connections: {document_id: [queue1, queue2, ...]}
        self._connections: Dict[str, list] = {}
        # Store progress data: {document_id: {step, progress, message, timestamp}}
        self._progress_data: Dict[str, dict] = {}
        self._lock = asyncio.Lock()
    
    async def subscribe(self, document_id: str) -> asyncio.Queue:
        """Subscribe to progress updates for a document"""
        async with self._lock:
            if document_id not in self._connections:
                self._connections[document_id] = []
            
            queue = asyncio.Queue()
            self._connections[document_id].append(queue)
            logger.info(f"New subscriber for document {document_id}. Total subscribers: {len(self._connections[document_id])}")
            
            # Send current progress if available
            if document_id in self._progress_data:
                await queue.put(self._progress_data[document_id])
            
            return queue
    
    async def unsubscribe(self, document_id: str, queue: asyncio.Queue):
        """Unsubscribe from progress updates"""
        async with self._lock:
            if document_id in self._connections:
                try:
                    self._connections[document_id].remove(queue)
                    logger.info(f"Unsubscribed from document {document_id}. Remaining subscribers: {len(self._connections[document_id])}")
                    
                    # Clean up if no more subscribers
                    if not self._connections[document_id]:
                        del self._connections[document_id]
                except ValueError:
                    pass
    
    async def update_progress(
        self, 
        document_id: str, 
        step: str, 
        progress: int, 
        message: str,
        status: Optional[str] = None
    ):
        """Update progress for a document and broadcast to all subscribers"""
        progress_data = {
            "document_id": document_id,
            "step": step,
            "progress": progress,  # 0-100
            "message": message,
            "status": status,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        async with self._lock:
            self._progress_data[document_id] = progress_data
        
        # Broadcast to all subscribers
        if document_id in self._connections:
            disconnected = []
            for queue in self._connections[document_id]:
                try:
                    await queue.put(progress_data)
                except Exception as e:
                    logger.error(f"Error sending progress update: {e}")
                    disconnected.append(queue)
            
            # Remove disconnected queues
            for queue in disconnected:
                try:
                    self._connections[document_id].remove(queue)
                except ValueError:
                    pass
    
    async def get_progress(self, document_id: str) -> Optional[dict]:
        """Get current progress for a document"""
        async with self._lock:
            return self._progress_data.get(document_id)
    
    async def clear_progress(self, document_id: str):
        """Clear progress data for a document"""
        async with self._lock:
            if document_id in self._progress_data:
                del self._progress_data[document_id]
            if document_id in self._connections:
                del self._connections[document_id]


# Global instance
progress_service = ProgressService()

