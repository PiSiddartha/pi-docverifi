"""
Pipeline Service - Routes document verification to type-specific pipelines
"""
import logging
import re
from typing import Dict, Any, Optional, Union
from app.db.models import (
    Document,
    DocumentType,
    CompaniesHouseDocument,
    CompanyRegistrationDocument,
    VATRegistrationDocument,
    DirectorVerificationDocument
)
from app.services.ocr_service import OCRService
from app.services.forensic_service import ForensicService
from app.services.companies_house_service import CompaniesHouseService
from app.services.scoring_service import ScoringService

# Try to import HMRC VAT service
try:
    from app.services.hmrc_vat_service import HMRCVATService
    HAS_HMRC_SERVICE = True
except ImportError:
    HAS_HMRC_SERVICE = False
    HMRCVATService = None

logger = logging.getLogger(__name__)

# Check if LLM service is available
try:
    from app.services.llm_service import LLMService
    HAS_LLM_SERVICE = True
except ImportError:
    HAS_LLM_SERVICE = False
    LLMService = None


class BasePipeline:
    """Base class for document verification pipelines"""
    
    def __init__(
        self,
        base_doc: Document,
        type_doc: Optional[Union[
            CompaniesHouseDocument,
            CompanyRegistrationDocument,
            VATRegistrationDocument,
            DirectorVerificationDocument
        ]],
        update_progress_callback=None
    ):
        self.base_doc = base_doc
        self.type_doc = type_doc
        self.file_path = base_doc.file_path
        self.update_progress = update_progress_callback or (lambda step, progress, message, status=None: None)
    
    def process(self) -> Dict[str, Any]:
        """
        Process the document through the pipeline
        Returns a dict with processing results
        """
        raise NotImplementedError("Subclasses must implement process()")


