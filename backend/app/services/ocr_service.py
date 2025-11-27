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
        
        # Extract company number (UK format: 8 digits or alphanumeric)
        company_number_pattern = r'\b([A-Z]{2}?\d{6}|\d{8})\b'
        matches = re.findall(company_number_pattern, text.upper())
        if matches:
            fields["company_number"] = matches[0]
        
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
        
        # Extract company name (usually at the beginning, before company number)
        lines = text.split('\n')
        for line in lines[:10]:  # Check first 10 lines
            line = line.strip()
            if line and len(line) > 3:
                # Skip if it's just numbers or dates
                if not re.match(r'^[\d\s\-/]+$', line):
                    if not fields["company_name"] or len(line) > len(fields["company_name"]):
                        fields["company_name"] = line
        
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

