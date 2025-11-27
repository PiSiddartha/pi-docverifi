# OCR Dependencies Setup Guide

This guide explains how to install the required system dependencies for OCR (Optical Character Recognition) and document processing.

## Required Dependencies

### 1. Tesseract OCR
Tesseract is the OCR engine used to extract text from images and PDFs.

### 2. Poppler
Poppler is used to convert PDF files to images for processing.

### 3. Image Processing Libraries
Additional libraries for image manipulation (libjpeg, libpng, libtiff).

## Quick Installation

### Automated Installation (Recommended)

Run the installation script:

```bash
chmod +x install_ocr_dependencies.sh
./install_ocr_dependencies.sh
```

This script will:
- Detect your operating system
- Install Tesseract OCR
- Install Poppler
- Install required image processing libraries
- Verify the installations

## Manual Installation by OS

### macOS

```bash
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install dependencies
brew install tesseract poppler libjpeg libpng libtiff
```

### Ubuntu/Debian

```bash
# Update package list
sudo apt-get update

# Install dependencies
sudo apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    poppler-utils \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libopencv-dev \
    python3-opencv
```

### Fedora/RHEL/CentOS

```bash
# Install dependencies
sudo dnf install -y \
    tesseract \
    tesseract-devel \
    poppler-utils \
    libjpeg-turbo-devel \
    libpng-devel \
    libtiff-devel \
    opencv-devel
```

### Windows

1. **Tesseract OCR:**
   - Download installer from: https://github.com/UB-Mannheim/tesseract/wiki
   - Run the installer
   - Add Tesseract to PATH (usually `C:\Program Files\Tesseract-OCR`)

2. **Poppler:**
   - Download from: https://github.com/oschwartz10612/poppler-windows/releases
   - Extract to a folder (e.g., `C:\poppler`)
   - Add `C:\poppler\Library\bin` to PATH

3. **Python packages:**
   ```bash
   pip install pytesseract pdf2image Pillow opencv-python
   ```

## Verification

After installation, verify that everything is working:

```bash
# Check Tesseract version
tesseract --version

# Check Poppler
pdftoppm -v

# Test Python integration
python -c "import pytesseract; print(pytesseract.get_tesseract_version())"
```

## Troubleshooting

### Tesseract not found

**macOS/Linux:**
- Ensure Tesseract is in your PATH
- Try: `export PATH="/usr/local/bin:$PATH"` (macOS)
- Or specify path in code: `pytesseract.pytesseract.tesseract_cmd = '/usr/local/bin/tesseract'`

**Windows:**
- Add Tesseract installation directory to PATH
- Or set in code: `pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'`

### Poppler not found

**macOS/Linux:**
- Ensure Poppler binaries are in PATH
- macOS: Usually installed to `/usr/local/bin` or `/opt/homebrew/bin`
- Linux: Usually in `/usr/bin`

**Windows:**
- Add Poppler `bin` directory to PATH
- Restart terminal/IDE after adding to PATH

### PDF conversion errors

- Ensure Poppler is properly installed
- Check file permissions
- Verify PDF is not corrupted
- Try converting a test PDF manually: `pdftoppm test.pdf output -png`

### Low OCR accuracy

- Ensure images are high resolution (300 DPI recommended)
- Check image quality (contrast, brightness)
- Try preprocessing images (grayscale, noise reduction)
- Use appropriate Tesseract language packs if needed

## Language Packs (Optional)

For better OCR accuracy with non-English documents:

**macOS:**
```bash
brew install tesseract-lang
```

**Ubuntu/Debian:**
```bash
sudo apt-get install tesseract-ocr-eng tesseract-ocr-fra tesseract-ocr-deu
```

**Windows:**
- Download language data files from: https://github.com/tesseract-ocr/tessdata
- Place in Tesseract `tessdata` folder

## Next Steps

1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure your `.env` file with database and API keys

3. Test the OCR service:
   ```bash
   python -c "from app.services.ocr_service import OCRService; print('OCR service ready')"
   ```

4. Start the server:
   ```bash
   python run.py
   ```

## Additional Resources

- [Tesseract OCR Documentation](https://tesseract-ocr.github.io/)
- [Poppler Documentation](https://poppler.freedesktop.org/)
- [pytesseract Documentation](https://pypi.org/project/pytesseract/)
- [pdf2image Documentation](https://pypi.org/project/pdf2image/)