class CompaniesHousePipeline(BasePipeline):
    """Pipeline for Companies House document verification"""
    
    def process(self) -> Dict[str, Any]:
        """
        Process Companies House document verification
        Steps:
        1. OCR Extraction
        2. Forensic Analysis
        3. Companies House API Lookup
        4. Scoring
        """
        results = {
            "ocr_result": None,
            "forensic_result": None,
            "companies_house_result": None,
            "scoring_result": None
        }
        
        # Ensure type_doc is CompaniesHouseDocument
        if not isinstance(self.type_doc, CompaniesHouseDocument):
            logger.error(f"[COMPANIES_HOUSE_PIPELINE] Type document is not CompaniesHouseDocument")
            return results
        
        # Step 1: OCR Extraction
        logger.info(f"[COMPANIES_HOUSE_PIPELINE] Starting OCR extraction for document: {self.base_doc.document_id}")
        self.update_progress("ocr_extraction", 20, "Extracting text from document using OCR", "processing")
        
        # Extract raw text first
        raw_text, confidence = OCRService.extract_text_from_pdf(self.file_path)
        
        # Update progress for LLM field extraction
        self.update_progress("llm_extraction", 30, "Extracting structured fields using LLM (gemma3:latest)", "processing")
        
        # Extract structured fields using LLM (with fallback to regex)
        fields = OCRService.extract_fields(raw_text)
        
        # Combine results
        ocr_result = {
            "raw_text": raw_text,
            "confidence": confidence,
            "company_name": fields.get("company_name"),
            "company_number": fields.get("company_number"),
            "address": fields.get("address"),
            "date": fields.get("date")
        }
        results["ocr_result"] = ocr_result
        
        # Update document with OCR data
        self.type_doc.ocr_company_name = ocr_result.get("company_name")
        self.type_doc.ocr_company_number = ocr_result.get("company_number")
        self.type_doc.ocr_address = ocr_result.get("address")
        self.type_doc.ocr_date = ocr_result.get("date")
        self.type_doc.ocr_confidence = ocr_result.get("confidence")
        self.type_doc.ocr_raw_text = ocr_result.get("raw_text")
        
        # Update progress after OCR completes
        extraction_method = "LLM" if ocr_result.get("company_name") or ocr_result.get("company_number") else "regex"
        self.update_progress("ocr_complete", 40, f"OCR completed ({extraction_method}). Company: {ocr_result.get('company_name', 'N/A')}", "processing")
        
        # Step 2: Forensic Analysis
        logger.info(f"[COMPANIES_HOUSE_PIPELINE] Starting forensic analysis for document: {self.base_doc.document_id}")
        self.update_progress("forensic_analysis", 50, "Analyzing document for tampering and authenticity", "processing")
        forensic_result = ForensicService.process_document(self.file_path)
        results["forensic_result"] = forensic_result
        
        # Update document with forensic data (common fields go to base_doc)
        self.base_doc.forensic_score = forensic_result.get("forensic_score")
        self.base_doc.forensic_penalty = forensic_result.get("forensic_penalty")
        self.base_doc.forensic_details = forensic_result.get("details")
        self.base_doc.exif_data = forensic_result.get("exif_data")
        self.base_doc.ela_score = forensic_result.get("ela_score")
        self.base_doc.jpeg_quality = forensic_result.get("jpeg_quality")
        self.base_doc.copy_move_detected = forensic_result.get("copy_move_detected")
        
        # Update progress after forensic analysis completes
        self.update_progress("forensic_complete", 60, f"Forensic analysis complete. Score: {forensic_result.get('forensic_score', 'N/A')}", "processing")
        
        # Step 3: Companies House API Lookup
        logger.info(f"[COMPANIES_HOUSE_PIPELINE] Starting Companies House lookup for document: {self.base_doc.document_id}")
        self.update_progress("companies_house_lookup", 70, "Looking up company information in Companies House registry", "processing")
        companies_house_service = CompaniesHouseService()
        company_number = None
        
        # Try to get company number from OCR or merchant input
        if self.type_doc.ocr_company_number:
            company_number = self.type_doc.ocr_company_number
        elif self.type_doc.merchant_company_number:
            company_number = self.type_doc.merchant_company_number
        
        if company_number:
            # Normalize company number for API call (handles 6, 7, 8 digit numbers)
            normalized_number = company_number.strip().upper()
            normalized_number = re.sub(r'[\s\-]', '', normalized_number)
            
            # Pad to 8 digits if it's all digits
            if normalized_number.isdigit():
                if len(normalized_number) == 6:
                    normalized_number = '00' + normalized_number  # 6 -> 8 digits
                elif len(normalized_number) == 7:
                    normalized_number = '0' + normalized_number    # 7 -> 8 digits
                # 8 digits is already correct
            
            ch_data = companies_house_service.extract_company_data(normalized_number)
            results["companies_house_result"] = ch_data
            
            # Update document with Companies House data
            self.type_doc.companies_house_company_name = ch_data.get("company_name")
            self.type_doc.companies_house_company_number = ch_data.get("company_number")
            self.type_doc.companies_house_address = ch_data.get("address")
            self.type_doc.companies_house_date = ch_data.get("date")
            self.type_doc.companies_house_officers = ch_data.get("officers")
            self.type_doc.companies_house_data = ch_data.get("data")
            
            # Update progress after Companies House lookup completes
            self.update_progress("companies_house_complete", 80, f"Companies House lookup complete. Company: {ch_data.get('company_name', 'N/A')}", "processing")
        else:
            logger.info(f"[COMPANIES_HOUSE_PIPELINE] No company number found, skipping Companies House lookup")
            results["companies_house_result"] = None
            self.update_progress("companies_house_skipped", 80, "Companies House lookup skipped (no company number found)", "processing")
        
        # Step 4: Scoring
        logger.info(f"[COMPANIES_HOUSE_PIPELINE] Calculating scores for document: {self.base_doc.document_id}")
        self.update_progress("score_calculation", 90, "Calculating final verification scores", "processing")
        ocr_data = {
            "company_name": self.type_doc.ocr_company_name,
            "company_number": self.type_doc.ocr_company_number,
            "address": self.type_doc.ocr_address,
            "date": self.type_doc.ocr_date,
            "confidence": self.type_doc.ocr_confidence
        }
        
        merchant_data = {
            "company_name": self.type_doc.merchant_company_name,
            "company_number": self.type_doc.merchant_company_number,
            "address": self.type_doc.merchant_address,
            "date": self.type_doc.merchant_date
        }
        
        companies_house_data = {
            "company_name": self.type_doc.companies_house_company_name,
            "company_number": self.type_doc.companies_house_company_number,
            "address": self.type_doc.companies_house_address,
            "date": self.type_doc.companies_house_date
        }
        
        scoring_result = ScoringService.process_scoring(
            ocr_data,
            merchant_data,
            companies_house_data,
            self.base_doc.forensic_penalty
        )
        results["scoring_result"] = scoring_result
        
        # Update document with scores
        if scoring_result:
            self.type_doc.ocr_score = scoring_result.get("ocr_score", 0.0)
            self.type_doc.registry_score = scoring_result.get("registry_score", 0.0)
            self.type_doc.provided_score = scoring_result.get("provided_score", 0.0)
            self.type_doc.data_match_score = scoring_result.get("data_match_score", 0.0)
            # Store OCR comparison score in comparison_details for now (can add DB field later)
            if not self.type_doc.comparison_details:
                self.type_doc.comparison_details = {}
            self.type_doc.comparison_details["ocr_comparison_score"] = scoring_result.get("ocr_comparison_score", 0.0)
            self.type_doc.final_score = scoring_result.get("final_score", 0.0)
            self.base_doc.decision = scoring_result.get("decision", "FAIL")
        
        return results


