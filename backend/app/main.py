"""
Main FastAPI application entry point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1 import router as api_router
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

