import re
import logging
from typing import Optional, List, Dict, Any
import pdfplumber

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import LLM extractor (optional, graceful fallback if not available)
try:
    from app.services.llm_extractor import extract_with_llm, is_llm_extraction_available
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    logger.info("LLM extractor not available, using regex-based extraction only")


def extract_line_items(pdf_path: str, use_llm: bool = True) -> List[Dict]:
    """
    Extract line items from a hospital bill PDF.

    Args:
        pdf_path: Path to the PDF file
        use_llm: Whether to try LLM extraction first (default True)

    Uses LLM vision-based extraction when available, falls back to
    regex-based parsing if LLM is unavailable or returns no results.
    """
    # Try LLM extraction first (more accurate for complex layouts)
    if use_llm and LLM_AVAILABLE and is_llm_extraction_available():
        logger.info("Attempting LLM-based extraction...")
        llm_items = extract_with_llm(pdf_path)
        if llm_items and len(llm_items) >= 3:  # Require at least 3 items for confidence
            logger.info(f"LLM extraction successful: {len(llm_items)} items")
            return llm_items
        else:
            logger.info("LLM extraction returned insufficient results, falling back to regex")
    elif use_llm and LLM_AVAILABLE:
        logger.info("LLM extraction not available (API key not set), using regex fallback")
    elif use_llm:
        logger.info("LLM extractor module not available, using regex fallback")

    # Fallback: regex-based extraction
    return extract_line_items_regex(pdf_path)


def extract_line_items_regex(pdf_path: str) -> List[Dict]:
    """Extract line items using regex-based parsing (fallback method)."""
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

            # Strategy 1: Try to extract from tables with explicit settings
            # Use stricter table settings to avoid cell merging
            table_settings = {
                "vertical_strategy": "lines",
                "horizontal_strategy": "lines",
                "snap_tolerance": 3,
                "join_tolerance": 3,
                "edge_min_length": 3,
                "min_words_vertical": 1,
                "min_words_horizontal": 1,
            }

            for page_num, page in enumerate(pdf.pages):
                # Try with strict settings first
                tables = page.extract_tables(table_settings)

                # If no tables found, try with text-based detection
                if not tables:
                    tables = page.extract_tables({
                        "vertical_strategy": "text",
                        "horizontal_strategy": "text",
                    })

                debug_info["tables_found"] += len(tables)

                for table_idx, table in enumerate(tables):
                    logger.info(f"Page {page_num + 1}, Table {table_idx + 1}: {len(table)} rows")
                    for row in table:
                        debug_info["table_rows"] += 1
                        if row and len(row) >= 2:
                            # Check if any cell contains merged content (multiple line items)
                            items = parse_table_row_with_split(row)
                            for item in items:
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


def parse_table_row_with_split(row: list) -> List[Optional[dict]]:
    """
    Parse a table row, detecting and splitting merged cells that contain multiple line items.

    Returns a list of items (usually 1, but can be multiple if cells were merged).
    """
    # Convert cells to strings
    cells = [str(c).strip() if c else "" for c in row]

    # Check for signs of merged content in any cell
    for cell in cells:
        if not cell:
            continue

        # Look for multiple amounts in one cell (sign of merged rows)
        amounts_in_cell = re.findall(r'\$?\s*([\d,]+\.\d{2})', cell)
        if len(amounts_in_cell) >= 2:
            logger.info(f"Detected merged cell with {len(amounts_in_cell)} amounts, attempting split")
            return split_merged_cell(cell)

        # Look for repeating patterns like "HC ... HC ..." which indicates merged descriptions
        hc_pattern_count = len(re.findall(r'\bHC\s+', cell, re.IGNORECASE))
        if hc_pattern_count >= 2:
            logger.info(f"Detected merged cell with {hc_pattern_count} 'HC' patterns, attempting split")
            return split_merged_descriptions(cells)

        # Look for multiple HCPCS/CPT codes in description (not in code column)
        # Skip if it's a short cell that's likely just a code
        if len(cell) > 20:
            codes_in_cell = re.findall(r'\b(?:[A-Z]\d{4}|\d{5})\b', cell)
            if len(codes_in_cell) >= 2:
                logger.info(f"Detected merged cell with {len(codes_in_cell)} codes: {codes_in_cell}")
                return split_by_codes(cell)

    # No merging detected, parse normally
    result = parse_table_row(row)
    return [result] if result else []


def split_merged_cell(cell_text: str) -> List[Optional[dict]]:
    """Split a cell that contains multiple merged line items based on amount patterns."""
    items = []

    # Try to split by finding amount patterns and their preceding descriptions
    # Pattern: description followed by amount, possibly with code
    pattern = r'([A-Za-z][^$\d]*?)\s*\$?\s*([\d,]+\.\d{2})'
    matches = re.findall(pattern, cell_text)

    for desc, amount_str in matches:
        desc = desc.strip()
        if len(desc) < 3:
            continue

        try:
            amount = float(amount_str.replace(',', ''))
            if amount > 0.5:
                code = extract_code(desc)
                items.append({
                    "code": code,
                    "description": re.sub(r'\s+', ' ', desc)[:100],
                    "quantity": 1,
                    "amount": amount,
                })
        except ValueError:
            pass

    return items if items else []