class CompanyRegistrationPipeline(BasePipeline):
    """Pipeline for Company Registration Certificate verification"""
    
    def process(self) -> Dict[str, Any]:
        """
        Process Company Registration Certificate verification
        Similar to Companies House but may have different format
        Steps:
        1. OCR Extraction
        2. Forensic Analysis
        3. Companies House API Lookup (if company number found)
        4. Scoring
        """
        results = {
            "ocr_result": None,
            "forensic_result": None,
            "companies_house_result": None,
            "scoring_result": None
        }
        
        # Ensure type_doc is CompanyRegistrationDocument
        if not isinstance(self.type_doc, CompanyRegistrationDocument):
            logger.error(f"[COMPANY_REGISTRATION_PIPELINE] Type document is not CompanyRegistrationDocument")
            return results
        
        # Step 1: OCR Extraction
        logger.info(f"[COMPANY_REGISTRATION_PIPELINE] Starting OCR extraction for document: {self.base_doc.document_id}")
        self.update_progress("ocr_extraction", 20, "Extracting text from document using OCR", "processing")
        
        raw_text, confidence = OCRService.extract_text_from_pdf(self.file_path)
        self.update_progress("llm_extraction", 30, "Extracting structured fields using LLM", "processing")
        
        # Extract fields using LLM (same as Companies House)
        fields = OCRService.extract_fields(raw_text)
        
        ocr_result = {
            "raw_text": raw_text,
            "confidence": confidence,
            "company_name": fields.get("company_name"),
            "company_number": fields.get("company_number"),
            "address": fields.get("address"),
            "date": fields.get("date")
        }
        results["ocr_result"] = ocr_result
        
        # Update document with OCR data
        self.type_doc.ocr_company_name = ocr_result.get("company_name")
        self.type_doc.ocr_company_number = ocr_result.get("company_number")
        self.type_doc.ocr_address = ocr_result.get("address")
        self.type_doc.ocr_date = ocr_result.get("date")
        self.type_doc.ocr_confidence = ocr_result.get("confidence")
        self.type_doc.ocr_raw_text = ocr_result.get("raw_text")
        
        extraction_method = "LLM" if ocr_result.get("company_name") or ocr_result.get("company_number") else "regex"
        self.update_progress("ocr_complete", 40, f"OCR completed ({extraction_method}). Company: {ocr_result.get('company_name', 'N/A')}", "processing")
        
        # Step 2: Forensic Analysis
        logger.info(f"[COMPANY_REGISTRATION_PIPELINE] Starting forensic analysis")
        self.update_progress("forensic_analysis", 50, "Analyzing document for tampering and authenticity", "processing")
        forensic_result = ForensicService.process_document(self.file_path)
        results["forensic_result"] = forensic_result
        
        self.base_doc.forensic_score = forensic_result.get("forensic_score")
        self.base_doc.forensic_penalty = forensic_result.get("forensic_penalty")
        self.base_doc.forensic_details = forensic_result.get("details")
        self.base_doc.exif_data = forensic_result.get("exif_data")
        self.base_doc.ela_score = forensic_result.get("ela_score")
        self.base_doc.jpeg_quality = forensic_result.get("jpeg_quality")
        self.base_doc.copy_move_detected = forensic_result.get("copy_move_detected")
        
        self.update_progress("forensic_complete", 60, f"Forensic analysis complete. Score: {forensic_result.get('forensic_score', 'N/A')}", "processing")
        
        # Step 3: Companies House API Lookup (if company number found)
        logger.info(f"[COMPANY_REGISTRATION_PIPELINE] Starting Companies House lookup")
        self.update_progress("companies_house_lookup", 70, "Looking up company information in Companies House registry", "processing")
        companies_house_service = CompaniesHouseService()
        company_number = None
        
        if self.type_doc.ocr_company_number:
            company_number = self.type_doc.ocr_company_number
        elif self.type_doc.merchant_company_number:
            company_number = self.type_doc.merchant_company_number
        
        if company_number:
            normalized_number = company_number.strip().upper()
            normalized_number = re.sub(r'[\s\-]', '', normalized_number)
            
            if normalized_number.isdigit():
                if len(normalized_number) == 6:
                    normalized_number = '00' + normalized_number
                elif len(normalized_number) == 7:
                    normalized_number = '0' + normalized_number
            
            ch_data = companies_house_service.extract_company_data(normalized_number)
            results["companies_house_result"] = ch_data
            
            self.type_doc.companies_house_company_name = ch_data.get("company_name")
            self.type_doc.companies_house_company_number = ch_data.get("company_number")
            self.type_doc.companies_house_address = ch_data.get("address")
            self.type_doc.companies_house_date = ch_data.get("date")
            self.type_doc.companies_house_officers = ch_data.get("officers")
            self.type_doc.companies_house_data = ch_data.get("data")
            
            self.update_progress("companies_house_complete", 80, f"Companies House lookup complete. Company: {ch_data.get('company_name', 'N/A')}", "processing")
        else:
            logger.info(f"[COMPANY_REGISTRATION_PIPELINE] No company number found, skipping Companies House lookup")
            results["companies_house_result"] = None
            self.update_progress("companies_house_skipped", 80, "Companies House lookup skipped (no company number found)", "processing")
        
        # Step 4: Scoring
        logger.info(f"[COMPANY_REGISTRATION_PIPELINE] Calculating scores")
        self.update_progress("score_calculation", 90, "Calculating final verification scores", "processing")
        
        ocr_data = {
            "company_name": self.type_doc.ocr_company_name,
            "company_number": self.type_doc.ocr_company_number,
            "address": self.type_doc.ocr_address,
            "date": self.type_doc.ocr_date,
            "confidence": self.type_doc.ocr_confidence
        }
        
        merchant_data = {
            "company_name": self.type_doc.merchant_company_name,
            "company_number": self.type_doc.merchant_company_number,
            "address": self.type_doc.merchant_address,
            "date": self.type_doc.merchant_date
        }
        
        companies_house_data = {
            "company_name": self.type_doc.companies_house_company_name,
            "company_number": self.type_doc.companies_house_company_number,
            "address": self.type_doc.companies_house_address,
            "date": self.type_doc.companies_house_date
        }
        
        scoring_result = ScoringService.process_scoring(
            ocr_data,
            merchant_data,
            companies_house_data,
            self.base_doc.forensic_penalty
        )
        results["scoring_result"] = scoring_result
        
        if scoring_result:
            self.type_doc.ocr_score = scoring_result.get("ocr_score", 0.0)
            self.type_doc.registry_score = scoring_result.get("registry_score", 0.0)
            self.type_doc.provided_score = scoring_result.get("provided_score", 0.0)
            self.type_doc.data_match_score = scoring_result.get("data_match_score", 0.0)
            if not self.type_doc.comparison_details:
                self.type_doc.comparison_details = {}
            self.type_doc.comparison_details["ocr_comparison_score"] = scoring_result.get("ocr_comparison_score", 0.0)
            self.type_doc.final_score = scoring_result.get("final_score", 0.0)
            self.base_doc.decision = scoring_result.get("decision", "FAIL")
        
        return results


