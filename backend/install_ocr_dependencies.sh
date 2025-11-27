#!/bin/bash

# Script to install OCR dependencies for document verification
# Supports: macOS, Ubuntu/Debian, and provides manual instructions for other systems

echo "🔍 Installing OCR Dependencies for Document Verification"
echo "=========================================================="
echo ""

# Detect OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macOS"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Try to detect Linux distribution
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
    else
        OS="linux"
    fi
else
    OS="unknown"
fi

echo "Detected OS: $OS"
echo ""

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Install based on OS
case $OS in
    "macOS")
        echo "📦 Installing dependencies for macOS..."
        
        # Check for Homebrew
        if ! command_exists brew; then
            echo "❌ Homebrew is not installed. Please install it first:"
            echo "   /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
            exit 1
        fi
        
        # Install Tesseract OCR
        if ! command_exists tesseract; then
            echo "Installing Tesseract OCR..."
            brew install tesseract
        else
            echo "✅ Tesseract OCR already installed"
        fi
        
        # Install Poppler (for PDF processing)
        if ! command_exists pdftoppm; then
            echo "Installing Poppler..."
            brew install poppler
        else
            echo "✅ Poppler already installed"
        fi
        
        # Install additional dependencies
        echo "Installing additional image processing libraries..."
        brew install libjpeg libpng libtiff
        
        echo ""
        echo "✅ macOS dependencies installed successfully!"
        ;;
    
    "ubuntu"|"debian")
        echo "📦 Installing dependencies for Ubuntu/Debian..."
        
        # Update package list
        echo "Updating package list..."
        sudo apt-get update
        
        # Install Tesseract OCR
        if ! command_exists tesseract; then
            echo "Installing Tesseract OCR..."
            sudo apt-get install -y tesseract-ocr libtesseract-dev
        else
            echo "✅ Tesseract OCR already installed"
        fi
        
        # Install Poppler
        if ! command_exists pdftoppm; then
            echo "Installing Poppler..."
            sudo apt-get install -y poppler-utils
        else
            echo "✅ Poppler already installed"
        fi
        
        # Install additional dependencies
        echo "Installing additional image processing libraries..."
        sudo apt-get install -y \
            libjpeg-dev \
            libpng-dev \
            libtiff-dev \
            libopencv-dev \
            python3-opencv
        
        echo ""
        echo "✅ Ubuntu/Debian dependencies installed successfully!"
        ;;
    
    "fedora"|"rhel"|"centos")
        echo "📦 Installing dependencies for Fedora/RHEL/CentOS..."
        
        # Install Tesseract OCR
        if ! command_exists tesseract; then
            echo "Installing Tesseract OCR..."
            sudo dnf install -y tesseract tesseract-devel
        else
            echo "✅ Tesseract OCR already installed"
        fi
        
        # Install Poppler
        if ! command_exists pdftoppm; then
            echo "Installing Poppler..."
            sudo dnf install -y poppler-utils
        else
            echo "✅ Poppler already installed"
        fi
        
        # Install additional dependencies
        echo "Installing additional image processing libraries..."
        sudo dnf install -y \
            libjpeg-turbo-devel \
            libpng-devel \
            libtiff-devel \
            opencv-devel
        
        echo ""
        echo "✅ Fedora/RHEL/CentOS dependencies installed successfully!"
        ;;
    
    *)
        echo "⚠️  Unsupported OS detected: $OS"
        echo ""
        echo "Please install the following dependencies manually:"
        echo ""
        echo "1. Tesseract OCR:"
        echo "   - macOS: brew install tesseract"
        echo "   - Ubuntu/Debian: sudo apt-get install tesseract-ocr libtesseract-dev"
        echo "   - Fedora: sudo dnf install tesseract tesseract-devel"
        echo "   - Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki"
        echo ""
        echo "2. Poppler (for PDF processing):"
        echo "   - macOS: brew install poppler"
        echo "   - Ubuntu/Debian: sudo apt-get install poppler-utils"
        echo "   - Fedora: sudo dnf install poppler-utils"
        echo "   - Windows: Download from https://github.com/oschwartz10612/poppler-windows/releases"
        echo ""
        echo "3. Image processing libraries:"
        echo "   - libjpeg, libpng, libtiff"
        echo ""
        exit 1
        ;;
esac

# Verify installations
echo ""
echo "🔍 Verifying installations..."
echo ""

# Check Tesseract
if command_exists tesseract; then
    TESSERACT_VERSION=$(tesseract --version 2>&1 | head -n 1)
    echo "✅ Tesseract: $TESSERACT_VERSION"
else
    echo "❌ Tesseract not found in PATH"
fi

# Check Poppler
if command_exists pdftoppm; then
    POPPLER_VERSION=$(pdftoppm -v 2>&1 | head -n 1)
    echo "✅ Poppler: $POPPLER_VERSION"
else
    echo "❌ Poppler not found in PATH"
fi

# Check Python packages (if virtual environment is active)
if [ -n "$VIRTUAL_ENV" ]; then
    echo ""
    echo "📦 Checking Python packages..."
    pip list | grep -E "(pytesseract|pdf2image|Pillow|opencv-python)" || echo "⚠️  Some Python packages may need to be installed"
fi

echo ""
echo "✅ Installation complete!"
echo ""
echo "Next steps:"
echo "1. Activate your virtual environment: source venv/bin/activate"
echo "2. Install Python dependencies: pip install -r requirements.txt"
echo "3. Test OCR: python -c 'import pytesseract; print(pytesseract.get_tesseract_version())'"
echo ""

