from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from app.database import get_db
from app.models.schemas import (
    TransactionCreate, TransactionResponse,
    RecurringItemCreate, RecurringItemResponse
)

def get_transactions(
    limit: int = 50,
    offset: int = 0,
    trans_type: Optional[str] = None,
    category: Optional[str] = None,
    user_id: Optional[int] = None
) -> List[TransactionResponse]:
    if not user_id:
        return []

    with get_db() as conn:
        cursor = conn.cursor()
        query = """
            SELECT t.*, a.name as account_name, c.card_name as card_name
            FROM transactions t
            LEFT JOIN accounts a ON t.account_id = a.id
            LEFT JOIN credit_cards c ON t.credit_card_id = c.id
            WHERE t.user_id = ?
        """
        params = [user_id]
        if trans_type:
            query += " AND t.type = ?"
            params.append(trans_type)
        if category:
            query += " AND t.category = ?"
            params.append(category)

        # MSSQL Standard Pagination
        query += " ORDER BY t.date DESC, t.id DESC OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
        params.extend([offset, limit])

        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()

        results = []
        for r in rows:
            results.append(TransactionResponse(
                id=r["id"],
                user_id=r["user_id"],
                date=r["date"],
                type=r["type"],
                category=r["category"],
                amount=float(r["amount"]),
                description=r["description"],
                payment_method=r["payment_method"],
                account_id=r.get("account_id"),
                credit_card_id=r.get("credit_card_id"),
                is_nlp_generated=bool(r.get("is_nlp_generated")),
                raw_input=r.get("raw_input"),
                created_at=str(r["created_at"]) if r.get("created_at") else None,
                account_name=r.get("account_name"),
                card_name=r.get("card_name"),
                emotion_tag=r.get("emotion_tag") or "essential"
            ))
        return results

