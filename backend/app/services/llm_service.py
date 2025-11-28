"""
LLM Service for extracting structured data from OCR text using Ollama
"""
import logging
import json
import requests
from typing import Dict, Optional
import os

logger = logging.getLogger(__name__)

# Try to import settings, but don't fail if not available
try:
    from app.core.config import settings
    HAS_SETTINGS = True
except ImportError:
    HAS_SETTINGS = False


class LLMService:
    """Service for extracting structured fields from OCR text using Ollama"""
    
    _ollama_base_url = None
    
    @classmethod
    def _get_ollama_url(cls) -> str:
        """Get Ollama API base URL"""
        if cls._ollama_base_url is None:
            if HAS_SETTINGS:
                cls._ollama_base_url = getattr(settings, 'OLLAMA_BASE_URL', 'http://localhost:11434')
            else:
                cls._ollama_base_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
        return cls._ollama_base_url
    
    @staticmethod
    def extract_company_fields(raw_text: str) -> Dict[str, Optional[str]]:
        """
        Extract structured company fields from raw OCR text using Ollama gemma3:latest
        
        Args:
            raw_text: Raw OCR extracted text
            
        Returns:
            Dictionary with company_name, company_number, and address
        """
        if not raw_text or not raw_text.strip():
            logger.warning("Empty raw text provided to LLM extraction")
            return {
                "company_name": None,
                "company_number": None,
                "address": None
            }
        
        try:
            ollama_url = LLMService._get_ollama_url()
            model = "gemma3:latest"
            
            # Truncate text if too long (Ollama has 4096 token limit, leave room for prompt)
            # Strategy: Keep first 2000 chars (header with company info) + last 1000 chars (address often at end)
            max_header_length = 2000
            max_footer_length = 1000
            
            if len(raw_text) > (max_header_length + max_footer_length):
                header = raw_text[:max_header_length]
                footer = raw_text[-max_footer_length:] if len(raw_text) > max_footer_length else ""
                truncated_text = f"{header}\n\n[... document truncated ...]\n\n{footer}"
                logger.info(f"Truncating OCR text from {len(raw_text)} to ~{max_header_length + max_footer_length} characters for LLM (header + footer)")
            else:
                truncated_text = raw_text
            
            # Create a focused prompt for extracting company information
            prompt = f"""Extract company info from UK Companies House document. Return JSON with keys: company_name, company_number, address.

Rules:
- company_name: Full company name ending in LIMITED/PLC/LLC
- company_number: Company number (6-8 digits, may have letters like SC)
- address: Registered office address

Use null if not found.

Text:
{truncated_text}

JSON only:"""

            # Call Ollama API
            api_url = f"{ollama_url}/api/generate"
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "format": "json",  # Request JSON format
                "options": {
                    "temperature": 0.1,  # Low temperature for more deterministic extraction
                    "top_p": 0.9
                }
            }
            
            logger.info(f"Calling Ollama API with model {model} for field extraction")
            # Increased timeout to 120 seconds for large documents
            response = requests.post(api_url, json=payload, timeout=120)
            response.raise_for_status()
            
            result = response.json()
            response_text = result.get("response", "")
            
            # Try to parse JSON from response
            # Sometimes Ollama wraps JSON in markdown code blocks or adds extra text
            json_text = response_text.strip()
            
            # Remove markdown code blocks if present
            if json_text.startswith("```"):
                lines = json_text.split("\n")
                json_text = "\n".join(lines[1:-1]) if len(lines) > 2 else json_text
            elif "```json" in json_text:
                # Handle ```json ... ``` format
                start_idx = json_text.find("```json") + 7
                end_idx = json_text.rfind("```")
                if end_idx > start_idx:
                    json_text = json_text[start_idx:end_idx].strip()
            
            # Try to extract JSON object if there's extra text
            if "{" in json_text and "}" in json_text:
                start_idx = json_text.find("{")
                end_idx = json_text.rfind("}") + 1
                json_text = json_text[start_idx:end_idx]
            
            # Parse JSON
            try:
                extracted_data = json.loads(json_text)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON from LLM response: {e}")
                logger.debug(f"Response text: {response_text[:500]}")
                # Fallback: try to extract fields using regex patterns
                return LLMService._fallback_extraction(raw_text)
            
            # Validate and clean extracted data
            fields = {
                "company_name": extracted_data.get("company_name"),
                "company_number": extracted_data.get("company_number"),
                "address": extracted_data.get("address")
            }
            
            # Clean up extracted values
            for key, value in fields.items():
                if value and isinstance(value, str):
                    # Remove extra whitespace
                    value = " ".join(value.split())
                    # Remove null string
                    if value.lower() in ["null", "none", "n/a", ""]:
                        value = None
                    fields[key] = value
            
            logger.info(f"LLM extracted fields: company_name={fields.get('company_name')}, "
                       f"company_number={fields.get('company_number')}, "
                       f"address={'Found' if fields.get('address') else 'Not found'}")
            
            return fields
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling Ollama API: {e}")
            logger.info("Falling back to regex-based extraction")
            return LLMService._fallback_extraction(raw_text)
        except Exception as e:
            logger.error(f"Unexpected error in LLM extraction: {e}", exc_info=True)
            logger.info("Falling back to regex-based extraction")
            return LLMService._fallback_extraction(raw_text)
    
    @staticmethod
    def _fallback_extraction(raw_text: str) -> Dict[str, Optional[str]]:
        """
        Fallback extraction using simple regex patterns if LLM fails
        """
        import re
        
        fields = {
            "company_name": None,
            "company_number": None,
            "address": None
        }
        
        # Extract company number
        company_number_patterns = [
            r'Company\s+No\.?[\s:]*([A-Z]{2}?\d{6,8}|\d{6,8})\b',
            r'(?:^|\s)No\.?[\s:]*([A-Z]{2}?\d{6,8}|\d{6,8})\b',
            r'\b([A-Z]{2}\d{6})\b',
            r'\b(\d{8})\b',
            r'\b(\d{7})\b',
        ]
        
        for pattern in company_number_patterns:
            matches = re.findall(pattern, raw_text, re.IGNORECASE | re.MULTILINE)
            if matches:
                fields["company_number"] = matches[0].upper()
                break
        
        # Extract company name
        name_patterns = [
            r'certify\s+that\s+([A-Z][A-Za-z0-9\s&.,\-()]{3,}?(?:\s+LIMITED|\s+PLC|\s+LLC|\s+INC\.?))',
            r'Company\s+name[\s:]+([A-Z][A-Za-z0-9\s&.,\-()]{3,}?(?:\s+LIMITED|\s+PLC|\s+LLC|\s+INC\.?))',
        ]
        
        for pattern in name_patterns:
            matches = re.findall(pattern, raw_text, re.IGNORECASE)
            if matches:
                fields["company_name"] = matches[0].strip()
                break
        
        # Extract address (look for UK postcode)
        postcode_pattern = r'\b([A-Z]{1,2}\d{1,2}\s?\d[A-Z]{2})\b'
        postcode_matches = re.findall(postcode_pattern, raw_text.upper())
        if postcode_matches:
            idx = raw_text.upper().find(postcode_matches[0])
            if idx > 0:
                start = max(0, idx - 100)
                address_candidate = raw_text[start:idx + len(postcode_matches[0])].strip()
                if len(address_candidate) > 10:
                    fields["address"] = address_candidate
        
        return fields

