"""
HMRC VAT API Service for VAT number verification
"""
import requests
from typing import Dict, Optional
import logging
import re
import base64
import time
from datetime import datetime, timedelta
from app.core.config import settings

logger = logging.getLogger(__name__)


class HMRCVATService:
    """Service for interacting with HMRC VAT API with OAuth authentication"""
    
    BASE_URL = "https://api.service.hmrc.gov.uk"
    TOKEN_URL = "https://api.service.hmrc.gov.uk/oauth/token"
    
    def __init__(self):
        self.base_url = getattr(settings, 'HMRC_VAT_API_BASE_URL', self.BASE_URL)
        self.client_id = getattr(settings, 'HMRC_CLIENT_ID', '')
        self.client_secret = getattr(settings, 'HMRC_CLIENT_SECRET', '')
        self.server_token = getattr(settings, 'HMRC_SERVER_TOKEN', '')
        self.use_oauth = getattr(settings, 'HMRC_USE_OAUTH', True)
        
        # OAuth token cache
        self._access_token = None
        self._token_expires_at = None
        
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.hmrc.1.0+json",
            "User-Agent": "pi-docverifi/1.0"
        })
    
    def _get_oauth_token(self) -> Optional[str]:
        """
        Get OAuth access token using client credentials grant
        HMRC uses OAuth 2.0 with client credentials flow for server-to-server authentication
        
        Returns:
            Access token string or None if authentication fails
        """
        # Check if we have a valid cached token
        if self._access_token and self._token_expires_at:
            if datetime.now() < self._token_expires_at - timedelta(minutes=5):  # Refresh 5 min before expiry
                logger.debug("Using cached OAuth token")
                return self._access_token
        
        if not self.client_id or not self.client_secret:
            logger.warning("HMRC OAuth credentials not configured. Set HMRC_CLIENT_ID and HMRC_CLIENT_SECRET")
            return None
        
        try:
            # Prepare OAuth request
            auth_string = f"{self.client_id}:{self.client_secret}"
            auth_bytes = auth_string.encode('ascii')
            auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
            
            headers = {
                "Authorization": f"Basic {auth_b64}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            # HMRC OAuth token request
            data = {
                "grant_type": "client_credentials",
                "scope": "read:vat"  # VAT API scope
            }
            
            logger.info("Requesting OAuth token from HMRC...")
            response = requests.post(
                self.TOKEN_URL,
                headers=headers,
                data=data,
                timeout=15
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self._access_token = token_data.get("access_token")
                expires_in = token_data.get("expires_in", 3600)  # Default 1 hour
                self._token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                
                logger.info(f"OAuth token obtained successfully. Expires in {expires_in} seconds")
                return self._access_token
            else:
                logger.error(f"Failed to obtain OAuth token. Status: {response.status_code}, Response: {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error requesting OAuth token: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in OAuth token request: {e}")
            return None
    
    def _get_auth_header(self) -> Optional[str]:
        """
        Get authorization header value
        Uses OAuth if configured, otherwise falls back to server token
        """
        if self.use_oauth:
            token = self._get_oauth_token()
            if token:
                return f"Bearer {token}"
        
        # Fallback to server token if OAuth fails or is disabled
        if self.server_token:
            return f"Bearer {self.server_token}"
        
        return None
    
    @staticmethod
    def normalize_vat_number(vat_number: str) -> str:
        """
        Normalize UK VAT number format
        UK VAT numbers can be:
        - GB + 9 digits (e.g., GB123456789)
        - 9 digits starting with 0-9 (e.g., 123456789)
        - May include spaces
        """
        if not vat_number:
            return ""
        
        # Remove spaces and convert to uppercase
        normalized = re.sub(r'[\s\-]', '', vat_number.upper())
        
        # Remove GB prefix if present (we'll add it back if needed)
        if normalized.startswith('GB'):
            normalized = normalized[2:]
        
        # Ensure it's 9 digits
        if normalized.isdigit() and len(normalized) == 9:
            return f"GB{normalized}"
        
        # If already has GB prefix and is correct length
        if normalized.startswith('GB') and len(normalized) == 11:
            return normalized
        
        return vat_number  # Return original if can't normalize
    
    @staticmethod
    def validate_vat_number_format(vat_number: str) -> bool:
        """
        Validate UK VAT number format
        Format: GB + 9 digits (e.g., GB123456789)
        """
        if not vat_number:
            return False
        
        normalized = HMRCVATService.normalize_vat_number(vat_number)
        
        # Check format: GB + 9 digits
        pattern = r'^GB\d{9}$'
        return bool(re.match(pattern, normalized))
    
    def verify_vat_number(self, vat_number: str) -> Optional[Dict]:
        """
        Verify VAT number using HMRC VAT API
        Uses OAuth authentication if configured
        
        Args:
            vat_number: UK VAT number to verify
            
        Returns:
            Dictionary with verification results or None if verification fails
        """
        if not vat_number:
            return None
        
        normalized_vat = self.normalize_vat_number(vat_number)
        
        if not self.validate_vat_number_format(normalized_vat):
            logger.warning(f"Invalid VAT number format: {vat_number}")
            return None
        
        logger.info(f"Verifying VAT number: {normalized_vat}")
        
        # Get authorization header
        auth_header = self._get_auth_header()
        if not auth_header:
            logger.warning("No HMRC authentication available. Set HMRC_CLIENT_ID and HMRC_CLIENT_SECRET for OAuth, or HMRC_SERVER_TOKEN")
            # Return placeholder response if no auth configured
            return {
                "vat_number": normalized_vat,
                "valid": None,
                "business_name": None,
                "address": None,
                "registration_date": None,
                "status": "authentication_required"
            }
        
        try:
            # HMRC VAT API endpoint for checking VAT numbers
            # Remove GB prefix for API call (HMRC API expects just the 9 digits)
            vat_for_api = normalized_vat[2:] if normalized_vat.startswith('GB') else normalized_vat
            
            url = f"{self.base_url}/organisations/vat/check-vat-number/{vat_for_api}"
            
            headers = {
                "Authorization": auth_header,
                "Accept": "application/vnd.hmrc.1.0+json"
            }
            
            logger.info(f"Calling HMRC VAT API: {url}")
            response = self.session.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"VAT verification successful for {normalized_vat}")
                
                # Parse HMRC API response
                return {
                    "vat_number": normalized_vat,
                    "valid": True,
                    "business_name": data.get("name"),
                    "address": data.get("address", {}).get("line1") if isinstance(data.get("address"), dict) else None,
                    "registration_date": data.get("registrationDate"),
                    "status": "verified",
                    "data": data
                }
            elif response.status_code == 404:
                logger.info(f"VAT number not found: {normalized_vat}")
                return {
                    "vat_number": normalized_vat,
                    "valid": False,
                    "business_name": None,
                    "address": None,
                    "registration_date": None,
                    "status": "not_found"
                }
            elif response.status_code == 401:
                logger.error("HMRC API authentication failed. Check OAuth credentials.")
                # Clear token cache to force refresh
                self._access_token = None
                self._token_expires_at = None
                return None
            else:
                logger.error(f"HMRC VAT API error. Status: {response.status_code}, Response: {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling HMRC VAT API: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in VAT verification: {e}")
            return None
    
    def extract_vat_data(self, vat_number: str) -> Dict:
        """
        Extract VAT registration data from HMRC API
        Similar to Companies House extract_company_data
        
        Args:
            vat_number: UK VAT number
            
        Returns:
            Dictionary with VAT registration data
        """
        normalized_vat = self.normalize_vat_number(vat_number)
        
        if not self.validate_vat_number_format(normalized_vat):
            logger.warning(f"Invalid VAT number format: {vat_number}")
            return {
                "vat_number": None,
                "business_name": None,
                "address": None,
                "registration_date": None,
                "data": None
            }
        
        logger.info(f"Looking up HMRC VAT data for: {normalized_vat}")
        
        # Verify VAT number
        verification_result = self.verify_vat_number(normalized_vat)
        
        if not verification_result:
            return {
                "vat_number": normalized_vat,
                "business_name": None,
                "address": None,
                "registration_date": None,
                "data": None
            }
        
        return {
            "vat_number": verification_result.get("vat_number"),
            "business_name": verification_result.get("business_name"),
            "address": verification_result.get("address"),
            "registration_date": verification_result.get("registration_date"),
            "data": verification_result
        }

