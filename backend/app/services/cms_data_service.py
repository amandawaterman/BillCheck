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
}


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

    def get_combined_pricing(self, hcpcs_code: str) -> Dict:
        """
        Get combined physician and facility pricing for a code.

        Returns both professional (physician) and facility components.
        Note: Facility data requires APC code mapping which isn't always 1:1 with HCPCS.
        """
        cache_key = self._get_cache_key("combined", hcpcs_code)
        cached = self._read_cache(cache_key)
        if cached is not None:
            return cached

        # Get physician fee data (uses HCPCS codes directly)
        physician_data = self.get_physician_fee_by_hcpcs(hcpcs_code)

        # Note: Outpatient data uses APC codes, not HCPCS codes directly
        # For now, we'll only return physician data
        # A full implementation would need an HCPCS-to-APC crosswalk

        result = {
            "hcpcs_code": hcpcs_code,
            "physician_fee": physician_data,
            "facility_fee": None,  # Would need APC code mapping
            "has_data": physician_data is not None,
            "cached_at": datetime.now().isoformat(),
        }

        # Only cache if we have some data
        if result["has_data"]:
            self._write_cache(cache_key, result)

        return result

    def get_pricing_for_codes(self, hcpcs_codes: List[str]) -> Dict[str, Dict]:
        """
        Batch fetch pricing for multiple HCPCS codes.

        Returns a dictionary mapping code -> pricing data.
        """
        results = {}
        for code in hcpcs_codes:
            if code:
                # Skip revenue codes (typically 4 digits starting with 0)
                # These aren't in the HCPCS/CPT datasets
                if len(code) == 4 and code.startswith('0'):
                    logger.info(f"Skipping revenue code: {code}")
                    results[code] = {"hcpcs_code": code, "has_data": False, "note": "Revenue code - not in HCPCS dataset"}
                    continue

                results[code] = self.get_combined_pricing(code)

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
