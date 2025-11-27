"""
AWS S3 service for document storage
"""
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from typing import Optional
import logging
from pathlib import Path
import io

from app.core.config import settings

logger = logging.getLogger(__name__)


class S3Service:
    """Service for interacting with AWS S3"""
    
    def __init__(self):
        self.bucket_name = settings.S3_BUCKET_NAME
        self.region = settings.AWS_REGION
        
        # Initialize S3 client if credentials are provided
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=self.region
            )
            self.enabled = True
        else:
            self.s3_client = None
            self.enabled = False
            logger.warning("S3 credentials not configured. S3 uploads will be disabled.")
    
    def is_enabled(self) -> bool:
        """Check if S3 is enabled"""
        return self.enabled and bool(self.bucket_name)
    
    def upload_file(self, file_path: str, s3_key: str) -> Optional[str]:
        """
        Upload a file to S3
        
        Args:
            file_path: Local file path
            s3_key: S3 object key (path in bucket)
            
        Returns:
            S3 URL if successful, None otherwise
        """
        if not self.is_enabled():
            logger.warning("S3 not enabled, skipping upload")
            return None
        
        try:
            self.s3_client.upload_file(
                file_path,
                self.bucket_name,
                s3_key,
                ExtraArgs={'ContentType': self._get_content_type(file_path)}
            )
            
            # Generate S3 URL
            s3_url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"
            logger.info(f"File uploaded to S3: {s3_key}")
            return s3_url
            
        except FileNotFoundError:
            logger.error(f"File not found: {file_path}")
            return None
        except NoCredentialsError:
            logger.error("AWS credentials not found")
            return None
        except ClientError as e:
            logger.error(f"Error uploading to S3: {e}")
            return None
    
    def upload_fileobj(self, file_obj: io.BytesIO, s3_key: str, content_type: str = "application/octet-stream") -> Optional[str]:
        """
        Upload a file-like object to S3
        
        Args:
            file_obj: File-like object (BytesIO)
            s3_key: S3 object key
            content_type: MIME type of the file
            
        Returns:
            S3 URL if successful, None otherwise
        """
        if not self.is_enabled():
            logger.warning("S3 not enabled, skipping upload")
            return None
        
        try:
            file_obj.seek(0)
            self.s3_client.upload_fileobj(
                file_obj,
                self.bucket_name,
                s3_key,
                ExtraArgs={'ContentType': content_type}
            )
            
            s3_url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"
            logger.info(f"File uploaded to S3: {s3_key}")
            return s3_url
            
        except NoCredentialsError:
            logger.error("AWS credentials not found")
            return None
        except ClientError as e:
            logger.error(f"Error uploading to S3: {e}")
            return None
    
    def download_file(self, s3_key: str, local_path: str) -> bool:
        """
        Download a file from S3
        
        Args:
            s3_key: S3 object key
            local_path: Local file path to save to
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_enabled():
            logger.warning("S3 not enabled, cannot download")
            return False
        
        try:
            # Create directory if it doesn't exist
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)
            
            self.s3_client.download_file(
                self.bucket_name,
                s3_key,
                local_path
            )
            logger.info(f"File downloaded from S3: {s3_key}")
            return True
            
        except NoCredentialsError:
            logger.error("AWS credentials not found")
            return False
        except ClientError as e:
            logger.error(f"Error downloading from S3: {e}")
            return False
    
    def get_file_url(self, s3_key: str, expires_in: int = 3600) -> Optional[str]:
        """
        Generate a presigned URL for a file
        
        Args:
            s3_key: S3 object key
            expires_in: URL expiration time in seconds (default 1 hour)
            
        Returns:
            Presigned URL if successful, None otherwise
        """
        if not self.is_enabled():
            return None
        
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=expires_in
            )
            return url
        except ClientError as e:
            logger.error(f"Error generating presigned URL: {e}")
            return None
    
    def delete_file(self, s3_key: str) -> bool:
        """
        Delete a file from S3
        
        Args:
            s3_key: S3 object key
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_enabled():
            return False
        
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            logger.info(f"File deleted from S3: {s3_key}")
            return True
        except ClientError as e:
            logger.error(f"Error deleting from S3: {e}")
            return False
    
    def _get_content_type(self, file_path: str) -> str:
        """Get content type based on file extension"""
        extension = Path(file_path).suffix.lower()
        content_types = {
            '.pdf': 'application/pdf',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.tiff': 'image/tiff',
            '.tif': 'image/tiff',
        }
        return content_types.get(extension, 'application/octet-stream')


# Global instance
s3_service = S3Service()

