#!/usr/bin/env python3
"""
Script to create test PDF documents for VAT Registration and Director Verification
Requires: reportlab (pip install reportlab)
"""
import os
import json
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

def create_vat_registration_pdf(output_path: str, data: dict):
    """Create a VAT Registration Certificate PDF"""
    doc = SimpleDocTemplate(output_path, pagesize=A4)
    story = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    story.append(Paragraph("HM REVENUE & CUSTOMS", title_style))
    story.append(Paragraph("VAT REGISTRATION CERTIFICATE", title_style))
    story.append(Spacer(1, 20))
    
    # VAT Number
    story.append(Paragraph(f"<b>VAT Registration Number:</b> {data['vat_number']}", styles['Normal']))
    story.append(Spacer(1, 15))
    
    # Business Name
    story.append(Paragraph(f"<b>Business Name:</b> {data['business_name']}", styles['Normal']))
    story.append(Spacer(1, 15))
    
    # Address
    story.append(Paragraph("<b>Registered Address:</b>", styles['Normal']))
    address_lines = data['business_address'].split(',')
    for line in address_lines:
        story.append(Paragraph(line.strip(), styles['Normal']))
    story.append(Spacer(1, 15))
    
    # Registration Date
    story.append(Paragraph(f"<b>Date of Registration:</b> {data['registration_date']}", styles['Normal']))
    story.append(Spacer(1, 30))
    
    # Footer
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#666666'),
        alignment=TA_CENTER
    )
    story.append(Spacer(1, 50))
    story.append(Paragraph("This certificate confirms that the above business is registered for VAT purposes.", footer_style))
    story.append(Paragraph(f"Certificate Number: VAT/{data['registration_date'][:4]}/001234", footer_style))
    story.append(Paragraph("Issued by HM Revenue & Customs", footer_style))
    
    doc.build(story)
    print(f"Created VAT Registration PDF: {output_path}")

def create_director_verification_pdf(output_path: str, data: dict):
    """Create a Director Verification Document PDF"""
    doc = SimpleDocTemplate(output_path, pagesize=A4)
    story = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    story.append(Paragraph("COMPANIES HOUSE", title_style))
    story.append(Paragraph("DIRECTOR VERIFICATION DOCUMENT", title_style))
    story.append(Spacer(1, 20))
    
    # Director Name
    story.append(Paragraph(f"<b>Director Name:</b> {data['director_name']}", styles['Normal']))
    story.append(Spacer(1, 15))
    
    # Date of Birth
    story.append(Paragraph(f"<b>Date of Birth:</b> {data['director_dob']}", styles['Normal']))
    story.append(Spacer(1, 15))
    
    # Address
    story.append(Paragraph("<b>Residential Address:</b>", styles['Normal']))
    address_lines = data['director_address'].split(',')
    for line in address_lines:
        story.append(Paragraph(line.strip(), styles['Normal']))
    story.append(Spacer(1, 15))
    
    # Company Information
    story.append(Paragraph(f"<b>Company Name:</b> {data['company_name']}", styles['Normal']))
    story.append(Paragraph(f"<b>Company Number:</b> {data['company_number']}", styles['Normal']))
    story.append(Spacer(1, 15))
    
    # Appointment Date
    story.append(Paragraph(f"<b>Date of Appointment:</b> {data['appointment_date']}", styles['Normal']))
    story.append(Spacer(1, 30))
    
    # Footer
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#666666'),
        alignment=TA_CENTER
    )
    story.append(Spacer(1, 50))
    story.append(Paragraph("This document confirms that the above named person is a director of the company listed.", footer_style))
    story.append(Paragraph(f"Certificate Number: DIR/{data['appointment_date'][:4]}/001234", footer_style))
    story.append(Paragraph("Issued by Companies House", footer_style))
    
    doc.build(story)
    print(f"Created Director Verification PDF: {output_path}")

def main():
    """Generate test documents from JSON data"""
    script_dir = Path(__file__).parent
    output_dir = script_dir / "generated_documents"
    output_dir.mkdir(exist_ok=True)
    
    # Load VAT samples
    vat_file = script_dir / "vat_registration_samples.json"
    if vat_file.exists():
        with open(vat_file, 'r') as f:
            vat_data = json.load(f)
        
        for i, sample in enumerate(vat_data['vat_registration_samples'], 1):
            filename = f"vat_registration_{i:02d}_{sample['vat_number'].replace('GB', '')}.pdf"
            output_path = output_dir / filename
            create_vat_registration_pdf(str(output_path), sample)
    
    # Load Director samples
    director_file = script_dir / "director_verification_samples.json"
    if director_file.exists():
        with open(director_file, 'r') as f:
            director_data = json.load(f)
        
        for i, sample in enumerate(director_data['director_verification_samples'], 1):
            filename = f"director_verification_{i:02d}_{sample['company_number']}.pdf"
            output_path = output_dir / filename
            create_director_verification_pdf(str(output_path), sample)
    
    print(f"\nAll test documents created in: {output_dir}")
    print(f"Total files: {len(list(output_dir.glob('*.pdf')))}")

if __name__ == "__main__":
    main()

