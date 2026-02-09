"""
CMS Data Service - Fetches real Medicare pricing data from CMS APIs.

Data Sources:
- Physician Fee Schedule: Medicare Physician & Other Practitioners dataset
- Outpatient Hospital: Medicare Outpatient Hospitals by Provider and Service
- Inpatient Hospital: Medicare Inpatient Hospitals by Provider and Service (DRG-based)

Caching: All data is cached for 24 hours to reduce API load and improve performance.
"""

import os
import json
import time
import logging
import hashlib
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

import httpx

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cache configuration
CACHE_DIR = Path("/tmp/billcheck_cache")
CACHE_EXPIRY_HOURS = 24

# CMS API base URL
CMS_DATA_API_BASE = "https://data.cms.gov/data-api/v1/dataset"

# Dataset IDs (these are the latest versions as of 2025)
DATASETS = {
    # Medicare Physician & Other Practitioners - by Provider and Service (2023 data)
    "physician_services": "92396110-2aed-4d63-a6a2-5d6207d46a29",
    # Medicare Outpatient Hospitals - by Provider and Service (2023 data)
    "outpatient_services": "ccbc9a44-40d4-46b4-a709-5caa59212e50",
    # Medicare Inpatient Hospitals - by Provider and Service (2023 data) - uses DRG codes
    "inpatient_services": "690ddc6c-2767-4618-b277-420ffb2bf27c",
    # Medicare Part B Spending by Drug - includes ASP pricing for J-codes, Q-codes, etc.
    "part_b_drugs": "76a714ad-3a2c-43ac-b76d-9dadf8f7d890",
}

# Code crosswalk for recently changed HCPCS codes
# Maps new codes to old codes that may still be in the dataset
CODE_CROSSWALK = {
    "J2003": "J2001",  # Lidocaine HCl injection (changed Oct 2024)
    "J2004": "J2001",  # Lidocaine with epinephrine
}

# Keywords that indicate specific medical categories
# Used for description matching to detect mismatched codes
DRUG_KEYWORDS = {
    'injection', 'infusion', 'vaccine', 'medication', 'drug', 'dose',
    'mg', 'ml', 'mcg', 'units', 'per', 'vial', 'tablet', 'capsule',
    'ketamine', 'lidocaine', 'morphine', 'fentanyl', 'propofol', 'antibiotic',
    'steroid', 'anesthetic', 'sedation', 'analgesic', 'saline', 'dextrose',
}

SURGERY_KEYWORDS = {
    'incision', 'excision', 'resection', 'repair', 'removal', 'insertion',
    'implant', 'graft', 'transplant', 'amputation', 'biopsy', 'drainage',
    'reconstruction', 'revision', 'exploration', 'dissection', 'suture',
}

BODY_PART_KEYWORDS = {
    'scrotum', 'scrotal', 'testis', 'testicle', 'penis', 'penile', 'prostate',
    'uterus', 'uterine', 'ovary', 'ovarian', 'vaginal', 'cervix', 'cervical',
    'breast', 'mammary', 'heart', 'cardiac', 'lung', 'pulmonary', 'liver',
    'hepatic', 'kidney', 'renal', 'brain', 'cerebral', 'spine', 'spinal',
    'knee', 'hip', 'shoulder', 'elbow', 'wrist', 'ankle', 'foot', 'hand',
}


def _normalize_text(text: str) -> set:
    """Normalize text to lowercase words for comparison."""
    if not text:
        return set()
    # Remove punctuation and split into words
    import re
    words = re.findall(r'[a-z]+', text.lower())
    return set(words)


