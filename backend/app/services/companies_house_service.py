"""
Companies House API Service
"""
import requests
from typing import Dict, Optional
import logging
import re
from app.core.config import settings

logger = logging.getLogger(__name__)


class CompaniesHouseService:
    """Service for interacting with Companies House API"""
    
    BASE_URL = "https://api.companieshouse.gov.uk"
    
    def __init__(self):
        self.api_key = settings.COMPANIES_HOUSE_API_KEY
        self.session = requests.Session()
        self.session.auth = (self.api_key, "")
        self.session.headers.update({
            "User-Agent": "pi-docverifi/1.0"
        })
    
    def get_company_profile(self, company_number: str) -> Optional[Dict]:
        """
        Get company profile from Companies House API
        """
        try:
            url = f"{self.BASE_URL}/company/{company_number}"
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error fetching company profile: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching company profile: {e}")
            return None
    
    def get_company_officers(self, company_number: str) -> Optional[Dict]:
        """
        Get company officers from Companies House API
        """
        try:
            url = f"{self.BASE_URL}/company/{company_number}/officers"
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error fetching officers: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching officers: {e}")
            return None
    
    def search_company(self, query: str) -> Optional[Dict]:
        """
        Search for company by name
        """
        try:
            url = f"{self.BASE_URL}/search/companies"
            params = {"q": query, "items_per_page": 5}
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error searching company: {e}")
            return None
    
    @staticmethod
    def validate_company_number_format(company_number: str) -> bool:
        """
        Validate UK Companies House number format
        Formats:
        - 8 digits (e.g., 01234567) - England and Wales limited companies
        - 2 letters + 6 digits (e.g., SC555555) - Scottish companies or LLPs
        """
        if not company_number:
            return False
        
        company_number = company_number.upper().strip()
        # Remove spaces and common separators
        company_number = re.sub(r'[\s\-]', '', company_number)
        
        # Check format: 8 digits OR 2 letters + 6 digits
        pattern = r'^([A-Z]{2}\d{6}|\d{8})$'
        return bool(re.match(pattern, company_number))
    
    def extract_company_data(self, company_number: str) -> Dict:
        """
        Extract company data from Companies House API
        Normalizes company number format before lookup (handles 6, 7, 8 digit numbers)
        """
        # Normalize first: remove spaces, ensure uppercase
        company_number = company_number.upper().strip()
        company_number = re.sub(r'[\s\-]', '', company_number)
        
        # Normalize to 8-digit format if it's all digits
        if company_number.isdigit():
            if len(company_number) == 6:
                company_number = '00' + company_number  # 6 digits -> 8 digits
            elif len(company_number) == 7:
                company_number = '0' + company_number    # 7 digits -> 8 digits
            # 8 digits is already correct
        
        # Validate format after normalization
        if not self.validate_company_number_format(company_number):
            logger.warning(f"Invalid UK Companies House number format after normalization: {company_number}")
            return {
                "company_name": None,
                "company_number": None,
                "address": None,
                "date": None,
                "officers": None,
                "data": None
            }
        
        logger.info(f"Looking up Companies House data for: {company_number}")
        
        # Get company profile and officers
        profile = self.get_company_profile(company_number)
        officers = self.get_company_officers(company_number)
        
        if not profile:
            return {
                "company_name": None,
                "company_number": company_number,
                "address": None,
                "date": None,
                "officers": [],
                "data": None
            }
        
        # Extract address
        registered_office_address = profile.get("registered_office_address", {})
        address_parts = [
            registered_office_address.get("address_line_1"),
            registered_office_address.get("address_line_2"),
            registered_office_address.get("locality"),
            registered_office_address.get("postal_code"),
            registered_office_address.get("country")
        ]
        address = ", ".join([part for part in address_parts if part])
        
        # Extract officers
        officers_list = []
        if officers and "items" in officers:
            for officer in officers["items"][:10]:  # Limit to 10
                officers_list.append({
                    "name": officer.get("name", ""),
                    "officer_role": officer.get("officer_role", ""),
                    "appointed_on": officer.get("appointed_on")
                })
        
        return {
            "company_name": profile.get("company_name"),
            "company_number": profile.get("company_number"),
            "address": address if address else None,
            "date": profile.get("date_of_creation"),
            "officers": officers_list,
            "data": profile
        }
    
    def verify_company_number(self, company_number: str) -> bool:
        """
        Verify if company number exists
        """
        profile = self.get_company_profile(company_number)
        return profile is not None
    
    def search_director(self, director_name: str, company_number: Optional[str] = None) -> Optional[Dict]:
        """
        Search for director by name, optionally filtered by company
        
        Args:
            director_name: Name of the director to search for
            company_number: Optional company number to filter results
            
        Returns:
            Dictionary with director information or None
        """
        try:
            # If company number is provided, get officers for that company
            if company_number:
                officers = self.get_company_officers(company_number)
                if officers and "items" in officers:
                    # Search for director by name in officers list
                    director_name_lower = director_name.lower()
                    for officer in officers["items"]:
                        officer_name = officer.get("name", "").lower()
                        if director_name_lower in officer_name or officer_name in director_name_lower:
                            return {
                                "name": officer.get("name"),
                                "officer_role": officer.get("officer_role"),
                                "appointed_on": officer.get("appointed_on"),
                                "resigned_on": officer.get("resigned_on"),
                                "date_of_birth": officer.get("date_of_birth"),
                                "nationality": officer.get("nationality"),
                                "occupation": officer.get("occupation"),
                                "address": officer.get("address"),
                                "company_number": company_number,
                                "data": officer
                            }
                return None
            
            # If no company number, use Companies House search API for officers
            # Note: Companies House doesn't have a direct officer search API
            # This would require searching companies first, then checking officers
            logger.warning("Director search without company number requires company search first")
            return None
            
        except Exception as e:
            logger.error(f"Error searching for director: {e}")
            return None
    
    def verify_director(self, director_name: str, company_number: str, 
                       date_of_birth: Optional[str] = None) -> Optional[Dict]:
        """
        Verify director information against Companies House records
        
        Args:
            director_name: Name of the director
            company_number: Company number where director should be listed
            date_of_birth: Optional date of birth for additional verification
            
        Returns:
            Dictionary with verification results or None
        """
        try:
            # Get officers for the company
            officers = self.get_company_officers(company_number)
            
            if not officers or "items" not in officers:
                logger.warning(f"No officers found for company {company_number}")
                return {
                    "verified": False,
                    "reason": "No officers found for company",
                    "director_data": None
                }
            
            # Search for director by name
            director_name_lower = director_name.lower()
            for officer in officers["items"]:
                officer_name = officer.get("name", "").lower()
                
                # Check if names match (fuzzy matching)
                if director_name_lower in officer_name or officer_name in director_name_lower:
                    # Extract director data
                    director_data = {
                        "name": officer.get("name"),
                        "officer_role": officer.get("officer_role"),
                        "appointed_on": officer.get("appointed_on"),
                        "resigned_on": officer.get("resigned_on"),
                        "date_of_birth": officer.get("date_of_birth"),
                        "nationality": officer.get("nationality"),
                        "occupation": officer.get("occupation"),
                        "address": officer.get("address"),
                        "company_number": company_number
                    }
                    
                    # If DOB provided, verify it matches
                    dob_match = True
                    if date_of_birth and officer.get("date_of_birth"):
                        # Compare dates (format may vary)
                        officer_dob = str(officer.get("date_of_birth", ""))
                        if date_of_birth not in officer_dob and officer_dob not in date_of_birth:
                            dob_match = False
                            logger.warning(f"Date of birth mismatch: {date_of_birth} vs {officer_dob}")
                    
                    return {
                        "verified": dob_match,
                        "reason": "Director found and verified" if dob_match else "Director found but DOB mismatch",
                        "director_data": director_data,
                        "data": officer
                    }
            
            # Director not found
            return {
                "verified": False,
                "reason": "Director not found in company officers",
                "director_data": None
            }
            
        except Exception as e:
            logger.error(f"Error verifying director: {e}")
            return {
                "verified": False,
                "reason": f"Error during verification: {str(e)}",
                "director_data": None
            }
    
    def get_director_details(self, company_number: str, director_name: str) -> Optional[Dict]:
        """
        Get detailed director information from Companies House
        
        Args:
            company_number: Company number
            director_name: Director name
            
        Returns:
            Dictionary with director details or None
        """
        verification_result = self.verify_director(director_name, company_number)
        
        if verification_result and verification_result.get("verified"):
            return verification_result.get("director_data")
        
        return None


