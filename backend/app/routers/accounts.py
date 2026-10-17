from fastapi import APIRouter, HTTPException, Depends
from typing import List
from app.models.schemas import AccountCreate, AccountResponse, NetWorthResponse
from app.services import account_service
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/accounts", tags=["Accounts & Net Worth"])

@router.get("", response_model=List[AccountResponse])
def list_accounts(user: dict = Depends(get_current_user)):
    return account_service.get_all_accounts(user_id=user["id"])

@router.post("", response_model=AccountResponse)
def create_new_account(account: AccountCreate, user: dict = Depends(get_current_user)):
    return account_service.create_account(account, user_id=user["id"])

@router.put("/{account_id}/balance")
def update_balance(account_id: int, new_balance: float, user: dict = Depends(get_current_user)):
    success = account_service.update_account_balance(account_id, new_balance, user_id=user["id"])
    if not success:
        raise HTTPException(status_code=404, detail="Hesap bulunamadı")
    return {"success": True, "account_id": account_id, "new_balance": new_balance}

@router.delete("/{account_id}")
def delete_account_item(account_id: int, user: dict = Depends(get_current_user)):
    success = account_service.delete_account(account_id, user_id=user["id"])
    if not success:
        raise HTTPException(status_code=404, detail="Hesap bulunamadı")
    return {"success": True, "deleted_id": account_id}

@router.get("/net-worth", response_model=NetWorthResponse)
def get_net_worth(user: dict = Depends(get_current_user)):
    return account_service.get_net_worth_summary(user_id=user["id"])
