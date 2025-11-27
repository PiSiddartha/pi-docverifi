"""
OCR Service for extracting text from documents
"""
import pytesseract
from PIL import Image
import pdf2image
import io
from typing import Dict, Optional, Tuple
import re
import logging

logger = logging.getLogger(__name__)


class OCRService:
    """Service for OCR extraction from PDFs and images"""
    
    @staticmethod
    def extract_text_from_pdf(pdf_path: str) -> Tuple[str, float]:
        """
        Extract text from PDF and return raw text with confidence score
        """
        try:
            # Convert PDF to images
            images = pdf2image.convert_from_path(pdf_path, dpi=300)
            
            all_text = []
            all_confidences = []
            
            for image in images:
                # Extract text with confidence
                data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
                
                text_parts = []
                confidences = []
                
                for i, text in enumerate(data['text']):
                    if text.strip():
                        text_parts.append(text)
                        conf = float(data['conf'][i])
                        if conf > 0:
                            confidences.append(conf)
                
                page_text = ' '.join(text_parts)
                all_text.append(page_text)
                
                if confidences:
                    all_confidences.extend(confidences)
            
            full_text = '\n'.join(all_text)
            avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0
            
            return full_text, avg_confidence
            
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            return "", 0.0
    
    @staticmethod
    def extract_fields(text: str) -> Dict[str, Optional[str]]:
        """
        Extract structured fields from OCR text
        Returns: company_name, company_number, address, date
        """
        fields = {
            "company_name": None,
            "company_number": None,
            "address": None,
            "date": None
        }
        
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
        
        # Extract dates (various formats)
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
        pattern1 = r'certify\s+that\s+([A-Z][A-Za-z0-9\s&.,\-]{3,}?(?:\s+LIMITED|\s+PLC|\s+LLC|\s+INC\.?))\s+is\s+this\s+day'
        matches = re.findall(pattern1, text, re.IGNORECASE)
        if matches:
            company_name = matches[0].strip()
            # Clean up whitespace
            company_name = re.sub(r'\s+', ' ', company_name)
            logger.info(f"Extracted company name (pattern 1 - certify that): {company_name}")
        
        # Pattern 2: "Company name: [NAME]" or "[NAME] (in full)"
        if not company_name:
            pattern2 = r'Company\s+name[\s:]+([A-Z][A-Za-z0-9\s&.,\-]{3,}?(?:\s+LIMITED|\s+PLC|\s+LLC|\s+INC\.?))(?:\s+\(in\s+full\))?'
            matches = re.findall(pattern2, text, re.IGNORECASE)
            if matches:
                company_name = matches[0].strip()
                company_name = re.sub(r'\s+', ' ', company_name)
                logger.info(f"Extracted company name (pattern 2 - Company name:): {company_name}")
        
        # Pattern 3: Look for standalone company names with LIMITED/PLC/LLC
        if not company_name:
            # Look for lines that contain LIMITED/PLC/LLC but aren't certificate headers
            lines = text.split('\n')
            for line in lines[:25]:  # Check first 25 lines
                line = line.strip()
                # Must contain company suffix
                if re.search(r'\b(LIMITED|PLC|LLC|INC\.?)\b', line, re.IGNORECASE):
                    # Skip certificate/document header text
                    skip_keywords = [
                        'CERTIFICATE', 'INCORPORATION', 'COMPANIES ACT', 'REGISTRAR',
                        'FILE COPY', 'PRIVATE LIMITED', 'COMPANY NO', 'NUMBER',
                        'HEREBY CERTIFIES', 'THIS DAY', 'REGISTRAR OF COMPANIES'
                    ]
                    if not any(keyword in line.upper() for keyword in skip_keywords):
                        # Must have substantial text (not just numbers)
                        if re.search(r'[A-Za-z]{4,}', line) and len(line) > 8:
                            # Extract just the company name part
                            # Remove "The Company's name is" type prefixes
                            cleaned = re.sub(r'^(The\s+)?Company[\'s\s]+name\s+is\s*:?\s*', '', line, flags=re.IGNORECASE)
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

