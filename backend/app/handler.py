"""
Lambda handler for FastAPI application
"""
from mangum import Mangum
from app.main import app

# Create Mangum adapter for FastAPI
handler = Mangum(app, lifespan="off")

