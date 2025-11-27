"""
Scoring Service for document verification
"""
from typing import Dict, Optional
import logging
import re
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class ScoringService:
    """Service for calculating verification scores"""
    
    @staticmethod
    def normalize_company_number(company_number: Optional[str]) -> Optional[str]:
        """
        Normalize UK company number to 8-digit format
        Handles both 7-digit (3035678) and 8-digit (03035678) formats
        """
        if not company_number:
            return None
        
        # Remove spaces and convert to uppercase
        normalized = re.sub(r'[\s\-]', '', str(company_number).upper())
        
        # If it's 7 digits, pad with leading zero
        if normalized.isdigit() and len(normalized) == 7:
            normalized = '0' + normalized
        
        # Validate it's now 8 digits or 2 letters + 6 digits
        if re.match(r'^([A-Z]{2}\d{6}|\d{8})$', normalized):
            return normalized
        
        return company_number  # Return original if can't normalize
    
    @staticmethod
    def calculate_similarity(str1: Optional[str], str2: Optional[str]) -> float:
        """
        Calculate similarity between two strings (0-1)
        """
        if not str1 or not str2:
            return 0.0
        
        # Normalize strings
        s1 = str1.upper().strip()
        s2 = str2.upper().strip()
        
        if s1 == s2:
            return 1.0
        
        # Use SequenceMatcher for fuzzy matching
        return SequenceMatcher(None, s1, s2).ratio()
    
    @staticmethod
    def calculate_registry_score(
        ocr_company_number: Optional[str],
        companies_house_company_number: Optional[str]
    ) -> float:
        """
        Calculate registry match score (0-40)
        Normalizes company numbers before comparison to handle 7-digit vs 8-digit formats
        """
        if not ocr_company_number or not companies_house_company_number:
            return 0.0
        
        # Normalize both numbers to 8-digit format for comparison
        ocr_normalized = ScoringService.normalize_company_number(ocr_company_number)
        ch_normalized = ScoringService.normalize_company_number(companies_house_company_number)
        
        if not ocr_normalized or not ch_normalized:
            return 0.0
        
        # Exact match after normalization
        if ocr_normalized == ch_normalized:
            logger.info(f"Registry match: {ocr_company_number} (normalized: {ocr_normalized}) == {companies_house_company_number} (normalized: {ch_normalized})")
            return 40.0
        
        # Partial match (some characters differ)
        similarity = ScoringService.calculate_similarity(
            ocr_normalized, ch_normalized
        )
        
        score = similarity * 40.0
        logger.info(f"Registry partial match: {ocr_company_number} vs {companies_house_company_number}, similarity: {similarity:.2f}, score: {score:.2f}")
        return score
    
    @staticmethod
    def calculate_provided_data_accuracy(
        merchant_data: Dict,
        companies_house_data: Dict
    ) -> float:
        """
        Calculate provided data accuracy score (0-30)
        """
        if not merchant_data or not companies_house_data:
            return 0.0
        
        scores = []
        weights = {
            "company_name": 0.4,
            "company_number": 0.4,
            "address": 0.2
        }
        
        # Company name
        if merchant_data.get("company_name") and companies_house_data.get("company_name"):
            name_sim = ScoringService.calculate_similarity(
                merchant_data["company_name"],
                companies_house_data["company_name"]
            )
            scores.append(("company_name", name_sim * weights["company_name"] * 30))
        
        # Company number
        if merchant_data.get("company_number") and companies_house_data.get("company_number"):
            num_sim = ScoringService.calculate_similarity(
                merchant_data["company_number"],
                companies_house_data["company_number"]
            )
            scores.append(("company_number", num_sim * weights["company_number"] * 30))
        
        # Address
        if merchant_data.get("address") and companies_house_data.get("address"):
            addr_sim = ScoringService.calculate_similarity(
                merchant_data["address"],
                companies_house_data["address"]
            )
            scores.append(("address", addr_sim * weights["address"] * 30))
        
        total_score = sum(score for _, score in scores)
        return min(30.0, total_score)
    
    @staticmethod
    def calculate_ocr_score(ocr_confidence: float) -> float:
        """
        Calculate OCR score based on confidence (0-30)
        """
        if not ocr_confidence or ocr_confidence <= 0:
            return 0.0
        
        # Normalize confidence (0-100) to score (0-30)
        return min(30.0, (ocr_confidence / 100.0) * 30.0)
    
    @staticmethod
    def calculate_data_match_score(
        ocr_data: Dict,
        merchant_data: Dict,
        companies_house_data: Dict
    ) -> float:
        """
        Calculate overall data match score
        """
        scores = []
        
        # Compare OCR vs Companies House
        if ocr_data.get("company_name") and companies_house_data.get("company_name"):
            ocr_ch_name = ScoringService.calculate_similarity(
                ocr_data["company_name"],
                companies_house_data["company_name"]
            )
            scores.append(ocr_ch_name)
        
        if ocr_data.get("company_number") and companies_house_data.get("company_number"):
            # Normalize company numbers before comparison
            ocr_num = ScoringService.normalize_company_number(ocr_data["company_number"])
            ch_num = ScoringService.normalize_company_number(companies_house_data["company_number"])
            if ocr_num and ch_num:
                ocr_ch_num = ScoringService.calculate_similarity(ocr_num, ch_num)
                scores.append(ocr_ch_num)
        
        # Compare Merchant vs Companies House
        if merchant_data.get("company_name") and companies_house_data.get("company_name"):
            merch_ch_name = ScoringService.calculate_similarity(
                merchant_data["company_name"],
                companies_house_data["company_name"]
            )
            scores.append(merch_ch_name)
        
        if merchant_data.get("company_number") and companies_house_data.get("company_number"):
            # Normalize company numbers before comparison
            merch_num = ScoringService.normalize_company_number(merchant_data["company_number"])
            ch_num = ScoringService.normalize_company_number(companies_house_data["company_number"])
            if merch_num and ch_num:
                merch_ch_num = ScoringService.calculate_similarity(merch_num, ch_num)
                scores.append(merch_ch_num)
        
        if not scores:
            return 0.0
        
        return sum(scores) / len(scores) * 100.0
    
    @staticmethod
    def calculate_final_score(
        ocr_score: float,
        registry_score: float,
        provided_score: float,
        forensic_penalty: float
    ) -> float:
        """
        Calculate final verification score (0-100)
        Formula: OCR(0-30) + Registry(0-40) + Provided(0-30) - Forensic Penalty(0-15)
        """
        base_score = ocr_score + registry_score + provided_score
        final_score = max(0.0, base_score - forensic_penalty)
        return min(100.0, final_score)
    
    @staticmethod
    def make_decision(final_score: float) -> str:
        """
        Make decision based on final score
        """
        if final_score >= 75:
            return "PASS"
        elif final_score >= 50:
            return "REVIEW"
        else:
            return "FAIL"
    
    @staticmethod
    def process_scoring(
        ocr_data: Dict,
        merchant_data: Dict,
        companies_house_data: Dict,
        forensic_penalty: float
    ) -> Dict:
        """
        Main method to calculate all scores
        """
        # OCR Score (0-30)
        ocr_score = ScoringService.calculate_ocr_score(
            ocr_data.get("confidence", 0.0)
        )
        
        # Registry Score (0-40)
        registry_score = ScoringService.calculate_registry_score(
            ocr_data.get("company_number"),
            companies_house_data.get("company_number")
        )
        
        # Provided Data Accuracy (0-30)
        provided_score = ScoringService.calculate_provided_data_accuracy(
            merchant_data,
            companies_house_data
        )
        
        # Data Match Score
        data_match_score = ScoringService.calculate_data_match_score(
            ocr_data,
            merchant_data,
            companies_house_data
        )
        
        # Final Score
        final_score = ScoringService.calculate_final_score(
            ocr_score,
            registry_score,
            provided_score,
            forensic_penalty
        )
        
        # Decision
        decision = ScoringService.make_decision(final_score)
        
        return {
            "ocr_score": ocr_score,
            "registry_score": registry_score,
            "provided_score": provided_score,
            "data_match_score": data_match_score,
            "final_score": final_score,
            "decision": decision,
            "forensic_penalty": forensic_penalty
        }

