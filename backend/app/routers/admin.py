from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from app.database import get_db
from app.models.schemas import (
    AdminOverviewResponse, AdminUserSummary, AdminUserDetail,
    AccountResponse, CreditCardResponse, LoanResponse, TransactionResponse
)
from app.services import account_service, credit_service, transaction_service
from app.routers.auth import get_current_admin

router = APIRouter(prefix="/api/admin", tags=["Super Admin Panel"])

@router.get("/overview", response_model=AdminOverviewResponse)
def get_admin_overview(admin: dict = Depends(get_current_admin)):
    with get_db() as conn:
        cursor = conn.cursor()

        # Total Users
        cursor.execute("SELECT COUNT(*) as cnt FROM users")
        total_users = int(cursor.fetchone()["cnt"] or 0)

        # Accounts & Total Assets
        cursor.execute("SELECT COUNT(*) as cnt, COALESCE(SUM(balance * exchange_rate), 0.0) as total_assets FROM accounts")
        acc_row = cursor.fetchone()
        total_accounts = int(acc_row["cnt"] or 0)
        total_assets = float(acc_row["total_assets"] or 0.0)

        # Credit Cards & Debts
        cursor.execute("""
            SELECT COUNT(*) as cnt, 
                   COALESCE(SUM(current_debt + statement_debt + installment_debt), 0.0) as card_debt
            FROM credit_cards
        """)
        card_row = cursor.fetchone()
        total_cards = int(card_row["cnt"] or 0)
        card_debt = float(card_row["card_debt"] or 0.0)

        # Loans & Debts
        cursor.execute("""
            SELECT COUNT(*) as cnt,
                   COALESCE(SUM(monthly_installment * remaining_installments), 0.0) as loan_debt
            FROM loans
        """)
        loan_row = cursor.fetchone()
        total_loans = int(loan_row["cnt"] or 0)
        loan_debt = float(loan_row["loan_debt"] or 0.0)

        total_system_net_worth = total_assets - (card_debt + loan_debt)

        return AdminOverviewResponse(
            total_users=total_users,
            total_accounts=total_accounts,
            total_cards=total_cards,
            total_loans=total_loans,
            total_system_assets_try=round(total_assets, 2),
            total_system_card_debt_try=round(card_debt, 2),
            total_system_loan_debt_try=round(loan_debt, 2),
            total_system_net_worth_try=round(total_system_net_worth, 2),
            mssql_status="Microsoft SQL Server 2022 (SmartFinanceDB) Aktif"
        )

@router.get("/users", response_model=List[AdminUserSummary])
def get_all_users_summary(admin: dict = Depends(get_current_admin)):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, full_name, is_admin, created_at FROM users ORDER BY is_admin DESC, id ASC")
        users = cursor.fetchall()

        summaries = []
        for u in users:
            uid = u["id"]
            nw = account_service.get_net_worth_summary(user_id=uid)
            accs = account_service.get_all_accounts(user_id=uid)
            cards = credit_service.get_all_credit_cards(user_id=uid)
            loans = credit_service.get_all_loans(user_id=uid)

            total_assets = nw.total_liquid_cash_try + nw.total_investment_try
            total_debt = nw.total_liabilities_try

            summaries.append(AdminUserSummary(
                id=uid,
                email=u["email"],
                full_name=u["full_name"],
                is_admin=bool(u["is_admin"]),
                created_at=str(u["created_at"]) if u.get("created_at") else None,
                accounts_count=len(accs),
                cards_count=len(cards),
                loans_count=len(loans),
                total_assets_try=round(total_assets, 2),
                total_debt_try=round(total_debt, 2),
                net_worth_try=round(nw.total_net_worth_try, 2)
            ))
        return summaries

@router.get("/users/{user_id}", response_model=AdminUserDetail)
def get_user_detail(user_id: int, admin: dict = Depends(get_current_admin)):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, full_name, is_admin, created_at FROM users WHERE id = ?", (user_id,))
        u = cursor.fetchone()
        if not u:
            raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")

        nw = account_service.get_net_worth_summary(user_id=user_id)
        accs = account_service.get_all_accounts(user_id=user_id)
        cards = credit_service.get_all_credit_cards(user_id=user_id)
        loans = credit_service.get_all_loans(user_id=user_id)
        txs = transaction_service.get_transactions(limit=50, user_id=user_id)

        user_summary = AdminUserSummary(
            id=u["id"],
            email=u["email"],
            full_name=u["full_name"],
            is_admin=bool(u["is_admin"]),
            created_at=str(u["created_at"]) if u.get("created_at") else None,
            accounts_count=len(accs),
            cards_count=len(cards),
            loans_count=len(loans),
            total_assets_try=round(nw.total_liquid_cash_try + nw.total_investment_try, 2),
            total_debt_try=round(nw.total_liabilities_try, 2),
            net_worth_try=round(nw.total_net_worth_try, 2)
        )

        return AdminUserDetail(
            user=user_summary,
            accounts=accs,
            credit_cards=cards,
            loans=loans,
            transactions=txs
        )

@router.delete("/users/{user_id}")
def delete_user_account(user_id: int, admin: dict = Depends(get_current_admin)):
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="Kendi yönetici hesabınızı silemezsiniz.")

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
        return {"success": True, "deleted_user_id": user_id}
