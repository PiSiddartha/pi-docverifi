"""
Forensic Analysis Service for document authenticity verification
"""
import cv2
import numpy as np
from PIL import Image
import exifread
import io
import pdf2image
from typing import Dict, Optional, Tuple, List
import logging
from skimage import metrics
import os
import tempfile
from pathlib import Path
import hashlib
from datetime import datetime

logger = logging.getLogger(__name__)

# Try to import pypdf for PDF metadata analysis
try:
    from pypdf import PdfReader
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False
    logger.warning("pypdf not available. PDF metadata analysis will be limited.")


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
            
            # Context-aware threshold adjustment
            # For scanned documents (especially old ones), we need higher thresholds
            # Check if this looks like a scanned document (grayscale, lower resolution, etc.)
            is_scanned = False
            try:
                # Check if image is mostly grayscale (scanned documents often are)
                if len(img.shape) == 3:
                    gray_test = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    color_variance = np.var([np.mean(img[:,:,0]), np.mean(img[:,:,1]), np.mean(img[:,:,2])])
                    if color_variance < 100:  # Low color variance suggests grayscale/scan
                        is_scanned = True
                else:
                    is_scanned = True
                
                # Check resolution - lower res often indicates scanned
                h, w = gray.shape
                if max(h, w) < 2000:  # Lower resolution suggests scan
                    is_scanned = True
            except:
                pass
            
            # Adjust threshold based on document type
            if is_scanned:
                # Scanned documents have more repeated patterns (paper texture, scanning artifacts)
                # Use higher threshold: 30% for scanned, 20% for regular
                threshold = 30.0
            else:
                # Official documents often have repeated elements (headers, footers, logos, form templates)
                threshold = 20.0
            
            detected = confidence > threshold
            
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
    def analyze_pdf_metadata(file_path: str) -> Dict:
        """
        Analyze PDF metadata for suspicious patterns
        Returns: dict with metadata analysis results
        """
        result = {
            "has_metadata": False,
            "suspicious": False,
            "metadata": {},
            "suspicious_flags": [],
            "score": 0.0
        }
        
        if not ForensicService.is_pdf(file_path):
            return result
        
        try:
            if not HAS_PYPDF:
                logger.warning("pypdf not available for PDF metadata analysis")
                return result
            
            logger.info(f"Analyzing PDF metadata: {file_path}")
            reader = PdfReader(file_path)
            metadata = reader.metadata
            
            if not metadata:
                result["has_metadata"] = False
                result["score"] = 50.0  # Neutral score if no metadata
                return result
            
            result["has_metadata"] = True
            result["metadata"] = {
                "title": metadata.get("/Title", ""),
                "author": metadata.get("/Author", ""),
                "subject": metadata.get("/Subject", ""),
                "creator": metadata.get("/Creator", ""),
                "producer": metadata.get("/Producer", ""),
                "creation_date": str(metadata.get("/CreationDate", "")),
                "modification_date": str(metadata.get("/ModDate", "")),
            }
            
            suspicious_flags = []
            score = 100.0  # Start with perfect score
            
            # Check 1: Creation date after modification date (suspicious)
            try:
                if metadata.get("/CreationDate") and metadata.get("/ModDate"):
                    creation = metadata.get("/CreationDate")
                    modification = metadata.get("/ModDate")
                    if creation and modification and creation > modification:
                        suspicious_flags.append("Creation date after modification date")
                        score -= 20.0
            except:
                pass
            
            # Check 2: Suspicious software names (image editors, etc.)
            creator = str(metadata.get("/Creator", "")).lower()
            producer = str(metadata.get("/Producer", "")).lower()
            suspicious_software = [
                "photoshop", "gimp", "paint", "paint.net", "coreldraw",
                "illustrator", "inkscape", "canva", "figma", "sketch"
            ]
            for software in suspicious_software:
                if software in creator or software in producer:
                    suspicious_flags.append(f"Suspicious software detected: {software}")
                    score -= 15.0
            
            # Check 3: Missing expected metadata for official documents
            if not metadata.get("/Creator") and not metadata.get("/Producer"):
                suspicious_flags.append("Missing creator/producer information")
                score -= 10.0
            
            # Check 4: Recent modification date on old document (suspicious)
            try:
                if metadata.get("/ModDate"):
                    mod_date_str = str(metadata.get("/ModDate"))
                    # Check if modification date is very recent but document claims to be old
                    # This is a simplified check - in production, parse dates properly
                    if "2024" in mod_date_str or "2025" in mod_date_str:
                        suspicious_flags.append("Recent modification date detected")
                        score -= 5.0
            except:
                pass
            
            result["suspicious_flags"] = suspicious_flags
            result["suspicious"] = len(suspicious_flags) > 0
            result["score"] = max(0.0, min(100.0, score))
            
            logger.info(f"PDF metadata analysis complete. Score: {result['score']:.2f}, Suspicious: {result['suspicious']}")
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing PDF metadata: {e}", exc_info=True)
            return result
    
    @staticmethod
    def analyze_resolution_consistency(image_path: str) -> Dict:
        """
        Analyze resolution/DPI consistency across the image
        Detects upscaling or resolution inconsistencies
        Returns: dict with resolution analysis results
        """
        result = {
            "consistent": True,
            "suspicious": False,
            "dpi_estimate": 0.0,
            "upscaling_detected": False,
            "score": 100.0,
            "details": []
        }
        
        try:
            logger.info(f"Analyzing resolution consistency: {image_path}")
            img = cv2.imread(image_path)
            if img is None:
                return result
            
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img
            
            h, w = gray.shape
            
            # Analyze different regions of the image
            regions = [
                gray[0:h//4, 0:w//4],  # Top-left
                gray[0:h//4, 3*w//4:w],  # Top-right
                gray[3*h//4:h, 0:w//4],  # Bottom-left
                gray[3*h//4:h, 3*w//4:w],  # Bottom-right
                gray[h//4:3*h//4, w//4:3*w//4],  # Center
            ]
            
            # Calculate frequency domain analysis for each region
            # Upscaled images show different frequency patterns
            fft_scores = []
            for region in regions:
                if region.size > 0:
                    # Calculate 2D FFT
                    f_transform = np.fft.fft2(region)
                    f_shift = np.fft.fftshift(f_transform)
                    magnitude_spectrum = np.log(np.abs(f_shift) + 1)
                    
                    # High-frequency content indicates original resolution
                    # Low high-frequency content suggests upscaling
                    high_freq_energy = np.sum(magnitude_spectrum[magnitude_spectrum > np.percentile(magnitude_spectrum, 90)])
                    fft_scores.append(high_freq_energy)
            
            if len(fft_scores) > 1:
                # Check for consistency
                fft_std = np.std(fft_scores)
                fft_mean = np.mean(fft_scores)
                
                # High variance suggests inconsistent resolution (suspicious)
                if fft_std > fft_mean * 0.3:
                    result["consistent"] = False
                    result["suspicious"] = True
                    result["score"] -= 30.0
                    result["details"].append("Inconsistent resolution patterns detected")
                
                # Very low high-frequency energy suggests upscaling
                if fft_mean < 100:  # Threshold may need adjustment
                    result["upscaling_detected"] = True
                    result["suspicious"] = True
                    result["score"] -= 25.0
                    result["details"].append("Possible upscaling detected")
            
            # Estimate DPI (rough estimate based on image dimensions and content)
            # This is a simplified estimation
            if w > 0 and h > 0:
                # Typical document DPI ranges: 150-300 for scanned, 72-96 for screen
                # Estimate based on content sharpness
                edges = cv2.Canny(gray, 50, 150)
                edge_density = np.sum(edges > 0) / (w * h)
                
                # Higher edge density suggests higher resolution
                if edge_density > 0.1:
                    result["dpi_estimate"] = 300.0
                elif edge_density > 0.05:
                    result["dpi_estimate"] = 200.0
                else:
                    result["dpi_estimate"] = 150.0
                    if edge_density < 0.02:
                        result["suspicious"] = True
                        result["score"] -= 15.0
                        result["details"].append("Low resolution detected")
            
            result["score"] = max(0.0, min(100.0, result["score"]))
            logger.info(f"Resolution analysis complete. Score: {result['score']:.2f}, Upscaling: {result['upscaling_detected']}")
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing resolution consistency: {e}", exc_info=True)
            return result
    
    @staticmethod
    def analyze_color_histogram(image_path: str) -> Dict:
        """
        Analyze color histogram for unusual patterns
        Detects color space inconsistencies and editing artifacts
        Returns: dict with color analysis results
        """
        result = {
            "consistent": True,
            "suspicious": False,
            "color_space_anomalies": False,
            "score": 100.0,
            "details": []
        }
        
        try:
            logger.info(f"Analyzing color histogram: {image_path}")
            img = cv2.imread(image_path)
            if img is None:
                return result
            
            # Convert to different color spaces
            bgr = img
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
            
            # Analyze histograms for each channel
            channels = {
                "B": bgr[:, :, 0],
                "G": bgr[:, :, 1],
                "R": bgr[:, :, 2],
                "H": hsv[:, :, 0],
                "S": hsv[:, :, 1],
                "V": hsv[:, :, 2]
            }
            
            histograms = {}
            for name, channel in channels.items():
                hist = cv2.calcHist([channel], [0], None, [256], [0, 256])
                histograms[name] = hist.flatten()
            
            # Check for unusual patterns
            # 1. Check for color space inconsistencies
            # Edited images often show spikes or gaps in histograms
            # But be lenient for scanned/grayscale documents
            is_grayscale = False
            try:
                # Check if image is mostly grayscale (common in scanned documents)
                if len(img.shape) == 3:
                    bgr_means = [np.mean(img[:,:,0]), np.mean(img[:,:,1]), np.mean(img[:,:,2])]
                    if np.std(bgr_means) < 10:  # Very similar means = grayscale
                        is_grayscale = True
                        logger.info("Detected grayscale/scanned document - applying lenient color analysis")
            except:
                pass
            
            issues_found = 0
            for name, hist in histograms.items():
                # Skip certain channels for grayscale images
                if is_grayscale and name in ['H', 'S']:
                    continue
                
                # Check for unusual spikes (potential editing artifacts)
                hist_max = np.max(hist)
                hist_mean = np.mean(hist)
                
                # Skip if mean is zero (no data in channel)
                if hist_mean == 0:
                    continue
                
                # If max is much higher than mean, might indicate editing
                # Use higher threshold for grayscale images
                threshold_multiplier = 15.0 if is_grayscale else 8.0
                if hist_max > hist_mean * threshold_multiplier:
                    issues_found += 1
                    result["suspicious"] = True
                    result["color_space_anomalies"] = True
                    # Limit total penalty to prevent score going to 0
                    if issues_found <= 2:  # Only penalize first 2 issues
                        result["score"] -= 15.0 if is_grayscale else 20.0
                        result["details"].append(f"Unusual histogram pattern in {name} channel")
                
                # Check for gaps (missing color values - sign of editing)
                # But be lenient for scanned documents which naturally have fewer colors
                if not is_grayscale:
                    zero_count = np.sum(hist == 0)
                    non_zero_count = np.sum(hist > 0)
                    
                    # Only flag if there are very few non-zero values (strong sign of editing)
                    # Scanned documents may have many zeros but still have reasonable color distribution
                    if non_zero_count > 0 and (zero_count / len(hist)) > 0.85 and non_zero_count < 15:
                        issues_found += 1
                        result["suspicious"] = True
                        if issues_found <= 2:  # Limit penalties
                            result["score"] -= 15.0
                            result["details"].append(f"Severe color gaps detected in {name} channel ({non_zero_count} unique values)")
            
            # 2. Check for color consistency across image regions
            h, w = img.shape[:2]
            regions = [
                img[0:h//3, 0:w//3],  # Top-left
                img[0:h//3, 2*w//3:w],  # Top-right
                img[2*h//3:h, 0:w//3],  # Bottom-left
                img[2*h//3:h, 2*w//3:w],  # Bottom-right
            ]
            
            region_means = []
            for region in regions:
                if region.size > 0:
                    mean_color = np.mean(region, axis=(0, 1))
                    region_means.append(mean_color)
            
            if len(region_means) > 1:
                # Calculate variance in mean colors
                mean_array = np.array(region_means)
                color_variance = np.var(mean_array, axis=0)
                
                # Very high variance might indicate editing
                if np.max(color_variance) > 1000:
                    result["suspicious"] = True
                    result["score"] -= 10.0
                    result["details"].append("Inconsistent color distribution across regions")
            
            result["score"] = max(0.0, min(100.0, result["score"]))
            logger.info(f"Color histogram analysis complete. Score: {result['score']:.2f}, Suspicious: {result['suspicious']}")
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing color histogram: {e}", exc_info=True)
            return result
    
    @staticmethod
    def analyze_noise_patterns(image_path: str) -> Dict:
        """
        Analyze noise patterns for consistency
        Tampered areas often have different noise characteristics
        Returns: dict with noise analysis results
        """
        result = {
            "consistent": True,
            "suspicious": False,
            "noise_variance": 0.0,
            "inconsistent_regions": 0,
            "score": 100.0,
            "details": []
        }
        
        try:
            logger.info(f"Analyzing noise patterns: {image_path}")
            img = cv2.imread(image_path)
            if img is None:
                return result
            
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img
            
            h, w = gray.shape
            
            # Divide image into blocks and analyze noise in each
            block_size = min(64, h//8, w//8)  # Adaptive block size
            blocks_h = h // block_size
            blocks_w = w // block_size
            
            noise_levels = []
            
            for i in range(blocks_h):
                for j in range(blocks_w):
                    block = gray[i*block_size:(i+1)*block_size, j*block_size:(j+1)*block_size]
                    
                    # Calculate noise level using variance of Laplacian
                    laplacian_var = cv2.Laplacian(block, cv2.CV_64F).var()
                    noise_levels.append(laplacian_var)
            
            if len(noise_levels) > 1:
                noise_mean = np.mean(noise_levels)
                noise_std = np.std(noise_levels)
                result["noise_variance"] = noise_std
                
                # High variance in noise suggests inconsistent regions (possible tampering)
                if noise_std > noise_mean * 0.5:
                    result["consistent"] = False
                    result["suspicious"] = True
                    result["score"] -= 30.0
                    result["details"].append("Inconsistent noise patterns detected")
                    
                    # Count regions with significantly different noise
                    threshold = noise_mean + 2 * noise_std
                    inconsistent = sum(1 for n in noise_levels if abs(n - noise_mean) > threshold)
                    result["inconsistent_regions"] = inconsistent
                    
                    if inconsistent > len(noise_levels) * 0.2:  # More than 20% inconsistent
                        result["score"] -= 20.0
                        result["details"].append(f"{inconsistent} regions with inconsistent noise")
            
            result["score"] = max(0.0, min(100.0, result["score"]))
            logger.info(f"Noise pattern analysis complete. Score: {result['score']:.2f}, Consistent: {result['consistent']}")
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing noise patterns: {e}", exc_info=True)
            return result
    
    @staticmethod
    def calculate_file_hash(file_path: str) -> Dict:
        """
        Calculate file hash for integrity verification
        Returns: dict with hash information
        """
        result = {
            "hash_md5": None,
            "hash_sha256": None,
            "file_size": 0,
            "calculated": False
        }
        
        try:
            logger.info(f"Calculating file hash: {file_path}")
            
            if not os.path.exists(file_path):
                return result
            
            result["file_size"] = os.path.getsize(file_path)
            
            # Calculate MD5 and SHA256 hashes
            md5_hash = hashlib.md5()
            sha256_hash = hashlib.sha256()
            
            with open(file_path, 'rb') as f:
                # Read file in chunks to handle large files
                while chunk := f.read(8192):
                    md5_hash.update(chunk)
                    sha256_hash.update(chunk)
            
            result["hash_md5"] = md5_hash.hexdigest()
            result["hash_sha256"] = sha256_hash.hexdigest()
            result["calculated"] = True
            
            logger.info(f"File hash calculated. MD5: {result['hash_md5'][:16]}..., SHA256: {result['hash_sha256'][:16]}...")
            return result
            
        except Exception as e:
            logger.error(f"Error calculating file hash: {e}", exc_info=True)
            return result
    
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
                    "pdf_metadata": {},
                    "resolution_analysis": {},
                    "color_analysis": {},
                    "noise_analysis": {},
                    "file_hash": {},
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
                        "pdf_metadata": {},
                        "resolution_analysis": {},
                        "color_analysis": {},
                        "noise_analysis": {},
                        "file_hash": {},
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
            
            # NEW: PDF Metadata Analysis
            logger.info("Analyzing PDF metadata...")
            pdf_metadata = ForensicService.analyze_pdf_metadata(file_path)
            
            # NEW: Resolution Consistency Analysis
            logger.info("Analyzing resolution consistency...")
            resolution_analysis = ForensicService.analyze_resolution_consistency(image_path)
            
            # NEW: Color Histogram Analysis
            logger.info("Analyzing color histogram...")
            color_analysis = ForensicService.analyze_color_histogram(image_path)
            
            # NEW: Noise Pattern Analysis
            logger.info("Analyzing noise patterns...")
            noise_analysis = ForensicService.analyze_noise_patterns(image_path)
            
            # NEW: File Hash Calculation
            logger.info("Calculating file hash...")
            file_hash = ForensicService.calculate_file_hash(file_path)
            
            # Calculate forensic penalty (0-15)
            penalty = 0.0
            details = []
            
            if ela_score > 50:
                penalty += 5.0
                details.append(f"High ELA score: {ela_score:.2f}")
            
            if copy_move_detected:
                # Graduated penalty based on confidence level and document type
                # Check if this is likely a scanned document (affects penalty severity)
                is_scanned_doc = False
                try:
                    if ForensicService.is_pdf(file_path):
                        # For PDFs, check if converted image looks scanned
                        test_img = cv2.imread(image_path)
                        if test_img is not None:
                            if len(test_img.shape) == 3:
                                gray_test = cv2.cvtColor(test_img, cv2.COLOR_BGR2GRAY)
                                color_var = np.var([np.mean(test_img[:,:,0]), np.mean(test_img[:,:,1]), np.mean(test_img[:,:,2])])
                                if color_var < 100 or max(test_img.shape[:2]) < 2000:
                                    is_scanned_doc = True
                            else:
                                is_scanned_doc = True
                except:
                    pass
                
                # Adjust penalties for scanned documents (they naturally have more repeated patterns)
                if is_scanned_doc:
                    # For scanned documents, be more lenient
                    if copy_move_confidence > 70.0:
                        penalty += 5.0  # Reduced from 7.0 for scanned docs
                        details.append(f"Copy-move detected: {copy_move_confidence:.2f}% (high confidence - scanned document)")
                    elif copy_move_confidence > 50.0:
                        penalty += 3.0  # Reduced penalty
                        details.append(f"Copy-move detected: {copy_move_confidence:.2f}% (medium confidence - scanned document)")
                    else:
                        penalty += 1.5  # Minimal penalty for scanned docs
                        details.append(f"Copy-move detected: {copy_move_confidence:.2f}% (low confidence - likely scanning artifacts)")
                else:
                    # For regular documents, use original penalties
                    if copy_move_confidence > 40.0:
                        penalty += 7.0  # Full penalty for high confidence
                        details.append(f"Copy-move detected: {copy_move_confidence:.2f}% (high confidence)")
                    elif copy_move_confidence > 25.0:
                        penalty += 4.0  # Reduced penalty for medium confidence
                        details.append(f"Copy-move detected: {copy_move_confidence:.2f}% (medium confidence)")
                    else:
                        penalty += 2.0  # Minimal penalty for low confidence (likely document structure)
                        details.append(f"Copy-move detected: {copy_move_confidence:.2f}% (low confidence - may be document structure)")
            
            if jpeg_quality < 30:
                penalty += 3.0
                details.append(f"Low JPEG quality: {jpeg_quality:.2f}")
            
            # NEW: PDF Metadata penalties
            if pdf_metadata.get("suspicious", False):
                pdf_score = pdf_metadata.get("score", 100.0)
                if pdf_score < 70:
                    penalty += 2.0
                    details.append(f"PDF metadata anomalies detected (score: {pdf_score:.1f})")
                    for flag in pdf_metadata.get("suspicious_flags", [])[:2]:  # Limit to first 2 flags
                        details.append(f"  - {flag}")
            
            # NEW: Resolution consistency penalties
            if resolution_analysis.get("suspicious", False):
                res_score = resolution_analysis.get("score", 100.0)
                if res_score < 70:
                    penalty += 2.0
                    details.append(f"Resolution inconsistencies detected (score: {res_score:.1f})")
                    if resolution_analysis.get("upscaling_detected", False):
                        details.append("  - Possible upscaling detected")
            
            # NEW: Color histogram penalties
            if color_analysis.get("suspicious", False):
                color_score = color_analysis.get("score", 100.0)
                # Only apply penalty if score is very low (scanned docs may have lower scores naturally)
                if color_score < 50:  # More lenient threshold
                    penalty += 1.5
                    details.append(f"Color space anomalies detected (score: {color_score:.1f})")
                elif color_score < 70:
                    # Just note it, don't penalize heavily
                    details.append(f"Minor color space variations (score: {color_score:.1f})")
            
            # NEW: Noise pattern penalties
            if noise_analysis.get("suspicious", False):
                noise_score = noise_analysis.get("score", 100.0)
                if noise_score < 70:
                    penalty += 2.0
                    details.append(f"Inconsistent noise patterns detected (score: {noise_score:.1f})")
                    if noise_analysis.get("inconsistent_regions", 0) > 0:
                        details.append(f"  - {noise_analysis['inconsistent_regions']} regions with inconsistent noise")
            
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
                # NEW: Additional forensic checks
                "pdf_metadata": pdf_metadata,
                "resolution_analysis": resolution_analysis,
                "color_analysis": color_analysis,
                "noise_analysis": noise_analysis,
                "file_hash": file_hash,
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
                "pdf_metadata": {},
                "resolution_analysis": {},
                "color_analysis": {},
                "noise_analysis": {},
                "file_hash": {},
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

