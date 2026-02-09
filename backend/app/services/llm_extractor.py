"""
LLM-based PDF extraction using Claude's vision capabilities.

This module converts PDF pages to images and uses Claude to extract
structured line item data, which is more accurate than regex-based parsing.
"""

import os
import io
import json
import base64
import logging
from typing import List, Dict, Optional
import pdfplumber
from PIL import Image

logger = logging.getLogger(__name__)

# Check if anthropic is available
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logger.warning("anthropic package not installed, LLM extraction disabled")


EXTRACTION_PROMPT = """Analyze this hospital bill image and extract all line items (charges).

For each line item, extract:
1. **code**: The CPT, HCPCS, or revenue code (e.g., "99213", "J2001", "0450")
   - CPT codes are 5 digits (e.g., 99213, 88305)
   - HCPCS codes start with a letter + 4 digits (e.g., J2001, Q0162)
   - Revenue codes are 4 digits starting with 0 (e.g., 0450, 0300)
   - Prefer CPT/HCPCS codes over revenue codes when both are present
   - The code is typically in its own column, NOT in parentheses within the description

2. **description**: The service/item description (e.g., "Office visit, established patient")
   - This is usually the longest text in each row
   - Remove any codes that appear within the description

3. **quantity**: The quantity/units (default to 1 if not shown)

4. **amount**: The charge amount in dollars (e.g., 150.00)
   - Look for the rightmost dollar amount in each row (the charge/total column)
   - Ignore intermediate columns like "unit price" if there's also a "total" column

IMPORTANT:
- Each line item should be a SEPARATE entry - do not combine multiple services
- Skip header rows, totals, subtotals, payments, and adjustments
- Skip rows that don't have both a description AND an amount
- Be precise with the codes - they must match exactly what's shown

Return the data as a JSON array. Example format:
```json
[
  {"code": "99213", "description": "Office visit, established patient", "quantity": 1, "amount": 150.00},
  {"code": "85025", "description": "Complete blood count", "quantity": 1, "amount": 45.00},
  {"code": "J2001", "description": "Lidocaine injection", "quantity": 2, "amount": 12.50}
]
```

If no line items can be extracted, return an empty array: []

Extract ALL line items visible in this image:"""


def get_anthropic_client() -> Optional["anthropic.Anthropic"]:
    """Get an Anthropic client if API key is available."""
    if not ANTHROPIC_AVAILABLE:
        return None

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set, LLM extraction disabled")
        return None

    return anthropic.Anthropic(api_key=api_key)


def pdf_page_to_base64(page) -> str:
    """Convert a pdfplumber page to a base64-encoded PNG image."""
    # Render page to image (default is 72 DPI, we use higher for better text recognition)
    img = page.to_image(resolution=150)

    # Convert to PIL Image
    pil_image = img.original

    # Convert to RGB if necessary (some PDFs have RGBA or other modes)
    if pil_image.mode != "RGB":
        pil_image = pil_image.convert("RGB")

    # Save to bytes
    buffer = io.BytesIO()
    pil_image.save(buffer, format="PNG", optimize=True)
    buffer.seek(0)

    # Encode to base64
    return base64.standard_b64encode(buffer.read()).decode("utf-8")


def extract_with_llm(pdf_path: str) -> Optional[List[Dict]]:
    """
    Extract line items from a PDF using Claude's vision capabilities.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        List of line items if successful, None if LLM extraction is unavailable
    """
    client = get_anthropic_client()
    if not client:
        logger.info("LLM extraction not available, will use fallback")
        return None

    all_items = []
    seen_amounts = set()  # For deduplication across pages

    try:
        with pdfplumber.open(pdf_path) as pdf:
            logger.info(f"Processing {len(pdf.pages)} pages with LLM extraction")

            for page_num, page in enumerate(pdf.pages):
                logger.info(f"Processing page {page_num + 1}/{len(pdf.pages)}")

                # Convert page to base64 image
                try:
                    image_data = pdf_page_to_base64(page)
                except Exception as e:
                    logger.error(f"Failed to convert page {page_num + 1} to image: {e}")
                    continue

                # Call Claude API with vision
                try:
                    message = client.messages.create(
                        model="claude-sonnet-4-20250514",
                        max_tokens=4096,
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "image",
                                        "source": {
                                            "type": "base64",
                                            "media_type": "image/png",
                                            "data": image_data,
                                        },
                                    },
                                    {
                                        "type": "text",
                                        "text": EXTRACTION_PROMPT,
                                    },
                                ],
                            }
                        ],
                    )

                    # Parse the response
                    response_text = message.content[0].text

                    # Extract JSON from response (handle markdown code blocks)
                    json_str = response_text
                    if "```json" in response_text:
                        json_str = response_text.split("```json")[1].split("```")[0]
                    elif "```" in response_text:
                        json_str = response_text.split("```")[1].split("```")[0]

                    items = json.loads(json_str.strip())

                    if isinstance(items, list):
                        for item in items:
                            # Validate item structure
                            if not isinstance(item, dict):
                                continue
                            if "amount" not in item or "description" not in item:
                                continue

                            # Basic validation
                            try:
                                amount = float(item.get("amount", 0))
                                if amount <= 0:
                                    continue

                                # Deduplicate by amount (simple approach)
                                amount_key = round(amount, 2)
                                if amount_key in seen_amounts:
                                    continue
                                seen_amounts.add(amount_key)

                                all_items.append({
                                    "code": item.get("code"),
                                    "description": str(item.get("description", ""))[:100],
                                    "quantity": int(item.get("quantity", 1)),
                                    "amount": amount,
                                })
                            except (ValueError, TypeError):
                                continue

                        logger.info(f"Page {page_num + 1}: extracted {len(items)} items")

                except anthropic.APIError as e:
                    logger.error(f"Anthropic API error on page {page_num + 1}: {e}")
                    continue
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse LLM response on page {page_num + 1}: {e}")
                    logger.debug(f"Response was: {response_text[:500]}")
                    continue

    except Exception as e:
        logger.error(f"Error during LLM extraction: {e}", exc_info=True)
        return None

    if all_items:
        logger.info(f"LLM extraction complete: {len(all_items)} total items")
        # Sort by amount descending for consistency
        all_items.sort(key=lambda x: x["amount"], reverse=True)
        return all_items

    logger.info("LLM extraction returned no items")
    return None


def is_llm_extraction_available() -> bool:
    """Check if LLM extraction is available (API key set and package installed)."""
    if not ANTHROPIC_AVAILABLE:
        return False
    return bool(os.environ.get("ANTHROPIC_API_KEY"))
