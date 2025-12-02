#!/bin/bash
# Simple script to create basic test PDFs using ImageMagick or other tools
# Alternative to Python script if reportlab is not available

echo "Creating test documents directory..."
mkdir -p generated_documents

echo "Note: This script requires ImageMagick or similar tools."
echo "For better results, use the Python script: create_test_documents.py"
echo ""
echo "Creating placeholder text files that can be converted to PDF..."

# VAT Registration Sample 1
cat > generated_documents/vat_registration_01.txt << 'EOF'
HM REVENUE & CUSTOMS
VAT REGISTRATION CERTIFICATE

VAT Registration Number: GB123456789

Business Name: ACME TRADING LIMITED

Registered Address:
123 High Street
London
SW1A 1AA

Date of Registration: 15 January 2020

This certificate confirms that the above business is registered for VAT purposes.

Certificate Number: VAT/2020/001234

Issued by HM Revenue & Customs
EOF

# Director Verification Sample 1
cat > generated_documents/director_verification_01.txt << 'EOF'
COMPANIES HOUSE
DIRECTOR VERIFICATION DOCUMENT

Director Name: JOHN MICHAEL SMITH

Date of Birth: 15 May 1975

Residential Address:
45 Oak Avenue
London
SW1A 2BB

Company Name: TECHNOLOGY SOLUTIONS LIMITED
Company Number: 12345678

Date of Appointment: 10 January 2020

This document confirms that the above named person is a director of the company listed.

Certificate Number: DIR/2020/001234

Issued by Companies House
EOF

echo "Text files created. To convert to PDF:"
echo "  - Use LibreOffice: libreoffice --headless --convert-to pdf generated_documents/*.txt"
echo "  - Use pandoc: pandoc generated_documents/*.txt -o output.pdf"
echo "  - Use online converters"
echo ""
echo "Or install reportlab and use: python create_test_documents.py"