class VATRegistrationPipeline(BasePipeline):
    """Pipeline for VAT Registration Certificate verification"""
    
    def process(self) -> Dict[str, Any]:
        """
        Process VAT Registration Certificate verification
        Steps:
        1. OCR Extraction
        2. LLM Field Extraction (VAT number, business name, address, registration date)
        3. Forensic Analysis
        4. HMRC VAT API Lookup (if available)
        5. Scoring
        """
        results = {
            "ocr_result": None,
            "forensic_result": None,
            "vat_lookup_result": None,
            "scoring_result": None
        }
        
        # Ensure type_doc is VATRegistrationDocument
        if not isinstance(self.type_doc, VATRegistrationDocument):
            logger.error(f"[VAT_REGISTRATION_PIPELINE] Type document is not VATRegistrationDocument")
            return results
        
        # Step 1: OCR Extraction
        logger.info(f"[VAT_REGISTRATION_PIPELINE] Starting OCR extraction for document: {self.base_doc.document_id}")
        self.update_progress("ocr_extraction", 20, "Extracting text from document using OCR", "processing")
        
        raw_text, confidence = OCRService.extract_text_from_pdf(self.file_path)
        self.update_progress("llm_extraction", 30, "Extracting VAT fields using LLM", "processing")
        
        # Extract VAT fields using LLM
        vat_fields = {}
        if HAS_LLM_SERVICE and raw_text and raw_text.strip():
            try:
                vat_fields = LLMService.extract_vat_fields(raw_text)
            except Exception as e:
                logger.warning(f"LLM VAT extraction failed: {e}")
        
        ocr_result = {
            "raw_text": raw_text,
            "confidence": confidence,
            "vat_number": vat_fields.get("vat_number"),
            "business_name": vat_fields.get("business_name"),
            "address": vat_fields.get("address"),
            "registration_date": vat_fields.get("registration_date")
        }
        results["ocr_result"] = ocr_result
        
        # Update document with OCR data
        self.type_doc.ocr_vat_number = ocr_result.get("vat_number")
        self.type_doc.ocr_business_name = ocr_result.get("business_name")
        self.type_doc.ocr_vat_address = ocr_result.get("address")
        self.type_doc.ocr_vat_registration_date = ocr_result.get("registration_date")
        self.type_doc.ocr_confidence = confidence
        self.type_doc.ocr_raw_text = raw_text
        
        self.update_progress("ocr_complete", 40, f"OCR completed. VAT Number: {ocr_result.get('vat_number', 'N/A')}", "processing")
        
        # Step 2: Forensic Analysis
        logger.info(f"[VAT_REGISTRATION_PIPELINE] Starting forensic analysis")
        self.update_progress("forensic_analysis", 50, "Analyzing document for tampering and authenticity", "processing")
        forensic_result = ForensicService.process_document(self.file_path)
        results["forensic_result"] = forensic_result
        
        self.base_doc.forensic_score = forensic_result.get("forensic_score")
        self.base_doc.forensic_penalty = forensic_result.get("forensic_penalty")
        self.base_doc.forensic_details = forensic_result.get("details")
        
        self.update_progress("forensic_complete", 60, f"Forensic analysis complete. Score: {forensic_result.get('forensic_score', 'N/A')}", "processing")
        
        # Step 3: HMRC VAT API Lookup
        logger.info(f"[VAT_REGISTRATION_PIPELINE] Starting HMRC VAT lookup")
        self.update_progress("vat_lookup", 70, "Looking up VAT information in HMRC registry", "processing")
        
        vat_number = None
        if self.type_doc.ocr_vat_number:
            vat_number = self.type_doc.ocr_vat_number
        elif self.type_doc.merchant_vat_number:
            vat_number = self.type_doc.merchant_vat_number
        
        hmrc_data = {}
        if vat_number and HAS_HMRC_SERVICE:
            hmrc_vat_service = HMRCVATService()
            hmrc_data = hmrc_vat_service.extract_vat_data(vat_number)
            results["vat_lookup_result"] = hmrc_data
            
            # Update document with HMRC data
            self.type_doc.hmrc_vat_number = hmrc_data.get("vat_number")
            self.type_doc.hmrc_business_name = hmrc_data.get("business_name")
            self.type_doc.hmrc_address = hmrc_data.get("address")
            self.type_doc.hmrc_registration_date = hmrc_data.get("registration_date")
            self.type_doc.hmrc_vat_data = hmrc_data.get("data")
            
            self.update_progress("vat_lookup_complete", 80, f"HMRC VAT lookup complete. VAT: {hmrc_data.get('vat_number', 'N/A')}", "processing")
        else:
            logger.info(f"[VAT_REGISTRATION_PIPELINE] No VAT number found or HMRC service unavailable, skipping VAT lookup")
            results["vat_lookup_result"] = None
            self.update_progress("vat_lookup_skipped", 80, "HMRC VAT lookup skipped (no VAT number found or service unavailable)", "processing")
        
        # Step 4: Scoring
        logger.info(f"[VAT_REGISTRATION_PIPELINE] Calculating scores")
        self.update_progress("score_calculation", 90, "Calculating final verification scores", "processing")
        
        ocr_data = {
            "vat_number": self.type_doc.ocr_vat_number,
            "business_name": self.type_doc.ocr_business_name,
            "address": self.type_doc.ocr_vat_address,
            "registration_date": self.type_doc.ocr_vat_registration_date,
            "confidence": self.type_doc.ocr_confidence
        }
        
        merchant_data = {
            "vat_number": self.type_doc.merchant_vat_number,
            "business_name": self.type_doc.merchant_business_name,
            "address": self.type_doc.merchant_address
        }
        
        scoring_result = ScoringService.process_vat_scoring(
            ocr_data,
            merchant_data,
            hmrc_data,
            self.base_doc.forensic_penalty
        )
        results["scoring_result"] = scoring_result
        
        # Update document with scores
        if scoring_result:
            self.type_doc.ocr_score = scoring_result.get("ocr_score", 0.0)
            self.type_doc.registry_score = scoring_result.get("registry_score", 0.0)
            self.type_doc.provided_score = scoring_result.get("provided_score", 0.0)
            self.type_doc.data_match_score = scoring_result.get("data_match_score", 0.0)
            self.type_doc.final_score = scoring_result.get("final_score", 0.0)
            self.base_doc.decision = scoring_result.get("decision", "FAIL")
        
        return results


