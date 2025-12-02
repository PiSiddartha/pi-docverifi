"""
LLM Service for extracting structured data from OCR text using OpenAI GPT-5 nano with structured outputs
"""
import logging
import json
from typing import Dict, Optional
import os
from openai import OpenAI
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Try to import settings, but don't fail if not available
try:
    from app.core.config import settings
    HAS_SETTINGS = True
except ImportError:
    HAS_SETTINGS = False


# Pydantic models for structured outputs
class CompanyFields(BaseModel):
    """Structured output model for company registration fields"""
    company_name: Optional[str] = Field(
        None,
        description="Full company name ending in LIMITED/PLC/LLC"
    )
    company_number: Optional[str] = Field(
        None,
        description="Company number (6-8 digits, may have letters like SC)"
    )
    address: Optional[str] = Field(
        None,
        description="Registered office address"
    )


class VATFields(BaseModel):
    """Structured output model for VAT registration fields"""
    vat_number: Optional[str] = Field(
        None,
        description="UK VAT number (format: GB + 9 digits, or 9 digits starting with 0-9)"
    )
    business_name: Optional[str] = Field(
        None,
        description="Full business/company name"
    )
    address: Optional[str] = Field(
        None,
        description="Registered business address"
    )
    registration_date: Optional[str] = Field(
        None,
        description="VAT registration date (format: DD/MM/YYYY or YYYY-MM-DD)"
    )


class DirectorFields(BaseModel):
    """Structured output model for director verification fields"""
    director_name: Optional[str] = Field(
        None,
        description="Full name of the director (first name + last name)"
    )
    date_of_birth: Optional[str] = Field(
        None,
        description="Date of birth (format: DD/MM/YYYY or YYYY-MM-DD)"
    )
    address: Optional[str] = Field(
        None,
        description="Director's residential address"
    )
    company_name: Optional[str] = Field(
        None,
        description="Company name where director is appointed"
    )
    company_number: Optional[str] = Field(
        None,
        description="Company registration number (6-8 digits, may have letters like SC)"
    )
    appointment_date: Optional[str] = Field(
        None,
        description="Date of appointment as director (format: DD/MM/YYYY or YYYY-MM-DD)"
    )


class LLMService:
    """Service for extracting structured fields from OCR text using OpenAI GPT-5 nano"""
    
    _client: Optional[OpenAI] = None
    _model: str = "gpt-5-nano"
    
    @classmethod
    def _get_client(cls) -> Optional[OpenAI]:
        """Get OpenAI client instance"""
        if cls._client is None:
            api_key = None
            if HAS_SETTINGS:
                api_key = getattr(settings, 'OPENAI_API_KEY', None) or os.getenv('OPENAI_API_KEY')
                model = getattr(settings, 'OPENAI_MODEL', 'gpt-5-nano')
                cls._model = model
            else:
                api_key = os.getenv('OPENAI_API_KEY')
            
            if not api_key:
                logger.warning("OpenAI API key not found. LLM service will not be available.")
                return None
            
            cls._client = OpenAI(api_key=api_key)
        return cls._client
    
    @classmethod
    def _get_model(cls) -> str:
        """Get OpenAI model name"""
        if HAS_SETTINGS:
            return getattr(settings, 'OPENAI_MODEL', 'gpt-5-nano')
        return os.getenv('OPENAI_MODEL', 'gpt-5-nano')
    
    @staticmethod
    def extract_company_fields(raw_text: str) -> Dict[str, Optional[str]]:
        """
        Extract structured company fields from raw OCR text using OpenAI GPT-5 nano with structured outputs
        
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
        
        client = LLMService._get_client()
        if not client:
            logger.warning("OpenAI client not available, falling back to regex extraction")
            return LLMService._fallback_extraction(raw_text)
        
        try:
            model = LLMService._get_model()
            
            # Truncate text if too long (OpenAI has token limits)
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
            
            # Create a focused, concise prompt for extracting company information
            prompt = f"""Extract only these fields from the document:
- company_name: Full company name (LIMITED/PLC/LLC)
- company_number: Company number (6-8 digits)
- address: Registered office address

Return null for missing fields. No explanations.

