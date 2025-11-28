# Document Verification Scoring System

This document explains the scoring system used in the Document Verification pipeline for Companies House documents.

## Overview

The verification system uses a multi-factor scoring approach to assess document authenticity and data accuracy. The final score is calculated from multiple components, each measuring different aspects of document verification.

**Total Possible Score**: 130 points (capped at 100)  
**Score Formula**: `OCR Confidence Score + Registry Score + Provided Score + OCR Data Match Score - Forensic Penalty`

---

## Score Components

### 1. OCR Confidence Score (0-30 points)

**Purpose**: Measures the quality and confidence of the OCR (Optical Character Recognition) extraction process. This score reflects how well the OCR system was able to read and extract text from the document.

**Calculation**:
- Based on the confidence score returned by AWS Textract
- Formula: `(OCR Confidence / 100) × 30`
- Maximum: 30 points (100% confidence)
- Minimum: 0 points (0% confidence or extraction failure)

**What it means**:
- **High Score (25-30)**: OCR extracted text with high confidence, indicating clear, readable document
- **Medium Score (15-24)**: OCR had moderate confidence, may have some unclear text
- **Low Score (0-14)**: OCR had low confidence, document may be blurry, damaged, or poorly scanned

**Note**: This is different from "OCR Data Match Score" (section 3), which compares the extracted data with Companies House records.

**Example**:
- OCR Confidence: 97% → OCR Confidence Score: 29.1/30
- OCR Confidence: 89% → OCR Confidence Score: 26.8/30

---

### 2. Registry Score (0-40 points)

**Purpose**: Validates that the company number extracted from the document matches the official Companies House registry. This is the **most critical** verification component.

**Calculation**:
- Compares OCR-extracted company number with Companies House API data
- Normalizes both numbers to 8-digit format (handles 6, 7, and 8-digit formats)
- **Exact Match**: 40 points
- **Partial Match**: Similarity ratio × 40 points
- **No Match**: 0 points

**Normalization Rules**:
- `640918` (6 digits) → `00640918` (8 digits)
- `3035678` (7 digits) → `03035678` (8 digits)
- `03035678` (8 digits) → `03035678` (no change)
- `SC555555` (2 letters + 6 digits) → `SC555555` (no change)

**What it means**:
- **40/40**: Perfect match - document company number matches official registry
- **20-39**: Partial match - numbers are similar but not exact
- **0-19**: No match or mismatch - document may be for wrong company or fraudulent

**Why it's critical**:
- Company numbers are unique identifiers
- A match confirms the document is for the correct registered company
- Hardest to fake or manipulate

**Example**:
- OCR: `3357630` → Normalized: `03357630`
- Companies House: `03357630`
- Result: **40.0/40** ✅ Perfect match

---

### 3. OCR Data Match Score (0-30 points)

**Purpose**: Validates that the company name, number, and address extracted from the document (via OCR/LLM) match the official Companies House registry data. This score measures the accuracy of the extracted data, not the OCR confidence.

**Calculation**:
- Compares three fields extracted by OCR/LLM with Companies House data:
  - **Company Name** (50% weight) - Most important, strict validation
  - **Company Number** (30% weight) - Already validated in Registry Score
  - **Address** (20% weight) - More lenient (addresses can change)
- Uses fuzzy string matching (SequenceMatcher) for similarity
- **Strict Name Validation**: If company name similarity < 0.98, penalties apply
- Formula: `(Name Similarity × 0.5 + Number Similarity × 0.3 + Address Similarity × 0.2) × 30`
- Maximum: 30 points (all fields match perfectly)

**What it means**:
- **25-30**: Strong match - extracted data closely matches registry
- **15-24**: Moderate match - some differences but generally correct
- **0-14**: Weak match - significant discrepancies found

**Comparison Details**:
- **Company Name**: 
  - **Strict validation**: Similarity ≥ 0.98 = Full score
  - **Penalty applied**: Similarity < 0.98 = Reduced score
  - Handles minor variations like "E. & C. HOLDEN LIMITED" vs "E & C HOLDEN LIMITED"
  - Catches OCR errors like "YE" vs "& E" (similarity ~0.94 = heavy penalty)
- **Company Number**: Normalized before comparison (same as Registry Score)
- **Address**: More lenient validation (addresses can change over time due to relocations)

**Examples**:

*Example 1: Perfect Name Match (No Penalty)*
- OCR Name: "E. & C. HOLDEN LIMITED"
- CH Name: "E & C HOLDEN LIMITED"
- Similarity: 98.5% (≥ 0.98 threshold)
- Name Score: 0.985 × 0.5 × 30 = **14.78 points** (full score for name component)

*Example 2: Good Match with Minor Penalty*
- OCR Name: "E. & C. HOLDEN LIMITED"
- CH Name: "E & C HOLDEN LIMITED"
- Similarity: 95% (< 0.98 threshold, but ≥ 0.90)
- Penalty Factor: (0.95 - 0.90) / 0.08 = 0.625
- Name Score: 0.95 × 0.625 × 0.5 × 30 = **8.9 points** (penalized)

