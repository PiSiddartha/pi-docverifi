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
        Handles 6-digit (640918 -> 00640918), 7-digit (3035678 -> 03035678), and 8-digit formats
        Also handles 2 letters + 6 digits format (SC555555)
        """
        if not company_number:
            return None
        
        # Remove spaces and convert to uppercase
        normalized = re.sub(r'[\s\-]', '', str(company_number).upper())
        
        # If it's all digits, pad to 8 digits with leading zeros
        if normalized.isdigit():
            if len(normalized) == 6:
                normalized = '00' + normalized  # 6 digits -> 8 digits (add 2 zeros)
            elif len(normalized) == 7:
                normalized = '0' + normalized   # 7 digits -> 8 digits (add 1 zero)
            elif len(normalized) == 8:
                pass  # Already 8 digits
            else:
                # Invalid length, return original
                return company_number
        
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
        Calculate overall data match score (0-100)
        Compares OCR and Merchant data with Companies House data
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
        
        # Compare OCR address vs Companies House address
        if ocr_data.get("address") and companies_house_data.get("address"):
            ocr_ch_addr = ScoringService.calculate_similarity(
                ocr_data["address"],
                companies_house_data["address"]
            )
            scores.append(ocr_ch_addr)
        
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
        
        if merchant_data.get("address") and companies_house_data.get("address"):
            merch_ch_addr = ScoringService.calculate_similarity(
                merchant_data["address"],
                companies_house_data["address"]
            )
            scores.append(merch_ch_addr)
        
        if not scores:
            return 0.0
        
        return sum(scores) / len(scores) * 100.0
    
    @staticmethod
    def calculate_ocr_comparison_score(
        ocr_data: Dict,
        companies_house_data: Dict
    ) -> float:
        """
        Calculate OCR vs Companies House comparison score (0-30)
        Compares company name, number, and address extracted from document with official registry data
        Uses stricter validation for company names to catch OCR errors
        """
        if not companies_house_data or not any(companies_house_data.values()):
            return 0.0
        
        scores = []
        weights = {
            "company_name": 0.5,  # Increased weight - most important
            "company_number": 0.3,  # Reduced (already in Registry Score)
            "address": 0.2
        }
        
        # Company name comparison with STRICT validation
        # Company names must match very closely - OCR errors like "YE" vs "& E" should be caught
        if ocr_data.get("company_name") and companies_house_data.get("company_name"):
            name_sim = ScoringService.calculate_similarity(
                ocr_data["company_name"],
                companies_house_data["company_name"]
            )
            
            # Very strict validation: if similarity < 0.98, apply heavy penalty
            # This catches OCR errors like "YE" vs "& E" or "O." vs "0."
            if name_sim < 0.98:
                # Heavy penalty for any mismatch
                if name_sim < 0.90:
                    # Very low similarity - severe penalty
                    penalty_factor = max(0.0, (name_sim - 0.70) / 0.20)  # Scale 0.70-0.90 to 0-1
                    name_score = name_sim * penalty_factor * weights["company_name"] * 30
                    logger.warning(f"Company name very low similarity: {name_sim:.3f} - '{ocr_data['company_name']}' vs '{companies_house_data['company_name']}'")
                else:
                    # Moderate mismatch - apply penalty
                    penalty_factor = (name_sim - 0.90) / 0.08  # Scale 0.90-0.98 to 0-1
                    name_score = name_sim * penalty_factor * weights["company_name"] * 30
                    logger.warning(f"Company name low similarity: {name_sim:.3f} - '{ocr_data['company_name']}' vs '{companies_house_data['company_name']}'")
            else:
                # High similarity (>= 0.98) - full score
                name_score = name_sim * weights["company_name"] * 30
            
            scores.append(("company_name", name_score))
        
        # Company number comparison (already handled in Registry Score, but include for completeness)
        if ocr_data.get("company_number") and companies_house_data.get("company_number"):
            ocr_num = ScoringService.normalize_company_number(ocr_data["company_number"])
            ch_num = ScoringService.normalize_company_number(companies_house_data["company_number"])
            if ocr_num and ch_num:
                num_sim = ScoringService.calculate_similarity(ocr_num, ch_num)
                scores.append(("company_number", num_sim * weights["company_number"] * 30))
        
        # Address comparison with LENIENT validation
        # Addresses can change over time (company relocations), so be more forgiving
        if ocr_data.get("address") and companies_house_data.get("address"):
            addr_sim = ScoringService.calculate_similarity(
                ocr_data["address"],
                companies_house_data["address"]
            )
            
            # Lenient validation: only penalize if similarity is very low (< 0.3)
            # Addresses can differ due to:
            # - Company relocations over time
            # - Formatting differences (commas, abbreviations)
            # - OCR extraction issues
            if addr_sim < 0.3:
                # Very different addresses - apply moderate penalty
                addr_score = addr_sim * 0.7 * weights["address"] * 30  # Moderate penalty
                logger.info(f"Address low similarity: {addr_sim:.3f} - may be different address or OCR issue")
            elif addr_sim < 0.5:
                # Different but not completely unrelated - small penalty
                addr_score = addr_sim * 0.9 * weights["address"] * 30  # Small penalty
            else:
                # Similar addresses - full score (addresses can change, so be lenient)
                addr_score = addr_sim * weights["address"] * 30
            
            scores.append(("address", addr_score))
        
        total_score = sum(score for _, score in scores)
        
        # Additional validation: if company name similarity is very low, cap the score
        # Company name is critical - must match closely
        if ocr_data.get("company_name") and companies_house_data.get("company_name"):
            name_sim = ScoringService.calculate_similarity(
                ocr_data["company_name"],
                companies_house_data["company_name"]
            )
            if name_sim < 0.95:
                # Cap score if name similarity is low (stricter threshold)
                max_score = 20.0 if name_sim < 0.90 else 25.0
                total_score = min(total_score, max_score)
                logger.warning(f"Company name similarity too low ({name_sim:.3f}), capping OCR comparison score at {max_score}")
        
        return min(30.0, total_score)
    
    @staticmethod
    def calculate_final_score(
        ocr_score: float,
        registry_score: float,
        provided_score: float,
        ocr_comparison_score: float,
        forensic_penalty: float
    ) -> float:
        """
        Calculate final verification score (0-100)
        Formula: OCR(0-30) + Registry(0-40) + Provided(0-30) + OCR Comparison(0-30) - Forensic Penalty(0-15)
        Note: OCR Comparison includes name/address matching, Registry is just number matching
        """
        base_score = ocr_score + registry_score + provided_score + ocr_comparison_score
        final_score = max(0.0, base_score - forensic_penalty)
        return min(100.0, final_score)
    
    @staticmethod
    def make_decision(final_score: float, ocr_data: Dict = None, companies_house_data: Dict = None) -> str:
        """
        Make decision based on final score and data validation
        """
        # Hard fail conditions - override score if critical mismatches
        if ocr_data and companies_house_data:
            # Check company name similarity - if too low, force REVIEW or FAIL
            if ocr_data.get("company_name") and companies_house_data.get("company_name"):
                name_sim = ScoringService.calculate_similarity(
                    ocr_data["company_name"],
                    companies_house_data["company_name"]
                )
                # Stricter thresholds for company name
                # If name similarity is very low (< 0.90), it's likely wrong company or OCR error
                if name_sim < 0.90:
                    logger.warning(f"Company name similarity too low ({name_sim:.3f}), forcing REVIEW")
                    return "REVIEW"  # Force review for name mismatches
                # If name similarity is extremely low (< 0.85), fail
                elif name_sim < 0.85:
                    logger.warning(f"Company name similarity extremely low ({name_sim:.3f}), forcing FAIL")
                    return "FAIL"
        
        # Normal decision logic based on score
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
        
        # Registry Score (0-40) - Company number match only
        registry_score = ScoringService.calculate_registry_score(
            ocr_data.get("company_number"),
            companies_house_data.get("company_number")
        )
        
        # OCR Comparison Score (0-30) - Compares OCR extracted name, number, and address with Companies House
        ocr_comparison_score = ScoringService.calculate_ocr_comparison_score(
            ocr_data,
            companies_house_data
        )
        
        # Provided Data Accuracy (0-30) - Compares merchant-provided data with Companies House
        provided_score = ScoringService.calculate_provided_data_accuracy(
            merchant_data,
            companies_house_data
        )
        
        # Data Match Score (0-100) - Overall similarity percentage (for display/info)
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
            ocr_comparison_score,
            forensic_penalty
        )
        
        # Decision (with data validation)
        decision = ScoringService.make_decision(final_score, ocr_data, companies_house_data)
        
        return {
            "ocr_score": ocr_score,
            "registry_score": registry_score,
            "ocr_comparison_score": ocr_comparison_score,
            "provided_score": provided_score,
            "data_match_score": data_match_score,
            "final_score": final_score,
            "decision": decision,
            "forensic_penalty": forensic_penalty
        }

