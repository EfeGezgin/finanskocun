from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime, date, timedelta
try:
    from dateutil.relativedelta import relativedelta
except ImportError:
    def relativedelta(months=0, days=0):
        return timedelta(days=int(months * 30.4375) + days)
from app.database import get_db
from app.models.schemas import (
    CreditCardCreate, CreditCardResponse, CardLimitAndDebtUpdate,
    CreditCardStatementCreate, CreditCardStatementResponse,
    CreditCardAnalyticsResponse, LoanCreate, LoanResponse
)

MONTHS_TR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]

def calculate_target_date_info(day_of_month: int) -> Tuple[int, str]:
    today = date.today()
    target_day = min(day_of_month, 28)
    try:
        target_date = date(today.year, today.month, target_day)
    except ValueError:
        target_date = date(today.year, today.month, 28)

    if target_date < today:
        if today.month == 12:
            target_date = date(today.year + 1, 1, target_day)
        else:
            target_date = date(today.year, today.month + 1, target_day)

    days_rem = (target_date - today).days
    formatted_str = f"{target_date.day} {MONTHS_TR[target_date.month - 1]} {target_date.year}"
    return days_rem, formatted_str

# ==========================================
# CREDIT CARDS
# ==========================================
def get_all_credit_cards(user_id: Optional[int] = None) -> List[CreditCardResponse]:
    if not user_id:
        return []

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM credit_cards WHERE user_id = ? ORDER BY current_debt DESC", (user_id,))
        rows = cursor.fetchall()

        cards = []
        for r in rows:
            limit = float(r["total_limit"] or 0.0)
            curr_debt = float(r["current_debt"] or 0.0)
            stmt_debt = float(r.get("statement_debt") or 0.0)
            inst_debt = float(r.get("installment_debt") or 0.0)
            rate = float(r.get("interest_rate") or 4.25)

            # Sum past unpaid statement debts strictly for this user & card
            cursor.execute("""
                SELECT COALESCE(SUM(remaining_debt), 0.0) as unpaid_past
                FROM credit_card_statements
                WHERE credit_card_id = ? AND user_id = ? AND status != 'paid'
            """, (r["id"], user_id))
            past_unpaid = float(cursor.fetchone()["unpaid_past"] or 0.0)

            total_debt_load = round(stmt_debt + curr_debt + inst_debt + past_unpaid, 2)
            avail = max(0.0, limit - total_debt_load)
            util = round((total_debt_load / limit * 100.0) if limit > 0 else 0.0, 1)

            effective_for_min = stmt_debt if stmt_debt > 0 else (curr_debt + past_unpaid)
            min_pay = round(effective_for_min * float(r.get("min_payment_rate") or 0.20), 2)

            days_due, due_date_str = calculate_target_date_info(r["due_day"])
            days_cutoff, cutoff_date_str = calculate_target_date_info(r["cutoff_day"])

            if days_due <= 3:
                urgency = "due_urgent"
            elif days_due <= 7:
                urgency = "due_soon"
            else:
                urgency = "normal"

            cards.append(CreditCardResponse(
                id=r["id"],
                user_id=r["user_id"],
                bank_name=r["bank_name"],
                bank_code=r.get("bank_code"),
                card_name=r["card_name"],
                total_limit=limit,
                current_debt=curr_debt,
                statement_debt=stmt_debt,
                installment_debt=inst_debt,
                cutoff_day=r["cutoff_day"],
                due_day=r["due_day"],
                min_payment_rate=float(r.get("min_payment_rate") or 0.20),
                interest_rate=rate,
                color=r.get("color") or "#6366f1",
                total_debt_load=total_debt_load,
                available_limit=round(avail, 2),
                utilization_rate=util,
                min_payment_amount=min_pay,
                days_until_due=days_due,
                days_until_cutoff=days_cutoff,
                due_date_str=due_date_str,
                cutoff_date_str=cutoff_date_str,
                urgency_level=urgency,
                unpaid_past_statements_total=round(past_unpaid, 2),
                created_at=str(r["created_at"]) if r.get("created_at") else None
            ))
        return cards

