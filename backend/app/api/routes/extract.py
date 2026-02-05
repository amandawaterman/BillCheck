import os
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.pdf_extractor import extract_bill_data
from app.data.mock_data.hospitals import get_hospital

router = APIRouter()

UPLOAD_DIR = "/tmp/billcheck_uploads"


class ExtractRequest(BaseModel):
    file_id: str


class LineItem(BaseModel):
    code: Optional[str]
    description: str
    quantity: int
    amount: float


class DetectedHospital(BaseModel):
    hospital_id: Optional[str]
    hospital_name: Optional[str]
    confidence: str
    detected_name: Optional[str] = None


class ExtractResponse(BaseModel):
    line_items: List[LineItem]
    detected_hospital: Optional[DetectedHospital] = None


@router.post("/extract", response_model=ExtractResponse)
async def extract_pdf(request: ExtractRequest):
    file_path = os.path.join(UPLOAD_DIR, f"{request.file_id}.pdf")

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    # Extract bill data including hospital detection
    bill_data = extract_bill_data(file_path)

    # Build response
    line_items = [LineItem(**item) for item in bill_data["line_items"]]

    detected_hospital = None
    if bill_data.get("detected_hospital"):
        hospital_info = bill_data["detected_hospital"]
        hospital_id = hospital_info.get("hospital_id")
        hospital_name = None

        # If we matched a hospital ID, get the full hospital name
        if hospital_id:
            hospital = get_hospital(hospital_id)
            if hospital:
                hospital_name = hospital["name"]

        detected_hospital = DetectedHospital(
            hospital_id=hospital_id,
            hospital_name=hospital_name,
            confidence=hospital_info.get("confidence", "low"),
            detected_name=hospital_info.get("detected_name"),
        )

    return ExtractResponse(
        line_items=line_items,
        detected_hospital=detected_hospital,
    )
