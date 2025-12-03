"""
Lambda handler that processes SQS messages and triggers document processing
on the ECS Fargate backend service
"""
import json
import os
import logging
import boto3
import requests
from typing import Dict, Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Get ALB DNS name from environment
ALB_DNS_NAME = os.environ.get("ALB_DNS_NAME", "")
ALB_URL = f"http://{ALB_DNS_NAME}" if ALB_DNS_NAME else None


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Process SQS messages and trigger document processing on ECS backend
    
    Event structure from SQS:
    {
        "Records": [
            {
                "body": "{\"document_id\": \"...\", \"action\": \"process\"}",
                ...
            }
        ]
    }
    """
    logger.info(f"Received event: {json.dumps(event)}")
    
    results = []
    
    for record in event.get("Records", []):
        try:
            # Parse SQS message body
            message_body = json.loads(record["body"])
            document_id = message_body.get("document_id")
            action = message_body.get("action", "process")
            
            if not document_id:
                logger.error("Missing document_id in message")
                results.append({
                    "success": False,
                    "error": "Missing document_id",
                })
                continue
            
            logger.info(f"Processing document_id: {document_id}, action: {action}")
            
            # Call ECS backend via ALB
            if ALB_URL:
                success = call_backend_via_alb(document_id, action)
            else:
                logger.error("ALB_DNS_NAME not configured")
                success = False
            
            results.append({
                "success": success,
                "document_id": document_id,
            })
            
        except Exception as e:
            logger.error(f"Error processing record: {str(e)}", exc_info=True)
            results.append({
                "success": False,
                "error": str(e),
            })
    
    return {
        "statusCode": 200,
        "body": json.dumps({
            "processed": len(results),
            "results": results,
        }),
    }


def call_backend_via_alb(document_id: str, action: str) -> bool:
    """
    Call the ECS backend service via Application Load Balancer
    """
    if not ALB_URL:
        logger.error("ALB_DNS_NAME not configured")
        return False
    
    try:
        # Call the processing endpoint
        process_url = f"{ALB_URL}/api/v1/verification/process/{document_id}"
        
        logger.info(f"Calling backend at: {process_url}")
        
        response = requests.post(
            process_url,
            json={"action": action},
            timeout=300,  # 5 minutes timeout
            headers={"Content-Type": "application/json"},
        )
        
        response.raise_for_status()
        logger.info(f"Successfully processed document {document_id}: {response.status_code}")
        return True
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to call backend: {str(e)}")
        return False

