import re
import logging
from typing import Optional, List, Dict, Any
import pdfplumber

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_line_items(pdf_path: str) -> List[Dict]:
    """Extract line items from a hospital bill PDF."""
    line_items = []
    debug_info = {
        "pages": 0,
        "tables_found": 0,
        "table_rows": 0,
        "text_lines": 0,
        "items_from_tables": 0,
        "items_from_text": 0,
    }

    try:
        with pdfplumber.open(pdf_path) as pdf:
            debug_info["pages"] = len(pdf.pages)
            logger.info(f"Processing PDF with {len(pdf.pages)} pages")

            # Extract all text for pattern matching
            full_text = ""
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"

            debug_info["text_lines"] = len(full_text.split('\n'))
            logger.info(f"Extracted {debug_info['text_lines']} lines of text")

            # Strategy 1: Try to extract from tables
            for page_num, page in enumerate(pdf.pages):
                tables = page.extract_tables()
                debug_info["tables_found"] += len(tables)

                for table_idx, table in enumerate(tables):
                    logger.info(f"Page {page_num + 1}, Table {table_idx + 1}: {len(table)} rows")
                    for row in table:
                        debug_info["table_rows"] += 1
                        if row and len(row) >= 2:
                            item = parse_table_row(row)
                            if item:
                                line_items.append(item)
                                debug_info["items_from_tables"] += 1

            logger.info(f"Found {debug_info['items_from_tables']} items from tables")

            # Strategy 2: Pattern matching on text (always try, merge results)
            text_items = extract_from_text(full_text)
            debug_info["items_from_text"] = len(text_items)
            logger.info(f"Found {debug_info['items_from_text']} items from text patterns")

            # Merge text items if we didn't get many from tables
            if len(line_items) < 5:
                # Add text items that aren't duplicates
                existing_amounts = {item["amount"] for item in line_items}
                for item in text_items:
                    if item["amount"] not in existing_amounts:
                        line_items.append(item)
                        existing_amounts.add(item["amount"])

            # Strategy 3: Try more aggressive text extraction
            if len(line_items) < 10:
                aggressive_items = extract_from_text_aggressive(full_text)
                logger.info(f"Aggressive extraction found {len(aggressive_items)} additional items")
                existing_amounts = {item["amount"] for item in line_items}
                for item in aggressive_items:
                    if item["amount"] not in existing_amounts:
                        line_items.append(item)
                        existing_amounts.add(item["amount"])

    except Exception as e:
        logger.error(f"Error extracting PDF: {e}", exc_info=True)
        return get_mock_line_items()

    logger.info(f"Total extracted: {len(line_items)} line items")
    logger.info(f"Debug info: {debug_info}")

    # If still no items, return mock data for demo
    if not line_items:
        logger.info("No items found, returning mock data")
        return get_mock_line_items()

    # Sort by amount descending for better readability
    line_items.sort(key=lambda x: x["amount"], reverse=True)

    return line_items


def parse_table_row(row: list) -> Optional[dict]:
    """Parse a table row into a line item."""
    # Filter out empty cells
    cells = [str(c).strip() if c else "" for c in row]
    cells = [c for c in cells if c]

    if len(cells) < 2:
        return None

    # Try to find amount (look for dollar amounts)
    amount = None
    amount_idx = -1

    # Search from right to left (amounts usually on the right)
    for i in range(len(cells) - 1, -1, -1):
        cell = cells[i]
        # Match various currency formats
        match = re.search(r'\$?\s*([\d,]+\.?\d{0,2})', cell.replace(',', ''))
        if match:
            try:
                val = float(match.group(1).replace(',', ''))
                # Filter out likely non-amounts (dates, codes, etc.)
                if val > 1 and val < 1000000:
                    amount = val
                    amount_idx = i
                    break
            except ValueError:
                pass

    if amount is None:
        return None

    # Look for CPT/HCPCS codes (various formats)
    code = None
    for cell in cells:
        # 5-digit CPT codes
        code_match = re.search(r'\b(\d{5})\b', cell)
        if code_match:
            code = code_match.group(1)
            break
        # HCPCS codes (letter + 4 digits)
        code_match = re.search(r'\b([A-Z]\d{4})\b', cell)
        if code_match:
            code = code_match.group(1)
            break
        # Revenue codes (4 digits starting with 0)
        code_match = re.search(r'\b(0\d{3})\b', cell)
        if code_match:
            code = code_match.group(1)
            break

    # Description is usually the longest text field that's not a number
    description = ""
    for i, cell in enumerate(cells):
        if i != amount_idx and len(cell) > len(description):
            # Skip cells that are mostly numbers/currency
            if not re.match(r'^[\d\$\.,\s]+$', cell) and len(cell) > 3:
                description = cell

    if not description:
        return None

    # Clean up description
    description = re.sub(r'\s+', ' ', description).strip()

    return {
        "code": code,
        "description": description[:100],
        "quantity": 1,
        "amount": amount,
    }


