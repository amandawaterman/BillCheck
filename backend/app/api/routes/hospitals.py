from typing import List, Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.data.mock_data.hospitals import search_hospitals, HOSPITALS, get_hospital

router = APIRouter()


class Hospital(BaseModel):
    id: str
    name: str
    address: str
    city: str
    state: str
    zip: str
    type: str


class HospitalListResponse(BaseModel):
    hospitals: List[Hospital]


@router.get("/hospitals", response_model=HospitalListResponse)
async def list_hospitals(search: Optional[str] = Query(None, description="Search query")):
    """Search hospitals or list all if no search query provided."""
    if search:
        results = search_hospitals(search)
    else:
        results = HOSPITALS

    return HospitalListResponse(hospitals=[Hospital(**h) for h in results])


@router.get("/hospitals/{hospital_id}", response_model=Hospital)
async def get_hospital_by_id(hospital_id: str):
    """Get a specific hospital by ID."""
    hospital = get_hospital(hospital_id)
    if not hospital:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Hospital not found")

    return Hospital(**hospital)
