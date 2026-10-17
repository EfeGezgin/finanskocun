from fastapi import APIRouter, Depends
from app.models.schemas import SpendingPsychologyResponse, PersonalInflationResponse, WhatIfRequest, WhatIfResponse
from app.services.psychology_service import analyze_spending_psychology
from app.services.inflation_service import calculate_personal_inflation
from app.services.what_if_service import simulate_what_if_scenario
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/analytics", tags=["Advanced Analytics & What-If"])

@router.get("/psychology", response_model=SpendingPsychologyResponse)
def get_spending_psychology(current_user = Depends(get_current_user)):
    return analyze_spending_psychology(user_id=current_user["id"])

@router.get("/personal-inflation", response_model=PersonalInflationResponse)
def get_personal_inflation(current_user = Depends(get_current_user)):
    return calculate_personal_inflation(user_id=current_user["id"])

@router.post("/what-if", response_model=WhatIfResponse)
def run_what_if_scenario(req: WhatIfRequest, current_user = Depends(get_current_user)):
    return simulate_what_if_scenario(user_id=current_user["id"], req=req)