Document text:
{truncated_text}"""

            # Log summary
            if len(raw_text) > (max_header_length + max_footer_length):
                logger.info(f"Calling OpenAI API ({model}): {len(raw_text):,} chars -> {len(truncated_text):,} chars (truncated)")
            else:
                logger.info(f"Calling OpenAI API ({model}): {len(raw_text):,} chars")
            
            # Use structured outputs with Pydantic model
            response = client.beta.chat.completions.parse(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "Extract structured data from UK Companies House documents. Return ONLY the requested JSON fields. No explanations or additional text."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format=CompanyFields,
                timeout=120.0
            )
            
            # Extract structured output
            parsed_response = response.choices[0].message.parsed
            raw_content = response.choices[0].message.content
            
            # Log complete response
            logger.info(f"Complete GPT response: {raw_content}")
            if parsed_response:
                logger.info(f"Parsed response: {parsed_response.model_dump_json(indent=2)}")
            
            if not parsed_response:
                logger.warning("No parsed response from OpenAI, falling back to regex")
                return LLMService._fallback_extraction(raw_text)
            
            # Log token usage summary
            usage = response.usage
            if usage:
                prompt_tokens = usage.prompt_tokens or 0
                completion_tokens = usage.completion_tokens or 0
                total_tokens = usage.total_tokens or 0
                logger.info(f"Token usage: {prompt_tokens:,} input + {completion_tokens:,} output = {total_tokens:,} total")
            
            # Convert Pydantic model to dict
            extracted_data = parsed_response.model_dump()
            
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
            
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}", exc_info=True)
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
    
    @staticmethod
    def extract_vat_fields(raw_text: str) -> Dict[str, Optional[str]]:
        """
        Extract VAT registration fields from raw OCR text using OpenAI GPT-5 nano with structured outputs
        
        Args:
            raw_text: Raw OCR extracted text
            
        Returns:
            Dictionary with vat_number, business_name, address, registration_date
        """
        if not raw_text or not raw_text.strip():
            logger.warning("Empty raw text provided to LLM VAT extraction")
            return {
                "vat_number": None,
                "business_name": None,
                "address": None,
                "registration_date": None
            }
        
        client = LLMService._get_client()
        if not client:
            logger.warning("OpenAI client not available, returning empty fields")
            return {
                "vat_number": None,
                "business_name": None,
                "address": None,
                "registration_date": None
            }
        
        try:
            model = LLMService._get_model()
            
            # Truncate text if too long
            max_header_length = 2000
            max_footer_length = 1000
            
            if len(raw_text) > (max_header_length + max_footer_length):
                header = raw_text[:max_header_length]
                footer = raw_text[-max_footer_length:] if len(raw_text) > max_footer_length else ""
                truncated_text = f"{header}\n\n[... document truncated ...]\n\n{footer}"
            else:
                truncated_text = raw_text
            
            prompt = f"""Extract only these fields:
- vat_number: UK VAT number (GB + 9 digits or 9 digits)
- business_name: Full business/company name
- address: Registered business address
- registration_date: Registration date (DD/MM/YYYY or YYYY-MM-DD)

Return null for missing fields. No explanations.

