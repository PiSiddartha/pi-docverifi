"""
Application configuration
"""
from pydantic_settings import BaseSettings
from typing import List, Union
from pydantic import field_validator, field_serializer
import json


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://piadmin:Payintellidevdb1234%23@pi-infra-dev-rds-ap-south-1-db.cvy62s2q2odo.ap-south-1.rds.amazonaws.com:5432/pi_database"
    
    # Companies House API
    COMPANIES_HOUSE_API_KEY: str = ""
    
    # AWS S3 (optional)
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = ""
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Application
    SECRET_KEY: str = "change-me-in-production"
    ENVIRONMENT: str = "development"
    CORS_ORIGINS: Union[str, List[str]] = ["http://localhost:3000"]
    
    # File Upload
    MAX_UPLOAD_SIZE: int = 10485760  # 10MB
    UPLOAD_DIR: str = "./uploads"
    
    @field_validator('CORS_ORIGINS', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS_ORIGINS from string or list"""
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            # Try JSON first
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
            # If not JSON, split by comma
            return [origin.strip() for origin in v.split(',') if origin.strip()]
        return ["http://localhost:3000"]
    
    def get_cors_origins_list(self) -> List[str]:
        """Get CORS origins as a list"""
        if isinstance(self.CORS_ORIGINS, list):
            return self.CORS_ORIGINS
        if isinstance(self.CORS_ORIGINS, str):
            try:
                parsed = json.loads(self.CORS_ORIGINS)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
            return [origin.strip() for origin in self.CORS_ORIGINS.split(',') if origin.strip()]
        return ["http://localhost:3000"]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

