from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from app.models.schemas import (
    CreditCardCreate, CreditCardResponse, CardLimitAndDebtUpdate,
    CreditCardStatementCreate, CreditCardStatementResponse,
    CreditCardAnalyticsResponse, LoanCreate, LoanResponse
)
from app.services import credit_service
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/credits", tags=["Credit Cards & Loans"])

# ==========================================
# Credit Cards
# ==========================================
@router.get("/cards", response_model=List[CreditCardResponse])
def list_credit_cards(user: dict = Depends(get_current_user)):
    return credit_service.get_all_credit_cards(user_id=user["id"])

@router.post("/cards", response_model=CreditCardResponse)
def create_card(card: CreditCardCreate, user: dict = Depends(get_current_user)):
    return credit_service.create_credit_card(card, user_id=user["id"])

@router.get("/cards/analytics", response_model=CreditCardAnalyticsResponse)
def get_card_analytics(user: dict = Depends(get_current_user)):
    return credit_service.get_credit_analytics(user_id=user["id"])

@router.put("/cards/{card_id}/limits-and-debts")
def update_card_limits_and_debts(
    card_id: int,
    payload: CardLimitAndDebtUpdate,
    user: dict = Depends(get_current_user)
):
    success = credit_service.update_card_limits_and_debts(card_id, payload, user_id=user["id"])
    if not success:
        raise HTTPException(status_code=404, detail="Kredi kartı bulunamadı")
    return {"success": True, "card_id": card_id, "updated": payload}

@router.put("/cards/{card_id}/debt")
def update_card_debt(
    card_id: int,
    new_debt: float,
    statement_debt: Optional[float] = None,
    user: dict = Depends(get_current_user)
):
    payload = CardLimitAndDebtUpdate(current_debt=new_debt, statement_debt=statement_debt)
    success = credit_service.update_card_limits_and_debts(card_id, payload, user_id=user["id"])
    if not success:
        raise HTTPException(status_code=404, detail="Kredi kartı bulunamadı")
    return {"success": True, "card_id": card_id, "new_debt": new_debt}

@router.delete("/cards/{card_id}")
def delete_credit_card(card_id: int, user: dict = Depends(get_current_user)):
    success = credit_service.delete_credit_card(card_id, user_id=user["id"])
    if not success:
        raise HTTPException(status_code=404, detail="Kredi kartı bulunamadı")
    return {"success": True, "deleted_id": card_id}

# ==========================================
# Credit Card Statements (Geçmiş Ekstreler)
# ==========================================
@router.get("/cards/{card_id}/statements", response_model=List[CreditCardStatementResponse])
def list_statements(card_id: int, user: dict = Depends(get_current_user)):
    return credit_service.get_card_statements(card_id, user_id=user["id"])

@router.post("/cards/{card_id}/statements", response_model=CreditCardStatementResponse)
def add_statement(
    card_id: int,
    stmt: CreditCardStatementCreate,
    user: dict = Depends(get_current_user)
):
    stmt.credit_card_id = card_id
    return credit_service.add_card_statement(stmt, user_id=user["id"])

@router.delete("/statements/{statement_id}")
def remove_statement(statement_id: int, user: dict = Depends(get_current_user)):
    success = credit_service.delete_statement(statement_id, user_id=user["id"])
    if not success:
        raise HTTPException(status_code=404, detail="Ekstre kaydı bulunamadı")
    return {"success": True, "deleted_id": statement_id}

# ==========================================
# Loans
# ==========================================
@router.get("/loans", response_model=List[LoanResponse])
def list_loans(user: dict = Depends(get_current_user)):
    return credit_service.get_all_loans(user_id=user["id"])

@router.post("/loans", response_model=LoanResponse)
def create_loan(loan: LoanCreate, user: dict = Depends(get_current_user)):
    return credit_service.create_loan(loan, user_id=user["id"])

@router.delete("/loans/{loan_id}")
def delete_loan(loan_id: int, user: dict = Depends(get_current_user)):
    success = credit_service.delete_loan(loan_id, user_id=user["id"])
    if not success:
        raise HTTPException(status_code=404, detail="Kredi taksiti bulunamadı")
    return {"success": True, "deleted_id": loan_id}