Document text:
{truncated_text}"""
            
            logger.info(f"Calling OpenAI API for VAT field extraction")
            
            # Use structured outputs with Pydantic model
            response = client.beta.chat.completions.parse(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "Extract structured data from UK VAT certificates. Return ONLY the requested JSON fields. No explanations or additional text."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format=VATFields,
                timeout=120.0
            )
            
            # Extract structured output
            parsed_response = response.choices[0].message.parsed
            raw_content = response.choices[0].message.content
            
            # Log complete response
            logger.info(f"Complete GPT response (VAT): {raw_content}")
            if parsed_response:
                logger.info(f"Parsed response (VAT): {parsed_response.model_dump_json(indent=2)}")
            
            if not parsed_response:
                logger.warning("No parsed response from OpenAI for VAT extraction")
                return {
                    "vat_number": None,
                    "business_name": None,
                    "address": None,
                    "registration_date": None
                }
            
            # Convert Pydantic model to dict
            extracted_data = parsed_response.model_dump()
            
            fields = {
                "vat_number": extracted_data.get("vat_number"),
                "business_name": extracted_data.get("business_name"),
                "address": extracted_data.get("address"),
                "registration_date": extracted_data.get("registration_date")
            }
            
            # Clean up extracted values
            for key, value in fields.items():
                if value and isinstance(value, str):
                    value = " ".join(value.split())
                    if value.lower() in ["null", "none", "n/a", ""]:
                        value = None
                    fields[key] = value
            
            logger.info(f"LLM extracted VAT fields: vat_number={fields.get('vat_number')}, "
                       f"business_name={fields.get('business_name')}")
            
            return fields
            
        except Exception as e:
            logger.error(f"Error in LLM VAT extraction: {e}", exc_info=True)
            return {
                "vat_number": None,
                "business_name": None,
                "address": None,
                "registration_date": None
            }
    
    @staticmethod
    def extract_director_fields(raw_text: str) -> Dict[str, Optional[str]]:
        """
        Extract director verification fields from raw OCR text using OpenAI GPT-5 nano with structured outputs
        
        Args:
            raw_text: Raw OCR extracted text
            
        Returns:
            Dictionary with director_name, date_of_birth, address, company_name, appointment_date
        """
        if not raw_text or not raw_text.strip():
            logger.warning("Empty raw text provided to LLM Director extraction")
            return {
                "director_name": None,
                "date_of_birth": None,
                "address": None,
                "company_name": None,
                "company_number": None,
                "appointment_date": None
            }
        
        client = LLMService._get_client()
        if not client:
            logger.warning("OpenAI client not available, returning empty fields")
            return {
                "director_name": None,
                "date_of_birth": None,
                "address": None,
                "company_name": None,
                "company_number": None,
                "appointment_date": None
            }
        
        try:
            model = LLMService._get_model()
            
            # Truncate text if too long
            max_header_length = 2000
            max_footer_length = 1000
            
            if len(raw_text) > (max_header_length + max_footer_length):
                header = raw_text[:max_header_length]
                footer = raw_text[-max_footer_length:] if len(raw_text) > max_footer_length else ""
                truncated_text = f"{header}\n\n[... document truncated ...]\n\n{footer}"
            else:
                truncated_text = raw_text
            
            prompt = f"""Extract only these fields:
- director_name: Full name (first + last)
- date_of_birth: DOB (DD/MM/YYYY or YYYY-MM-DD)
- address: Residential address
- company_name: Company name
- company_number: Company number (6-8 digits)
- appointment_date: Appointment date (DD/MM/YYYY or YYYY-MM-DD)

Return null for missing fields. No explanations.

Document text:
{truncated_text}"""
            
            logger.info(f"Calling OpenAI API for Director field extraction")
            
            # Use structured outputs with Pydantic model
            response = client.beta.chat.completions.parse(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "Extract structured data from UK director verification documents. Return ONLY the requested JSON fields. No explanations or additional text."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format=DirectorFields,
                timeout=120.0
            )
            
            # Extract structured output
            parsed_response = response.choices[0].message.parsed
            raw_content = response.choices[0].message.content
            
            # Log complete response
            logger.info(f"Complete GPT response (Director): {raw_content}")
            if parsed_response:
                logger.info(f"Parsed response (Director): {parsed_response.model_dump_json(indent=2)}")
            
            if not parsed_response:
                logger.warning("No parsed response from OpenAI for Director extraction")
                return {
                    "director_name": None,
                    "date_of_birth": None,
                    "address": None,
                    "company_name": None,
                    "company_number": None,
                    "appointment_date": None
                }
            
            # Convert Pydantic model to dict
            extracted_data = parsed_response.model_dump()
            
            fields = {
                "director_name": extracted_data.get("director_name"),
                "date_of_birth": extracted_data.get("date_of_birth"),
                "address": extracted_data.get("address"),
                "company_name": extracted_data.get("company_name"),
                "company_number": extracted_data.get("company_number"),
                "appointment_date": extracted_data.get("appointment_date")
            }
            
            # Clean up extracted values
            for key, value in fields.items():
                if value and isinstance(value, str):
                    value = " ".join(value.split())
                    if value.lower() in ["null", "none", "n/a", ""]:
                        value = None
                    fields[key] = value
            
            logger.info(f"LLM extracted Director fields: director_name={fields.get('director_name')}, "
                       f"company_name={fields.get('company_name')}, company_number={fields.get('company_number')}")
            
            return fields
            
        except Exception as e:
            logger.error(f"Error in LLM Director extraction: {e}", exc_info=True)
            return {
                "director_name": None,
                "date_of_birth": None,
                "address": None,
                "company_name": None,
                "company_number": None,
                "appointment_date": None
            }