def create_credit_card(card: CreditCardCreate, user_id: Optional[int] = None) -> CreditCardResponse:
    if not user_id:
        raise ValueError("Kullanıcı oturumu zorunludur.")

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO credit_cards (user_id, bank_name, bank_code, card_name, total_limit, current_debt, statement_debt, installment_debt, cutoff_day, due_day, min_payment_rate, interest_rate, color)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, card.bank_name, card.bank_code, card.card_name, card.total_limit,
            card.current_debt, card.statement_debt, card.installment_debt,
            card.cutoff_day, card.due_day, card.min_payment_rate, card.interest_rate, card.color
        ))
        row = cursor.fetchone()
        card_id = row["id"] if isinstance(row, dict) else row[0]

        cursor.execute("SELECT * FROM credit_cards WHERE id = ? AND user_id = ?", (card_id, user_id))
        r = cursor.fetchone()

        limit = float(r["total_limit"])
        curr_debt = float(r["current_debt"])
        stmt_debt = float(r.get("statement_debt") or 0.0)
        inst_debt = float(r.get("installment_debt") or 0.0)
        total_debt_load = round(stmt_debt + curr_debt + inst_debt, 2)

        days_due, due_date_str = calculate_target_date_info(r["due_day"])
        days_cutoff, cutoff_date_str = calculate_target_date_info(r["cutoff_day"])
        urgency = "due_urgent" if days_due <= 3 else "due_soon" if days_due <= 7 else "normal"

        return CreditCardResponse(
            id=r["id"],
            user_id=r["user_id"],
            bank_name=r["bank_name"],
            bank_code=r.get("bank_code"),
            card_name=r["card_name"],
            total_limit=limit,
            current_debt=curr_debt,
            statement_debt=stmt_debt,
            installment_debt=inst_debt,
            cutoff_day=r["cutoff_day"],
            due_day=r["due_day"],
            min_payment_rate=float(r.get("min_payment_rate") or 0.20),
            interest_rate=float(r.get("interest_rate") or 4.25),
            color=r.get("color") or "#6366f1",
            total_debt_load=total_debt_load,
            available_limit=round(max(0.0, limit - total_debt_load), 2),
            utilization_rate=round((total_debt_load / limit * 100.0) if limit > 0 else 0.0, 1),
            min_payment_amount=round((stmt_debt or curr_debt) * float(r.get("min_payment_rate") or 0.20), 2),
            days_until_due=days_due,
            days_until_cutoff=days_cutoff,
            due_date_str=due_date_str,
            cutoff_date_str=cutoff_date_str,
            urgency_level=urgency,
            unpaid_past_statements_total=0.0,
            created_at=str(r["created_at"]) if r.get("created_at") else None
        )

def update_card_limits_and_debts(card_id: int, update: CardLimitAndDebtUpdate, user_id: Optional[int] = None) -> bool:
    if not user_id:
        return False

    with get_db() as conn:
        cursor = conn.cursor()
        clauses = []
        params = []
        if update.total_limit is not None:
            clauses.append("total_limit = ?")
            params.append(update.total_limit)
        if update.statement_debt is not None:
            clauses.append("statement_debt = ?")
            params.append(update.statement_debt)
        if update.current_debt is not None:
            clauses.append("current_debt = ?")
            params.append(update.current_debt)
        if update.installment_debt is not None:
            clauses.append("installment_debt = ?")
            params.append(update.installment_debt)
        if update.min_payment_rate is not None:
            clauses.append("min_payment_rate = ?")
            params.append(update.min_payment_rate)
        if update.interest_rate is not None:
            clauses.append("interest_rate = ?")
            params.append(update.interest_rate)

        if not clauses:
            return False

        sql = f"UPDATE credit_cards SET {', '.join(clauses)} WHERE id = ? AND user_id = ?"
        params.extend([card_id, user_id])

        cursor.execute(sql, params)
        return cursor.rowcount > 0

