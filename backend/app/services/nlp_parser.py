import re
from datetime import date, timedelta
from typing import Dict, Any, Optional
from app.database import get_db
from app.models.schemas import NLPExtractResponse, TransactionCreate
from app.services.transaction_service import create_transaction

# Category keyword dictionaries for Turkish financial intent
CATEGORY_KEYWORDS = {
    "Market & Gıda": [
        "market", "markette", "migros", "bim", "a101", "şok", "carrefour", "bakkal",
        "manav", "kasap", "şarküteri", "pazar", "gıda", "ekmek", "kahvaltılık", "süt", "su"
    ],
    "Yeme & İçme": [
        "restoran", "yemek", "lokanta", "burger", "pizza", "kebap", "döner", "köfte",
        "kafe", "kahve", "starbucks", "espresso", "latte", "tatlı", "akşam yemeği", "öğle yemeği", "kahvaltı"
    ],
    "Ulaşım & Yakıt": [
        "benzin", "mazot", "yakıt", "akaryakıt", "opet", "shell", "bp", "petrol",
        "taksi", "uber", "martı", "binbin", "otobüs", "metro", "marmaray", "otopark", "hgs", "ogs", "bilet"
    ],
    "Faturalar & Abonelikler": [
        "fatura", "elektrik", "doğalgaz", "su faturası", "internet", "turkcell", "vodafone",
        "türk telekom", "superonline", "netflix", "spotify", "youtube", "icloud", "aidat", "abonelik"
    ],
    "Kira & Konut": [
        "kira", "kirası", "ev kirası", "ev sahibi", "tadilat", "tesisat", "boya", "mobilya"
    ],
    "Kredi & Finans": [
        "kredi", "taksit", "kart borcu", "ekstre", "avans", "komisyon", "faiz"
    ],
    "Sağlık & Bakım": [
        "eczane", "ilaç", "hastane", "doktor", "muayene", "dişçi", "diş", "sağlık",
        "kuaför", "berber", "kozmetik", "gratis", "watsons"
    ],
    "Giyim & Alışveriş": [
        "giyim", "kıyafet", "ayakkabı", "pantolon", "gömlek", "mont", "zara", "mango",
        "lcw", "koton", "boyner", "trendyol", "hepsiburada", "amazon", "alışveriş"
    ],
    "Eğlence & Sosyal": [
        "sinema", "tiyatro", "konser", "biletix", "pub", "bar", "bira", "alkol",
        "oyun", "steam", "playstation", "tatil", "otel"
    ],
    "Teknoloji & Elektronik": [
        "telefon", "bilgisayar", "laptop", "tablet", "apple", "vatan", "teknosa",
        "mediamarkt", "kulaklık", "şarj", "monitor"
    ],
    "Maaş & Gelir": [
        "maaş", "maaşım", "avans", "ikramiye", "prim", "freelance", "ek gelir", "tahsilat", "gelir"
    ]
}

def clean_turkish_number(s: str) -> float:
    """Safely converts Turkish formatted number string (e.g. 5.000, 1.250,50) to float."""
    s = s.strip()
    if not s:
        return 0.0
    if '.' in s and ',' in s:
        if s.rfind(',') > s.rfind('.'):
            # European: 1.250,50 -> 1250.50
            s = s.replace('.', '').replace(',', '.')
        else:
            # US format: 1,250.50 -> 1250.50
            s = s.replace(',', '')
    elif '.' in s:
        parts = s.split('.')
        if len(parts) == 2 and len(parts[1]) == 3:
            s = s.replace('.', '')
        elif len(parts) > 2:
            s = s.replace('.', '')
    elif ',' in s:
        parts = s.split(',')
        if len(parts) == 2 and len(parts[1]) == 3:
            s = s.replace(',', '')
        elif len(parts) > 2:
            s = s.replace(',', '')
        else:
            s = s.replace(',', '.')
    try:
        return float(s)
    except Exception:
        return 0.0

def extract_financial_amount(text: str) -> float:
    """Extracts numeric financial transaction amount from Turkish natural text."""
    lowered = text.lower()
    
    # 1. "bin" multiplier (e.g. "85 bin TL", "85.5 bin")
    bin_m = re.search(r'(\d+(?:[\.,]\d+)?)\s*bin', lowered)
    if bin_m:
        val = clean_turkish_number(bin_m.group(1))
        return val * 1000.0

    # 2. "milyon" multiplier (e.g. "1.2 milyon")
    mil_m = re.search(r'(\d+(?:[\.,]\d+)?)\s*milyon', lowered)
    if mil_m:
        val = clean_turkish_number(mil_m.group(1))
        return val * 1000000.0

    # 3. Currency-adjacent amount (e.g. "5000 TL", "5000₺", "5000 lira", "1.250 TL", "1,250.50 TL")
    curr_m = re.search(r'(\d+(?:[\.,]\d+)*)\s*(?:tl|lira|₺)', lowered)
    if curr_m:
        return clean_turkish_number(curr_m.group(1))
        
    # 4. Standalone numbers with word boundaries
    num_matches = re.findall(r'\b(\d+(?:[\.,]\d+)*)\b', lowered)
    if num_matches:
        # Pick the largest or most plausible financial number (skipping 4-digit years like 2026)
        candidates = []
        for nm in num_matches:
            val = clean_turkish_number(nm)
            if val != 2025 and val != 2026:
                candidates.append(val)
        if candidates:
            return candidates[-1]

    return 0.0

