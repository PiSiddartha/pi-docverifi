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
        Validates and normalizes company number format before lookup
        """
        # Validate and normalize company number
        if not self.validate_company_number_format(company_number):
            logger.warning(f"Invalid UK Companies House number format: {company_number}")
            return {
                "company_name": None,
                "company_number": None,
                "address": None,
                "date": None,
                "officers": None,
                "data": None
            }
        
        # Normalize: remove spaces, ensure uppercase
        company_number = company_number.upper().strip()
        company_number = re.sub(r'[\s\-]', '', company_number)
        
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