*Example 3: OCR Error (Heavy Penalty)*
- OCR Name: "E. YE. INVESTMENTS LIMITED" (OCR error)
- CH Name: "E. & E. INVESTMENTS LIMITED"
- Similarity: 94.3% (< 0.90 threshold)
- Penalty Factor: (0.943 - 0.70) / 0.20 = 1.215 (capped at 1.0) = 1.0
- Name Score: 0.943 × 1.0 × 0.5 × 30 = **14.15 points** (but score is capped lower due to strict validation)

---

### 4. Provided Score (0-30 points)

**Purpose**: Validates that the merchant/user-provided data matches the official Companies House registry.

**Calculation**:
- Compares merchant-provided data with Companies House API data:
  - **Company Name** (40% weight)
  - **Company Number** (40% weight)
  - **Address** (20% weight)
- Uses fuzzy string matching for similarity
- Formula: `(Name Similarity × 0.4 + Number Similarity × 0.4 + Address Similarity × 0.2) × 30`
- Maximum: 30 points

**What it means**:
- **25-30**: Merchant data matches registry perfectly
- **15-24**: Merchant data mostly correct with minor differences
- **0-14**: Merchant data has significant errors or mismatches

**Use Case**:
- Validates that the merchant knows the correct company information
- Helps detect if merchant is submitting documents for wrong company
- Useful when merchant provides data upfront

**Example**:
- Merchant Name: "E & C HOLDEN LIMITED"
- CH Name: "E & C HOLDEN LIMITED"
- Similarity: 100% → Score: 12/30 (for name component)

---

### 5. Data Match Score (0-100 percentage)

**Purpose**: Provides an overall similarity percentage across all data sources. This is an **informational metric** and does not contribute to the final score.

**Calculation**:
- Compares all available data points:
  - OCR company name vs Companies House
  - OCR company number vs Companies House
  - OCR address vs Companies House
  - Merchant company name vs Companies House
  - Merchant company number vs Companies House
  - Merchant address vs Companies House
- Averages all similarity scores
- Returns as percentage (0-100%)

**What it means**:
- **80-100%**: Excellent overall match
- **60-79%**: Good match with some differences
- **40-59%**: Moderate match, review recommended
- **0-39%**: Poor match, likely issues

**Note**: This score is for informational purposes and helps understand overall data consistency.

---

### 6. Forensic Penalty (0-15 points deducted)

**Purpose**: Penalizes documents that show signs of tampering, manipulation, or forgery.

**Calculation**:
- Based on forensic analysis results:
  - **EXIF Data**: Missing or suspicious metadata
  - **ELA Score**: Error Level Analysis detects image manipulation
  - **JPEG Quality**: Inconsistent compression suggests editing
  - **Copy-Move Detection**: Detects cloned/copied regions
- Penalty ranges from 0 to 15 points
- **Subtracted** from the total score (not added)

**Forensic Checks**:
1. **EXIF Analysis**: Checks for metadata inconsistencies
2. **Error Level Analysis (ELA)**: Detects image editing/manipulation
3. **JPEG Quality Analysis**: Identifies recompression artifacts
4. **Copy-Move Detection**: Finds duplicated regions (common in forgeries)

**What it means**:
- **0 points**: No forensic issues detected
- **1-5 points**: Minor anomalies, may be due to scanning/compression
- **6-10 points**: Moderate issues, document may be edited
- **11-15 points**: Significant forensic issues, high risk of tampering

**Example**:
- Copy-move detected: 78.62% confidence
- Forensic Score: 66.7/100
- Penalty: **-5.0 points**

---

### 7. Final Score (0-100 points)

**Purpose**: The overall verification score that determines document authenticity.

**Calculation**:
```
Final Score = OCR Confidence Score + Registry Score + Provided Score + OCR Data Match Score - Forensic Penalty
Final Score = min(100, max(0, Final Score))  // Capped between 0 and 100
```

**Maximum Possible**: 130 points (capped at 100)  
**Minimum Possible**: 0 points

**Score Breakdown**:
- OCR Confidence Score: 0-30 points (measures OCR extraction quality)
- Registry Score: 0-40 points (most critical - company number match)
- Provided Score: 0-30 points (merchant data accuracy)
- OCR Data Match Score: 0-30 points (extracted data vs registry match)
- Forensic Penalty: 0-15 points (deducted)

---

### 8. Decision Logic

Based on the Final Score, the system makes one of three decisions:

| Final Score | Decision | Meaning |
|------------|----------|---------|
| **≥ 75 points** | **PASS** | Document is authentic and verified. All checks passed. |
| **50-74 points** | **REVIEW** | Document needs manual review. Some discrepancies found. |
| **< 50 points** | **FAIL** | Document failed verification. Significant issues detected. |

