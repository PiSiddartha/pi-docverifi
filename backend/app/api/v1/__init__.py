from fastapi import APIRouter
from app.api.v1 import documents, verification

router = APIRouter()

router.include_router(documents.router, prefix="/documents", tags=["documents"])
router.include_router(verification.router, prefix="/verification", tags=["verification"])

