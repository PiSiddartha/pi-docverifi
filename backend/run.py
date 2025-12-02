"""
Run the FastAPI application
"""
import logging
import uvicorn

# Configure logging before starting uvicorn
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True  # Force reconfiguration even if logging was already configured
)

# Set log level for uvicorn to INFO to see all logs
logging.getLogger("uvicorn").setLevel(logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.INFO)

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"  # Ensure uvicorn uses INFO level
    )

