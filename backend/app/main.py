"""
Main FastAPI application entry point
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1 import router as api_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # This ensures logs go to stdout/stderr
    ]
)

# Set specific loggers to INFO level
logging.getLogger("app").setLevel(logging.INFO)
logging.getLogger("app.services.llm_service").setLevel(logging.INFO)
logging.getLogger("app.services.ocr_service").setLevel(logging.INFO)
logging.getLogger("app.services.pipeline_service").setLevel(logging.INFO)
logging.getLogger("app.api.v1.verification").setLevel(logging.INFO)

logger = logging.getLogger(__name__)

# Note: Tables should be created manually using database_schema.sql
# or SQL migrations from the migrations/ directory.
# Uncomment below if you want auto-creation (not recommended for production):
# from app.db.database import engine
# from app.db.models import Base
# Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Document Verification API",
    description="Industry-standard document verification system with OCR, forensics, and Companies House integration",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(api_router, prefix="/api/v1")

# Log LLM service availability on startup
try:
    from app.services.llm_service import LLMService
    from app.core.config import settings
    logger.info("=" * 80)
    logger.info("LLM Service Status: AVAILABLE")
    logger.info(f"OpenAI Model: {getattr(settings, 'OPENAI_MODEL', 'gpt-5-nano')}")
    logger.info(f"OpenAI API Key: {'Set' if getattr(settings, 'OPENAI_API_KEY', None) else 'Not Set'}")
    logger.info("=" * 80)
except Exception as e:
    logger.warning(f"LLM Service Status: UNAVAILABLE - {e}")


@app.get("/")
async def root():
    return {
        "message": "Document Verification API",
        "version": "1.0.0",
        "docs": "/api/docs"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}

