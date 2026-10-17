from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from app.models.schemas import CategoryBudgetCreate, CategoryBudgetResponse
from app.services.budget_service import get_category_budgets, set_category_budget, delete_category_budget
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/budgets", tags=["Category Budgets"])

@router.get("", response_model=List[CategoryBudgetResponse])
def read_category_budgets(current_user = Depends(get_current_user)):
    return get_category_budgets(user_id=current_user["id"])

@router.post("", response_model=CategoryBudgetResponse)
def upsert_category_budget(budget: CategoryBudgetCreate, current_user = Depends(get_current_user)):
    try:
        return set_category_budget(user_id=current_user["id"], budget_data=budget)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/{budget_id}")
def remove_category_budget(budget_id: int, current_user = Depends(get_current_user)):
    success = delete_category_budget(user_id=current_user["id"], budget_id=budget_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bütçe limiti bulunamadı.")
    return {"status": "success", "message": "Bütçe limiti silindi."}