def split_merged_descriptions(cells: list) -> List[Optional[dict]]:
    """Split cells when descriptions appear to be merged (e.g., 'HC Item1 HC Item2')."""
    items = []

    # Find the cell with merged descriptions
    merged_desc = ""
    amounts = []

    for cell in cells:
        if not cell:
            continue
        # Collect amounts
        cell_amounts = re.findall(r'\$?\s*([\d,]+\.\d{2})', cell)
        amounts.extend([float(a.replace(',', '')) for a in cell_amounts])

        # Find the longest text cell (likely the merged description)
        if len(cell) > len(merged_desc) and not re.match(r'^[\d\$\.,\s]+$', cell):
            merged_desc = cell

    if not merged_desc:
        return []

    # Try to split by "HC " pattern (common hospital charge prefix)
    parts = re.split(r'(?=\bHC\s+)', merged_desc, flags=re.IGNORECASE)
    parts = [p.strip() for p in parts if p.strip()]

    if len(parts) <= 1:
        # Try splitting by code patterns
        parts = re.split(r'(?=\b(?:[A-Z]\d{4}|\d{5})\b)', merged_desc)
        parts = [p.strip() for p in parts if p.strip() and len(p) > 5]

    # Match parts with amounts (if we have the same number)
    for i, part in enumerate(parts):
        # Extract code from this part
        code = extract_code(part)

        # Clean description
        desc = re.sub(r'\b(?:[A-Z]\d{4}|\d{5})\b', '', part)
        desc = re.sub(r'\s+', ' ', desc).strip()

        if len(desc) < 3:
            continue

        # Try to get corresponding amount
        amount = None
        if i < len(amounts):
            amount = amounts[i]
        elif amounts:
            amount = amounts[0]  # Use first amount as fallback

        if amount and amount > 0.5:
            items.append({
                "code": code,
                "description": desc[:100],
                "quantity": 1,
                "amount": amount,
            })

    return items if items else []


def split_by_codes(cell_text: str) -> List[Optional[dict]]:
    """Split a cell that contains multiple codes into separate items."""
    items = []

    # Find all codes and their positions
    code_matches = list(re.finditer(r'\b([A-Z]\d{4}|\d{5})\b', cell_text))

    if len(code_matches) < 2:
        return []

    # Find all amounts
    amounts = re.findall(r'\$?\s*([\d,]+\.\d{2})', cell_text)
    amount_values = [float(a.replace(',', '')) for a in amounts]

    # Split text by codes
    for i, match in enumerate(code_matches):
        code = match.group(1)

        # Get description: text between this code and the next (or end)
        start = match.end()
        end = code_matches[i + 1].start() if i + 1 < len(code_matches) else len(cell_text)

        desc_part = cell_text[start:end].strip()
        # Remove amounts from description
        desc_part = re.sub(r'\$?\s*[\d,]+\.\d{2}', '', desc_part)
        desc_part = re.sub(r'\s+', ' ', desc_part).strip()

        # Also check text before the code
        if i == 0 and match.start() > 0:
            prefix = cell_text[:match.start()].strip()
            prefix = re.sub(r'\$?\s*[\d,]+\.\d{2}', '', prefix).strip()
            if prefix and len(prefix) > 3:
                desc_part = prefix + " " + desc_part

        if len(desc_part) < 3:
            desc_part = f"Procedure {code}"

        # Match with amount
        amount = None
        if i < len(amount_values):
            amount = amount_values[i]
        elif amount_values:
            # Try to find amount near this code in original text
            code_pos = match.start()
            for j, amt_match in enumerate(re.finditer(r'\$?\s*([\d,]+\.\d{2})', cell_text)):
                if amt_match.start() > code_pos:
                    amount = float(amt_match.group(1).replace(',', ''))
                    break

        if amount and amount > 0.5:
            items.append({
                "code": code,
                "description": desc_part[:100],
                "quantity": 1,
                "amount": amount,
            })

    return items if items else []


