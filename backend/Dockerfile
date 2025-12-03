FROM python:3.12-slim

# Install system dependencies required by Python packages
RUN apt-get update && apt-get install -y \
    # Build tools for compiling Python packages (psycopg2, cryptography, etc.)
    gcc \
    g++ \
    # PostgreSQL client library (required by psycopg2-binary)
    libpq-dev \
    # Poppler utilities (required by pdf2image for PDF to image conversion)
    poppler-utils \
    # File type detection (required by python-magic)
    libmagic1 \
    # OpenCV system libraries (opencv-python-headless has minimal requirements)
    libglib2.0-0 \
    libgomp1 \
    # Image processing libraries (required by Pillow/PIL)
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create uploads directory
RUN mkdir -p /tmp/uploads

# Expose port
EXPOSE 8000

# Set environment variable for headless OpenCV
ENV QT_QPA_PLATFORM=offscreen
ENV OPENCV_IO_ENABLE_OPENEXR=0

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

