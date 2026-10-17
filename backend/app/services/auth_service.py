import hashlib
import secrets
from typing import Optional, Dict, Any
from app.database import get_db, reset_all_data

def hash_password(password: str, salt: str = "smartfin_salt_2026") -> str:
    """Generates a secure SHA-256 hash with salt."""
    return hashlib.sha256(f"{salt}{password}".encode("utf-8")).hexdigest()

def register_user(email: str, password: str, full_name: str) -> Dict[str, Any]:
    cleaned_email = email.strip().lower()
    if not cleaned_email or "@" not in cleaned_email:
        raise ValueError("Geçerli bir e-posta adresi giriniz.")
    if len(password) < 4:
        raise ValueError("Şifre en az 4 karakter olmalıdır.")

    pwd_hash = hash_password(password)

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email = ?", (cleaned_email,))
        if cursor.fetchone():
            raise ValueError("Bu e-posta adresi zaten kayıtlı.")

        is_admin = 1 if cleaned_email == "efegezgin45@gmail.com" else 0
        cursor.execute("""
            INSERT INTO users (email, password_hash, full_name, is_admin)
            OUTPUT INSERTED.id, INSERTED.is_admin
            VALUES (?, ?, ?, ?)
        """, (cleaned_email, pwd_hash, full_name.strip(), is_admin))
        row = cursor.fetchone()
        user_id = row["id"] if isinstance(row, dict) else row[0]
        user_is_admin = bool(row["is_admin"] if isinstance(row, dict) else row[1])

        # Generate unique session token
        token = secrets.token_hex(32)
        cursor.execute("""
            INSERT INTO user_sessions (token, user_id)
            VALUES (?, ?)
        """, (token, user_id))

        user_plan = "vip" if user_is_admin else "free"
        return {
            "token": token,
            "user": {
                "id": user_id,
                "email": cleaned_email,
                "full_name": full_name.strip(),
                "is_admin": user_is_admin,
                "plan": user_plan
            }
        }

def login_user(email: str, password: str) -> Dict[str, Any]:
    cleaned_email = email.strip().lower()
    pwd_hash = hash_password(password)

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, full_name, password_hash, is_admin, [plan] FROM users WHERE email = ?", (cleaned_email,))
        user = cursor.fetchone()

        if not user or user["password_hash"] != pwd_hash:
            raise ValueError("E-posta veya şifre hatalı.")

        user_id = user["id"]
        user_is_admin = bool(user["is_admin"])
        user_plan = user.get("plan") or ("vip" if user_is_admin else "free")
        token = secrets.token_hex(32)
        cursor.execute("INSERT INTO user_sessions (token, user_id) VALUES (?, ?)", (token, user_id))

        return {
            "token": token,
            "user": {
                "id": user_id,
                "email": user["email"],
                "full_name": user["full_name"],
                "is_admin": user_is_admin,
                "plan": user_plan
            }
        }



def login_or_create_demo_user() -> Dict[str, Any]:
    """
    Creates a dedicated, isolated test sandbox account for demonstration.
    Each demo session is unique so multiple concurrent visitors never share or overwrite each other's data!
    """
    random_suffix = secrets.token_hex(4)
    demo_email = f"misafir_{random_suffix}@smartfinance.ai"
    demo_pass = "demo1234"
    demo_name = f"Misafir Test #{random_suffix.upper()}"
    
    auth_data = register_user(demo_email, demo_pass, demo_name)
    user_id = auth_data["user"]["id"]
    
    # Pre-seed isolated demo data for this user
    _seed_isolated_demo_data(user_id)
    return auth_data

def _seed_isolated_demo_data(user_id: int):
    """Adds initial sample data exclusively for this demo user so they can immediately test the dashboard."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # 1. Bank Account
        cursor.execute("""
            INSERT INTO accounts (user_id, name, type, currency, balance, exchange_rate, is_active_cash, bank_name, bank_code, color, icon)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, "Garanti Vadesiz TL", "bank_checking", "TRY", 42500.0, 1.0, 1, "Garanti BBVA", "garanti", "#059669", "landmark"))
        
        # 2. Credit Card
        cursor.execute("""
            INSERT INTO credit_cards (user_id, bank_name, bank_code, card_name, total_limit, current_debt, statement_debt, installment_debt, cutoff_day, due_day, min_payment_rate, interest_rate, color)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, "Yapı Kredi", "yapikredi", "World Platinum", 50000.0, 4800.0, 7200.0, 12000.0, 15, 25, 0.20, 4.25, "#2563eb"))

def get_user_by_token(token: str) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.id, u.email, u.full_name, u.is_admin, u.[plan], u.created_at
            FROM user_sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.token = ?
        """, (token,))
        row = cursor.fetchone()
        if row:
            is_adm = bool(row["is_admin"])
            return {
                "id": row["id"],
                "email": row["email"],
                "full_name": row["full_name"],
                "is_admin": is_adm,
                "plan": row["plan"] or ("vip" if is_adm else "free"),
                "created_at": str(row["created_at"]) if row["created_at"] else None
            }
        return None

def upgrade_user_plan(user_id: int, plan: str) -> Dict[str, Any]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET [plan] = ? WHERE id = ?", (plan, user_id))
        cursor.execute("SELECT id, email, full_name, is_admin, [plan], created_at FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        is_adm = bool(row["is_admin"])
        return {
            "id": row["id"],
            "email": row["email"],
            "full_name": row["full_name"],
            "is_admin": is_adm,
            "plan": row["plan"] or ("vip" if is_adm else "free"),
            "created_at": str(row["created_at"]) if row["created_at"] else None
        }



def logout_user(token: str) -> bool:
    if not token:
        return False
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_sessions WHERE token = ?", (token,))
        return cursor.rowcount > 0

def clear_user_finances(user_id: int):
    """Resets all numbers, balances, cards, loans for this user to zero."""
    reset_all_data(user_id=user_id)