class DirectorVerificationPipeline(BasePipeline):
    """Pipeline for Director Verification Document verification"""
    
    def process(self) -> Dict[str, Any]:
        """
        Process Director Verification Document verification
        Steps:
        1. OCR Extraction
        2. LLM Field Extraction (director name, DOB, address, company name, appointment date)
        3. Forensic Analysis
        4. Companies House Director Lookup (if company name/number found)
        5. Scoring
        """
        results = {
            "ocr_result": None,
            "forensic_result": None,
            "director_lookup_result": None,
            "scoring_result": None
        }
        
        # Ensure type_doc is DirectorVerificationDocument
        if not isinstance(self.type_doc, DirectorVerificationDocument):
            logger.error(f"[DIRECTOR_VERIFICATION_PIPELINE] Type document is not DirectorVerificationDocument")
            return results
        
        # Step 1: OCR Extraction
        logger.info(f"[DIRECTOR_VERIFICATION_PIPELINE] Starting OCR extraction for document: {self.base_doc.document_id}")
        self.update_progress("ocr_extraction", 20, "Extracting text from document using OCR", "processing")
        
        raw_text, confidence = OCRService.extract_text_from_pdf(self.file_path)
        self.update_progress("llm_extraction", 30, "Extracting director fields using LLM", "processing")
        
        # Extract director fields using LLM
        director_fields = {}
        if HAS_LLM_SERVICE and raw_text and raw_text.strip():
            try:
                director_fields = LLMService.extract_director_fields(raw_text)
            except Exception as e:
                logger.warning(f"LLM Director extraction failed: {e}")
        
        ocr_result = {
            "raw_text": raw_text,
            "confidence": confidence,
            "director_name": director_fields.get("director_name"),
            "date_of_birth": director_fields.get("date_of_birth"),
            "address": director_fields.get("address"),
            "company_name": director_fields.get("company_name"),
            "company_number": director_fields.get("company_number"),
            "appointment_date": director_fields.get("appointment_date")
        }
        results["ocr_result"] = ocr_result
        
        # Update document with OCR data
        self.type_doc.ocr_director_name = ocr_result.get("director_name")
        self.type_doc.ocr_director_dob = ocr_result.get("date_of_birth")
        self.type_doc.ocr_director_address = ocr_result.get("address")
        self.type_doc.ocr_director_company_name = ocr_result.get("company_name")
        self.type_doc.ocr_appointment_date = ocr_result.get("appointment_date")
        self.type_doc.ocr_confidence = confidence
        self.type_doc.ocr_raw_text = raw_text
        
        # Store OCR-extracted company number in comparison_details for display
        # (DirectorVerificationDocument doesn't have ocr_company_number field)
        ocr_company_number = ocr_result.get("company_number")
        if ocr_company_number:
            if not self.type_doc.comparison_details:
                self.type_doc.comparison_details = {}
            self.type_doc.comparison_details["ocr_company_number"] = ocr_company_number
        
        self.update_progress("ocr_complete", 40, f"OCR completed. Director: {ocr_result.get('director_name', 'N/A')}", "processing")
        
        # Step 2: Forensic Analysis
        logger.info(f"[DIRECTOR_VERIFICATION_PIPELINE] Starting forensic analysis")
        self.update_progress("forensic_analysis", 50, "Analyzing document for tampering and authenticity", "processing")
        forensic_result = ForensicService.process_document(self.file_path)
        results["forensic_result"] = forensic_result
        
        self.base_doc.forensic_score = forensic_result.get("forensic_score")
        self.base_doc.forensic_penalty = forensic_result.get("forensic_penalty")
        self.base_doc.forensic_details = forensic_result.get("details")
        self.base_doc.exif_data = forensic_result.get("exif_data")
        self.base_doc.ela_score = forensic_result.get("ela_score")
        self.base_doc.jpeg_quality = forensic_result.get("jpeg_quality")
        self.base_doc.copy_move_detected = str(forensic_result.get("copy_move_detected")) if forensic_result.get("copy_move_detected") is not None else None
        
        self.update_progress("forensic_complete", 60, f"Forensic analysis complete. Score: {forensic_result.get('forensic_score', 'N/A')}", "processing")
        
        # Step 3: Companies House Director Verification
        logger.info(f"[DIRECTOR_VERIFICATION_PIPELINE] Starting director verification")
        self.update_progress("director_lookup", 70, "Verifying director information with Companies House", "processing")
        
        director_lookup_result = None
        companies_house_service = CompaniesHouseService()
        
        # Try to get company number from multiple sources
        company_number = None
        company_number_source = None
        # First try merchant input
        if self.type_doc.merchant_company_number:
            company_number = self.type_doc.merchant_company_number
            company_number_source = "merchant_input"
        # Then try OCR extraction (if LLM extracted it)
        elif ocr_result.get("company_number"):
            company_number = ocr_result.get("company_number")
            company_number_source = "ocr_llm_extraction"
        # Finally, try to extract from OCR text using regex
        elif raw_text:
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
                    company_number = matches[0].upper()
                    company_number_source = "ocr_regex_extraction"
                    logger.info(f"[DIRECTOR_VERIFICATION_PIPELINE] Extracted company number from OCR text: {company_number}")
                    break
        
        # Log which company number will be used for API lookup
        if company_number:
            logger.info(f"[DIRECTOR_VERIFICATION_PIPELINE] Using company number '{company_number}' for Companies House API lookup (source: {company_number_source})")
        else:
            logger.warning(f"[DIRECTOR_VERIFICATION_PIPELINE] No company number found from any source (merchant, OCR LLM, or regex)")
        
        # Get director name
        director_name = None
        if self.type_doc.ocr_director_name:
            director_name = self.type_doc.ocr_director_name
        elif self.type_doc.merchant_director_name:
            director_name = self.type_doc.merchant_director_name
        
        if director_name and company_number:
            # Normalize company number
            normalized_number = company_number.strip().upper()
            normalized_number = re.sub(r'[\s\-]', '', normalized_number)
            
            if normalized_number.isdigit():
                if len(normalized_number) == 6:
                    normalized_number = '00' + normalized_number
                elif len(normalized_number) == 7:
                    normalized_number = '0' + normalized_number
            
            # Verify director
            director_dob = self.type_doc.ocr_director_dob or self.type_doc.merchant_director_dob
            verification_result = companies_house_service.verify_director(
                director_name,
                normalized_number,
                director_dob
            )
            
            director_lookup_result = verification_result
            
            if verification_result and verification_result.get("verified"):
                director_data = verification_result.get("director_data", {})
                self.type_doc.companies_house_director_name = director_data.get("name")
                self.type_doc.companies_house_director_dob = director_data.get("date_of_birth")
                self.type_doc.companies_house_director_address = str(director_data.get("address", ""))
                self.type_doc.companies_house_appointment_date = director_data.get("appointed_on")
                self.type_doc.companies_house_director_data = verification_result.get("data")
                
                # Also store company info if available
                if verification_result.get("company_name"):
                    self.type_doc.companies_house_company_name = verification_result.get("company_name")
                if verification_result.get("company_number"):
                    self.type_doc.companies_house_company_number = verification_result.get("company_number")
                
                self.update_progress("director_lookup_complete", 80, f"Director verified: {director_data.get('name', 'N/A')}", "processing")
            else:
                logger.warning(f"[DIRECTOR_VERIFICATION_PIPELINE] Director verification failed: {verification_result.get('reason', 'Unknown') if verification_result else 'No result'}")
                self.update_progress("director_lookup_failed", 80, f"Director verification failed: {verification_result.get('reason', 'Unknown') if verification_result else 'No result'}", "processing")
        else:
            logger.info(f"[DIRECTOR_VERIFICATION_PIPELINE] Missing director name or company number, skipping director verification")
            director_lookup_result = {"verified": False, "reason": "Missing director name or company number"}
            self.update_progress("director_lookup_skipped", 80, "Director verification skipped (missing director name or company number)", "processing")
        
        results["director_lookup_result"] = director_lookup_result
        
        # Step 4: Scoring
        logger.info(f"[DIRECTOR_VERIFICATION_PIPELINE] Calculating scores")
        self.update_progress("score_calculation", 90, "Calculating final verification scores", "processing")
        
        ocr_data = {
            "director_name": self.type_doc.ocr_director_name,
            "date_of_birth": self.type_doc.ocr_director_dob,
            "address": self.type_doc.ocr_director_address,
            "company_name": self.type_doc.ocr_director_company_name,
            "appointment_date": self.type_doc.ocr_appointment_date,
            "confidence": self.type_doc.ocr_confidence
        }
        
        merchant_data = {
            "director_name": self.type_doc.merchant_director_name,
            "date_of_birth": self.type_doc.merchant_director_dob,
            "company_name": self.type_doc.merchant_company_name,
            "company_number": self.type_doc.merchant_company_number
        }
        
        companies_house_data = director_lookup_result if director_lookup_result else {}
        
        scoring_result = ScoringService.process_director_scoring(
            ocr_data,
            merchant_data,
            companies_house_data,
            self.base_doc.forensic_penalty
        )
        results["scoring_result"] = scoring_result
        
        # Update document with scores
        if scoring_result:
            self.type_doc.ocr_score = scoring_result.get("ocr_score", 0.0)
            self.type_doc.registry_score = scoring_result.get("registry_score", 0.0)
            self.type_doc.provided_score = scoring_result.get("provided_score", 0.0)
            self.type_doc.data_match_score = scoring_result.get("data_match_score", 0.0)
            self.type_doc.final_score = scoring_result.get("final_score", 0.0)
            self.base_doc.decision = scoring_result.get("decision", "FAIL")
        
        return results


