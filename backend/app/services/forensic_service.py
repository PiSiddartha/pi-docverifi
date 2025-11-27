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

logger = logging.getLogger(__name__)


class ForensicService:
    """Service for forensic analysis of documents"""
    
    @staticmethod
    def extract_exif_data(file_path: str) -> Dict:
        """
        Extract EXIF metadata from image/PDF
        """
        exif_data = {}
        try:
            if file_path.lower().endswith('.pdf'):
                # Convert first page to image
                images = pdf2image.convert_from_path(file_path, dpi=150)
                if images:
                    img_byte_arr = io.BytesIO()
                    images[0].save(img_byte_arr, format='PNG')
                    img_byte_arr.seek(0)
                    tags = exifread.process_file(img_byte_arr)
            else:
                with open(file_path, 'rb') as f:
                    tags = exifread.process_file(f)
            
            for tag in tags.keys():
                if tag not in ('JPEGThumbnail', 'TIFFThumbnail', 'Filename', 'EXIF MakerNote'):
                    exif_data[tag] = str(tags[tag])
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
            # Read image
            img = cv2.imread(image_path)
            if img is None:
                # Try converting PDF to image
                images = pdf2image.convert_from_path(image_path, dpi=150)
                if not images:
                    return 0.0
                img = np.array(images[0])
                if len(img.shape) == 2:
                    img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Save at quality 90 and reload
            temp_path = "/tmp/ela_temp.jpg"
            cv2.imwrite(temp_path, gray, [cv2.IMWRITE_JPEG_QUALITY, 90])
            reloaded = cv2.imread(temp_path, cv2.IMREAD_GRAYSCALE)
            os.remove(temp_path)
            
            # Calculate difference
            diff = cv2.absdiff(gray, reloaded)
            ela_score = np.mean(diff)
            
            # Normalize to 0-100 scale (higher = more suspicious)
            normalized_score = min(100, (ela_score / 10) * 100)
            
            return float(normalized_score)
            
        except Exception as e:
            logger.error(f"Error calculating ELA score: {e}")
            return 0.0
    
    @staticmethod
    def detect_copy_move(image_path: str) -> Tuple[bool, float]:
        """
        Detect copy-move forgery using block matching
        Returns: (detected, confidence)
        """
        try:
            img = cv2.imread(image_path)
            if img is None:
                images = pdf2image.convert_from_path(image_path, dpi=150)
                if not images:
                    return False, 0.0
                img = np.array(images[0])
                if len(img.shape) == 2:
                    img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Simple block-based copy-move detection
            block_size = 16
            h, w = gray.shape
            blocks = []
            
            for i in range(0, h - block_size, block_size):
                for j in range(0, w - block_size, block_size):
                    block = gray[i:i+block_size, j:j+block_size]
                    blocks.append((i, j, block))
            
            # Find similar blocks
            similar_pairs = 0
            total_pairs = 0
            
            for i, (y1, x1, block1) in enumerate(blocks):
                for j, (y2, x2, block2) in enumerate(blocks[i+1:], i+1):
                    # Skip if blocks are too close
                    if abs(y1 - y2) < block_size * 2 and abs(x1 - x2) < block_size * 2:
                        continue
                    
                    total_pairs += 1
                    # Calculate similarity
                    similarity = metrics.structural_similarity(
                        block1, block2, data_range=255
                    )
                    if similarity > 0.95:  # Very similar blocks
                        similar_pairs += 1
            
            if total_pairs == 0:
                return False, 0.0
            
            confidence = (similar_pairs / total_pairs) * 100
            detected = confidence > 5.0  # Threshold
            
            return detected, float(confidence)
            
        except Exception as e:
            logger.error(f"Error detecting copy-move: {e}")
            return False, 0.0
    
    @staticmethod
    def analyze_jpeg_quality(image_path: str) -> float:
        """
        Analyze JPEG quality (multiple saves reduce quality)
        """
        try:
            img = cv2.imread(image_path)
            if img is None:
                images = pdf2image.convert_from_path(image_path, dpi=150)
                if not images:
                    return 0.0
                img = np.array(images[0])
                if len(img.shape) == 2:
                    img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            
            # Estimate quality by analyzing DCT coefficients
            # Simplified: check for compression artifacts
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Calculate variance in 8x8 blocks (low variance = compression artifacts)
            block_size = 8
            variances = []
            
            for i in range(0, gray.shape[0] - block_size, block_size):
                for j in range(0, gray.shape[1] - block_size, block_size):
                    block = gray[i:i+block_size, j:j+block_size]
                    variances.append(np.var(block))
            
            avg_variance = np.mean(variances)
            # Lower variance suggests multiple compressions
            quality_score = min(100, (avg_variance / 100) * 100)
            
            return float(quality_score)
            
        except Exception as e:
            logger.error(f"Error analyzing JPEG quality: {e}")
            return 0.0
    
    @staticmethod
    def process_document(file_path: str) -> Dict:
        """
        Main method to perform all forensic analyses
        """
        try:
            # Convert PDF to image if needed
            image_path = file_path
            if file_path.lower().endswith('.pdf'):
                images = pdf2image.convert_from_path(file_path, dpi=150)
                if images:
                    temp_path = "/tmp/forensic_temp.png"
                    images[0].save(temp_path, "PNG")
                    image_path = temp_path
                else:
                    return {
                        "forensic_score": 0.0,
                        "forensic_penalty": 15.0,
                        "exif_data": {},
                        "ela_score": 0.0,
                        "jpeg_quality": 0.0,
                        "copy_move_detected": False,
                        "copy_move_confidence": 0.0,
                        "details": {"error": "Could not process PDF"}
                    }
            
            # Extract EXIF
            exif_data = ForensicService.extract_exif_data(file_path)
            
            # Calculate ELA
            ela_score = ForensicService.calculate_ela_score(image_path)
            
            # Detect copy-move
            copy_move_detected, copy_move_confidence = ForensicService.detect_copy_move(image_path)
            
            # Analyze JPEG quality
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
            
            # Cleanup temp file
            if image_path != file_path and os.path.exists(image_path):
                os.remove(image_path)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in forensic analysis: {e}")
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