def _calculate_description_match(bill_desc: str, cms_desc: str) -> dict:
    """
    Calculate how well a bill description matches a CMS description.

    Returns a dict with:
    - score: 0-100 confidence score
    - match_type: 'good', 'partial', 'mismatch', 'category_mismatch'
    - reason: explanation of the match result
    """
    if not bill_desc or not cms_desc:
        return {"score": 50, "match_type": "unknown", "reason": "Missing description"}

    bill_words = _normalize_text(bill_desc)
    cms_words = _normalize_text(cms_desc)

    if not bill_words or not cms_words:
        return {"score": 50, "match_type": "unknown", "reason": "Empty description after normalization"}

    # Check for category mismatches (e.g., drug vs surgery)
    bill_is_drug = bool(bill_words & DRUG_KEYWORDS)
    cms_is_drug = bool(cms_words & DRUG_KEYWORDS)
    bill_is_surgery = bool(bill_words & SURGERY_KEYWORDS)
    cms_is_surgery = bool(cms_words & SURGERY_KEYWORDS)

    # Major category mismatch: bill says drug but CMS says surgery (or vice versa)
    if bill_is_drug and cms_is_surgery and not cms_is_drug:
        return {
            "score": 10,
            "match_type": "category_mismatch",
            "reason": f"Bill describes a drug/medication but CMS code is for surgery"
        }
    if bill_is_surgery and cms_is_drug and not bill_is_drug:
        return {
            "score": 10,
            "match_type": "category_mismatch",
            "reason": f"Bill describes surgery but CMS code is for a drug"
        }

    # Check for body part mismatches in surgical codes
    bill_body_parts = bill_words & BODY_PART_KEYWORDS
    cms_body_parts = cms_words & BODY_PART_KEYWORDS

    if bill_body_parts and cms_body_parts and not (bill_body_parts & cms_body_parts):
        # Both mention body parts but they don't overlap
        return {
            "score": 15,
            "match_type": "category_mismatch",
            "reason": f"Body part mismatch: bill mentions {bill_body_parts}, CMS mentions {cms_body_parts}"
        }

    # Calculate word overlap
    common_words = bill_words & cms_words
    # Exclude very common words
    stopwords = {'the', 'a', 'an', 'of', 'for', 'to', 'in', 'on', 'with', 'and', 'or', 'per'}
    meaningful_common = common_words - stopwords
    meaningful_bill = bill_words - stopwords
    meaningful_cms = cms_words - stopwords

    if not meaningful_bill or not meaningful_cms:
        return {"score": 50, "match_type": "unknown", "reason": "No meaningful words to compare"}

    # Jaccard similarity on meaningful words
    union_size = len(meaningful_bill | meaningful_cms)
    overlap_score = len(meaningful_common) / union_size if union_size > 0 else 0

    # Convert to 0-100 scale
    score = int(overlap_score * 100)

    # Be permissive with matching - medical terminology varies widely between
    # billing systems and official CMS descriptions. Only reject clear mismatches.
    # Even a single common word (like "injection" or "visit") suggests relevance.
    if len(meaningful_common) >= 1 or score >= 15:
        if score >= 40:
            return {"score": score, "match_type": "good", "reason": f"Good word overlap ({len(meaningful_common)} common terms)"}
        else:
            return {"score": score, "match_type": "partial", "reason": f"Partial match ({len(meaningful_common)} common terms)"}
    else:
        return {"score": score, "match_type": "mismatch", "reason": f"No common terms found between descriptions"}


