from fastapi import APIRouter, Query, Depends
from typing import Optional
from app.models.schemas import CashFlowSimulationResponse
from app.services import simulation_engine
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/simulation", tags=["Cash Flow Simulation"])

@router.get("", response_model=CashFlowSimulationResponse)
def get_simulation(
    custom_daily_spend: Optional[float] = Query(None, description="Override average daily spend for what-if simulation"),
    extra_expense: float = Query(0.0, description="Hypothetical one-time expense to simulate impact"),
    extra_income: float = Query(0.0, description="Hypothetical one-time income to simulate impact"),
    user: dict = Depends(get_current_user)
):
    return simulation_engine.run_cash_flow_simulation(
        custom_daily_spend=custom_daily_spend,
        extra_one_time_expense=extra_expense,
        extra_one_time_income=extra_income,
        user_id=user["id"]
    )
