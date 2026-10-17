from typing import List, Dict, Any, Optional
from app.database import get_db
from app.models.schemas import AccountCreate, AccountResponse, NetWorthResponse

def get_all_accounts(user_id: Optional[int] = None) -> List[AccountResponse]:
    if not user_id:
        return []
        
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM accounts 
            WHERE user_id = ? 
            ORDER BY is_active_cash DESC, (balance * exchange_rate) DESC
        """, (user_id,))
        rows = cursor.fetchall()

        result = []
        for r in rows:
            bal_try = round(float(r["balance"]) * float(r["exchange_rate"]), 2)
            result.append(AccountResponse(
                id=r["id"],
                user_id=r["user_id"],
                name=r["name"],
                type=r["type"],
                currency=r["currency"],
                balance=float(r["balance"]),
                exchange_rate=float(r["exchange_rate"]),
                is_active_cash=1 if r["is_active_cash"] else 0,
                bank_name=r["bank_name"],
                bank_code=r.get("bank_code"),
                account_number=r.get("account_number"),
                color=r.get("color") or "#10b981",
                icon=r.get("icon") or "wallet",
                updated_at=str(r["updated_at"]) if r.get("updated_at") else None,
                balance_try=bal_try
            ))
        return result

def create_account(account: AccountCreate, user_id: Optional[int] = None) -> AccountResponse:
    if not user_id:
        raise ValueError("Kullanıcı oturumu zorunludur.")
        
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO accounts (user_id, name, type, currency, balance, exchange_rate, is_active_cash, bank_name, bank_code, account_number, color, icon)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, account.name, account.type, account.currency, account.balance,
            account.exchange_rate, 1 if account.is_active_cash else 0, account.bank_name,
            account.bank_code, account.account_number, account.color, account.icon
        ))
        row = cursor.fetchone()
        acc_id = row["id"] if isinstance(row, dict) else row[0]

        cursor.execute("SELECT * FROM accounts WHERE id = ? AND user_id = ?", (acc_id, user_id))
        r = cursor.fetchone()
        return AccountResponse(
            id=r["id"],
            user_id=r["user_id"],
            name=r["name"],
            type=r["type"],
            currency=r["currency"],
            balance=float(r["balance"]),
            exchange_rate=float(r["exchange_rate"]),
            is_active_cash=1 if r["is_active_cash"] else 0,
            bank_name=r["bank_name"],
            bank_code=r.get("bank_code"),
            account_number=r.get("account_number"),
            color=r.get("color"),
            icon=r.get("icon"),
            updated_at=str(r["updated_at"]) if r.get("updated_at") else None,
            balance_try=round(float(r["balance"]) * float(r["exchange_rate"]), 2)
        )

def update_account_balance(account_id: int, new_balance: float, user_id: Optional[int] = None) -> bool:
    if not user_id:
        return False
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE accounts 
            SET balance = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ? AND user_id = ?
        """, (new_balance, account_id, user_id))
        return cursor.rowcount > 0

def delete_account(account_id: int, user_id: Optional[int] = None) -> bool:
    if not user_id:
        return False
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM accounts WHERE id = ? AND user_id = ?", (account_id, user_id))
        return cursor.rowcount > 0

def get_net_worth_summary(user_id: Optional[int] = None) -> NetWorthResponse:
    if not user_id:
        return NetWorthResponse(
            total_net_worth_try=0.0,
            total_liquid_cash_try=0.0,
            total_investment_try=0.0,
            total_credit_debt_try=0.0,
            total_loan_debt_try=0.0,
            total_liabilities_try=0.0,
            accounts_by_type={}
        )

    with get_db() as conn:
        cursor = conn.cursor()

        # 1. Accounts
        cursor.execute("SELECT type, balance, exchange_rate, is_active_cash FROM accounts WHERE user_id = ?", (user_id,))
        accounts = cursor.fetchall()

        liquid_cash = 0.0
        investments = 0.0
        by_type: Dict[str, float] = {}

        for acc in accounts:
            val_try = float(acc["balance"]) * float(acc["exchange_rate"])
            t = acc["type"]
            by_type[t] = round(by_type.get(t, 0.0) + val_try, 2)

            if acc["is_active_cash"]:
                liquid_cash += val_try
            else:
                investments += val_try

        # 2. Credit Cards Total Debt
        cursor.execute("""
            SELECT (COALESCE(SUM(current_debt), 0.0) + COALESCE(SUM(statement_debt), 0.0) + COALESCE(SUM(installment_debt), 0.0)) as base_debt
            FROM credit_cards WHERE user_id = ?
        """, (user_id,))
        base_debt = float(cursor.fetchone()["base_debt"] or 0.0)

        cursor.execute("""
            SELECT COALESCE(SUM(remaining_debt), 0.0) as past_debt
            FROM credit_card_statements WHERE user_id = ? AND status != 'paid'
        """, (user_id,))
        past_debt = float(cursor.fetchone()["past_debt"] or 0.0)
        credit_debt = round(base_debt + past_debt, 2)

        # 3. Loans Remaining Principal
        cursor.execute("""
            SELECT COALESCE(SUM(monthly_installment * remaining_installments), 0.0) as total_loans 
            FROM loans WHERE user_id = ?
        """, (user_id,))
        loan_debt = float(cursor.fetchone()["total_loans"] or 0.0)

        total_liabilities = credit_debt + loan_debt
        total_assets = liquid_cash + investments
        net_worth = total_assets - total_liabilities

        return NetWorthResponse(
            total_net_worth_try=round(net_worth, 2),
            total_liquid_cash_try=round(liquid_cash, 2),
            total_investment_try=round(investments, 2),
            total_credit_debt_try=round(credit_debt, 2),
            total_loan_debt_try=round(loan_debt, 2),
            total_liabilities_try=round(total_liabilities, 2),
            accounts_by_type=by_type
        )
