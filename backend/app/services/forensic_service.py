"""
Forensic Analysis Service for document authenticity verification
"""
import cv2
import numpy as np
from PIL import Image
import exifread
import io
import pdf2image
from typing import Dict, Optional, Tuple
import logging
from skimage import metrics
import os
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


class ForensicService:
    """Service for forensic analysis of documents"""
    
    @staticmethod
    def is_pdf(file_path: str) -> bool:
        """Check if file is a PDF"""
        return file_path.lower().endswith('.pdf')
    
    @staticmethod
    def is_image(file_path: str) -> bool:
        """Check if file is an image"""
        image_extensions = ['.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp', '.gif']
        return any(file_path.lower().endswith(ext) for ext in image_extensions)
    
    @staticmethod
    def convert_pdf_to_image(file_path: str, dpi: int = 150) -> Optional[str]:
        """
        Convert PDF to image and return temp file path
        Returns None if conversion fails
        """
        try:
            logger.info(f"Converting PDF to image: {file_path}")
            images = pdf2image.convert_from_path(file_path, dpi=dpi)
            if not images:
                logger.warning("PDF conversion returned no images")
                return None
            
            # Create temp file
            temp_fd, temp_path = tempfile.mkstemp(suffix='.png', prefix='forensic_')
            os.close(temp_fd)
            
            # Save first page
            images[0].save(temp_path, "PNG")
            logger.info(f"PDF converted to image: {temp_path}")
            return temp_path
        except Exception as e:
            logger.error(f"Error converting PDF to image: {e}")
            return None
    
    @staticmethod
    def extract_exif_data(file_path: str) -> Dict:
        """
        Extract EXIF metadata from image/PDF
        """
        exif_data = {}
        try:
            if ForensicService.is_pdf(file_path):
                logger.info("Extracting EXIF from PDF (converted to image)")
                # PDFs don't have EXIF data, but we can check the converted image
                temp_image = ForensicService.convert_pdf_to_image(file_path)
                if temp_image:
                    try:
                        with open(temp_image, 'rb') as f:
                            tags = exifread.process_file(f)
                            for tag in tags.keys():
                                if tag not in ('JPEGThumbnail', 'TIFFThumbnail', 'Filename', 'EXIF MakerNote'):
                                    exif_data[tag] = str(tags[tag])
                    finally:
                        if os.path.exists(temp_image):
                            os.remove(temp_image)
                else:
                    logger.info("PDF file does not have EXIF data (expected for PDFs)")
            elif ForensicService.is_image(file_path):
                logger.info(f"Extracting EXIF from image: {file_path}")
                with open(file_path, 'rb') as f:
                    tags = exifread.process_file(f)
                    for tag in tags.keys():
                        if tag not in ('JPEGThumbnail', 'TIFFThumbnail', 'Filename', 'EXIF MakerNote'):
                            exif_data[tag] = str(tags[tag])
            else:
                logger.warning(f"Unknown file type for EXIF extraction: {file_path}")
        except Exception as e:
            logger.warning(f"Could not extract EXIF data: {e}")
        
        return exif_data
    
    @staticmethod
    def calculate_ela_score(image_path: str) -> float:
        """
        Calculate Error Level Analysis (ELA) score
        Higher scores indicate potential tampering
        """
        try:
            logger.info(f"Calculating ELA score for: {image_path}")
            # Read image
            img = cv2.imread(image_path)
            if img is None:
                logger.warning(f"Could not read image with cv2.imread, trying PDF conversion")
                if ForensicService.is_pdf(image_path):
                    temp_image = ForensicService.convert_pdf_to_image(image_path)
                    if not temp_image:
                        return 0.0
                    img = cv2.imread(temp_image)
                    if img is None:
                        return 0.0
                else:
                    return 0.0
            
            # Convert to grayscale
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img
            
            # Save at quality 90 and reload
            temp_fd, temp_path = tempfile.mkstemp(suffix='.jpg', prefix='ela_')
            os.close(temp_fd)
            
            try:
                cv2.imwrite(temp_path, gray, [cv2.IMWRITE_JPEG_QUALITY, 90])
                reloaded = cv2.imread(temp_path, cv2.IMREAD_GRAYSCALE)
                
                if reloaded is None:
                    return 0.0
                
                # Calculate difference
                diff = cv2.absdiff(gray, reloaded)
                ela_score = np.mean(diff)
                
                # Normalize to 0-100 scale (higher = more suspicious)
                normalized_score = min(100, (ela_score / 10) * 100)
                
                logger.info(f"ELA score calculated: {normalized_score:.2f}")
                return float(normalized_score)
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            
        except Exception as e:
            logger.error(f"Error calculating ELA score: {e}", exc_info=True)
            return 0.0
    
    @staticmethod
    def detect_copy_move(image_path: str) -> Tuple[bool, float]:
        """
        Detect copy-move forgery using block matching
        Returns: (detected, confidence)
        Optimized to avoid O(n²) complexity for large images
        """
        try:
            logger.info(f"Detecting copy-move for: {image_path}")
            img = cv2.imread(image_path)
            if img is None:
                logger.warning(f"Could not read image with cv2.imread, trying PDF conversion")
                if ForensicService.is_pdf(image_path):
                    temp_image = ForensicService.convert_pdf_to_image(image_path)
                    if not temp_image:
                        return False, 0.0
                    img = cv2.imread(temp_image)
                    if img is None:
                        return False, 0.0
                else:
                    return False, 0.0
            
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img
            
            # Resize large images to speed up processing (max 2000px on longest side)
            h, w = gray.shape
            max_dimension = 2000
            scale = 1.0
            if max(h, w) > max_dimension:
                scale = max_dimension / max(h, w)
                new_w = int(w * scale)
                new_h = int(h * scale)
                gray = cv2.resize(gray, (new_w, new_h), interpolation=cv2.INTER_AREA)
                logger.info(f"Resized image from {w}x{h} to {new_w}x{new_h} for faster processing")
            
            # Use larger block size for faster processing
            block_size = 32
            h, w = gray.shape
            
            # Limit number of blocks to check (sample blocks if too many)
            step = block_size
            max_blocks = 500  # Limit to prevent excessive computation
            
            blocks = []
            for i in range(0, h - block_size, step):
                for j in range(0, w - block_size, step):
                    block = gray[i:i+block_size, j:j+block_size]
                    blocks.append((i, j, block))
                    if len(blocks) >= max_blocks:
                        break
                if len(blocks) >= max_blocks:
                    break
            
            logger.info(f"Checking {len(blocks)} blocks for copy-move detection")
            
            # Find similar blocks (optimized: only check every Nth block)
            similar_pairs = 0
            total_pairs = 0
            check_interval = max(1, len(blocks) // 100)  # Check up to 100 pairs
            
            for i in range(0, len(blocks), check_interval):
                y1, x1, block1 = blocks[i]
                for j in range(i + check_interval, len(blocks), check_interval):
                    y2, x2, block2 = blocks[j]
                    # Skip if blocks are too close
                    if abs(y1 - y2) < block_size * 2 and abs(x1 - x2) < block_size * 2:
                        continue
                    
                    total_pairs += 1
                    # Calculate similarity (faster method)
                    try:
                        similarity = metrics.structural_similarity(
                            block1, block2, data_range=255
                        )
                        if similarity > 0.95:  # Very similar blocks
                            similar_pairs += 1
                    except:
                        pass
                    
                    # Limit total pairs checked
                    if total_pairs > 1000:
                        break
                if total_pairs > 1000:
                    break
            
            if total_pairs == 0:
                logger.info("No pairs checked for copy-move detection")
                return False, 0.0
            
            confidence = (similar_pairs / total_pairs) * 100
            detected = confidence > 5.0  # Threshold
            
            logger.info(f"Copy-move detection: detected={detected}, confidence={confidence:.2f}%")
            return detected, float(confidence)
            
        except Exception as e:
            logger.error(f"Error detecting copy-move: {e}", exc_info=True)
            return False, 0.0
    
    @staticmethod
    def analyze_jpeg_quality(image_path: str) -> float:
        """
        Analyze JPEG quality (multiple saves reduce quality)
        """
        try:
            logger.info(f"Analyzing JPEG quality for: {image_path}")
            img = cv2.imread(image_path)
            if img is None:
                logger.warning(f"Could not read image with cv2.imread, trying PDF conversion")
                if ForensicService.is_pdf(image_path):
                    temp_image = ForensicService.convert_pdf_to_image(image_path)
                    if not temp_image:
                        return 0.0
                    img = cv2.imread(temp_image)
                    if img is None:
                        return 0.0
                else:
                    return 0.0
            
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img
            
            # For PDFs, quality analysis is less meaningful, return a default
            if ForensicService.is_pdf(image_path):
                logger.info("PDF file - skipping JPEG quality analysis (not applicable)")
                return 75.0  # Default quality for PDFs
            
            # Estimate quality by analyzing DCT coefficients
            # Simplified: check for compression artifacts
            # Sample blocks instead of checking all (for performance)
            block_size = 8
            variances = []
            sample_rate = 4  # Check every 4th block
            
            h, w = gray.shape
            for i in range(0, h - block_size, block_size * sample_rate):
                for j in range(0, w - block_size, block_size * sample_rate):
                    block = gray[i:i+block_size, j:j+block_size]
                    variances.append(np.var(block))
            
            if not variances:
                return 0.0
            
            avg_variance = np.mean(variances)
            # Lower variance suggests multiple compressions
            quality_score = min(100, (avg_variance / 100) * 100)
            
            logger.info(f"JPEG quality score: {quality_score:.2f}")
            return float(quality_score)
            
        except Exception as e:
            logger.error(f"Error analyzing JPEG quality: {e}", exc_info=True)
            return 0.0
    
    @staticmethod
    def process_document(file_path: str) -> Dict:
        """
        Main method to perform all forensic analyses
        """
        temp_image_path = None
        try:
            logger.info(f"Starting forensic analysis for: {file_path}")
            
            # Check file type
            if not os.path.exists(file_path):
                logger.error(f"File does not exist: {file_path}")
                return {
                    "forensic_score": 0.0,
                    "forensic_penalty": 15.0,
                    "exif_data": {},
                    "ela_score": 0.0,
                    "jpeg_quality": 0.0,
                    "copy_move_detected": False,
                    "copy_move_confidence": 0.0,
                    "details": {"error": "File does not exist"}
                }
            
            # Convert PDF to image if needed
            image_path = file_path
            if ForensicService.is_pdf(file_path):
                logger.info("Processing PDF file - converting to image")
                temp_image_path = ForensicService.convert_pdf_to_image(file_path)
                if not temp_image_path:
                    logger.error("Failed to convert PDF to image")
                    return {
                        "forensic_score": 0.0,
                        "forensic_penalty": 15.0,
                        "exif_data": {},
                        "ela_score": 0.0,
                        "jpeg_quality": 0.0,
                        "copy_move_detected": False,
                        "copy_move_confidence": 0.0,
                        "details": {"error": "Could not convert PDF to image"}
                    }
                image_path = temp_image_path
                logger.info(f"PDF converted to image: {image_path}")
            elif not ForensicService.is_image(file_path):
                logger.warning(f"Unknown file type: {file_path}")
            
            # Extract EXIF
            logger.info("Extracting EXIF data...")
            exif_data = ForensicService.extract_exif_data(file_path)
            logger.info(f"EXIF data extracted: {len(exif_data)} tags")
            
            # Calculate ELA
            logger.info("Calculating ELA score...")
            ela_score = ForensicService.calculate_ela_score(image_path)
            
            # Detect copy-move
            logger.info("Detecting copy-move forgery...")
            copy_move_detected, copy_move_confidence = ForensicService.detect_copy_move(image_path)
            
            # Analyze JPEG quality
            logger.info("Analyzing JPEG quality...")
            jpeg_quality = ForensicService.analyze_jpeg_quality(image_path)
            
            # Calculate forensic penalty (0-15)
            penalty = 0.0
            details = []
            
            if ela_score > 50:
                penalty += 5.0
                details.append(f"High ELA score: {ela_score:.2f}")
            
            if copy_move_detected:
                penalty += 7.0
                details.append(f"Copy-move detected: {copy_move_confidence:.2f}%")
            
            if jpeg_quality < 30:
                penalty += 3.0
                details.append(f"Low JPEG quality: {jpeg_quality:.2f}")
            
            # Check for suspicious EXIF data
            if exif_data:
                suspicious_keys = ['Software', 'ModifyDate', 'CreateDate']
                for key in suspicious_keys:
                    if key in exif_data:
                        details.append(f"EXIF {key}: {exif_data[key]}")
            
            forensic_penalty = min(15.0, penalty)
            forensic_score = 100.0 - (forensic_penalty / 15.0 * 100.0)
            
            result = {
                "forensic_score": forensic_score,
                "forensic_penalty": forensic_penalty,
                "exif_data": exif_data,
                "ela_score": ela_score,
                "jpeg_quality": jpeg_quality,
                "copy_move_detected": copy_move_detected,
                "copy_move_confidence": copy_move_confidence,
                "details": details
            }
            
            logger.info(f"Forensic analysis complete. Score: {forensic_score:.2f}, Penalty: {forensic_penalty:.2f}")
            return result
            
        except Exception as e:
            logger.error(f"Error in forensic analysis: {e}", exc_info=True)
            return {
                "forensic_score": 0.0,
                "forensic_penalty": 15.0,
                "exif_data": {},
                "ela_score": 0.0,
                "jpeg_quality": 0.0,
                "copy_move_detected": False,
                "copy_move_confidence": 0.0,
                "details": {"error": str(e)}
            }
        finally:
            # Cleanup temp file
            if temp_image_path and os.path.exists(temp_image_path):
                try:
                    os.remove(temp_image_path)
                    logger.info(f"Cleaned up temp file: {temp_image_path}")
                except Exception as e:
                    logger.warning(f"Could not remove temp file {temp_image_path}: {e}")

