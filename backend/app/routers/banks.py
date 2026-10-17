from fastapi import APIRouter
from typing import List
from app.models.schemas import BankInfo
from app.config import TURKISH_BANKS

router = APIRouter(prefix="/api/banks", tags=["Turkish Banks Catalog"])

@router.get("", response_model=List[BankInfo])
def list_banks():
    """Returns the comprehensive catalog of all Turkish banks."""
    return TURKISH_BANKS