# ==========================================
# CREDIT CARD STATEMENTS & PAST DEBTS
# ==========================================
def add_card_statement(stmt: CreditCardStatementCreate, user_id: Optional[int] = None) -> CreditCardStatementResponse:
    if not user_id:
        raise ValueError("Kullanıcı oturumu zorunludur.")

    with get_db() as conn:
        cursor = conn.cursor()
        rem_debt = max(0.0, stmt.statement_amount - stmt.paid_amount)
        status = 'paid' if rem_debt == 0 else ('partially_paid' if stmt.paid_amount > 0 else 'unpaid')
        min_amt = stmt.min_payment_amount or round(stmt.statement_amount * 0.20, 2)

        cursor.execute("""
            INSERT INTO credit_card_statements (credit_card_id, user_id, period, statement_date, due_date, statement_amount, min_payment_amount, paid_amount, remaining_debt, interest_rate, status, notes)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            stmt.credit_card_id, user_id, stmt.period, stmt.statement_date, stmt.due_date,
            stmt.statement_amount, min_amt, stmt.paid_amount, rem_debt,
            stmt.interest_rate, status, stmt.notes
        ))
        row = cursor.fetchone()
        stmt_id = row["id"] if isinstance(row, dict) else row[0]

        cursor.execute("""
            SELECT s.*, c.card_name, c.bank_name
            FROM credit_card_statements s
            JOIN credit_cards c ON s.credit_card_id = c.id
            WHERE s.id = ? AND s.user_id = ?
        """, (stmt_id, user_id))
        r = cursor.fetchone()

        rate = float(r["interest_rate"])
        est_interest = round(rem_debt * (rate / 100.0), 2)

        return CreditCardStatementResponse(
            id=r["id"],
            credit_card_id=r["credit_card_id"],
            user_id=r["user_id"],
            period=r["period"],
            statement_date=r.get("statement_date"),
            due_date=r.get("due_date"),
            statement_amount=float(r["statement_amount"]),
            min_payment_amount=float(r["min_payment_amount"]),
            paid_amount=float(r["paid_amount"]),
            remaining_debt=float(r["remaining_debt"]),
            interest_rate=rate,
            status=r["status"],
            notes=r.get("notes"),
            card_name=r["card_name"],
            bank_name=r["bank_name"],
            estimated_interest=est_interest,
            created_at=str(r["created_at"]) if r.get("created_at") else None
        )

def get_card_statements(card_id: int, user_id: Optional[int] = None) -> List[CreditCardStatementResponse]:
    if not user_id:
        return []

    with get_db() as conn:
        cursor = conn.cursor()
        query = """
            SELECT s.*, c.card_name, c.bank_name
            FROM credit_card_statements s
            JOIN credit_cards c ON s.credit_card_id = c.id
            WHERE s.credit_card_id = ? AND s.user_id = ?
            ORDER BY s.id DESC
        """
        cursor.execute(query, (card_id, user_id))
        rows = cursor.fetchall()
        results = []
        for r in rows:
            rem = float(r["remaining_debt"] or 0.0)
            rate = float(r["interest_rate"] or 4.25)
            results.append(CreditCardStatementResponse(
                id=r["id"],
                credit_card_id=r["credit_card_id"],
                user_id=r["user_id"],
                period=r["period"],
                statement_date=r.get("statement_date"),
                due_date=r.get("due_date"),
                statement_amount=float(r["statement_amount"]),
                min_payment_amount=float(r["min_payment_amount"] or 0.0),
                paid_amount=float(r["paid_amount"] or 0.0),
                remaining_debt=rem,
                interest_rate=rate,
                status=r["status"],
                notes=r.get("notes"),
                card_name=r["card_name"],
                bank_name=r["bank_name"],
                estimated_interest=round(rem * (rate / 100.0), 2),
                created_at=str(r["created_at"]) if r.get("created_at") else None
            ))
        return results

def delete_statement(statement_id: int, user_id: Optional[int] = None) -> bool:
    if not user_id:
        return False
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM credit_card_statements WHERE id = ? AND user_id = ?", (statement_id, user_id))
        return cursor.rowcount > 0

def get_credit_analytics(user_id: Optional[int] = None) -> CreditCardAnalyticsResponse:
    if not user_id:
        return CreditCardAnalyticsResponse(
            total_limits_all_cards=0.0,
            total_statement_debt_all=0.0,
            total_current_debt_all=0.0,
            total_installment_debt_all=0.0,
            total_combined_debt=0.0,
            total_available_limit_all=0.0,
            overall_utilization_rate=0.0,
            total_past_unpaid_debt=0.0,
            estimated_monthly_interest_load=0.0
        )

    cards = get_all_credit_cards(user_id=user_id)

    total_limits = sum(c.total_limit for c in cards)
    total_statement_debt = sum(c.statement_debt for c in cards)
    total_current_debt = sum(c.current_debt for c in cards)
    total_installment_debt = sum(c.installment_debt for c in cards)
    total_past_unpaid = sum(c.unpaid_past_statements_total for c in cards)

    total_combined = round(total_statement_debt + total_current_debt + total_installment_debt + total_past_unpaid, 2)
    total_avail = max(0.0, total_limits - total_combined)
    overall_util = round((total_combined / total_limits * 100.0) if total_limits > 0 else 0.0, 1)

    unpaid_portion = sum(max(0.0, c.statement_debt - c.min_payment_amount) for c in cards)
    est_interest = round(unpaid_portion * 0.0425, 2)

    return CreditCardAnalyticsResponse(
        total_limits_all_cards=round(total_limits, 2),
        total_statement_debt_all=round(total_statement_debt, 2),
        total_current_debt_all=round(total_current_debt, 2),
        total_installment_debt_all=round(total_installment_debt, 2),
        total_combined_debt=total_combined,
        total_available_limit_all=round(total_avail, 2),
        overall_utilization_rate=overall_util,
        total_past_unpaid_debt=round(total_past_unpaid, 2),
        estimated_monthly_interest_load=est_interest
    )

# ==========================================
# LOANS
# ==========================================
def get_all_loans(user_id: Optional[int] = None) -> List[LoanResponse]:
    if not user_id:
        return []

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM loans WHERE user_id = ? ORDER BY remaining_installments DESC", (user_id,))
        rows = cursor.fetchall()

        today = date.today()
        loans = []
        for r in rows:
            rem = r["remaining_installments"]
            total_inst = r["total_installments"]
            paid = max(0, total_inst - rem)
            monthly = float(r["monthly_installment"])
            principal = round(rem * monthly, 2)
            days_due, due_date_str = calculate_target_date_info(r["due_day"])

            end_date = today + relativedelta(months=rem)
            end_date_str = f"{MONTHS_TR[end_date.month - 1]} {end_date.year}"

            loans.append(LoanResponse(
                id=r["id"],
                user_id=r["user_id"],
                bank_name=r["bank_name"],
                bank_code=r.get("bank_code"),
                loan_title=r["loan_title"],
                total_amount=float(r["total_amount"]),
                monthly_installment=monthly,
                remaining_installments=rem,
                total_installments=total_inst,
                due_day=r["due_day"],
                interest_rate=float(r.get("interest_rate") or 0.0),
                color=r.get("color") or "#f59e0b",
                remaining_principal=principal,
                paid_installments=paid,
                days_until_due=days_due,
                due_date_str=due_date_str,
                end_date_estimate=end_date_str,
                created_at=str(r["created_at"]) if r.get("created_at") else None
            ))
        return loans

def create_loan(loan: LoanCreate, user_id: Optional[int] = None) -> LoanResponse:
    if not user_id:
        raise ValueError("Kullanıcı oturumu zorunludur.")

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO loans (user_id, bank_name, bank_code, loan_title, total_amount, monthly_installment, remaining_installments, total_installments, due_day, interest_rate, color)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, loan.bank_name, loan.bank_code, loan.loan_title, loan.total_amount,
            loan.monthly_installment, loan.remaining_installments, loan.total_installments,
            loan.due_day, loan.interest_rate, loan.color
        ))
        row = cursor.fetchone()
        loan_id = row["id"] if isinstance(row, dict) else row[0]

        cursor.execute("SELECT * FROM loans WHERE id = ? AND user_id = ?", (loan_id, user_id))
        r = cursor.fetchone()

        today = date.today()
        end_date = today + relativedelta(months=r["remaining_installments"])
        end_date_str = f"{MONTHS_TR[end_date.month - 1]} {end_date.year}"
        days_due, due_date_str = calculate_target_date_info(r["due_day"])

        return LoanResponse(
            id=r["id"],
            user_id=r["user_id"],
            bank_name=r["bank_name"],
            bank_code=r.get("bank_code"),
            loan_title=r["loan_title"],
            total_amount=float(r["total_amount"]),
            monthly_installment=float(r["monthly_installment"]),
            remaining_installments=r["remaining_installments"],
            total_installments=r["total_installments"],
            due_day=r["due_day"],
            interest_rate=float(r.get("interest_rate") or 0.0),
            color=r.get("color") or "#f59e0b",
            remaining_principal=round(r["remaining_installments"] * float(r["monthly_installment"]), 2),
            paid_installments=max(0, r["total_installments"] - r["remaining_installments"]),
            days_until_due=days_due,
            due_date_str=due_date_str,
            end_date_estimate=end_date_str,
            created_at=str(r["created_at"]) if r.get("created_at") else None
        )

def delete_credit_card(card_id: int, user_id: Optional[int] = None) -> bool:
    if not user_id:
        return False
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM credit_cards WHERE id = ? AND user_id = ?", (card_id, user_id))
        return cursor.rowcount > 0

def delete_loan(loan_id: int, user_id: Optional[int] = None) -> bool:
    if not user_id:
        return False
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM loans WHERE id = ? AND user_id = ?", (loan_id, user_id))
        return cursor.rowcount > 0
