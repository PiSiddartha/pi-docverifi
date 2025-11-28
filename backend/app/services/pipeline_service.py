"""
Pipeline Service - Routes document verification to type-specific pipelines
"""
import logging
import re
from typing import Dict, Any
from app.db.models import DocumentVerification, DocumentType
from app.services.ocr_service import OCRService
from app.services.forensic_service import ForensicService
from app.services.companies_house_service import CompaniesHouseService
from app.services.scoring_service import ScoringService

logger = logging.getLogger(__name__)


class BasePipeline:
    """Base class for document verification pipelines"""
    
    def __init__(self, document: DocumentVerification, update_progress_callback=None):
        self.document = document
        self.file_path = document.file_path
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
        
        # Step 1: OCR Extraction
        logger.info(f"[COMPANIES_HOUSE_PIPELINE] Starting OCR extraction for document: {self.document.document_id}")
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
        self.document.ocr_company_name = ocr_result.get("company_name")
        self.document.ocr_company_number = ocr_result.get("company_number")
        self.document.ocr_address = ocr_result.get("address")
        self.document.ocr_date = ocr_result.get("date")
        self.document.ocr_confidence = ocr_result.get("confidence")
        self.document.ocr_raw_text = ocr_result.get("raw_text")
        
        # Update progress after OCR completes
        extraction_method = "LLM" if ocr_result.get("company_name") or ocr_result.get("company_number") else "regex"
        self.update_progress("ocr_complete", 40, f"OCR completed ({extraction_method}). Company: {ocr_result.get('company_name', 'N/A')}", "processing")
        
        # Step 2: Forensic Analysis
        logger.info(f"[COMPANIES_HOUSE_PIPELINE] Starting forensic analysis for document: {self.document.document_id}")
        self.update_progress("forensic_analysis", 50, "Analyzing document for tampering and authenticity", "processing")
        forensic_result = ForensicService.process_document(self.file_path)
        results["forensic_result"] = forensic_result
        
        # Update document with forensic data
        self.document.forensic_score = forensic_result.get("forensic_score")
        self.document.forensic_penalty = forensic_result.get("forensic_penalty")
        self.document.forensic_details = forensic_result.get("details")
        self.document.exif_data = forensic_result.get("exif_data")
        self.document.ela_score = forensic_result.get("ela_score")
        self.document.jpeg_quality = forensic_result.get("jpeg_quality")
        self.document.copy_move_detected = forensic_result.get("copy_move_detected")
        
        # Update progress after forensic analysis completes
        self.update_progress("forensic_complete", 60, f"Forensic analysis complete. Score: {forensic_result.get('forensic_score', 'N/A')}", "processing")
        
        # Step 3: Companies House API Lookup
        logger.info(f"[COMPANIES_HOUSE_PIPELINE] Starting Companies House lookup for document: {self.document.document_id}")
        self.update_progress("companies_house_lookup", 70, "Looking up company information in Companies House registry", "processing")
        companies_house_service = CompaniesHouseService()
        company_number = None
        
        # Try to get company number from OCR or merchant input
        if self.document.ocr_company_number:
            company_number = self.document.ocr_company_number
        elif self.document.merchant_company_number:
            company_number = self.document.merchant_company_number
        
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
            self.document.companies_house_company_name = ch_data.get("company_name")
            self.document.companies_house_company_number = ch_data.get("company_number")
            self.document.companies_house_address = ch_data.get("address")
            self.document.companies_house_date = ch_data.get("date")
            self.document.companies_house_officers = ch_data.get("officers")
            self.document.companies_house_data = ch_data.get("data")
            
            # Update progress after Companies House lookup completes
            self.update_progress("companies_house_complete", 80, f"Companies House lookup complete. Company: {ch_data.get('company_name', 'N/A')}", "processing")
        else:
            logger.info(f"[COMPANIES_HOUSE_PIPELINE] No company number found, skipping Companies House lookup")
            results["companies_house_result"] = None
            self.update_progress("companies_house_skipped", 80, "Companies House lookup skipped (no company number found)", "processing")
        
        # Step 4: Scoring
        logger.info(f"[COMPANIES_HOUSE_PIPELINE] Calculating scores for document: {self.document.document_id}")
        self.update_progress("score_calculation", 90, "Calculating final verification scores", "processing")
        ocr_data = {
            "company_name": self.document.ocr_company_name,
            "company_number": self.document.ocr_company_number,
            "address": self.document.ocr_address,
            "date": self.document.ocr_date,
            "confidence": self.document.ocr_confidence
        }
        
        merchant_data = {
            "company_name": self.document.merchant_company_name,
            "company_number": self.document.merchant_company_number,
            "address": self.document.merchant_address,
            "date": self.document.merchant_date
        }
        
        companies_house_data = {
            "company_name": self.document.companies_house_company_name,
            "company_number": self.document.companies_house_company_number,
            "address": self.document.companies_house_address,
            "date": self.document.companies_house_date
        }
        
        scoring_result = ScoringService.process_scoring(
            ocr_data,
            merchant_data,
            companies_house_data,
            self.document.forensic_penalty
        )
        results["scoring_result"] = scoring_result
        
        # Update document with scores
        if scoring_result:
            self.document.ocr_score = scoring_result.get("ocr_score", 0.0)
            self.document.registry_score = scoring_result.get("registry_score", 0.0)
            self.document.provided_score = scoring_result.get("provided_score", 0.0)
            self.document.data_match_score = scoring_result.get("data_match_score", 0.0)
            # Store OCR comparison score in comparison_details for now (can add DB field later)
            if not self.document.comparison_details:
                self.document.comparison_details = {}
            self.document.comparison_details["ocr_comparison_score"] = scoring_result.get("ocr_comparison_score", 0.0)
            self.document.final_score = scoring_result.get("final_score", 0.0)
            self.document.decision = scoring_result.get("decision", "FAIL")
        
        return results


class PipelineFactory:
    """Factory for creating appropriate pipeline based on document type"""
    
    _pipelines = {
        DocumentType.COMPANIES_HOUSE.value: CompaniesHousePipeline,
        # Future pipelines can be added here:
        # DocumentType.ID_DOCUMENT.value: IDDocumentPipeline,
        # DocumentType.PASSPORT.value: PassportPipeline,
    }
    
    @classmethod
    def create_pipeline(cls, document: DocumentVerification, update_progress_callback=None) -> BasePipeline:
        """
        Create the appropriate pipeline for the document type
        """
        document_type = document.document_type or DocumentType.COMPANIES_HOUSE.value
        
        if document_type not in cls._pipelines:
            logger.warning(f"Unknown document type: {document_type}, defaulting to Companies House")
            document_type = DocumentType.COMPANIES_HOUSE.value
        
        pipeline_class = cls._pipelines[document_type]
        return pipeline_class(document, update_progress_callback)
    
    @classmethod
    def get_available_types(cls) -> list:
        """Get list of available document types"""
        return list(cls._pipelines.keys())

