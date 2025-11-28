"""
OCR Service for extracting text from documents using AWS Textract
"""
import boto3
from botocore.exceptions import ClientError, BotoCoreError
from typing import Dict, Optional, Tuple
import re
import logging
import os
import time
import uuid
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

# Try to import settings, but don't fail if not available
try:
    from app.core.config import settings
    HAS_SETTINGS = True
except ImportError:
    HAS_SETTINGS = False

# Try to import S3 service, but don't fail if not available
try:
    from app.services.s3_service import s3_service
    HAS_S3_SERVICE = True
except ImportError:
    HAS_S3_SERVICE = False
    s3_service = None

# Try to import pdf2image for PDF to image conversion fallback
try:
    import pdf2image
    from PIL import Image
    HAS_PDF2IMAGE = True
except ImportError:
    HAS_PDF2IMAGE = False
    logger.warning("pdf2image not available. PDF to image fallback will not work.")

# Try to import LLM service for field extraction
try:
    from app.services.llm_service import LLMService
    HAS_LLM_SERVICE = True
except ImportError:
    HAS_LLM_SERVICE = False
    logger.warning("LLM service not available. Will use regex-based extraction.")


class OCRService:
    """Service for OCR extraction from PDFs and images using AWS Textract"""
    
    _textract_client = None
    
    @classmethod
    def _get_textract_client(cls):
        """Get or initialize AWS Textract client (singleton pattern)"""
        if cls._textract_client is None:
            try:
                # Get AWS credentials from config settings or environment
                if HAS_SETTINGS:
                    aws_access_key_id = settings.AWS_ACCESS_KEY_ID or os.getenv('AWS_ACCESS_KEY_ID', '')
                    aws_secret_access_key = settings.AWS_SECRET_ACCESS_KEY or os.getenv('AWS_SECRET_ACCESS_KEY', '')
                    aws_region = settings.AWS_REGION or os.getenv('AWS_REGION', 'us-east-1')
                else:
                    aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID', '')
                    aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY', '')
                    aws_region = os.getenv('AWS_REGION', 'us-east-1')
                
                if aws_access_key_id and aws_secret_access_key:
                    cls._textract_client = boto3.client(
                        'textract',
                        aws_access_key_id=aws_access_key_id,
                        aws_secret_access_key=aws_secret_access_key,
                        region_name=aws_region
                    )
                else:
                    # Try to use default credentials (IAM role, ~/.aws/credentials, etc.)
                    cls._textract_client = boto3.client('textract', region_name=aws_region)
                
                logger.info(f"AWS Textract client initialized for region: {aws_region}")
            except Exception as e:
                logger.error(f"Error initializing AWS Textract client: {e}")
                cls._textract_client = None
        
        return cls._textract_client
    
    @staticmethod
    def _extract_text_from_blocks(blocks: list) -> Tuple[str, float]:
        """
        Extract text and confidence from Textract blocks
        Helper method used by both sync and async processing
        """
        all_confidences = []
        
        # Extract LINE blocks and sort by geometry (top to bottom, left to right)
        line_blocks = []
        for block in blocks:
            if block['BlockType'] == 'LINE':
                text = block.get('Text', '')
                confidence = block.get('Confidence', 0.0)
                if text.strip():
                    # Get geometry for sorting
                    geometry = block.get('Geometry', {})
                    bounding_box = geometry.get('BoundingBox', {})
                    top = bounding_box.get('Top', 0)
                    left = bounding_box.get('Left', 0)
                    line_blocks.append({
                        'text': text,
                        'confidence': confidence,
                        'top': top,
                        'left': left,
                        'page': block.get('Page', 1)
                    })
                    all_confidences.append(confidence)
        
        # Sort by page, then by top position, then by left position
        line_blocks.sort(key=lambda x: (x['page'], x['top'], x['left']))
        
        # Combine text blocks maintaining reading order
        full_text = '\n'.join([block['text'] for block in line_blocks])
        
        # Calculate average confidence
        avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0
        
        return full_text, avg_confidence
    
    @staticmethod
    def _validate_pdf(pdf_bytes: bytes) -> Tuple[bool, Optional[str]]:
        """
        Validate PDF format
        Returns: (is_valid, error_message)
        """
        try:
            # Check PDF header
            if not pdf_bytes.startswith(b'%PDF'):
                return False, "File does not have valid PDF header"
            
            # Check for encryption (encrypted PDFs may not work with Textract)
            if b'/Encrypt' in pdf_bytes[:5000]:  # Check first 5KB for encryption marker
                return False, "PDF appears to be encrypted/password protected"
            
            return True, None
        except Exception as e:
            logger.warning(f"Error validating PDF: {e}")
            return True, None  # Assume valid if we can't check
    
    @staticmethod
    def _convert_pdf_to_images(pdf_path: str, dpi: int = 200) -> Optional[list]:
        """
        Convert PDF to images as fallback - OPTIMIZED for speed
        Uses lower DPI (200 instead of 300) and JPEG format for faster processing
        Returns list of image file paths or None
        """
        if not HAS_PDF2IMAGE:
            logger.error("pdf2image not available, cannot convert PDF to images")
            return None
        
        try:
            logger.info(f"Converting PDF to images (optimized, DPI={dpi}): {pdf_path}")
            start_time = time.time()
            
            # Use lower DPI for faster conversion (200 is sufficient for Textract)
            # Use thread_count for parallel page processing if available
            try:
                images = pdf2image.convert_from_path(
                    pdf_path, 
                    dpi=dpi,
                    thread_count=4,  # Parallel processing
                    fmt='jpeg',  # JPEG is faster than PNG
                    jpegopt={'quality': 85, 'optimize': True}  # Good quality, optimized
                )
            except TypeError:
                # Fallback if thread_count not supported
                images = pdf2image.convert_from_path(pdf_path, dpi=dpi, fmt='jpeg')
            
            if not images:
                logger.warning("PDF conversion returned no images")
                return None
            
            conversion_time = time.time() - start_time
            logger.info(f"PDF conversion took {conversion_time:.2f}s for {len(images)} pages")
            
            # Save images in parallel for speed
            temp_image_paths = []
            def save_image(i, image):
                temp_fd, temp_path = tempfile.mkstemp(suffix='.jpg', prefix=f'textract_page_{i}_')
                os.close(temp_fd)
                # Save as JPEG for speed (much faster than PNG)
                image.save(temp_path, "JPEG", quality=85, optimize=True)
                return temp_path
            
            # Use ThreadPoolExecutor for parallel image saving
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {executor.submit(save_image, i, img): i for i, img in enumerate(images)}
                for future in as_completed(futures):
                    try:
                        temp_path = future.result()
                        temp_image_paths.append(temp_path)
                    except Exception as e:
                        logger.error(f"Error saving image: {e}")
            
            # Sort by page number to maintain order
            temp_image_paths.sort(key=lambda x: int(x.split('_')[-1].split('.')[0]) if x.split('_')[-1].split('.')[0].isdigit() else 0)
            
            total_time = time.time() - start_time
            logger.info(f"Converted PDF to {len(temp_image_paths)} images in {total_time:.2f}s (avg {total_time/len(images):.2f}s per page)")
            return temp_image_paths
        except Exception as e:
            logger.error(f"Error converting PDF to images: {e}")
            return None
    
    @staticmethod
    def _process_single_image(textract_client, image_path: str, page_num: int, total_pages: int) -> Tuple[Optional[str], float]:
        """
        Process a single image with Textract - optimized for parallel processing
        """
        try:
            with open(image_path, 'rb') as img_file:
                image_bytes = img_file.read()
            
            response = textract_client.detect_document_text(
                Document={'Bytes': image_bytes}
            )
            
            blocks = response.get('Blocks', [])
            page_text, page_confidence = OCRService._extract_text_from_blocks(blocks)
            
            return page_text, page_confidence
        except Exception as e:
            logger.error(f"Error processing image page {page_num}: {e}")
            return None, 0.0
        finally:
            # Clean up temp image file immediately after processing
            try:
                os.unlink(image_path)
            except:
                pass
    
    @staticmethod
    def _extract_text_from_images(textract_client, image_paths: list) -> Tuple[str, float]:
        """
        Extract text from multiple images using Textract - OPTIMIZED with parallel processing
        """
        if not image_paths:
            return "", 0.0
        
        start_time = time.time()
        logger.info(f"Processing {len(image_paths)} images in parallel...")
        
        all_results = []
        
        # Process images in parallel for maximum speed
        # Textract API calls are I/O bound, so parallel processing significantly speeds things up
        with ThreadPoolExecutor(max_workers=min(5, len(image_paths))) as executor:
            # Submit all tasks
            futures = {
                executor.submit(
                    OCRService._process_single_image,
                    textract_client,
                    img_path,
                    i,
                    len(image_paths)
                ): i for i, img_path in enumerate(image_paths)
            }
            
            # Collect results as they complete
            results_dict = {}
            for future in as_completed(futures):
                page_num = futures[future]
                try:
                    page_text, page_confidence = future.result()
                    results_dict[page_num] = (page_text, page_confidence)
                except Exception as e:
                    logger.error(f"Error processing page {page_num}: {e}")
                    results_dict[page_num] = (None, 0.0)
        
        # Reconstruct in page order
        all_text_parts = []
        all_confidences = []
        for i in range(len(image_paths)):
            if i in results_dict:
                page_text, page_confidence = results_dict[i]
                if page_text:
                    all_text_parts.append(page_text)
                    if page_confidence > 0:
                        all_confidences.append(page_confidence)
        
        full_text = '\n\n'.join(all_text_parts)  # Separate pages with double newline
        avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0
        
        processing_time = time.time() - start_time
        logger.info(f"Processed {len(image_paths)} images in {processing_time:.2f}s (avg {processing_time/len(image_paths):.2f}s per page)")
        
        return full_text, avg_confidence
    
    @staticmethod
    def _extract_text_sync(textract_client, pdf_bytes: bytes, pdf_path: Optional[str] = None) -> Tuple[str, float]:
        """
        Extract text using synchronous Textract analyze_document API
        Used for files <= 5MB
        Falls back to image conversion if PDF format is unsupported
        OPTIMIZED: Fast fallback with parallel processing
        """
        logger.info("Using synchronous Textract API (detect_document_text)")
        
        # Quick validation - check if PDF looks problematic
        # If we detect it will likely fail, skip straight to image conversion
        quick_check_failed = False
        try:
            # Check for common issues that cause Textract to reject PDFs
            if b'/XObject' in pdf_bytes[:10000] and b'/Image' in pdf_bytes[:10000]:
                # PDF with embedded images - might work, but could be slow
                pass
            # Check for very old PDF versions that Textract might not support
            if b'%PDF-1.0' in pdf_bytes[:100] or b'%PDF-1.1' in pdf_bytes[:100]:
                logger.info("Detected old PDF version - may need image conversion")
        except:
            pass
        
        # Try Textract first (it's fastest if it works)
        try:
            sync_start = time.time()
            response = textract_client.detect_document_text(
                Document={'Bytes': pdf_bytes}
            )
            sync_time = time.time() - sync_start
            logger.info(f"Textract sync processing completed in {sync_time:.2f}s")
            
            blocks = response.get('Blocks', [])
            return OCRService._extract_text_from_blocks(blocks)
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            
            # If PDF format is unsupported, try optimized fallback
            if error_code == 'UnsupportedDocumentException' and pdf_path and HAS_PDF2IMAGE:
                logger.warning(f"Textract rejected PDF format: {error_message}")
                logger.info("Switching to optimized parallel image processing...")
                fallback_start = time.time()
                image_paths = OCRService._convert_pdf_to_images(pdf_path, dpi=200)  # Lower DPI for speed
                if image_paths:
                    result = OCRService._extract_text_from_images(textract_client, image_paths)
                    fallback_time = time.time() - fallback_start
                    logger.info(f"Optimized fallback completed in {fallback_time:.2f}s (total: {fallback_time:.2f}s)")
                    return result
                else:
                    logger.error("Failed to convert PDF to images for fallback processing")
                    return "", 0.0
            else:
                raise
    
    @staticmethod
    def _extract_text_async(textract_client, pdf_path: str, s3_bucket: str, s3_key: Optional[str] = None) -> Tuple[str, float]:
        """
        Extract text using asynchronous Textract start_document_analysis API
        Used for files > 5MB. Requires S3.
        
        Args:
            textract_client: Textract client
            pdf_path: Local path to PDF file
            s3_bucket: S3 bucket name
            s3_key: Optional S3 key (if file already in S3)
        
        Returns:
            Tuple of (text, confidence)
        """
        logger.info("Using asynchronous Textract API (start_document_text_detection)")
        
        # Generate S3 key if not provided
        if not s3_key:
            file_name = Path(pdf_path).name
            s3_key = f"textract-temp/{uuid.uuid4()}/{file_name}"
        
        # Upload file to S3 if not already there
        uploaded_to_s3 = False
        try:
            if HAS_S3_SERVICE and s3_service.is_enabled():
                # Use existing S3 service
                s3_url = s3_service.upload_file(pdf_path, s3_key)
                if s3_url:
                    uploaded_to_s3 = True
                    logger.info(f"File uploaded to S3 for Textract: {s3_key}")
                else:
                    raise Exception("Failed to upload file to S3")
            else:
                # Upload directly using boto3 with same credentials as Textract
                if HAS_SETTINGS:
                    aws_access_key_id = settings.AWS_ACCESS_KEY_ID or os.getenv('AWS_ACCESS_KEY_ID', '')
                    aws_secret_access_key = settings.AWS_SECRET_ACCESS_KEY or os.getenv('AWS_SECRET_ACCESS_KEY', '')
                    aws_region = settings.AWS_REGION or os.getenv('AWS_REGION', 'us-east-1')
                else:
                    aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID', '')
                    aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY', '')
                    aws_region = os.getenv('AWS_REGION', 'us-east-1')
                
                if aws_access_key_id and aws_secret_access_key:
                    s3_client = boto3.client(
                        's3',
                        aws_access_key_id=aws_access_key_id,
                        aws_secret_access_key=aws_secret_access_key,
                        region_name=aws_region
                    )
                else:
                    s3_client = boto3.client('s3', region_name=aws_region)
                
                with open(pdf_path, 'rb') as f:
                    s3_client.upload_fileobj(f, s3_bucket, s3_key)
                uploaded_to_s3 = True
                logger.info(f"File uploaded to S3 for Textract: {s3_key}")
        except Exception as e:
            logger.error(f"Failed to upload file to S3: {e}")
            if uploaded_to_s3:
                # Try to clean up
                try:
                    if HAS_S3_SERVICE and s3_service.is_enabled():
                        s3_service.delete_file(s3_key)
                    else:
                        # Use same credentials as Textract
                        if HAS_SETTINGS:
                            aws_access_key_id = settings.AWS_ACCESS_KEY_ID or os.getenv('AWS_ACCESS_KEY_ID', '')
                            aws_secret_access_key = settings.AWS_SECRET_ACCESS_KEY or os.getenv('AWS_SECRET_ACCESS_KEY', '')
                            aws_region = settings.AWS_REGION or os.getenv('AWS_REGION', 'us-east-1')
                        else:
                            aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID', '')
                            aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY', '')
                            aws_region = os.getenv('AWS_REGION', 'us-east-1')
                        
                        if aws_access_key_id and aws_secret_access_key:
                            s3_client = boto3.client(
                                's3',
                                aws_access_key_id=aws_access_key_id,
                                aws_secret_access_key=aws_secret_access_key,
                                region_name=aws_region
                            )
                        else:
                            s3_client = boto3.client('s3', region_name=aws_region)
                        s3_client.delete_object(Bucket=s3_bucket, Key=s3_key)
                except:
                    pass
            return "", 0.0
        
        try:
            # Start async Textract job
            logger.info(f"Starting Textract async job for S3 object: s3://{s3_bucket}/{s3_key}")
            try:
                response = textract_client.start_document_text_detection(
                    DocumentLocation={
                        'S3Object': {
                            'Bucket': s3_bucket,
                            'Name': s3_key
                        }
                    }
                )
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                error_message = e.response.get('Error', {}).get('Message', str(e))
                
                # If PDF format is unsupported, try fallback to image conversion
                if error_code == 'UnsupportedDocumentException' and HAS_PDF2IMAGE:
                    logger.warning(f"Textract rejected PDF format in async mode: {error_message}")
                    logger.info("Attempting fallback: converting PDF to images for async processing")
                    image_paths = OCRService._convert_pdf_to_images(pdf_path)
                    if image_paths:
                        # Process images synchronously (since we already have them)
                        return OCRService._extract_text_from_images(textract_client, image_paths)
                    else:
                        logger.error("Failed to convert PDF to images for fallback processing")
                        return "", 0.0
                else:
                    raise
            
            job_id = response['JobId']
            logger.info(f"Textract job started. Job ID: {job_id}")
            
            # Poll for job completion
            max_wait_time = 300  # 5 minutes max
            poll_interval = 3  # Check every 3 seconds
            start_time = time.time()
            
            while True:
                # Check if we've exceeded max wait time
                if time.time() - start_time > max_wait_time:
                    logger.error(f"Textract job {job_id} exceeded max wait time ({max_wait_time}s)")
                    return "", 0.0
                
                # Get job status
                response = textract_client.get_document_text_detection(JobId=job_id)
                status = response['JobStatus']
                
                if status == 'SUCCEEDED':
                    logger.info(f"Textract job {job_id} completed successfully")
                    break
                elif status == 'FAILED':
                    error_message = response.get('StatusMessage', 'Unknown error')
                    logger.error(f"Textract job {job_id} failed: {error_message}")
                    return "", 0.0
                elif status in ['IN_PROGRESS', 'PARTIAL_SUCCESS']:
                    logger.debug(f"Textract job {job_id} status: {status}. Waiting...")
                    time.sleep(poll_interval)
                else:
                    logger.warning(f"Textract job {job_id} has unexpected status: {status}")
                    time.sleep(poll_interval)
            
            # Extract all blocks from all pages
            all_blocks = response.get('Blocks', [])
            next_token = response.get('NextToken')
            
            # Get remaining pages if any
            while next_token:
                logger.debug(f"Fetching next page of results for job {job_id}")
                response = textract_client.get_document_text_detection(
                    JobId=job_id,
                    NextToken=next_token
                )
                all_blocks.extend(response.get('Blocks', []))
                next_token = response.get('NextToken')
            
            # Extract text from all blocks
            full_text, avg_confidence = OCRService._extract_text_from_blocks(all_blocks)
            
            logger.info(f"Textract async extraction completed. Text length: {len(full_text)}, Avg confidence: {avg_confidence:.2f}%")
            
            return full_text, avg_confidence
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            logger.error(f"AWS Textract async ClientError: {error_code} - {error_message}")
            return "", 0.0
        except Exception as e:
            logger.error(f"Error in async Textract processing: {e}")
            return "", 0.0
        finally:
            # Clean up S3 file if we uploaded it
            if uploaded_to_s3:
                try:
                    if HAS_S3_SERVICE and s3_service.is_enabled():
                        s3_service.delete_file(s3_key)
                    else:
                        # Use same credentials as Textract
                        if HAS_SETTINGS:
                            aws_access_key_id = settings.AWS_ACCESS_KEY_ID or os.getenv('AWS_ACCESS_KEY_ID', '')
                            aws_secret_access_key = settings.AWS_SECRET_ACCESS_KEY or os.getenv('AWS_SECRET_ACCESS_KEY', '')
                            aws_region = settings.AWS_REGION or os.getenv('AWS_REGION', 'us-east-1')
                        else:
                            aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID', '')
                            aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY', '')
                            aws_region = os.getenv('AWS_REGION', 'us-east-1')
                        
                        if aws_access_key_id and aws_secret_access_key:
                            s3_client = boto3.client(
                                's3',
                                aws_access_key_id=aws_access_key_id,
                                aws_secret_access_key=aws_secret_access_key,
                                region_name=aws_region
                            )
                        else:
                            s3_client = boto3.client('s3', region_name=aws_region)
                        s3_client.delete_object(Bucket=s3_bucket, Key=s3_key)
                    logger.info(f"Cleaned up temporary S3 file: {s3_key}")
                except Exception as e:
                    logger.warning(f"Failed to clean up S3 file {s3_key}: {e}")
    
    @staticmethod
    def extract_text_from_pdf(pdf_path: str, s3_key: Optional[str] = None) -> Tuple[str, float]:
        """
        Extract text from PDF using AWS Textract and return raw text with confidence score.
        Automatically chooses sync (<=5MB) or async (>5MB) processing.
        
        Args:
            pdf_path: Path to PDF file
            s3_key: Optional S3 key if file is already in S3 (for async processing)
        
        Returns:
            Tuple of (text, confidence_score)
        """
        try:
            textract_client = OCRService._get_textract_client()
            
            if not textract_client:
                logger.error("AWS Textract client not initialized")
                return "", 0.0
            
            # Read PDF file to check size
            with open(pdf_path, 'rb') as document:
                pdf_bytes = document.read()
            
            file_size_mb = len(pdf_bytes) / (1024 * 1024)
            logger.info(f"Processing PDF: {pdf_path} (size: {file_size_mb:.2f}MB)")
            
            # Choose sync or async based on file size
            TEXTTRACT_SYNC_LIMIT_MB = 5.0
            
            if file_size_mb <= TEXTTRACT_SYNC_LIMIT_MB:
                # Use synchronous API for small files
                try:
                    full_text, avg_confidence = OCRService._extract_text_sync(textract_client, pdf_bytes, pdf_path)
                    logger.info(f"Textract sync extraction completed. Text length: {len(full_text)}, Avg confidence: {avg_confidence:.2f}%")
                    return full_text, avg_confidence
                except ClientError as e:
                    error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                    error_message = e.response.get('Error', {}).get('Message', str(e))
                    
                    # If file size error, fall back to async
                    if error_code == 'InvalidParameterException' and ('size' in error_message.lower() or '5MB' in error_message):
                        logger.warning("Sync API failed due to size, falling back to async processing")
                        # Fall through to async processing
                    else:
                        raise
            
            # Use asynchronous API for large files or if sync failed
            if HAS_SETTINGS:
                s3_bucket = settings.S3_BUCKET_NAME
            else:
                s3_bucket = os.getenv('S3_BUCKET_NAME', '')
            
            if not s3_bucket:
                logger.error("S3_BUCKET_NAME not configured. Cannot process files > 5MB without S3.")
                return "", 0.0
            
            logger.info(f"File size ({file_size_mb:.2f}MB) exceeds sync limit ({TEXTTRACT_SYNC_LIMIT_MB}MB). Using async processing.")
            full_text, avg_confidence = OCRService._extract_text_async(textract_client, pdf_path, s3_bucket, s3_key)
            return full_text, avg_confidence
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            logger.error(f"AWS Textract ClientError: {error_code} - {error_message}")
            
            # Provide helpful error messages for common issues
            if error_code == 'InvalidParameterException':
                if 'size' in error_message.lower() or '5MB' in error_message:
                    logger.error("File size exceeds Textract limit. Ensure S3 is configured for async processing.")
            elif error_code == 'InvalidS3ObjectException':
                logger.error("Invalid S3 object. Check file format and S3 permissions.")
            elif error_code == 'UnsupportedDocumentException':
                logger.error("Unsupported document format. Textract supports PDF, PNG, JPEG, and TIFF.")
                logger.error("This may occur if the PDF is encrypted, corrupted, or uses an unsupported format.")
                logger.error("The system will attempt to convert the PDF to images as a fallback.")
            elif error_code == 'DocumentTooLargeException':
                logger.error("Document exceeds size limit. Use async API for files larger than 500 pages.")
            elif error_code == 'ProvisionedThroughputExceededException':
                logger.error("Textract throughput limit exceeded. Please retry after a moment.")
            elif error_code == 'AccessDeniedException':
                logger.error("Access denied. Check AWS credentials and IAM permissions for Textract.")
            
            return "", 0.0
        except BotoCoreError as e:
            logger.error(f"AWS Textract BotoCoreError: {e}")
            return "", 0.0
        except FileNotFoundError:
            logger.error(f"PDF file not found: {pdf_path}")
            return "", 0.0
        except Exception as e:
            logger.error(f"Error extracting text from PDF with Textract: {e}")
            return "", 0.0
    
    @staticmethod
    def extract_fields(text: str) -> Dict[str, Optional[str]]:
        """
        Extract structured fields from OCR text using LLM (Ollama gemma3:latest)
        Falls back to regex-based extraction if LLM is unavailable
        Returns: company_name, company_number, address, date
        """
        fields = {
            "company_name": None,
            "company_number": None,
            "address": None,
            "date": None
        }
        
        # Try LLM extraction first if available
        llm_extraction_successful = False
        if HAS_LLM_SERVICE and text and text.strip():
            try:
                logger.info("Using LLM (Ollama gemma3:latest) for field extraction from OCR text")
                llm_fields = LLMService.extract_company_fields(text)
                
                # Check if LLM extraction was successful (at least one field found)
                if llm_fields.get("company_name") or llm_fields.get("company_number") or llm_fields.get("address"):
                    fields["company_name"] = llm_fields.get("company_name")
                    fields["company_number"] = llm_fields.get("company_number")
                    fields["address"] = llm_fields.get("address")
                    llm_extraction_successful = True
                    logger.info("LLM extraction successful")
                else:
                    logger.warning("LLM extraction returned no fields, falling back to regex")
            except Exception as e:
                logger.warning(f"LLM extraction failed, falling back to regex: {e}")
        
        # If LLM extraction didn't work or wasn't available, use regex fallback
        if not llm_extraction_successful:
            logger.info("Using regex-based field extraction")
            
            # Extract UK Companies House number
            # Formats:
            # - 8 digits (e.g., 01234567) - England and Wales limited companies
            # - 2 letters + 6 digits (e.g., SC555555) - Scottish companies or LLPs
            # Priority: Look for numbers after "Company No." or "No." first
            
            company_number = None
            
            # First, try to find number immediately after "Company No." or "No." (highest priority)
            priority_patterns = [
                r'Company\s+No\.?[\s:]*([A-Z]{2}?\d{6,8}|\d{6,8})\b',
                r'(?:^|\s)No\.?[\s:]*([A-Z]{2}?\d{6,8}|\d{6,8})\b',
                r'Number[\s:]*([A-Z]{2}?\d{6,8}|\d{6,8})\b',
            ]
            
            for pattern in priority_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
                if matches:
                    # Take the first match from priority patterns
                    company_number = matches[0].upper()
                    logger.info(f"Found company number after 'No.' pattern: {company_number}")
                    break
            
            # If not found in priority patterns, try standalone formats
            if not company_number:
                standalone_patterns = [
                    r'\b([A-Z]{2}\d{6})\b',  # 2 letters + 6 digits (SC, OC, etc.)
                    r'\b(\d{8})\b',  # 8 digits
                    r'\b(\d{7})\b',  # 7 digits
                ]
                
                for pattern in standalone_patterns:
                    matches = re.findall(pattern, text.upper())
                    if matches:
                        # Prefer numbers that appear earlier in the document (more likely to be the main number)
                        company_number = matches[0]
                        logger.info(f"Found standalone company number: {company_number}")
                        break
            
            # Clean and validate the extracted number (keep original format)
            if company_number:
                # Remove any non-alphanumeric characters but keep original format
                original_number = re.sub(r'[^A-Z0-9]', '', company_number.upper())
                
                # Store the original extracted format (e.g., 3035678)
                # We'll normalize it later when needed for API calls
                if re.match(r'^([A-Z]{2}\d{6}|\d{6,8})$', original_number):
                    fields["company_number"] = original_number
                    logger.info(f"Extracted UK Companies House number (original format): {original_number}")
                else:
                    logger.warning(f"Extracted number doesn't match UK format: {original_number}")
                    company_number = None
            
            # If still not found, try fallback: any 6-8 digit number after "No."
            if not company_number:
                fallback_pattern = r'(?:Company\s+)?No\.?[\s:]*(\d{6,8})\b'
                matches = re.findall(fallback_pattern, text, re.IGNORECASE)
                if matches:
                    number = matches[0]
                    # Keep original format (don't pad here - normalization happens when needed)
                    if re.match(r'^\d{6,8}$', number):
                        fields["company_number"] = number
                        logger.info(f"Extracted company number (fallback, original format): {number}")
            
            # Extract dates (various formats) - always use regex for dates
            date_patterns = [
                r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b',
                r'\b(\d{4}[/-]\d{1,2}[/-]\d{1,2})\b',
                r'\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4})\b',
            ]
            for pattern in date_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    fields["date"] = matches[0]
                    break
            
            # Extract company name - look for patterns in certificates
            # Priority: "certify that [COMPANY NAME] is this day incorporated"
            company_name = None
            
            # Pattern 1: "certify that [COMPANY NAME] is this day incorporated" - Most reliable
            # Updated to handle single letters with periods (O.), ampersands (&), and parentheses
            pattern1 = r'certify\s+that\s+([A-Z][A-Za-z0-9\s&.,\-()]{3,}?(?:\s+LIMITED|\s+PLC|\s+LLC|\s+INC\.?))\s+is\s+this\s+day'
            matches = re.findall(pattern1, text, re.IGNORECASE)
            if matches:
                company_name = matches[0].strip()
                # Clean up whitespace
                company_name = re.sub(r'\s+', ' ', company_name)
                logger.info(f"Extracted company name (pattern 1 - certify that): {company_name}")
            
            # Pattern 1b: "certify that [COMPANY NAME]" (without "is this day" - more flexible)
            if not company_name:
                pattern1b = r'certify\s+that\s+([A-Z][A-Za-z0-9\s&.,\-()]{5,}?(?:\s+LIMITED|\s+PLC|\s+LLC|\s+INC\.?))(?:\s+is\s+this\s+day|\s+is\s+incorporated|\.|$)'
                matches = re.findall(pattern1b, text, re.IGNORECASE | re.MULTILINE)
                if matches:
                    company_name = matches[0].strip()
                    company_name = re.sub(r'\s+', ' ', company_name)
                    # Remove trailing punctuation
                    company_name = re.sub(r'[.,;:]+$', '', company_name)
                    logger.info(f"Extracted company name (pattern 1b - certify that flexible): {company_name}")
            
            # Pattern 2: "Company name: [NAME]" or "[NAME] (in full)"
            if not company_name:
                pattern2 = r'Company\s+name[\s:]+([A-Z][A-Za-z0-9\s&.,\-()]{3,}?(?:\s+LIMITED|\s+PLC|\s+LLC|\s+INC\.?))(?:\s+\(in\s+full\))?'
                matches = re.findall(pattern2, text, re.IGNORECASE)
                if matches:
                    company_name = matches[0].strip()
                    company_name = re.sub(r'\s+', ' ', company_name)
                    logger.info(f"Extracted company name (pattern 2 - Company name:): {company_name}")
            
            # Pattern 2b: Look for company name near company number
            if not company_name:
                # Try to find company name on same line or near company number
                if fields.get("company_number"):
                    # Look for text before company number that contains LIMITED/PLC
                    number_pattern = re.escape(fields["company_number"])
                    pattern2b = r'([A-Z][A-Za-z0-9\s&.,\-()]{5,}?(?:\s+LIMITED|\s+PLC|\s+LLC|\s+INC\.?))(?:\s+[Cc]ompany\s+[Nn]o\.?|\s+No\.?)?\s*' + number_pattern
                    matches = re.findall(pattern2b, text, re.IGNORECASE | re.MULTILINE)
                    if matches:
                        company_name = matches[0].strip()
                        company_name = re.sub(r'\s+', ' ', company_name)
                        logger.info(f"Extracted company name (pattern 2b - near company number): {company_name}")
            
            # Pattern 3: Look for standalone company names with LIMITED/PLC/LLC
            # Updated to handle parentheses and single letters with periods
            if not company_name:
                # Look for lines that contain LIMITED/PLC/LLC but aren't certificate headers
                lines = text.split('\n')
                for line in lines[:30]:  # Check first 30 lines (increased from 25)
                    line = line.strip()
                    # Must contain company suffix
                    if re.search(r'\b(LIMITED|PLC|LLC|INC\.?)\b', line, re.IGNORECASE):
                        # Skip certificate/document header text
                        skip_keywords = [
                            'CERTIFICATE', 'INCORPORATION', 'COMPANIES ACT', 'REGISTRAR',
                            'FILE COPY', 'PRIVATE LIMITED', 'COMPANY NO', 'NUMBER',
                            'HEREBY CERTIFIES', 'THIS DAY', 'REGISTRAR OF COMPANIES',
                            'CERTIFICATE OF INCORPORATION'
                        ]
                        if not any(keyword in line.upper() for keyword in skip_keywords):
                            # Must have substantial text (not just numbers)
                            # Updated to allow single letters with periods (O. HEAP)
                            if re.search(r'[A-Za-z]{2,}', line) and len(line) > 8:
                                # Extract just the company name part
                                # Remove "The Company's name is" type prefixes
                                cleaned = re.sub(r'^(The\s+)?Company[\'s\s]+name\s+is\s*:?\s*', '', line, flags=re.IGNORECASE)
                                cleaned = cleaned.strip()
                                # Remove common prefixes
                                cleaned = re.sub(r'^(Name\s+of\s+Company|Company\s+Name)[\s:]+', '', cleaned, flags=re.IGNORECASE)
                                cleaned = cleaned.strip()
                                if len(cleaned) > 5 and len(cleaned) < 200:  # Reasonable length
                                    company_name = cleaned
                                    company_name = re.sub(r'\s+', ' ', company_name)
                                    logger.info(f"Extracted company name (pattern 3 - standalone): {company_name}")
                                    break
            
            if company_name:
                # Final cleanup
                company_name = company_name.strip()
                # Remove trailing punctuation
                company_name = re.sub(r'[,\-;:]+$', '', company_name)
                # Remove any remaining certificate text that might have been captured
                if 'CERTIFICATE' in company_name.upper() or 'INCORPORATION' in company_name.upper():
                    # Try to extract just the company name part
                    parts = re.split(r'(?:CERTIFICATE|INCORPORATION|COMPANY\s+NO)', company_name, flags=re.IGNORECASE)
                    if parts and len(parts) > 0:
                        potential_name = parts[0].strip()
                        if len(potential_name) > 5:
                            company_name = potential_name
                
                fields["company_name"] = company_name
                logger.info(f"Final extracted company name: {company_name}")
            
            # Extract address (look for UK postcode pattern)
            if not fields.get("address"):  # Only if LLM didn't extract it
                postcode_pattern = r'\b([A-Z]{1,2}\d{1,2}\s?\d[A-Z]{2})\b'
                postcode_matches = re.findall(postcode_pattern, text.upper())
                if postcode_matches:
                    # Get context around postcode for address
                    for match in postcode_matches:
                        idx = text.upper().find(match)
                        if idx > 0:
                            # Get 100 chars before postcode
                            start = max(0, idx - 100)
                            address_candidate = text[start:idx + len(match)].strip()
                            if len(address_candidate) > 10:
                                fields["address"] = address_candidate
                                break
        else:
            # LLM extraction was successful, only extract date using regex
            date_patterns = [
                r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b',
                r'\b(\d{4}[/-]\d{1,2}[/-]\d{1,2})\b',
                r'\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4})\b',
            ]
            for pattern in date_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    fields["date"] = matches[0]
                    break
        
        return fields
    
    @staticmethod
    def process_document(file_path: str) -> Dict:
        """
        Main method to process document and extract all OCR data
        """
        try:
            raw_text, confidence = OCRService.extract_text_from_pdf(file_path)
            fields = OCRService.extract_fields(raw_text)
            
            return {
                "raw_text": raw_text,
                "confidence": confidence,
                "company_name": fields.get("company_name"),
                "company_number": fields.get("company_number"),
                "address": fields.get("address"),
                "date": fields.get("date")
            }
        except Exception as e:
            logger.error(f"Error processing document: {e}")
            return {
                "raw_text": "",
                "confidence": 0.0,
                "company_name": None,
                "company_number": None,
                "address": None,
                "date": None
            }