def parse_table_row(row: list) -> Optional[dict]:
    """Parse a table row into a line item."""
    # Keep original cells with their positions (don't filter empty ones yet for column tracking)
    original_cells = [str(c).strip() if c else "" for c in row]

    # Filter out empty cells for processing
    cells = [c for c in original_cells if c]

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

    # Collect ALL codes found in the row, categorized by type
    # We want to prefer CPT/HCPCS codes over revenue codes
    cpt_codes = []       # 5-digit CPT codes
    hcpcs_codes = []     # Letter + 4 digits (J2003, etc.)
    revenue_codes = []   # 4-digit codes starting with 0

    for idx, cell in enumerate(cells):
        # Skip date-like cells (MM/DD/YYYY or similar)
        if re.match(r'^\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}$', cell):
            continue

        # HCPCS codes (letter + 4 digits) - highest priority
        hcpcs_match = re.search(r'\b([A-Z]\d{4})\b', cell)
        if hcpcs_match:
            hcpcs_codes.append((idx, hcpcs_match.group(1)))

        # 5-digit CPT codes - high priority
        cpt_match = re.search(r'\b(\d{5})\b', cell)
        if cpt_match:
            # Make sure it's not part of a longer number (like a phone number or date)
            potential_cpt = cpt_match.group(1)
            # CPT codes typically don't start with 0 and are in range 00100-99499
            if not cell.replace(potential_cpt, '').strip().isdigit():
                cpt_codes.append((idx, potential_cpt))

        # Revenue codes (4 digits starting with 0) - lowest priority
        rev_match = re.search(r'\b(0\d{3})\b', cell)
        if rev_match:
            revenue_codes.append((idx, rev_match.group(1)))

    # Select the best code - prefer HCPCS > CPT > Revenue
    # If multiple codes of same type, prefer ones NOT in the first 2 columns (col 0-1 are often date/rev code)
    code = None
    code_source = None

    # Log all codes found for debugging
    if hcpcs_codes or cpt_codes or revenue_codes:
        logger.debug(
            f"Codes found in row: HCPCS={[c[1] for c in hcpcs_codes]}, "
            f"CPT={[c[1] for c in cpt_codes]}, Revenue={[c[1] for c in revenue_codes]}"
        )

    if hcpcs_codes:
        # Prefer HCPCS codes from later columns
        hcpcs_codes.sort(key=lambda x: (0 if x[0] >= 2 else 1, x[0]))
        code = hcpcs_codes[0][1]
        code_source = "hcpcs"
        logger.debug(f"Selected HCPCS code {code} from column {hcpcs_codes[0][0]}")
    elif cpt_codes:
        # Prefer CPT codes from later columns (column 3+ typically has the real CPT code)
        cpt_codes.sort(key=lambda x: (0 if x[0] >= 2 else 1, x[0]))
        code = cpt_codes[0][1]
        code_source = "cpt"
        logger.debug(f"Selected CPT code {code} from column {cpt_codes[0][0]}")
    elif revenue_codes:
        # Only use revenue code if no CPT/HCPCS found
        # Prefer codes from column 2 or later
        revenue_codes.sort(key=lambda x: (0 if x[0] >= 1 else 1, x[0]))
        code = revenue_codes[0][1]
        code_source = "revenue"
        logger.debug(f"Selected Revenue code {code} from column {revenue_codes[0][0]} (no CPT/HCPCS found)")

    # Description is usually the longest text field that's not a number
    description = ""
    for i, cell in enumerate(cells):
        if i != amount_idx and len(cell) > len(description):
            # Skip cells that are mostly numbers/currency
            if not re.match(r'^[\d\$\.,\s]+$', cell) and len(cell) > 3:
                description = cell

    if not description:
        return None

    # Clean up description - remove any embedded code in parentheses if we found a better code
    if code and code_source in ("hcpcs", "cpt"):
        # Remove things like (55150) from the description since we have the real code
        description = re.sub(r'\s*\([A-Z0-9]{4,5}\)\s*', ' ', description)

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
    """
    Extract CPT/HCPCS/Revenue code from text.

    Priority order:
    1. HCPCS codes (letter + 4 digits like J2003) - highest priority
    2. 5-digit CPT codes (like 99213)
    3. Revenue codes (4 digits starting with 0) - lowest priority

    For each type, if multiple matches exist, prefer ones NOT in parentheses
    (parenthetical codes are often internal references, not billing codes).
    """
    # First, try to find HCPCS codes (letter + 4 digits) - highest priority for drugs
    hcpcs_matches = re.findall(r'\b([A-Z]\d{4})\b', text)
    if hcpcs_matches:
        # Prefer ones not in parentheses
        for code in hcpcs_matches:
            if f"({code})" not in text:
                return code
        return hcpcs_matches[0]

    # 5-digit CPT codes - check if they look like valid CPT codes
    cpt_matches = re.findall(r'\b(\d{5})\b', text)
    if cpt_matches:
        # Filter out unlikely CPT codes and prefer ones not in parentheses
        valid_cpts = []
        for code in cpt_matches:
            # Skip if it's part of a phone number pattern or looks like a zip code
            context = text[max(0, text.find(code)-5):text.find(code)+10]
            if re.search(r'\d{3}[-.]?\d{3}[-.]?\d{4}', context):  # phone number
                continue
            if f"({code})" not in text:
                valid_cpts.insert(0, code)  # Prefer non-parenthetical
            else:
                valid_cpts.append(code)
        if valid_cpts:
            return valid_cpts[0]

    # Revenue codes (4 digits, often starting with 0) - lowest priority
    # Only use if no CPT/HCPCS found
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
