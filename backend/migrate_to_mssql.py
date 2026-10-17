import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import sqlite3
import pyodbc
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "backend" / "data" / "smartfinance.db"

def run_migration():
    print("=" * 60)
    print("🔄 SmartFinance AI - SQLite -> MSSQL Veri Taşıma Başlatıldı")
    print("=" * 60)

    if not DB_PATH.exists():
        print(f"Hata: SQLite dosyası bulunamadı: {DB_PATH}")
        return

    # 1. Connect SQLite
    s_conn = sqlite3.connect(str(DB_PATH))
    s_conn.row_factory = sqlite3.Row
    sc = s_conn.cursor()

    # 2. Connect MSSQL
    m_conn = pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};SERVER=.\\SQLEXPRESS;DATABASE=SmartFinanceDB;Trusted_Connection=yes;",
        autocommit=True
    )
    mc = m_conn.cursor()

    # Ensure is_admin column exists in users
    mc.execute("""
    IF NOT EXISTS (
        SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'users' AND COLUMN_NAME = 'is_admin'
    )
    ALTER TABLE users ADD is_admin BIT NOT NULL DEFAULT 0;
    """)
    print("✅ is_admin sütunu MSSQL users tablosunda doğrulandı.")

    # 3. Migrate Users
    sc.execute("SELECT * FROM users")
    s_users = sc.fetchall()
    user_map = {}

    for u in s_users:
        email = u["email"].strip().lower()
        is_admin = 1 if email == "efegezgin45@gmail.com" else 0

        mc.execute("SELECT id FROM users WHERE email = ?", (email,))
        row = mc.fetchone()
        if row:
            m_uid = row[0]
            mc.execute("UPDATE users SET is_admin = ? WHERE id = ?", (is_admin, m_uid))
        else:
            mc.execute("""
                INSERT INTO users (email, password_hash, full_name, created_at, is_admin)
                OUTPUT INSERTED.id
                VALUES (?, ?, ?, ?, ?)
            """, (email, u["password_hash"], u["full_name"], u["created_at"], is_admin))
            m_uid = mc.fetchone()[0]

        user_map[u["id"]] = m_uid
        admin_tag = "👑 [SİSTEM YÖNETİCİSİ]" if is_admin else "👤 [Kullanıcı]"
        print(f"Kullanıcı Aktarıldı: {email} -> MSSQL ID {m_uid} {admin_tag}")

    # 4. Migrate Accounts
    sc.execute("SELECT * FROM accounts")
    s_accounts = sc.fetchall()
    acc_map = {}

    for a in s_accounts:
        s_uid = a["user_id"]
        if s_uid not in user_map:
            continue
        m_uid = user_map[s_uid]

        mc.execute("SELECT id FROM accounts WHERE user_id = ? AND name = ? AND bank_name = ?", (m_uid, a["name"], a["bank_name"]))
        row = mc.fetchone()
        if row:
            m_acc_id = row[0]
        else:
            mc.execute("""
                INSERT INTO accounts (user_id, name, type, currency, balance, exchange_rate, is_active_cash, bank_name, bank_code, account_number, color, icon)
                OUTPUT INSERTED.id
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                m_uid, a["name"], a["type"], a["currency"], a["balance"], a["exchange_rate"],
                1 if a["is_active_cash"] else 0, a["bank_name"], a["bank_code"], a["account_number"],
                a["color"], a["icon"]
            ))
            m_acc_id = mc.fetchone()[0]

        acc_map[a["id"]] = m_acc_id
        print(f"  └─ Hesap Aktarıldı: {a['bank_name']} - {a['name']} ({a['balance']:,.2f} TL) -> User {m_uid}")

    # 5. Migrate Credit Cards
    sc.execute("SELECT * FROM credit_cards")
    s_cards = sc.fetchall()
    card_map = {}

    for c in s_cards:
        s_uid = c["user_id"]
        if s_uid not in user_map:
            continue
        m_uid = user_map[s_uid]

        mc.execute("SELECT id FROM credit_cards WHERE user_id = ? AND card_name = ? AND bank_name = ?", (m_uid, c["card_name"], c["bank_name"]))
        row = mc.fetchone()
        if row:
            m_cid = row[0]
        else:
            mc.execute("""
                INSERT INTO credit_cards (user_id, bank_name, bank_code, card_name, total_limit, current_debt, statement_debt, installment_debt, cutoff_day, due_day, min_payment_rate, interest_rate, color)
                OUTPUT INSERTED.id
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                m_uid, c["bank_name"], c["bank_code"], c["card_name"], c["total_limit"],
                c["current_debt"], c["statement_debt"] if "statement_debt" in c.keys() else 0.0,
                c["installment_debt"] if "installment_debt" in c.keys() else 0.0,
                c["cutoff_day"], c["due_day"],
                c["min_payment_rate"] if "min_payment_rate" in c.keys() else 0.20,
                c["interest_rate"] if "interest_rate" in c.keys() else 4.25,
                c["color"]
            ))
            m_cid = mc.fetchone()[0]

        card_map[c["id"]] = m_cid
        print(f"  └─ Kredi Kartı Aktarıldı: {c['bank_name']} {c['card_name']} (Limit: {c['total_limit']:,.0f} TL | Borç: {c['current_debt']:,.0f} TL) -> User {m_uid}")

    # 6. Migrate Loans
    sc.execute("SELECT * FROM loans")
    s_loans = sc.fetchall()

    for l in s_loans:
        s_uid = l["user_id"]
        if s_uid not in user_map:
            continue
        m_uid = user_map[s_uid]

        mc.execute("SELECT id FROM loans WHERE user_id = ? AND loan_title = ? AND bank_name = ?", (m_uid, l["loan_title"], l["bank_name"]))
        row = mc.fetchone()
        if not row:
            mc.execute("""
                INSERT INTO loans (user_id, bank_name, bank_code, loan_title, total_amount, monthly_installment, remaining_installments, total_installments, due_day, interest_rate, color)
                OUTPUT INSERTED.id
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                m_uid, l["bank_name"], l["bank_code"] if "bank_code" in l.keys() else None,
                l["loan_title"], l["total_amount"], l["monthly_installment"],
                l["remaining_installments"], l["total_installments"],
                l["due_day"], l["interest_rate"] if "interest_rate" in l.keys() else 0.0, l["color"]
            ))
            m_lid = mc.fetchone()[0]
            print(f"  └─ Kredi Aktarıldı: {l['bank_name']} {l['loan_title']} ({l['total_amount']:,.0f} TL) -> User {m_uid}")

    # 7. Migrate Transactions
    sc.execute("SELECT * FROM transactions")
    s_txs = sc.fetchall()
    for t in s_txs:
        s_uid = t["user_id"]
        if s_uid not in user_map:
            continue
        m_uid = user_map[s_uid]
        m_acc = acc_map.get(t["account_id"])
        m_card = card_map.get(t["credit_card_id"])

        mc.execute("""
            INSERT INTO transactions (user_id, date, type, category, amount, description, payment_method, account_id, credit_card_id, is_nlp_generated, raw_input)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            m_uid, t["date"], t["type"], t["category"], t["amount"], t["description"],
            t["payment_method"], m_acc, m_card, 1 if t["is_nlp_generated"] else 0, t["raw_input"]
        ))
    print(f"✅ {len(s_txs)} adet işlem kaydı başarıyla aktarıldı.")

    # 8. Migrate Recurring Items
    sc.execute("SELECT * FROM recurring_items")
    s_recs = sc.fetchall()
    for r in s_recs:
        s_uid = r["user_id"]
        if s_uid not in user_map:
            continue
        m_uid = user_map[s_uid]
        m_acc = acc_map.get(r["account_id"])
        mc.execute("""
            INSERT INTO recurring_items (user_id, title, type, category, amount, day_of_month, account_id, is_active, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            m_uid, r["title"], r["type"], r["category"], r["amount"], r["day_of_month"],
            m_acc, 1 if r["is_active"] else 0, r["notes"]
        ))
    print(f"✅ {len(s_recs)} adet düzenli işlem kuralı aktarıldı.")

    s_conn.close()
    m_conn.close()
    print("=" * 60)
    print("🎉 TÜM VERİLER MSSQL VERİTABANINA EKSİKSİZ TAŞINDI!")
    print("=" * 60)

if __name__ == "__main__":
    run_migration()
