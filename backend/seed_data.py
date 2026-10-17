import random
from datetime import date, timedelta
from app.database import get_db, init_db

def seed_demo_data(force: bool = False):
    init_db()
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Check if already seeded
        cursor.execute("SELECT COUNT(*) as cnt FROM accounts")
        if cursor.fetchone()["cnt"] > 0 and not force:
            print("Database already contains data, skipping seed.")
            return

        print("Seeding demo financial data...")
        
        # 1. Accounts
        accounts = [
            ("Garanti BBVA Vadesiz TL", "bank_checking", "TRY", 38500.0, 1.0, 1, "Garanti BBVA", "TR45 0006 2000 ...", "#10b981", "landmark"),
            ("İş Bankası Maaş Hesabı", "bank_checking", "TRY", 14800.0, 1.0, 1, "İş Bankası", "TR12 0006 4000 ...", "#3b82f6", "landmark"),
            ("Yapı Kredi Döviz (USD)", "foreign_currency", "USD", 1850.0, 35.20, 0, "Yapı Kredi", "TR88 0006 7000 ...", "#8b5cf6", "dollar-sign"),
            ("Fiziki / Banka Gram Altın", "gold", "GAU", 25.0, 3150.0, 0, "Kuveyt Türk", "TR22 0020 5000 ...", "#eab308", "coins"),
            ("Nakit Cüzdan", "cash", "TRY", 2400.0, 1.0, 1, "Cüzdan", "-", "#06b6d4", "wallet")
        ]
        cursor.executemany("""
            INSERT INTO accounts (name, type, currency, balance, exchange_rate, is_active_cash, bank_name, account_number, color, icon)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, accounts)

        # 2. Credit Cards
        cards = [
            ("Garanti BBVA", "Bonus Platinum", 90000.0, 22400.0, 10, 20, 0.20, "#10b981"),
            ("İş Bankası", "Maximum Kart", 50000.0, 8900.0, 5, 15, 0.20, "#3b82f6"),
            ("Yapı Kredi", "World Gold", 65000.0, 14500.0, 18, 28, 0.20, "#8b5cf6")
        ]
        cursor.executemany("""
            INSERT INTO credit_cards (bank_name, card_name, total_limit, current_debt, cutoff_day, due_day, min_payment_rate, color)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, cards)

        # 3. Loans
        loans = [
            ("Akbank", "İhtiyaç Kredisi", 150000.0, 6450.0, 14, 24, 15, 3.89, "#ef4444"),
            ("Ziraat Bankası", "Taşıt Kredisi", 320000.0, 9800.0, 22, 36, 25, 3.45, "#f59e0b")
        ]
        cursor.executemany("""
            INSERT INTO loans (bank_name, loan_title, total_amount, monthly_installment, remaining_installments, total_installments, due_day, interest_rate, color)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, loans)

        # 4. Recurring Items
        recurring = [
            ("Şirket Maaşı", "income", "Maaş & Gelir", 85000.0, 1, 2, 1, "Her ayın 1'inde yatan net maaş"),
            ("Ev Kirası", "expense", "Kira & Konut", 24000.0, 5, 1, 1, "Kadıköy daire kirası"),
            ("Apartman Aidatı", "expense", "Kira & Konut", 1600.0, 8, 1, 1, "Site ve kapıcı aidatı"),
            ("Turkcell Superonline Fiber", "expense", "Faturalar & Abonelikler", 480.0, 12, 1, 1, "100 Mbps ev interneti"),
            ("Netflix & Spotify Aile", "expense", "Faturalar & Abonelikler", 450.0, 17, 1, 1, "Dijital abonelikler"),
            ("Bireysel Emeklilik (BES)", "expense", "Kredi & Finans", 3500.0, 22, 1, 1, "Aylık BES birikim fonu")
        ]
        cursor.executemany("""
            INSERT INTO recurring_items (title, type, category, amount, day_of_month, account_id, is_active, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, recurring)

        # 5. Realistic Transactions (This month and last month)
        today = date.today()
        transactions = []
        
        # This month expenses (including elevated dining spend for the AI coach scenario!)
        recent_expenses = [
            (today - timedelta(days=1), "expense", "Market & Gıda", 620.0, "Migros haftalık gıda alışverişi", "credit_card", 1),
            (today - timedelta(days=2), "expense", "Yeme & İçme", 1450.0, "Nusret Burger & Arkadaş yemeği", "credit_card", 1),
            (today - timedelta(days=3), "expense", "Ulaşım & Yakıt", 1250.0, "Shell benzin dolumu", "credit_card", 2),
            (today - timedelta(days=4), "expense", "Yeme & İçme", 380.0, "Starbucks kahve & tatlı", "cash", None),
            (today - timedelta(days=5), "expense", "Giyim & Alışveriş", 2400.0, "Zara sonbahar mont", "credit_card", 3),
            (today - timedelta(days=6), "expense", "Yeme & İçme", 1850.0, "Karaköy Balıkçısı akşam yemeği", "credit_card", 1),
            (today - timedelta(days=7), "expense", "Market & Gıda", 480.0, "Carrefour manav ve kasap", "account", 1),
            (today - timedelta(days=8), "expense", "Eğlence & Sosyal", 950.0, "Biletix konser bileti", "credit_card", 2),
            (today - timedelta(days=9), "expense", "Yeme & İçme", 850.0, "Hafta sonu kahvaltısı", "account", 1),
            (today - timedelta(days=10), "expense", "Sağlık & Bakım", 720.0, "Eczane vitamin ve ilaçlar", "cash", None),
            (today - timedelta(days=11), "expense", "Yeme & İçme", 640.0, "Öğle yemeği ve tatlı", "credit_card", 1),
            (today - timedelta(days=12), "expense", "Ulaşım & Yakıt", 1100.0, "Opet yakıt ve oto yıkama", "credit_card", 2),
            (today - timedelta(days=13), "expense", "Yeme & İçme", 1200.0, "Moda İtalyan Restoranı", "credit_card", 3),
            (today - timedelta(days=14), "expense", "Teknoloji & Elektronik", 1650.0, "Logitech kablosuz klavye & mouse", "credit_card", 1),
        ]
        
        for d, t, cat, amt, desc, method, card_idx in recent_expenses:
            transactions.append((
                d.strftime("%Y-%m-%d"), t, cat, amt, desc, method, 1 if method == "account" else None, card_idx, 0, None
            ))
            
        # Add last month dining expenses (lower, so this month is ~30% higher)
        for i in range(15, 45):
            past_date = today - timedelta(days=i)
            # Last month lower dining
            if i % 4 == 0:
                transactions.append((
                    past_date.strftime("%Y-%m-%d"), "expense", "Yeme & İçme", 420.0, "Geçen ay yemek", "credit_card", None, 1, 0, None
                ))
            elif i % 5 == 0:
                transactions.append((
                    past_date.strftime("%Y-%m-%d"), "expense", "Market & Gıda", 550.0, "Geçen ay market", "account", 1, None, 0, None
                ))

        cursor.executemany("""
            INSERT INTO transactions (date, type, category, amount, description, payment_method, account_id, credit_card_id, is_nlp_generated, raw_input)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, transactions)

        print("Demo data successfully seeded!")

if __name__ == "__main__":
    seed_demo_data(force=True)
