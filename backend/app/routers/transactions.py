from fastapi import APIRouter, Query, HTTPException, Depends
from typing import List, Optional
from app.models.schemas import (
    TransactionCreate, TransactionResponse,
    RecurringItemCreate, RecurringItemResponse,
    NLPExtractRequest, NLPExtractResponse
)
from app.services import transaction_service, nlp_parser
from app.config import CATEGORIES
from app.routers.auth import get_current_user, get_current_user_optional

router = APIRouter(prefix="/api/transactions", tags=["Transactions & Expenses"])

@router.get("", response_model=List[TransactionResponse])
def list_transactions(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    trans_type: Optional[str] = None,
    category: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    return transaction_service.get_transactions(
        limit=limit, offset=offset, trans_type=trans_type, category=category, user_id=user["id"]
    )

@router.post("", response_model=TransactionResponse)
def add_transaction(trans: TransactionCreate, user: dict = Depends(get_current_user)):
    return transaction_service.create_transaction(trans, user_id=user["id"])

@router.get("/categories")
def get_categories():
    return CATEGORIES

@router.get("/recurring", response_model=List[RecurringItemResponse])
def list_recurring_items(user: dict = Depends(get_current_user)):
    return transaction_service.get_recurring_items(user_id=user["id"])

@router.post("/recurring", response_model=RecurringItemResponse)
def add_recurring_item(item: RecurringItemCreate, user: dict = Depends(get_current_user)):
    return transaction_service.create_recurring_item(item, user_id=user["id"])

@router.get("/monthly-comparison")
def get_monthly_comparison(user: dict = Depends(get_current_user)):
    return transaction_service.get_monthly_category_comparison(user_id=user["id"])

@router.delete("/{transaction_id}")
def delete_transaction_item(transaction_id: int, user: dict = Depends(get_current_user)):
    success = transaction_service.delete_transaction(transaction_id, user_id=user["id"])
    if not success:
        raise HTTPException(status_code=404, detail="İşlem kaydı bulunamadı")
    return {"success": True, "deleted_id": transaction_id}

@router.delete("/recurring/{item_id}")
def delete_recurring_rule(item_id: int, user: dict = Depends(get_current_user)):
    success = transaction_service.delete_recurring_item(item_id, user_id=user["id"])
    if not success:
        raise HTTPException(status_code=404, detail="Düzenli işlem kuralı bulunamadı")
    return {"success": True, "deleted_id": item_id}

@router.post("/nlp-parse", response_model=NLPExtractResponse)
def parse_natural_language_transaction(payload: NLPExtractRequest, user: Optional[dict] = Depends(get_current_user_optional)):
    if not payload.text or not payload.text.strip():
        raise HTTPException(status_code=400, detail="Metin boş olamaz")
    user_id = user["id"] if user else None
    return nlp_parser.process_nlp_and_save(payload.text, auto_save=payload.auto_save, user_id=user_id)