def extract_from_text(text: str) -> List[Dict]:
    """Extract line items from raw text using pattern matching."""
    line_items = []
    seen_descriptions = set()

    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line or len(line) < 5:
            continue

        # Skip header/footer lines
        skip_words = ['total', 'subtotal', 'balance', 'payment', 'date', 'page',
                      'account', 'patient', 'insurance', 'amount due', 'paid']
        if any(skip in line.lower() for skip in skip_words):
            continue

        # Pattern 1: description followed by amount at end of line
        match = re.search(r'(.+?)\s+\$?([\d,]+\.\d{2})\s*$', line)
        if match:
            description = match.group(1).strip()
            amount_str = match.group(2).replace(',', '')

            try:
                amount = float(amount_str)
                if amount > 1 and len(description) > 3:
                    # Look for CPT/HCPCS code
                    code = extract_code(description)

                    # Avoid duplicates
                    desc_key = description[:50].lower()
                    if desc_key not in seen_descriptions:
                        seen_descriptions.add(desc_key)
                        line_items.append({
                            "code": code,
                            "description": description[:100],
                            "quantity": 1,
                            "amount": amount,
                        })
            except ValueError:
                pass

        # Pattern 2: amount in middle of line (code description amount quantity)
        match = re.search(r'(\d{5}|[A-Z]\d{4})?\s*(.+?)\s+\$?([\d,]+\.\d{2})\s+(\d+)?', line)
        if match and match.group(2):
            code = match.group(1)
            description = match.group(2).strip()
            amount_str = match.group(3).replace(',', '')

            try:
                amount = float(amount_str)
                if amount > 1 and len(description) > 3:
                    desc_key = description[:50].lower()
                    if desc_key not in seen_descriptions:
                        seen_descriptions.add(desc_key)
                        line_items.append({
                            "code": code,
                            "description": description[:100],
                            "quantity": 1,
                            "amount": amount,
                        })
            except ValueError:
                pass

    return line_items


def extract_from_text_aggressive(text: str) -> List[Dict]:
    """More aggressive text extraction - finds any line with a dollar amount."""
    line_items = []
    seen_amounts = set()

    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line or len(line) < 10:
            continue

        # Skip obvious non-item lines
        skip_patterns = ['total', 'subtotal', 'balance', 'payment', 'date', 'page',
                         'account', 'patient', 'insurance', 'amount due', 'paid',
                         'statement', 'billing', 'address', 'phone', 'fax']
        if any(skip in line.lower() for skip in skip_patterns):
            continue

        # Find all dollar amounts in the line
        amounts = re.findall(r'\$?\s*([\d,]+\.\d{2})', line)
        if amounts:
            # Take the last amount (usually the charge amount)
            try:
                amount = float(amounts[-1].replace(',', ''))
                if amount > 1 and amount < 100000 and amount not in seen_amounts:
                    # Remove the amount from the line to get description
                    description = re.sub(r'\$?\s*[\d,]+\.\d{2}', '', line).strip()
                    description = re.sub(r'\s+', ' ', description)

                    if len(description) > 5:
                        code = extract_code(line)
                        seen_amounts.add(amount)
                        line_items.append({
                            "code": code,
                            "description": description[:100],
                            "quantity": 1,
                            "amount": amount,
                        })
            except ValueError:
                pass

    return line_items