**Decision Criteria**:
- **PASS**: High confidence in document authenticity
- **REVIEW**: Moderate confidence, requires human verification
- **FAIL**: Low confidence, likely fraudulent or incorrect document

---

## Score Examples

### Example 1: Perfect Match
```
OCR Confidence:    29.1/30  (97% confidence)
Registry Score:     40.0/40  (Perfect number match)
OCR Data Match:     28.5/30  (Name/address match well)
Provided Score:    0.0/30   (No merchant data)
Forensic Penalty:  -0.0/15   (No issues)
─────────────────────────────────────
Final Score:        97.6/100 → PASS ✅
```

### Example 2: Good Match with Minor Issues
```
OCR Confidence:    26.8/30  (89% confidence)
Registry Score:     40.0/40  (Perfect number match)
OCR Data Match:     22.0/30  (Name/address mostly match)
Provided Score:    0.0/30   (No merchant data)
Forensic Penalty:  -5.0/15   (Copy-move detected)
─────────────────────────────────────
Final Score:        83.8/100 → PASS ✅
```

### Example 3: Needs Review
```
OCR Confidence:    24.0/30  (80% confidence)
Registry Score:     0.0/40   (Number mismatch)
OCR Data Match:     15.0/30  (Partial name/address match)
Provided Score:    0.0/30   (No merchant data)
Forensic Penalty:  -2.0/15   (Minor forensic issues)
─────────────────────────────────────
Final Score:        37.0/100 → REVIEW ⚠️
```

### Example 4: Failed Verification
```
OCR Confidence:    18.0/30  (60% confidence)
Registry Score:     0.0/40   (Number doesn't match)
OCR Data Match:     8.0/30   (Poor name/address match)
Provided Score:    0.0/30   (No merchant data)
Forensic Penalty:  -10.0/15  (Significant forensic issues)
─────────────────────────────────────
Final Score:        16.0/100 → FAIL ❌
```

---

## Score Weighting Summary

| Component | Weight | Importance | Notes |
|-----------|-------|-----------|-------|
| **Registry Score** | 40 points | ⭐⭐⭐⭐⭐ Critical | Company number match is most important |
| **OCR Confidence Score** | 30 points | ⭐⭐⭐⭐ High | Measures OCR extraction quality |
| **OCR Data Match Score** | 30 points | ⭐⭐⭐⭐ High | Validates extracted name/address accuracy |
| **Provided Score** | 30 points | ⭐⭐⭐ Medium | Only if merchant provides data |
| **Forensic Penalty** | -15 points | ⭐⭐⭐⭐ High | Can significantly impact score |

---

## Best Practices

### For High Scores:
1. **Clear Documents**: Ensure documents are high-quality scans with good resolution
2. **Correct Company**: Verify document is for the correct company
3. **No Tampering**: Avoid any image editing or manipulation
4. **Complete Data**: Provide merchant data when available

### For Review Cases:
- Check if company number was extracted correctly
- Verify company name matches (handles variations)
- Review address formatting differences
- Check for scanning/compression artifacts

### For Failed Cases:
- Verify document is authentic and not tampered
- Check if document is for correct company
- Ensure OCR extraction was successful
- Review forensic analysis details

---

## Technical Details

### String Similarity Algorithm
- Uses Python's `difflib.SequenceMatcher` for fuzzy matching
- Returns similarity ratio between 0.0 (no match) and 1.0 (exact match)
- Handles:
  - Case differences ("LIMITED" vs "limited")
  - Punctuation variations ("E. & C." vs "E & C")
  - Whitespace differences
  - Partial matches

### Company Number Normalization
- Automatically handles 6, 7, and 8-digit formats
- Pads with leading zeros to 8-digit format
- Preserves letter prefixes (e.g., "SC", "OC")
- Used consistently across all comparisons

### Forensic Analysis
- **EXIF**: Extracts and validates image metadata
- **ELA**: Error Level Analysis detects image manipulation
- **JPEG Quality**: Analyzes compression consistency
- **Copy-Move**: Detects cloned regions using computer vision

---

## API Response Format

The scoring results are returned in the following format:

```json
{
  "ocr_score": 29.1,
  "registry_score": 40.0,
  "ocr_comparison_score": 28.5,
  "provided_score": 0.0,
  "data_match_score": 85.3,
  "final_score": 97.6,
  "decision": "PASS",
  "forensic_penalty": 0.0
}
```

**Note**: The API field names use `ocr_score` and `ocr_comparison_score` for backward compatibility, but they represent:
- `ocr_score`: OCR Confidence Score (extraction quality)
- `ocr_comparison_score`: OCR Data Match Score (extracted data accuracy)

---

**Last Updated**: 2025-11-28  
**Version**: 2.1 (clarified distinction between OCR Confidence Score and OCR Data Match Score)

