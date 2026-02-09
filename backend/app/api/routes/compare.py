"""
Bill comparison route - compares line items against CMS pricing data.

Data Sources (in priority order):
1. Real CMS Medicare data (physician fees + facility fees)
2. Mock hospital data (fallback for demo/development)

All CMS data is cached for 24 hours.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.data.mock_data.hospitals import (
    get_hospital,
    get_price_for_code,
    get_regional_stats,
    get_all_prices_for_code,
)
from app.services.cms_data_service import get_cms_service

logger = logging.getLogger(__name__)

router = APIRouter()


class LineItemInput(BaseModel):
    code: Optional[str]
    description: str
    quantity: int
    amount: float


class CompareRequest(BaseModel):
    line_items: List[LineItemInput]
    hospital_id: str
    use_cms_data: bool = True  # Option to disable CMS queries


class RegionalStats(BaseModel):
    min: float
    max: float
    median: float
    average: float
    count: int


class CMSData(BaseModel):
    """CMS Medicare pricing data for a code."""
    medicare_avg_payment: Optional[float]
    medicare_min_payment: Optional[float]
    medicare_max_payment: Optional[float]
    avg_submitted_charge: Optional[float]
    facility_avg_payment: Optional[float]
    data_source: Optional[str]
    description: Optional[str]
    match_warning: Optional[str] = None  # Warning if description doesn't match bill


class PriceComparison(BaseModel):
    hospital_name: str
    gross_charge: float
    negotiated_rate: float


class LineItemComparison(BaseModel):
    code: Optional[str]
    description: str
    billed_amount: float
    quantity: int

    # CMS data (real Medicare data)
    cms_data: Optional[CMSData]

    # Mock hospital data (fallback)
    cms_description: Optional[str]
    hospital_gross_charge: Optional[float]
    hospital_negotiated_rate: Optional[float]
    regional_stats: Optional[RegionalStats]

    # Assessment
    status: str  # "fair", "high", "very_high", "low", "unknown"
    variance_percent: Optional[float]
    potential_savings: Optional[float]

    # Other hospital prices for this code
    other_hospitals: List[PriceComparison]


class CompareResponse(BaseModel):
    hospital_name: str
    hospital_id: str
    total_billed: float
    total_fair_value: Optional[float]
    total_potential_savings: Optional[float]
    overall_assessment: str
    line_items: List[LineItemComparison]
    data_sources: List[str]  # Which data sources were used


def assess_price_cms(billed: float, cms_data: Optional[dict]) -> tuple:
    """
    Assess price using CMS Medicare data.
    Returns (status, variance_percent, potential_savings, fair_price)
    """
    if not cms_data:
        return ("unknown", None, None, None)

    # Determine the best reference price from CMS data
    # Priority: drug ASP > facility payment > physician payment
    fair_price = None

    # Check drug pricing first (for J-codes, Q-codes)
    if cms_data.get("drug_pricing") and cms_data["drug_pricing"]:
        drug = cms_data["drug_pricing"]
        # ASP price is per unit - use avg_spending_per_unit as it's more comparable to billed amounts
        if drug.get("avg_spending_per_unit"):
            fair_price = drug["avg_spending_per_unit"]
        elif drug.get("asp_price"):
            fair_price = drug["asp_price"]

    if fair_price is None and cms_data.get("facility_fee") and cms_data["facility_fee"]:
        facility = cms_data["facility_fee"]
        if facility.get("facility_payment", {}).get("average"):
            fair_price = facility["facility_payment"]["average"]

    if fair_price is None and cms_data.get("physician_fee") and cms_data["physician_fee"]:
        physician = cms_data["physician_fee"]
        if physician.get("medicare_payment", {}).get("average"):
            fair_price = physician["medicare_payment"]["average"]

    if fair_price is None:
        return ("unknown", None, None, None)

    # Assess the price
    if billed <= fair_price:
        return ("low", round((billed - fair_price) / fair_price * 100, 1), 0, fair_price)
    elif billed <= fair_price * 1.5:  # Within 50%
        return ("fair", round((billed - fair_price) / fair_price * 100, 1), 0, fair_price)
    elif billed <= fair_price * 2.0:  # 50-100% above
        return ("high", round((billed - fair_price) / fair_price * 100, 1),
                round(billed - fair_price, 2), fair_price)
    else:  # More than 100% above
        return ("very_high", round((billed - fair_price) / fair_price * 100, 1),
                round(billed - fair_price, 2), fair_price)


def assess_price_mock(billed: float, gross_charge: Optional[float],
                      negotiated_rate: Optional[float]) -> tuple:
    """
    Assess price using mock hospital data.
    Returns (status, variance_percent, potential_savings, fair_price)
    """
    if gross_charge is None or negotiated_rate is None:
        return ("unknown", None, None, None)

    fair_price = negotiated_rate

    if billed <= fair_price:
        return ("low", round((billed - fair_price) / fair_price * 100, 1), 0, fair_price)
    elif billed <= fair_price * 1.2:  # Within 20%
        return ("fair", round((billed - fair_price) / fair_price * 100, 1), 0, fair_price)
    elif billed <= fair_price * 1.5:  # 20-50% above
        return ("high", round((billed - fair_price) / fair_price * 100, 1),
                round(billed - fair_price, 2), fair_price)
    else:  # More than 50% above
        return ("very_high", round((billed - fair_price) / fair_price * 100, 1),
                round(billed - fair_price, 2), fair_price)


def extract_cms_summary(cms_pricing: dict) -> Optional[CMSData]:
    """Extract a summary of CMS data for the response."""
    if not cms_pricing or not cms_pricing.get("has_data"):
        return None

    physician = cms_pricing.get("physician_fee")
    facility = cms_pricing.get("facility_fee")
    drug = cms_pricing.get("drug_pricing")
    description_match = cms_pricing.get("description_match")

    medicare_payment = None
    medicare_min = None
    medicare_max = None
    submitted_charge = None
    facility_payment = None
    description = None
    data_source = []
    match_warning = None

    # Check for description mismatch warning
    if description_match and not cms_pricing.get("has_reliable_data", True):
        match_warning = description_match.get("reason", "Description may not match billed service")

    # Check drug pricing first (for J-codes, Q-codes)
    if drug:
        # For drugs, use avg_spending_per_unit as the primary price
        medicare_payment = drug.get("avg_spending_per_unit") or drug.get("asp_price")
        # Drug datasets don't have min/max in the same way
        medicare_min = drug.get("asp_price")  # ASP is often the floor
        medicare_max = None
        description = drug.get("description")
        if drug.get("brand_name"):
            description = f"{description} ({drug.get('brand_name')})"
        data_source.append("Medicare Part B Drug Spending (ASP)")

    if physician:
        mp = physician.get("medicare_payment", {})
        if not medicare_payment:
            medicare_payment = mp.get("average")
        if not medicare_min:
            medicare_min = mp.get("min")
        if not medicare_max:
            medicare_max = mp.get("max")
        sc = physician.get("submitted_charges", {})
        if sc:
            submitted_charge = sc.get("average")
        if not description:
            description = physician.get("description")
        data_source.append("Medicare Physician Fee Schedule")

    if facility:
        fp = facility.get("facility_payment", {})
        facility_payment = fp.get("average")
        if not description:
            description = facility.get("description")
        data_source.append("Medicare Outpatient Hospital Data")

    if not medicare_payment and not facility_payment:
        return None

    return CMSData(
        medicare_avg_payment=medicare_payment,
        medicare_min_payment=medicare_min,
        medicare_max_payment=medicare_max,
        avg_submitted_charge=submitted_charge,
        facility_avg_payment=facility_payment,
        data_source=", ".join(data_source) if data_source else None,
        description=description,
        match_warning=match_warning,
    )


@router.post("/compare", response_model=CompareResponse)
async def compare_charges(request: CompareRequest):
    """
    Compare line items against CMS hospital price transparency data.

    Uses real CMS Medicare data when available, falls back to mock data.
    All CMS data is cached for 24 hours.
    """
    hospital = get_hospital(request.hospital_id)
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    # Collect code-description pairs for batch CMS lookup with validation
    code_desc_pairs = [
        (item.code, item.description)
        for item in request.line_items
        if item.code
    ]

    # Fetch CMS data for all codes with description validation
    cms_pricing_data = {}
    data_sources_used = set()

    if request.use_cms_data and code_desc_pairs:
        try:
            cms_service = get_cms_service()
            cms_pricing_data = cms_service.get_pricing_for_codes(code_desc_pairs)
            logger.info(f"Fetched CMS data for {len(cms_pricing_data)} codes")

            # Track which data sources were used (only count reliable matches)
            for code, data in cms_pricing_data.items():
                if data.get("has_reliable_data", data.get("has_data")):
                    if data.get("physician_fee"):
                        data_sources_used.add("CMS Medicare Physician Data")
                    if data.get("facility_fee"):
                        data_sources_used.add("CMS Medicare Outpatient Data")
                    if data.get("drug_pricing"):
                        data_sources_used.add("CMS Medicare Part B Drug Spending")
                elif data.get("has_data") and not data.get("has_reliable_data"):
                    # Log when we skip data due to description mismatch
                    match_info = data.get("description_match", {})
                    logger.info(
                        f"Skipped CMS data for {code} due to description mismatch: "
                        f"{match_info.get('reason', 'unknown')}"
                    )
        except Exception as e:
            logger.error(f"Failed to fetch CMS data: {e}")
            # Continue with mock data

    comparisons = []
    total_billed = 0
    total_fair_value = 0
    total_potential_savings = 0
    items_with_data = 0

    for item in request.line_items:
        total_billed += item.amount * item.quantity

        # Get CMS data if available
        cms_pricing = cms_pricing_data.get(item.code) if item.code else None
        cms_summary = extract_cms_summary(cms_pricing) if cms_pricing else None

        # Get mock data as fallback
        hospital_price = None
        regional = None
        other_hospitals = []

        if item.code:
            hospital_price = get_price_for_code(request.hospital_id, item.code)
            regional = get_regional_stats(item.code)

            # Get prices from other hospitals (mock data)
            all_prices = get_all_prices_for_code(item.code)
            for price_info in all_prices:
                if price_info["hospital"]["id"] != request.hospital_id:
                    other_hospitals.append(PriceComparison(
                        hospital_name=price_info["hospital"]["name"],
                        gross_charge=price_info["price"]["gross_charge"],
                        negotiated_rate=price_info["price"]["negotiated_rate"],
                    ))

        # Assess the price - prefer CMS data (only if reliable), fall back to mock
        fair_price = None
        # Use has_reliable_data to skip mismatched descriptions (e.g., drug billed as surgery code)
        if cms_pricing and cms_pricing.get("has_reliable_data", cms_pricing.get("has_data")):
            status, variance, savings, fair_price = assess_price_cms(item.amount, cms_pricing)
        elif hospital_price:
            gross_charge = hospital_price["gross_charge"]
            negotiated_rate = hospital_price["negotiated_rate"]
            status, variance, savings, fair_price = assess_price_mock(
                item.amount, gross_charge, negotiated_rate
            )
            data_sources_used.add("Hospital Mock Data")
        else:
            status, variance, savings = "unknown", None, None

        # Track fair values
        if fair_price is not None:
            items_with_data += 1
            total_fair_value += fair_price * item.quantity
            if savings:
                total_potential_savings += savings * item.quantity

        comparisons.append(LineItemComparison(
            code=item.code,
            description=item.description,
            billed_amount=item.amount,
            quantity=item.quantity,
            cms_data=cms_summary,
            cms_description=hospital_price["description"] if hospital_price else None,
            hospital_gross_charge=hospital_price["gross_charge"] if hospital_price else None,
            hospital_negotiated_rate=hospital_price["negotiated_rate"] if hospital_price else None,
            regional_stats=RegionalStats(**regional) if regional else None,
            status=status,
            variance_percent=variance,
            potential_savings=savings,
            other_hospitals=other_hospitals,
        ))

    # Overall assessment
    if items_with_data == 0:
        overall_assessment = "insufficient_data"
    elif total_potential_savings > total_billed * 0.3:
        overall_assessment = "significantly_overcharged"
    elif total_potential_savings > total_billed * 0.15:
        overall_assessment = "moderately_overcharged"
    elif total_potential_savings > 0:
        overall_assessment = "slightly_overcharged"
    else:
        overall_assessment = "fair"

    return CompareResponse(
        hospital_name=hospital["name"],
        hospital_id=request.hospital_id,
        total_billed=round(total_billed, 2),
        total_fair_value=round(total_fair_value, 2) if items_with_data > 0 else None,
        total_potential_savings=round(total_potential_savings, 2) if total_potential_savings > 0 else None,
        overall_assessment=overall_assessment,
        line_items=comparisons,
        data_sources=list(data_sources_used) if data_sources_used else ["No matching data found"],
    )


@router.get("/cache-stats")
async def get_cache_stats():
    """Get CMS data cache statistics."""
    try:
        cms_service = get_cms_service()
        return cms_service.get_cache_stats()
    except Exception as e:
        return {"error": str(e)}


@router.post("/clear-cache")
async def clear_cache():
    """Clear the CMS data cache."""
    try:
        cms_service = get_cms_service()
        cms_service.clear_cache()
        return {"status": "Cache cleared"}
    except Exception as e:
        return {"error": str(e)}
