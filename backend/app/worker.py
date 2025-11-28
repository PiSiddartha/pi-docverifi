"""
ECS Fargate Worker for processing documents from SQS queue
"""
import os
import json
import logging
import boto3
import time
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize SQS client
sqs = boto3.client('sqs', region_name=os.getenv('AWS_REGION', 'ap-south-1'))

# Import processing function
from app.api.v1.verification import process_document_verification


def process_message(message: Dict[str, Any]) -> bool:
    """
    Process a single SQS message
    
    Args:
        message: SQS message dictionary
        
    Returns:
        True if processing succeeded, False otherwise
    """
    try:
        body = json.loads(message['Body'])
        document_id = body.get('document_id')
        action = body.get('action', 'process')
        
        if not document_id:
            logger.error("Message missing document_id")
            return False
        
        if action == 'process':
            logger.info(f"Processing document: {document_id}")
            process_document_verification(document_id)
            logger.info(f"Successfully processed document: {document_id}")
            return True
        else:
            logger.warning(f"Unknown action: {action}")
            return False
            
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in message: {e}")
        return False
    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        return False


def main():
    """
    Main worker loop - polls SQS queue and processes messages
    """
    queue_url = os.getenv('SQS_QUEUE_URL')
    
    if not queue_url:
        logger.error("SQS_QUEUE_URL environment variable not set")
        return
    
    logger.info(f"Worker started. Polling queue: {queue_url}")
    
    while True:
        try:
            # Receive messages from SQS (long polling)
            response = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=20,  # Long polling
                VisibilityTimeout=900  # 15 minutes
            )
            
            if 'Messages' in response:
                for message in response['Messages']:
                    receipt_handle = message['ReceiptHandle']
                    
                    try:
                        # Process the message
                        success = process_message(message)
                        
                        if success:
                            # Delete message from queue on success
                            sqs.delete_message(
                                QueueUrl=queue_url,
                                ReceiptHandle=receipt_handle
                            )
                            logger.info("Message processed and deleted from queue")
                        else:
                            # On failure, message will become visible again after VisibilityTimeout
                            logger.warning("Message processing failed, will retry after visibility timeout")
                            
                    except Exception as e:
                        logger.error(f"Error handling message: {e}", exc_info=True)
                        # Message will become visible again after VisibilityTimeout
            else:
                # No messages, continue polling
                logger.debug("No messages in queue, continuing to poll...")
                
        except KeyboardInterrupt:
            logger.info("Worker interrupted, shutting down...")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)
            # Wait before retrying
            time.sleep(5)


if __name__ == "__main__":
    main()

