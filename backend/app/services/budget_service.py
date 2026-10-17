from typing import List, Optional
from datetime import datetime
from app.database import get_db
from app.models.schemas import CategoryBudgetCreate, CategoryBudgetResponse

CATEGORY_DEFAULT_COLORS = {
    "Market": "#10b981",
    "Restoran & Yemek": "#f59e0b",
    "Faturalar": "#06b6d4",
    "Ulaşım": "#3b82f6",
    "Eğlence & Sosyal": "#ec4899",
    "Giyim & Alışveriş": "#8b5cf6",
    "Kira & Barınma": "#6366f1",
    "Sağlık & Bakım": "#14b8a6",
    "Eğitim & Kitap": "#f97316",
    "Elektronik": "#64748b",
    "Diğer": "#94a3b8"
}

def get_category_budgets(user_id: int) -> List[CategoryBudgetResponse]:
    """Retrieves all budget limits for user, calculates current month's spent amount,
    percentage, and visual alert status (<80% safe, 80-99% warning, >=100% exceeded)."""
    if not user_id:
        return []

    now = datetime.now()
    first_day_of_month = f"{now.year}-{now.month:02d}-01"

    with get_db() as conn:
        cursor = conn.cursor()

        # 1. Get all configured budget limits for this user
        cursor.execute("""
            SELECT id, user_id, category, monthly_limit, created_at
            FROM category_budgets
            WHERE user_id = ?
            ORDER BY monthly_limit DESC
        """, (user_id,))
        budget_rows = cursor.fetchall()

        # 2. Get actual monthly spending grouped by category for current month
        cursor.execute("""
            SELECT category, SUM(amount) as total_spent
            FROM transactions
            WHERE user_id = ? 
              AND type = 'expense'
              AND date >= ?
            GROUP BY category
        """, (user_id, first_day_of_month))
        spent_rows = cursor.fetchall()
        spent_map = {r["category"]: float(r["total_spent"]) for r in spent_rows}

        results = []
        for b in budget_rows:
            category = b["category"]
            limit = float(b["monthly_limit"])
            spent = spent_map.get(category, 0.0)
            percentage = round((spent / limit * 100), 1) if limit > 0 else 0.0
            remaining = round(max(0.0, limit - spent), 2)

            if percentage >= 100.0:
                status = "exceeded"
            elif percentage >= 80.0:
                status = "warning"
            else:
                status = "safe"

            color = CATEGORY_DEFAULT_COLORS.get(category, "#10b981")

            results.append(CategoryBudgetResponse(
                id=b["id"],
                user_id=b["user_id"],
                category=category,
                monthly_limit=limit,
                current_spent=spent,
                percentage_spent=percentage,
                remaining_budget=remaining,
                status=status,
                color=color,
                created_at=str(b["created_at"]) if b.get("created_at") else None
            ))

        return results

def set_category_budget(user_id: int, budget_data: CategoryBudgetCreate) -> CategoryBudgetResponse:
    """Sets or updates a monthly budget limit for a category."""
    if not user_id:
        raise ValueError("Kullanıcı oturumu zorunludur.")
    if budget_data.monthly_limit <= 0:
        raise ValueError("Bütçe limiti 0'dan büyük olmalıdır.")

    with get_db() as conn:
        cursor = conn.cursor()
        
        # Check if already exists
        cursor.execute("SELECT id FROM category_budgets WHERE user_id = ? AND category = ?", (user_id, budget_data.category))
        existing = cursor.fetchone()

        if existing:
            budget_id = existing["id"] if isinstance(existing, dict) else existing[0]
            cursor.execute("UPDATE category_budgets SET monthly_limit = ? WHERE id = ? AND user_id = ?", 
                           (budget_data.monthly_limit, budget_id, user_id))
        else:
            cursor.execute("""
                INSERT INTO category_budgets (user_id, category, monthly_limit)
                OUTPUT INSERTED.id
                VALUES (?, ?, ?)
            """, (user_id, budget_data.category, budget_data.monthly_limit))
            row = cursor.fetchone()
            budget_id = row["id"] if isinstance(row, dict) else row[0]

    # Return full calculated response
    all_budgets = get_category_budgets(user_id)
    for b in all_budgets:
        if b.id == budget_id:
            return b
    raise RuntimeError("Bütçe kaydedilemedi.")

def delete_category_budget(user_id: int, budget_id: int) -> bool:
    """Deletes a category budget limit."""
    if not user_id:
        return False
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM category_budgets WHERE id = ? AND user_id = ?", (budget_id, user_id))
        return cursor.rowcount > 0