def create_transaction(trans: TransactionCreate, user_id: Optional[int] = None) -> TransactionResponse:
    if not user_id:
        raise ValueError("Kullanıcı oturumu zorunludur.")

    with get_db() as conn:
        cursor = conn.cursor()

        target_account_id = trans.account_id
        target_card_id = trans.credit_card_id
        actual_payment_method = trans.payment_method or "account"

        # Resolve Account:
        # If income, or payment_method is account or cash, or if no card is specified:
        if trans.type == "income" or actual_payment_method in ("account", "cash") or (not target_card_id and actual_payment_method != "credit_card"):
            if target_account_id:
                cursor.execute("SELECT id FROM accounts WHERE id = ? AND user_id = ?", (target_account_id, user_id))
                if not cursor.fetchone():
                    target_account_id = None
            if not target_account_id:
                # Pick active liquid checking account, or first user account
                cursor.execute("SELECT TOP 1 id FROM accounts WHERE user_id = ? AND is_active_cash = 1 ORDER BY id ASC", (user_id,))
                acc_row = cursor.fetchone()
                if not acc_row:
                    cursor.execute("SELECT TOP 1 id FROM accounts WHERE user_id = ? ORDER BY id ASC", (user_id,))
                    acc_row = cursor.fetchone()
                if acc_row:
                    target_account_id = acc_row["id"] if isinstance(acc_row, dict) else acc_row[0]

        # Resolve Credit Card:
        if actual_payment_method == "credit_card":
            if target_card_id:
                cursor.execute("SELECT id FROM credit_cards WHERE id = ? AND user_id = ?", (target_card_id, user_id))
                if not cursor.fetchone():
                    target_card_id = None
            if not target_card_id:
                cursor.execute("SELECT TOP 1 id FROM credit_cards WHERE user_id = ? ORDER BY id ASC", (user_id,))
                card_row = cursor.fetchone()
                if card_row:
                    target_card_id = card_row["id"] if isinstance(card_row, dict) else card_row[0]

        # 1. Insert transaction with resolved IDs
        cursor.execute("""
            INSERT INTO transactions (user_id, date, type, category, amount, description, payment_method, account_id, credit_card_id, is_nlp_generated, raw_input, emotion_tag)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, trans.date, trans.type, trans.category, trans.amount, trans.description,
            actual_payment_method, target_account_id, target_card_id,
            1 if trans.is_nlp_generated else 0, trans.raw_input,
            trans.emotion_tag or "essential"
        ))
        row = cursor.fetchone()
        trans_id = row["id"] if isinstance(row, dict) else row[0]

        # 2. Reflect balance change automatically on account and/or card!
        # Case A: Cash / Bank Account was used
        if target_account_id:
            if trans.type == "expense":
                cursor.execute("UPDATE accounts SET balance = balance - ? WHERE id = ? AND user_id = ?", (trans.amount, target_account_id, user_id))
            elif trans.type == "income":
                cursor.execute("UPDATE accounts SET balance = balance + ? WHERE id = ? AND user_id = ?", (trans.amount, target_account_id, user_id))

        # Case B: Credit card is involved
        if target_card_id:
            desc_lower = (trans.description or "").lower()
            cat_lower = (trans.category or "").lower()
            is_debt_payment = (
                cat_lower in ["kredi & finans", "borç ödemesi"] or
                "borç" in desc_lower or
                "kapattım" in desc_lower or
                "ödeme" in desc_lower or
                actual_payment_method in ["account", "cash"]
            ) and actual_payment_method != "credit_card"

            if is_debt_payment or trans.type == "income":
                # Debt reduction on credit card
                cursor.execute("""
                    UPDATE credit_cards 
                    SET current_debt = CASE WHEN current_debt >= ? THEN current_debt - ? ELSE 0.0 END,
                        statement_debt = CASE WHEN statement_debt >= ? THEN statement_debt - ? ELSE 0.0 END
                    WHERE id = ? AND user_id = ?
                """, (trans.amount, trans.amount, trans.amount, trans.amount, target_card_id, user_id))
            elif actual_payment_method == "credit_card" and trans.type == "expense" and not target_account_id:
                # Direct purchase made with credit card
                cursor.execute("UPDATE credit_cards SET current_debt = current_debt + ? WHERE id = ? AND user_id = ?", (trans.amount, target_card_id, user_id))



        # 3. Retrieve created transaction
        cursor.execute("""
            SELECT t.*, a.name as account_name, c.card_name as card_name
            FROM transactions t
            LEFT JOIN accounts a ON t.account_id = a.id
            LEFT JOIN credit_cards c ON t.credit_card_id = c.id
            WHERE t.id = ? AND t.user_id = ?
        """, (trans_id, user_id))
        r = cursor.fetchone()

        # 4. Auto-generate In-App & Phone Notification
        try:
            desc_text = r["description"] if r and r.get("description") else (trans.description or "İşlem")
            if trans.type == "income":
                notif_title = "💰 Para Girişi Sağlandı"
                notif_msg = f"+{trans.amount:,.2f} TL tutarındaki gelir ({desc_text}) hesabınıza eklendi."
                notif_type = "income"
            elif is_debt_payment or (target_card_id and ("borç" in desc_text.lower() or "kapattım" in desc_text.lower())):
                card_lbl = r.get("card_name") or "Kredi Kartı"
                notif_title = "💳 Kredi Kartı Borcu Kapandı"
                notif_msg = f"-{trans.amount:,.2f} TL tutarındaki borç ödemeniz {card_lbl} kartınıza yansıtıldı."
                notif_type = "debt_payment"
            else:
                notif_title = "💸 Harcama Kaydedildi"
                notif_msg = f"-{trans.amount:,.2f} TL ({desc_text}) harcamanız kaydedildi."
                notif_type = "expense"

            cursor.execute("""
                INSERT INTO notifications (user_id, title, message, type, is_read)
                VALUES (?, ?, ?, ?, 0)
            """, (user_id, notif_title, notif_msg, notif_type))
        except Exception as notif_err:
            print("Notification insert notice:", notif_err)

        return TransactionResponse(
            id=r["id"],
            user_id=r["user_id"],
            date=r["date"],
            type=r["type"],
            category=r["category"],
            amount=float(r["amount"]),
            description=r["description"],
            payment_method=r["payment_method"],
            account_id=r.get("account_id"),
            credit_card_id=r.get("credit_card_id"),
            is_nlp_generated=bool(r.get("is_nlp_generated")),
            raw_input=r.get("raw_input"),
            created_at=str(r["created_at"]) if r.get("created_at") else None,
            account_name=r.get("account_name"),
            card_name=r.get("card_name"),
            emotion_tag=r.get("emotion_tag") or "essential"
        )

# ---------------- Recurring Items ----------------
def get_recurring_items(user_id: Optional[int] = None) -> List[RecurringItemResponse]:
    if not user_id:
        return []

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM recurring_items WHERE is_active = 1 AND user_id = ? ORDER BY day_of_month ASC", (user_id,))
        rows = cursor.fetchall()
        return [
            RecurringItemResponse(
                id=r["id"],
                user_id=r["user_id"],
                title=r["title"],
                type=r["type"],
                category=r["category"],
                amount=float(r["amount"]),
                day_of_month=r["day_of_month"],
                account_id=r.get("account_id"),
                is_active=1 if r.get("is_active") else 0,
                notes=r.get("notes")
            )
            for r in rows
        ]

def create_recurring_item(item: RecurringItemCreate, user_id: Optional[int] = None) -> RecurringItemResponse:
    if not user_id:
        raise ValueError("Kullanıcı oturumu zorunludur.")

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO recurring_items (user_id, title, type, category, amount, day_of_month, account_id, is_active, notes)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, item.title, item.type, item.category, item.amount,
            item.day_of_month, item.account_id, 1 if item.is_active else 0, item.notes
        ))
        row = cursor.fetchone()
        item_id = row["id"] if isinstance(row, dict) else row[0]

        return RecurringItemResponse(
            id=item_id,
            user_id=user_id,
            title=item.title,
            type=item.type,
            category=item.category,
            amount=item.amount,
            day_of_month=item.day_of_month,
            account_id=item.account_id,
            is_active=item.is_active,
            notes=item.notes
        )

# ---------------- Monthly Spending Analysis ----------------
def get_monthly_category_comparison(user_id: Optional[int] = None) -> Dict[str, Any]:
    today = date.today()
    this_month_prefix = today.strftime("%Y-%m")

    first_this_month = today.replace(day=1)
    last_month_end = first_this_month - timedelta(days=1)
    last_month_prefix = last_month_end.strftime("%Y-%m")

    if not user_id:
        return {
            "this_month": this_month_prefix,
            "last_month": last_month_prefix,
            "this_month_total": 0.0,
            "last_month_total": 0.0,
            "categories": []
        }

    with get_db() as conn:
        cursor = conn.cursor()

        # This month expenses by category strictly for this user
        cursor.execute("""
            SELECT category, SUM(amount) as total
            FROM transactions
            WHERE type = 'expense' AND date LIKE ? AND user_id = ?
            GROUP BY category
        """, (f"{this_month_prefix}%", user_id))
        this_month_rows = {r["category"]: float(r["total"] or 0.0) for r in cursor.fetchall()}

        # Last month expenses by category strictly for this user
        cursor.execute("""
            SELECT category, SUM(amount) as total
            FROM transactions
            WHERE type = 'expense' AND date LIKE ? AND user_id = ?
            GROUP BY category
        """, (f"{last_month_prefix}%", user_id))
        last_month_rows = {r["category"]: float(r["total"] or 0.0) for r in cursor.fetchall()}

        all_categories = sorted(set(list(this_month_rows.keys()) + list(last_month_rows.keys())))

        categories_data = []
        for cat in all_categories:
            current_amt = this_month_rows.get(cat, 0.0)
            last_amt = last_month_rows.get(cat, 0.0)
            pct_change = round(((current_amt - last_amt) / last_amt * 100.0), 1) if last_amt > 0 else 0.0
            categories_data.append({
                "category": cat,
                "this_month": round(current_amt, 2),
                "last_month": round(last_amt, 2),
                "percent_change": pct_change,
                "diff": round(current_amt - last_amt, 2)
            })

        this_month_total = sum(this_month_rows.values())
        last_month_total = sum(last_month_rows.values())

        return {
            "this_month": this_month_prefix,
            "last_month": last_month_prefix,
            "this_month_total": round(this_month_total, 2),
            "last_month_total": round(last_month_total, 2),
            "categories": categories_data
        }

def delete_transaction(transaction_id: int, user_id: Optional[int] = None) -> bool:
    if not user_id:
        return False
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM transactions WHERE id = ? AND user_id = ?", (transaction_id, user_id))
        tx = cursor.fetchone()
        if not tx:
            return False

        amt = float(tx["amount"] or 0.0)
        tx_type = tx["type"]
        acc_id = tx.get("account_id")
        card_id = tx.get("credit_card_id")

        # Rollback the balance or debt
        if acc_id:
            if tx_type == "expense":
                cursor.execute("UPDATE accounts SET balance = balance + ? WHERE id = ? AND user_id = ?", (amt, acc_id, user_id))
            elif tx_type == "income":
                cursor.execute("UPDATE accounts SET balance = balance - ? WHERE id = ? AND user_id = ?", (amt, acc_id, user_id))
        elif card_id:
            if tx_type == "expense":
                cursor.execute("UPDATE credit_cards SET current_debt = CASE WHEN current_debt >= ? THEN current_debt - ? ELSE 0.0 END WHERE id = ? AND user_id = ?", (amt, amt, card_id, user_id))
            elif tx_type == "income":
                cursor.execute("UPDATE credit_cards SET current_debt = current_debt + ? WHERE id = ? AND user_id = ?", (amt, card_id, user_id))

        cursor.execute("DELETE FROM transactions WHERE id = ? AND user_id = ?", (transaction_id, user_id))
        return cursor.rowcount > 0


def delete_recurring_item(item_id: int, user_id: Optional[int] = None) -> bool:
    if not user_id:
        return False
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM recurring_items WHERE id = ? AND user_id = ?", (item_id, user_id))
        return cursor.rowcount > 0