class PipelineFactory:
    """Factory for creating appropriate pipeline based on document type"""
    
    _pipelines = {
        DocumentType.COMPANIES_HOUSE.value: CompaniesHousePipeline,
        DocumentType.COMPANY_REGISTRATION.value: CompanyRegistrationPipeline,
        DocumentType.VAT_REGISTRATION.value: VATRegistrationPipeline,
        DocumentType.DIRECTOR_VERIFICATION.value: DirectorVerificationPipeline,
    }
    
    @classmethod
    def create_pipeline(
        cls,
        base_doc: Document,
        type_doc: Optional[Union[
            CompaniesHouseDocument,
            CompanyRegistrationDocument,
            VATRegistrationDocument,
            DirectorVerificationDocument
        ]],
        update_progress_callback=None
    ) -> BasePipeline:
        """
        Create the appropriate pipeline for the document type
        
        Args:
            base_doc: Document instance (base table)
            type_doc: Type-specific document instance
            update_progress_callback: Optional callback for progress updates
        """
        document_type = base_doc.document_type or DocumentType.COMPANIES_HOUSE.value
        
        if document_type not in cls._pipelines:
            logger.warning(f"Unknown document type: {document_type}, defaulting to Companies House")
            document_type = DocumentType.COMPANIES_HOUSE.value
        
        pipeline_class = cls._pipelines[document_type]
        return pipeline_class(base_doc, type_doc, update_progress_callback)
    
    @classmethod
    def get_available_types(cls) -> list:
        """Get list of available document types"""
        return list(cls._pipelines.keys())