class CMSDataService:
    """Service for fetching and caching CMS Medicare pricing data."""

    def __init__(self):
        self.client = httpx.Client(timeout=30.0)
        self._ensure_cache_dir()

    def _ensure_cache_dir(self):
        """Create cache directory if it doesn't exist."""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, *args) -> str:
        """Generate a cache key from arguments."""
        key_str = ":".join(str(a) for a in args)
        return hashlib.md5(key_str.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get the file path for a cache key."""
        return CACHE_DIR / f"{cache_key}.json"

    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cache file exists and is not expired."""
        if not cache_path.exists():
            return False

        # Check if file is older than 24 hours
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        expiry_time = datetime.now() - timedelta(hours=CACHE_EXPIRY_HOURS)
        return mtime > expiry_time

    def _read_cache(self, cache_key: str) -> Optional[Any]:
        """Read data from cache if valid."""
        cache_path = self._get_cache_path(cache_key)
        if self._is_cache_valid(cache_path):
            try:
                with open(cache_path, "r") as f:
                    data = json.load(f)
                    logger.info(f"Cache hit for key: {cache_key[:8]}...")
                    return data
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to read cache: {e}")
        return None

    def _write_cache(self, cache_key: str, data: Any):
        """Write data to cache."""
        cache_path = self._get_cache_path(cache_key)
        try:
            with open(cache_path, "w") as f:
                json.dump(data, f)
            logger.info(f"Cached data with key: {cache_key[:8]}...")
        except IOError as e:
            logger.warning(f"Failed to write cache: {e}")

    def _fetch_from_cms(self, dataset_id: str, filters: Optional[Dict] = None,
                        size: int = 500, offset: int = 0) -> Optional[List[Dict]]:
        """
        Fetch data from CMS Data API.

        Args:
            dataset_id: The CMS dataset identifier (UUID format)
            filters: Optional filter conditions {field_name: value}
            size: Number of records to fetch (max 5000)
            offset: Starting offset for pagination

        Returns:
            List of records or None if request fails
        """
        # Build URL with query parameters
        params = {"size": min(size, 5000), "offset": offset}

        # Add filters using the CMS filter syntax
        if filters:
            for field, value in filters.items():
                params[f"filter[{field}]"] = value

        url = f"{CMS_DATA_API_BASE}/{dataset_id}/data?{urlencode(params)}"

        try:
            logger.info(f"Fetching from CMS: {url}")
            response = self.client.get(url)
            response.raise_for_status()
            data = response.json()
            logger.info(f"CMS API returned {len(data)} records")
            return data
        except httpx.HTTPError as e:
            logger.error(f"CMS API request failed: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse CMS response: {e}")
            return None

    def get_physician_fee_by_hcpcs(self, hcpcs_code: str) -> Optional[Dict]:
        """
        Get physician fee schedule data for a specific HCPCS/CPT code.

        Uses Medicare Physician & Other Practitioners dataset.
        Returns average payment amounts across providers.
        """
        cache_key = self._get_cache_key("pfs", hcpcs_code)
        cached = self._read_cache(cache_key)
        if cached is not None:
            return cached

        # Query CMS data - field name is HCPCS_Cd
        data = self._fetch_from_cms(
            DATASETS["physician_services"],
            filters={"HCPCS_Cd": hcpcs_code},
            size=500
        )

        if not data:
            return None

        # Aggregate the data
        result = self._aggregate_physician_data(hcpcs_code, data)

        if result:
            self._write_cache(cache_key, result)

        return result

    def _aggregate_physician_data(self, hcpcs_code: str, records: List[Dict]) -> Optional[Dict]:
        """Aggregate physician fee data from multiple providers."""
        if not records:
            return None

        # Extract payment amounts
        payments = []
        submitted_charges = []
        description = None

        for record in records:
            # Field names from CMS dataset
            payment = self._safe_float(record.get("Avg_Mdcr_Pymt_Amt"))
            charge = self._safe_float(record.get("Avg_Sbmtd_Chrg"))

            if payment and payment > 0:
                payments.append(payment)
            if charge and charge > 0:
                submitted_charges.append(charge)

            # Get description from first record that has one
            if not description:
                description = record.get("HCPCS_Desc")

        if not payments:
            return None

        # Calculate statistics
        payments.sort()
        charges_sorted = sorted(submitted_charges) if submitted_charges else []

        return {
            "hcpcs_code": hcpcs_code,
            "description": description or f"Service {hcpcs_code}",
            "medicare_payment": {
                "min": min(payments),
                "max": max(payments),
                "median": payments[len(payments) // 2],
                "average": sum(payments) / len(payments),
                "count": len(payments),
            },
            "submitted_charges": {
                "min": min(charges_sorted) if charges_sorted else None,
                "max": max(charges_sorted) if charges_sorted else None,
                "median": charges_sorted[len(charges_sorted) // 2] if charges_sorted else None,
                "average": sum(charges_sorted) / len(charges_sorted) if charges_sorted else None,
                "count": len(charges_sorted),
            } if charges_sorted else None,
            "data_source": "CMS Medicare Physician & Other Practitioners",
            "cached_at": datetime.now().isoformat(),
        }

    def get_outpatient_fee_by_apc(self, apc_code: str) -> Optional[Dict]:
        """
        Get outpatient facility fee data for a specific APC code.

        Uses Medicare Outpatient Hospitals dataset.
        Note: This uses APC codes, not HCPCS codes.
        """
        cache_key = self._get_cache_key("opps_apc", apc_code)
        cached = self._read_cache(cache_key)
        if cached is not None:
            return cached

        # Query CMS data - field name is APC_Cd
        data = self._fetch_from_cms(
            DATASETS["outpatient_services"],
            filters={"APC_Cd": apc_code},
            size=500
        )

        if not data:
            return None

        result = self._aggregate_outpatient_data(apc_code, data)

        if result:
            self._write_cache(cache_key, result)

        return result

    def _aggregate_outpatient_data(self, code: str, records: List[Dict]) -> Optional[Dict]:
        """Aggregate outpatient facility fee data."""
        if not records:
            return None

        payments = []
        charges = []
        description = None

        for record in records:
            payment = self._safe_float(record.get("Avg_Mdcr_Pymt_Amt"))
            charge = self._safe_float(record.get("Avg_Tot_Sbmtd_Chrgs"))

            if payment and payment > 0:
                payments.append(payment)
            if charge and charge > 0:
                charges.append(charge)

            if not description:
                description = record.get("APC_Desc")

        if not payments:
            return None

        payments.sort()
        charges_sorted = sorted(charges) if charges else []

        return {
            "code": code,
            "description": description or f"Service {code}",
            "facility_payment": {
                "min": min(payments),
                "max": max(payments),
                "median": payments[len(payments) // 2],
                "average": sum(payments) / len(payments),
                "count": len(payments),
            },
            "facility_charges": {
                "min": min(charges_sorted) if charges_sorted else None,
                "max": max(charges_sorted) if charges_sorted else None,
                "median": charges_sorted[len(charges_sorted) // 2] if charges_sorted else None,
                "average": sum(charges_sorted) / len(charges_sorted) if charges_sorted else None,
                "count": len(charges_sorted),
            } if charges_sorted else None,
            "data_source": "CMS Medicare Outpatient Hospitals",
            "cached_at": datetime.now().isoformat(),
        }

    def get_drug_pricing(self, hcpcs_code: str) -> Optional[Dict]:
        """
        Get drug pricing data for J-codes, Q-codes, and other drug HCPCS codes.

        Uses Medicare Part B Spending by Drug dataset which includes ASP pricing.
        """
        cache_key = self._get_cache_key("drug", hcpcs_code)
        cached = self._read_cache(cache_key)
        if cached is not None:
            return cached

        # Try the code directly first
        data = self._fetch_from_cms(
            DATASETS["part_b_drugs"],
            filters={"HCPCS_Cd": hcpcs_code},
            size=10
        )

        # If no data found, try crosswalk to older code
        if not data and hcpcs_code in CODE_CROSSWALK:
            old_code = CODE_CROSSWALK[hcpcs_code]
            logger.info(f"Code {hcpcs_code} not found, trying crosswalk to {old_code}")
            data = self._fetch_from_cms(
                DATASETS["part_b_drugs"],
                filters={"HCPCS_Cd": old_code},
                size=10
            )

        if not data:
            return None

        result = self._process_drug_data(hcpcs_code, data)

        if result:
            self._write_cache(cache_key, result)

        return result

    def _process_drug_data(self, hcpcs_code: str, records: List[Dict]) -> Optional[Dict]:
        """Process drug pricing data from Part B Drug Spending dataset."""
        if not records:
            return None

        # Use the first record (usually there's one per drug)
        record = records[0]

        asp_price = self._safe_float(record.get("Avg_DY23_ASP_Price"))
        avg_spending = self._safe_float(record.get("Avg_Spndng_Per_Dsg_Unt_2023"))

        if not asp_price and not avg_spending:
            return None

        return {
            "hcpcs_code": hcpcs_code,
            "original_code": record.get("HCPCS_Cd"),
            "description": record.get("HCPCS_Desc"),
            "brand_name": record.get("Brnd_Name"),
            "generic_name": record.get("Gnrc_Name"),
            "asp_price": asp_price,
            "avg_spending_per_unit": avg_spending,
            "total_claims_2023": self._safe_float(record.get("Tot_Clms_2023")),
            "total_beneficiaries_2023": self._safe_float(record.get("Tot_Benes_2023")),
            "data_source": "CMS Medicare Part B Drug Spending",
            "cached_at": datetime.now().isoformat(),
        }

    def _is_drug_code(self, hcpcs_code: str) -> bool:
        """Check if a code is likely a drug code (J, Q, or similar prefix)."""
        if not hcpcs_code:
            return False
        prefix = hcpcs_code[0].upper()
        # J-codes are drugs, Q-codes often include drugs/biologicals
        return prefix in ('J', 'Q')

    def get_combined_pricing(self, hcpcs_code: str, bill_description: str = None) -> Dict:
        """
        Get combined pricing for a code from all available sources.

        Args:
            hcpcs_code: The HCPCS/CPT code to look up
            bill_description: Optional description from the bill to validate against

        Returns physician fee, facility fee, and/or drug pricing depending on code type.
        Includes description match validation when bill_description is provided.
        """
        # Use a different cache key when we have a bill description to validate
        cache_suffix = "_validated" if bill_description else ""
        cache_key = self._get_cache_key(f"combined_v3{cache_suffix}", hcpcs_code)

        # Only use cache if we don't have a bill description to validate
        # (cached results might not have been validated against this specific description)
        if not bill_description:
            cached = self._read_cache(cache_key)
            if cached is not None:
                return cached

        physician_data = None
        drug_data = None
        description_match = None

        # Check if this is a drug code
        if self._is_drug_code(hcpcs_code):
            # For drug codes, query the Part B Drug Spending dataset
            drug_data = self.get_drug_pricing(hcpcs_code)
        else:
            # For non-drug codes, query the Physician Fee Schedule
            physician_data = self.get_physician_fee_by_hcpcs(hcpcs_code)

        # Validate description match if we have a bill description
        cms_description = None
        if physician_data:
            cms_description = physician_data.get("description")
        elif drug_data:
            cms_description = drug_data.get("description")

        if bill_description and cms_description:
            description_match = _calculate_description_match(bill_description, cms_description)

            # If there's a category mismatch, mark data as unreliable
            if description_match.get("match_type") == "category_mismatch":
                logger.warning(
                    f"Description mismatch for {hcpcs_code}: "
                    f"Bill='{bill_description}' vs CMS='{cms_description}'. "
                    f"Reason: {description_match.get('reason')}"
                )

        # Determine if data should be trusted
        has_reliable_data = False
        if physician_data is not None or drug_data is not None:
            if description_match is None:
                # No validation requested, trust the data
                has_reliable_data = True
            elif description_match.get("match_type") in ("good", "partial", "unknown"):
                # Match type indicates acceptable match - trust the data
                has_reliable_data = True
            else:
                # Category mismatch or no common terms - mark as unreliable
                logger.info(f"Marking CMS data for {hcpcs_code} as unreliable due to description mismatch")
                has_reliable_data = False

        result = {
            "hcpcs_code": hcpcs_code,
            "physician_fee": physician_data,
            "facility_fee": None,  # Would need APC code mapping
            "drug_pricing": drug_data,
            "has_data": physician_data is not None or drug_data is not None,
            "has_reliable_data": has_reliable_data,
            "description_match": description_match,
            "cached_at": datetime.now().isoformat(),
        }

        # Only cache if we have some data and didn't do validation
        # (validated results depend on the specific bill description)
        if result["has_data"] and not bill_description:
            self._write_cache(cache_key, result)

        return result

    def get_pricing_for_codes(self, code_description_pairs: List[tuple]) -> Dict[str, Dict]:
        """
        Batch fetch pricing for multiple HCPCS codes with description validation.

        Args:
            code_description_pairs: List of (code, description) tuples from the bill

        Returns a dictionary mapping code -> pricing data with match validation.
        """
        results = {}
        for item in code_description_pairs:
            # Handle both old format (just codes) and new format (code, description tuples)
            if isinstance(item, tuple):
                code, description = item
            else:
                code, description = item, None

            if code:
                # Skip revenue codes (typically 4 digits starting with 0)
                # These aren't in the HCPCS/CPT datasets
                if len(code) == 4 and code.startswith('0'):
                    logger.info(f"Skipping revenue code: {code}")
                    results[code] = {
                        "hcpcs_code": code,
                        "has_data": False,
                        "has_reliable_data": False,
                        "note": "Revenue code - not in HCPCS dataset"
                    }
                    continue

                results[code] = self.get_combined_pricing(code, description)

        return results

    def clear_cache(self):
        """Clear all cached data."""
        import shutil
        if CACHE_DIR.exists():
            shutil.rmtree(CACHE_DIR)
            self._ensure_cache_dir()
            logger.info("Cache cleared")

    def get_cache_stats(self) -> Dict:
        """Get cache statistics."""
        if not CACHE_DIR.exists():
            return {"files": 0, "size_bytes": 0}

        files = list(CACHE_DIR.glob("*.json"))
        total_size = sum(f.stat().st_size for f in files)

        valid_count = sum(1 for f in files if self._is_cache_valid(f))

        return {
            "total_files": len(files),
            "valid_files": valid_count,
            "expired_files": len(files) - valid_count,
            "size_bytes": total_size,
            "cache_dir": str(CACHE_DIR),
        }

    def _safe_float(self, value: Any) -> Optional[float]:
        """Safely convert a value to float."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def __del__(self):
        """Clean up HTTP client."""
        if hasattr(self, 'client'):
            self.client.close()


# Singleton instance
_cms_service: Optional[CMSDataService] = None


def get_cms_service() -> CMSDataService:
    """Get the singleton CMS data service instance."""
    global _cms_service
    if _cms_service is None:
        _cms_service = CMSDataService()
    return _cms_service