def parse_turkish_financial_nlp(text: str, user_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Parses a natural language Turkish financial sentence into structured transaction data.
    Accurately classifies INCOME (Gelir), EXPENSE (Gider), and CREDIT CARD DEBT PAYOFF.
    Automatically matches user's specific credit cards and accounts from database.
    """
    cleaned = text.strip()
    lowered = cleaned.lower()

    # 1. Extract Amount
    amount = extract_financial_amount(lowered)

    # 2. Extract Date
    trans_date = date.today()
    if "dün" in lowered:
        trans_date = date.today() - timedelta(days=1)
    elif "önceki gün" in lowered or "evvelsi gün" in lowered:
        trans_date = date.today() - timedelta(days=2)
    elif "yarın" in lowered:
        trans_date = date.today() + timedelta(days=1)

    # 3. Detect Credit Card Debt Payment Intent
    debt_pay_phrases = [
        "borcunu kapattım", "borcumu kapattım", "borcu kapattım", "borç kapattım", "borçlarımı kapattım",
        "borcunu ödedim", "borcumu ödedim", "borcu ödedim", "borç ödedim", "borçlarımı ödedim",
        "kartı kapattım", "kartımı kapattım", "kart borcu", "kart borcum", "kredi kartı borcu",
        "ekstre borcunu ödedim", "ekstre borcumu ödedim", "ekstremi ödedim", "ekstremi kapattım",
        "ekstre borcunu kapattım", "ekstre borcumu kapattım", "ekstreyi ödedim", "ekstreyi kapattım",
        "kredi kartı borcunu", "kredi kartı borcumu", "kart borcumu", "kart borcunu"
    ]
    is_debt_pay = any(p in lowered for p in debt_pay_phrases) or (
        ("kart" in lowered or "kredi" in lowered) and ("ödedim" in lowered or "kapattım" in lowered or "yatırdım" in lowered)
    ) or (
        "borç" in lowered and ("ödedim" in lowered or "kapattım" in lowered or "yatırdım" in lowered)
    )

    # 4. Determine Type (Income or Expense)
    if is_debt_pay:
        is_income = False
        trans_type = "expense"
        matched_category = "Kredi & Finans"
    else:
        income_indicators = [
            "gelir", "gelirim", "gelir sağladım", "gelir elde", "ek gelir", "net gelir",
            "maaş", "maas", "maaşım", "hakediş",
            "kazandım", "kazandık", "kazanç", "para kazandım", "para kazandık",
            "para geldi", "havale geldi", "eft geldi", "iade geldi", "para girişi",
            "hesabıma geçti", "hesabıma yattı", "hesaba yattı", "bakiye yüklendi",
            "tahsil", "tahsilat", "tahsil ettim",
            "satış", "sattım", "satışı", "satış yaptım",
            "prim", "ikramiye", "avans", "burs", "harçlık", "temettü"
        ]
        income_receive_phrases = [
            "ödeme aldım", "ödememi aldım", "paramı aldım", "ücret aldım", "ücretimi aldım",
            "alacağımı aldım", "avans aldım", "harçlık aldım", "burs aldım", "prim aldım", "ikramiye aldım"
        ]
        expense_keywords = [
            "harcadım", "harcadık", "harcama", "verdim", "ödedim", "ödeme yaptım", "ödedik",
            "masraf", "gider", "faturası", "aidat", "taksit"
        ]

        has_income_phrase = any(p in lowered for p in income_receive_phrases)
        has_income_kw = any(kw in lowered for kw in income_indicators)
        has_expense_kw = any(kw in lowered for kw in expense_keywords)

        if has_income_phrase:
            is_income = True
        elif has_income_kw and not has_expense_kw:
            is_income = True
        elif has_income_kw and has_expense_kw:
            is_income = any(p in lowered for p in ["gelir", "maaş", "kazandım", "sattım", "tahsil", "burs", "prim", "ikramiye"])
        else:
            is_income = False
            
        trans_type = "income" if is_income else "expense"
        matched_category = "Maaş & Gelir" if is_income else "Diğer"

    # 5. Classify Category and Smart Description
    clean_desc = ""
    if is_debt_pay:
        clean_desc = "Kredi Kartı Borç Ödemesi"
    elif trans_type == "income":
        if "maaş" in lowered:
            matched_category = "Maaş & Gelir"
            clean_desc = "Maaş Geliri"
        elif "prim" in lowered or "ikramiye" in lowered or "avans" in lowered:
            matched_category = "Maaş & Gelir"
            clean_desc = "Prim / İkramiye Geliri"
        elif "freelance" in lowered or "proje" in lowered:
            matched_category = "Maaş & Gelir"
            clean_desc = "Freelance Proje Geliri"
        elif "satış" in lowered or "sattım" in lowered:
            matched_category = "Maaş & Gelir"
            clean_desc = "Satış Geliri"
        elif "burs" in lowered:
            matched_category = "Maaş & Gelir"
            clean_desc = "Burs Geliri"
        elif "harçlık" in lowered:
            matched_category = "Maaş & Gelir"
            clean_desc = "Harçlık"
        elif "iade" in lowered:
            matched_category = "Maaş & Gelir"
            clean_desc = "Para İadesi"
        elif "kira" in lowered and ("aldım" in lowered or "gelir" in lowered):
            matched_category = "Maaş & Gelir"
            clean_desc = "Kira Geliri"
        else:
            matched_category = "Maaş & Gelir"
            clean_desc = "Gelir Girişi"
    else:
        highest_score = 0
        for category, keywords in CATEGORY_KEYWORDS.items():
            if category == "Maaş & Gelir":
                continue
            score = sum(1 for kw in keywords if kw in lowered)
            if score > highest_score:
                highest_score = score
                matched_category = category

        if "kahve" in lowered or "starbucks" in lowered or "latte" in lowered:
            clean_desc = "Kahve"
        elif "market" in lowered or "migros" in lowered or "a101" in lowered or "bim" in lowered:
            clean_desc = "Market alışverişi"
        elif "benzin" in lowered or "yakıt" in lowered or "mazot" in lowered:
            clean_desc = "Benzin"
        elif "restoran" in lowered or "yemek" in lowered or "kebap" in lowered or "döner" in lowered or "burger" in lowered or "pizza" in lowered:
            clean_desc = "Yemek"
        elif "kira" in lowered:
            clean_desc = "Kira"
        elif "fatura" in lowered or "elektrik" in lowered or "su faturası" in lowered or "doğalgaz" in lowered:
            clean_desc = "Fatura"
        elif "eczane" in lowered or "ilaç" in lowered:
            clean_desc = "Eczane / İlaç"
        elif "taksi" in lowered or "uber" in lowered:
            clean_desc = "Taksi"
        else:
            stop_words = ["tl", "lira", "₺", "bin", "harcadım", "verdim", "ödedim", "aldım", "aldık", "yattı", "gitti", "bugün", "dün"]
            tokens = re.sub(r'\d+(?:[\.,]\d+)?', '', lowered).split()
            filtered = [t for t in tokens if t not in stop_words]
            if filtered:
                clean_desc = " ".join(filtered).capitalize()
                if len(clean_desc) > 30:
                    clean_desc = clean_desc[:27] + "..."
            else:
                clean_desc = f"{matched_category} Harcaması"

    # 6. Determine Payment Method, Specific Account or Credit Card from DB
    payment_method = "cash"
    suggested_account_id = None
    suggested_credit_card_id = None
    card_display_name = ""

    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Fetch user credit cards
            if user_id:
                cursor.execute("SELECT id, bank_name, bank_code, card_name, current_debt, statement_debt FROM credit_cards WHERE user_id = ? ORDER BY id ASC", (user_id,))
            else:
                cursor.execute("SELECT id, bank_name, bank_code, card_name, current_debt, statement_debt FROM credit_cards ORDER BY id ASC")
            cards = cursor.fetchall()

            # Fetch user accounts
            if user_id:
                cursor.execute("SELECT id, name, bank_name, is_active_cash, balance FROM accounts WHERE user_id = ? ORDER BY id ASC", (user_id,))
            else:
                cursor.execute("SELECT id, name, bank_name, is_active_cash, balance FROM accounts ORDER BY id ASC")
            accounts = cursor.fetchall()

            active_acc = next((a for a in accounts if a.get("is_active_cash") == 1), None) or (accounts[0] if accounts else None)
            if active_acc:
                suggested_account_id = active_acc["id"]

            if is_debt_pay:
                # Debt payment: money leaves account to pay off a credit card
                payment_method = "account"
                matched_card = None

                # Step 1: Match by bank or card name in user input
                for c in cards:
                    b_name = (c.get("bank_name") or "").lower()
                    c_name = (c.get("card_name") or "").lower()
                    b_code = (c.get("bank_code") or "").lower()
                    if (b_name and b_name in lowered) or (c_name and c_name in lowered) or (b_code and b_code in lowered):
                        matched_card = c
                        break

                # Step 2: If no explicit card name mentioned, pick card with active debt
                if not matched_card and cards:
                    # Prefer card with positive statement_debt, sorted descending
                    cards_with_stmt = [c for c in cards if (c.get("statement_debt") or 0) > 0]
                    if cards_with_stmt:
                        cards_with_stmt.sort(key=lambda x: float(x.get("statement_debt") or 0), reverse=True)
                        matched_card = cards_with_stmt[0]
                    else:
                        # Otherwise card with positive current_debt
                        cards_with_debt = [c for c in cards if (c.get("current_debt") or 0) > 0]
                        if cards_with_debt:
                            cards_with_debt.sort(key=lambda x: float(x.get("current_debt") or 0), reverse=True)
                            matched_card = cards_with_debt[0]
                        else:
                            matched_card = cards[0]

                if matched_card:
                    suggested_credit_card_id = matched_card["id"]
                    card_display_name = f"{matched_card.get('bank_name', '')} {matched_card.get('card_name', '')}".strip()
                    clean_desc = f"{card_display_name} Borç Ödemesi" if card_display_name else "Kredi Kartı Borç Ödemesi"

                    # If amount was not specified in message, auto-default to card's statement or current debt!
                    if amount <= 0:
                        stmt_debt = float(matched_card.get("statement_debt") or 0.0)
                        curr_debt = float(matched_card.get("current_debt") or 0.0)
                        if stmt_debt > 0:
                            amount = stmt_debt
                        elif curr_debt > 0:
                            amount = curr_debt

            elif trans_type == "expense":
                # Standard purchase: was it paid with card or cash/account?
                card_matched = False
                for c in cards:
                    b_name = (c.get("bank_name") or "").lower()
                    c_name = (c.get("card_name") or "").lower()
                    if (b_name and b_name in lowered) or (c_name and c_name in lowered):
                        payment_method = "credit_card"
                        suggested_credit_card_id = c["id"]
                        card_matched = True
                        break
                
                if not card_matched:
                    if "kredi kartı" in lowered or ("kart" in lowered and "kartal" not in lowered and "karton" not in lowered):
                        payment_method = "credit_card"
                        if cards:
                            suggested_credit_card_id = cards[0]["id"]
                    else:
                        payment_method = "account" if suggested_account_id else "cash"
            else:
                # Income: arrives to active account
                payment_method = "account" if suggested_account_id else "cash"

    except Exception as e:
        print("NLP account/card resolution notice:", e)

    explanation = (
        f"Metinden '{amount:,.2f} ₺' tutar ve '{matched_category}' kategorisi tespit edildi."
        if not is_debt_pay else
        f"{card_display_name or 'Kredi kartı'} için {amount:,.2f} ₺ borç kapatma ödemesi tespit edildi."
    )

    return {
        "success": amount > 0,
        "amount": round(amount, 2),
        "currency": "TRY",
        "category": matched_category,
        "type": trans_type,
        "date": trans_date.strftime("%Y-%m-%d"),
        "description": clean_desc,
        "payment_method": payment_method,
        "suggested_account_id": suggested_account_id,
        "suggested_credit_card_id": suggested_credit_card_id,
        "confidence": 0.98 if amount > 0 else 0.40,
        "explanation": explanation
    }

def process_nlp_and_save(text: str, auto_save: bool = False, user_id: Optional[int] = None) -> NLPExtractResponse:
    parsed = parse_turkish_financial_nlp(text, user_id=user_id)
    saved_id = None
    
    if auto_save and parsed["success"] and user_id:
        trans_create = TransactionCreate(
            date=parsed["date"],
            type=parsed["type"],
            category=parsed["category"],
            amount=parsed["amount"],
            description=parsed["description"],
            payment_method=parsed["payment_method"],
            account_id=parsed["suggested_account_id"],
            credit_card_id=parsed["suggested_credit_card_id"],
            is_nlp_generated=1,
            raw_input=text
        )
        saved = create_transaction(trans_create, user_id=user_id)
        saved_id = saved.id
        
    return NLPExtractResponse(
        success=parsed["success"],
        amount=parsed["amount"],
        currency=parsed["currency"],
        category=parsed["category"],
        type=parsed["type"],
        date=parsed["date"],
        description=parsed["description"],
        payment_method=parsed["payment_method"],
        suggested_account_id=parsed["suggested_account_id"],
        suggested_credit_card_id=parsed["suggested_credit_card_id"],
        confidence=parsed["confidence"],
        saved_transaction_id=saved_id,
        explanation=parsed["explanation"]
    )