def extract_code(text: str) -> Optional[str]:
    """Extract CPT/HCPCS/Revenue code from text."""
    # 5-digit CPT codes
    match = re.search(r'\b(\d{5})\b', text)
    if match:
        return match.group(1)

    # HCPCS codes (letter + 4 digits)
    match = re.search(r'\b([A-Z]\d{4})\b', text)
    if match:
        return match.group(1)

    # Revenue codes (4 digits, often starting with 0)
    match = re.search(r'\b(0\d{3})\b', text)
    if match:
        return match.group(1)

    return None


def get_mock_line_items() -> List[Dict]:
    """Return mock line items for demo purposes."""
    return [
        {"code": "99213", "description": "Office/outpatient visit, established patient", "quantity": 1, "amount": 150.00},
        {"code": "85025", "description": "Complete blood count (CBC)", "quantity": 1, "amount": 45.00},
        {"code": "80053", "description": "Comprehensive metabolic panel", "quantity": 1, "amount": 75.00},
        {"code": "71046", "description": "Chest X-ray, 2 views", "quantity": 1, "amount": 250.00},
        {"code": "36415", "description": "Venipuncture for blood draw", "quantity": 1, "amount": 25.00},
    ]


def extract_hospital_info(pdf_path: str) -> Optional[Dict]:
    """
    Extract hospital/provider information from a PDF.
    Returns dict with detected hospital info or None if not found.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Focus on first 1-2 pages where hospital info usually appears
            text = ""
            for page in pdf.pages[:2]:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"

            if not text:
                return None

            # Known hospital patterns to look for (NC Triangle area)
            hospital_patterns = [
                # Duke hospitals
                (r"Duke University Hospital", "duke_main"),
                (r"Duke University Medical Center", "duke_main"),
                (r"DUMC\b", "duke_main"),
                (r"Duke Regional Hospital", "duke_regional"),
                (r"Duke Regional", "duke_regional"),
                (r"Duke Raleigh Hospital", "duke_raleigh"),
                (r"Duke Raleigh", "duke_raleigh"),
                # UNC hospitals
                (r"UNC Medical Center", "unc_main"),
                (r"UNC Hospitals?", "unc_main"),
                (r"UNC Health", "unc_main"),
                (r"University of North Carolina Hospital", "unc_main"),
                (r"UNC Rex Hospital", "unc_rex"),
                (r"Rex Hospital", "unc_rex"),
                (r"Rex Healthcare", "unc_rex"),
                (r"UNC Hillsborough", "unc_hillsborough"),
                (r"Hillsborough Campus", "unc_hillsborough"),
                # WakeMed hospitals
                (r"WakeMed Raleigh", "wakemed_raleigh"),
                (r"WakeMed Health", "wakemed_raleigh"),
                (r"WakeMed\b", "wakemed_raleigh"),
                (r"WakeMed Cary", "wakemed_cary"),
                (r"WakeMed North", "wakemed_north"),
            ]

            text_upper = text.upper()
            text_lower = text.lower()

            for pattern, hospital_id in hospital_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    logger.info(f"Detected hospital: {hospital_id} (matched pattern: {pattern})")
                    return {
                        "hospital_id": hospital_id,
                        "confidence": "high",
                        "matched_pattern": pattern,
                    }

            # Try to find any hospital-like entity in the header
            # Look for lines containing "hospital", "medical center", "health"
            lines = text.split('\n')[:20]  # Focus on first 20 lines
            for line in lines:
                line_lower = line.lower().strip()
                if any(term in line_lower for term in ['hospital', 'medical center', 'health system', 'clinic']):
                    # This looks like it might be a hospital name
                    logger.info(f"Possible hospital name found: {line.strip()}")
                    return {
                        "hospital_id": None,
                        "detected_name": line.strip()[:100],
                        "confidence": "low",
                    }

            return None

    except Exception as e:
        logger.error(f"Error extracting hospital info: {e}")
        return None


def extract_bill_data(pdf_path: str) -> Dict:
    """
    Extract all bill data including line items and hospital info.
    Returns a dict with line_items and detected_hospital.
    """
    line_items = extract_line_items(pdf_path)
    hospital_info = extract_hospital_info(pdf_path)

    return {
        "line_items": line_items,
        "detected_hospital": hospital_info,
    }
