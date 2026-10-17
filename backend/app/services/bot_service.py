import os
import re
import json
import random
import string
import base64
from datetime import datetime, date
from typing import Dict, Any, Optional, List

import httpx
from app.database import get_db
from app.models.schemas import TransactionCreate
from app.services.transaction_service import create_transaction
from app.services.simulation_engine import run_cash_flow_simulation
from app.services.nlp_parser import parse_turkish_financial_nlp
from app.services.vision_service import process_receipt_image

def get_app_setting(key: str) -> Optional[str]:
    """Retrieves an application setting from database."""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT [value] FROM app_settings WHERE [key] = ?", (key,))
            row = cursor.fetchone()
            if row:
                return row["value"] if isinstance(row, dict) else row[0]
    except Exception:
        pass
    return None

def set_app_setting(key: str, value: str):
    """Sets or updates an application setting in database."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT [key] FROM app_settings WHERE [key] = ?", (key,))
        if cursor.fetchone():
            cursor.execute("UPDATE app_settings SET [value] = ? WHERE [key] = ?", (value, key))
        else:
            cursor.execute("INSERT INTO app_settings ([key], [value]) VALUES (?, ?)", (key, value))

def get_telegram_bot_token() -> Optional[str]:
    """Retrieves Telegram bot token from environment or database settings."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if token:
        return token
    return get_app_setting("telegram_bot_token")

def sync_telegram_webhook(tunnel_url: Optional[str] = None) -> Dict[str, Any]:
    """Registers or updates Telegram bot webhook with current live tunnel URL."""
    token = get_telegram_bot_token()
    if not token:
        return {"success": False, "message": "Telegram bot token henüz yapılandırılmadı."}
    
    if not tunnel_url:
        try:
            from pathlib import Path
            url_file = Path(__file__).resolve().parent.parent.parent.parent / "tunnel_url.txt"
            if url_file.exists():
                tunnel_url = url_file.read_text(encoding="utf-8").strip()
        except Exception:
            pass
            
    if not tunnel_url or not tunnel_url.startswith("https://"):
        return {"success": False, "message": "Geçerli bir HTTPS tünel adresi bulunamadı."}
        
    webhook_url = f"{tunnel_url.rstrip('/')}/api/bot/webhook"
    try:
        url = f"https://api.telegram.org/bot{token}/setWebhook"
        res = httpx.post(url, json={"url": webhook_url}, timeout=12.0)
        data = res.json()
        if data.get("ok"):
            return {
                "success": True,
                "webhook_url": webhook_url,
                "description": data.get("description", "Webhook başarıyla kuruldu.")
            }
        return {"success": False, "error": data.get("description", "Bilinmeyen Telegram hatası")}
    except Exception as e:
        return {"success": False, "error": str(e)}

def generate_pairing_code(user_id: int, platform: str = "telegram") -> str:
    """Generates a memorable 6-character linking code (e.g. FK-8492) for user bot pairing."""
    digits = ''.join(random.choices(string.digits, k=4))
    code = f"FK-{digits}"
    pending_id = f"pending_{user_id}_{digits}"
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM bot_pairings WHERE platform = ? AND bot_user_id = ?", (platform, pending_id))
        row = cursor.fetchone()
        if row:
            cursor.execute("UPDATE bot_pairings SET pairing_code = ? WHERE platform = ? AND bot_user_id = ?", (code, platform, pending_id))
        else:
            cursor.execute("""
                INSERT INTO bot_pairings (user_id, platform, bot_user_id, pairing_code, is_verified)
                VALUES (?, ?, ?, ?, 0)
            """, (user_id, platform, pending_id, code))
    return code

def pair_bot_user(platform: str, bot_user_id: str, code: str) -> Optional[int]:
    """Verifies a pairing code and maps the platform sender ID (e.g. chat_id) to the user."""
    code_clean = code.strip().upper().replace("_", "-")
    if not code_clean.startswith("FK-") and not code_clean.startswith("FK"):
        code_clean = f"FK-{code_clean}"
    elif code_clean.startswith("FK") and not code_clean.startswith("FK-"):
        code_clean = f"FK-{code_clean[2:]}"

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, id FROM bot_pairings WHERE UPPER(pairing_code) = ?", (code_clean,))
        row = cursor.fetchone()
        if not row:
            # Also try without FK- prefix
            bare_code = code_clean.replace("FK-", "")
            cursor.execute("SELECT user_id, id FROM bot_pairings WHERE UPPER(pairing_code) LIKE ?", (f"%{bare_code}%",))
            row = cursor.fetchone()

        if row:
            user_id = row["user_id"] if isinstance(row, dict) else row[0]
            # Link this actual bot_user_id to the user
            cursor.execute("SELECT id FROM bot_pairings WHERE platform = ? AND bot_user_id = ?", (platform, str(bot_user_id)))
            existing = cursor.fetchone()
            if existing:
                cursor.execute("""
                    UPDATE bot_pairings SET user_id = ?, pairing_code = ?, is_verified = 1
                    WHERE platform = ? AND bot_user_id = ?
                """, (user_id, code_clean, platform, str(bot_user_id)))
            else:
                cursor.execute("""
                    INSERT INTO bot_pairings (user_id, platform, bot_user_id, pairing_code, is_verified)
                    VALUES (?, ?, ?, ?, 1)
                """, (user_id, platform, str(bot_user_id), code_clean))
            return user_id
    return None

def pair_direct(user_id: int, platform: str, bot_user_id: str) -> bool:
    """Directly links a user with a Telegram username, chat_id, or phone number from within the app."""
    clean_id = str(bot_user_id).strip()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM bot_pairings WHERE platform = ? AND bot_user_id = ?", (platform, clean_id))
        existing = cursor.fetchone()
        if existing:
            cursor.execute("""
                UPDATE bot_pairings SET user_id = ?, is_verified = 1
                WHERE platform = ? AND bot_user_id = ?
            """, (user_id, platform, clean_id))
        else:
            cursor.execute("""
                INSERT INTO bot_pairings (user_id, platform, bot_user_id, pairing_code, is_verified)
                VALUES (?, ?, ?, 'DIRECT_LINK', 1)
            """, (user_id, platform, clean_id))
    return True

def resolve_user_for_bot(platform: str, sender_id: str, token: Optional[str] = None, username: Optional[str] = None) -> Optional[int]:
    """
    Finds the user_id associated with a bot sender:
    1. Direct session token match
    2. Bot pairings match in database (by sender_id or username)
    3. Single user default fallback (for local single-user instances)
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # 1. Check session token if provided
        if token:
            cursor.execute("SELECT user_id FROM user_sessions WHERE token = ?", (token,))
            row = cursor.fetchone()
            if row:
                return row["user_id"] if isinstance(row, dict) else row[0]

        # 2. Check bot_pairings by sender_id
        cursor.execute("""
            SELECT user_id FROM bot_pairings 
            WHERE platform = ? AND bot_user_id = ? AND is_verified = 1
        """, (platform, str(sender_id)))
        row = cursor.fetchone()
        if row:
            return row["user_id"] if isinstance(row, dict) else row[0]

        # 3. Check bot_pairings by username (e.g. "efegezgin" or "@efegezgin")
        if username:
            clean_user = username.lstrip("@").strip()
            cursor.execute("""
                SELECT user_id FROM bot_pairings 
                WHERE platform = ? AND (bot_user_id = ? OR bot_user_id = ?) AND is_verified = 1
            """, (platform, clean_user, f"@{clean_user}"))
            row = cursor.fetchone()
            if row:
                user_id = row["user_id"] if isinstance(row, dict) else row[0]
                try:
                    cursor.execute("""
                        INSERT INTO bot_pairings (user_id, platform, bot_user_id, pairing_code, is_verified)
                        VALUES (?, ?, ?, 'AUTO_LINKED', 1)
                    """, (user_id, platform, str(sender_id)))
                except Exception:
                    pass
                return user_id

        # 4. If there is exactly one user registered, fallback to that user for ease of testing
        cursor.execute("SELECT id FROM users")
        users = cursor.fetchmany(2)
        if len(users) == 1:
            default_user_id = users[0]["id"] if isinstance(users[0], dict) else users[0][0]
            try:
                cursor.execute("SELECT id FROM bot_pairings WHERE platform = ? AND bot_user_id = ?", (platform, str(sender_id)))
                if not cursor.fetchone():
                    cursor.execute("""
                        INSERT INTO bot_pairings (user_id, platform, bot_user_id, is_verified)
                        VALUES (?, ?, ?, 1)
                    """, (default_user_id, platform, str(sender_id)))
            except Exception:
                pass
            return default_user_id

    return None

def get_user_daily_remaining_budget(user_id: int) -> float:
    """Calculates user's remaining safe daily discretionary budget via simulation engine."""
    try:
        sim = run_cash_flow_simulation(user_id=user_id)
        return float(sim.recommended_max_daily_spend)
    except Exception as e:
        print("Error getting daily budget for bot:", e)
        return 0.0

def log_bot_message(user_id: Optional[int], platform: str, sender_id: str, message_text: str, reply_text: str, status: str = "success"):
    """Records bot interaction in bot_logs table."""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO bot_logs (user_id, platform, sender_id, message_text, reply_text, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, platform, str(sender_id), message_text[:500], reply_text[:500], status))
    except Exception:
        pass

def send_telegram_message(chat_id: str, text: str, bot_token: Optional[str] = None) -> bool:
    """Proactively sends a message to Telegram using Bot API if token is configured."""
    token = bot_token or get_telegram_bot_token()
    if not token or not chat_id:
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        resp = httpx.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }, timeout=8.0)
        if resp.status_code == 200:
            return True
        # If HTML entity parsing failed, fallback to plain text
        fallback_text = re.sub(r'<[^>]+>', '', text)
        fallback_resp = httpx.post(url, json={
            "chat_id": chat_id,
            "text": fallback_text
        }, timeout=8.0)
        return fallback_resp.status_code == 200
    except Exception as e:
        print("Telegram proactive send notice:", e)
        return False

def download_telegram_file(file_id: str, bot_token: Optional[str] = None) -> Optional[bytes]:
    """Downloads a photo or voice note file from Telegram servers."""
    token = bot_token or get_telegram_bot_token()
    if not token:
        return None
    try:
        with httpx.Client(timeout=15.0) as client:
            info_res = client.get(f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}")
            if info_res.status_code == 200:
                file_path = info_res.json()["result"]["file_path"]
                file_res = client.get(f"https://api.telegram.org/file/bot{token}/{file_path}")
                if file_res.status_code == 200:
                    return file_res.content
    except Exception as e:
        print("Telegram download file notice:", e)
    return None

def process_bot_message(
    platform: str,
    sender_id: str,
    text: Optional[str] = None,
    image_bytes: Optional[bytes] = None,
    token: Optional[str] = None,
    user_id_override: Optional[int] = None,
    username: Optional[str] = None
) -> Dict[str, Any]:
    """
    Main Bot Message Handler (Telegram, WhatsApp, or Generic HTTP Webhook):
    1. Resolves / verifies user account
    2. Handles commands (/start, /durum, /bagla, /yardim)
    3. Analyzes Receipt Photo (OCR/Vision) OR Text (NLP)
    4. Automatically saves transaction to transactions table
    5. Formats exact confirmation message with remaining daily budget
    """
    raw_text = (text or "").strip()
    user_id = user_id_override or resolve_user_for_bot(platform, sender_id, token, username=username)

    # 1. Handle Account Pairing Command
    # Matches: /start FK-8492, /bagla FK-8492, /link FK-8492, FK-8492, 8492
    link_match = re.search(r'(?:/start|/bagla|/link|bagla|link)?\s*(FK[-_]?\d{4}|\b\d{4}\b)', raw_text, re.IGNORECASE)
    is_explicit_link = (
        link_match and (
            raw_text.startswith("/") or
            "bagla" in raw_text.lower() or
            "link" in raw_text.lower() or
            raw_text.upper().startswith("FK") or
            re.fullmatch(r'\d{4}', raw_text.strip())
        )
    )

    if is_explicit_link:
        code = link_match.group(1).upper().replace("_", "-")
        if not code.startswith("FK-") and not code.startswith("FK"):
            code = f"FK-{code}"
        elif code.startswith("FK") and not code.startswith("FK-"):
            code = f"FK-{code[2:]}"

        paired_user_id = pair_bot_user(platform, sender_id, code)
        if paired_user_id:
            reply = (
                "🎉 <b>Hesabınız Başarıyla Bağlandı!</b>\n\n"
                "Finans Koçun asistanınız artık aktif. Harcamalarınızı doğrudan buraya yazabilir veya fiş fotoğrafı gönderebilirsiniz.\n\n"
                "📌 <b>Örnek Harcama Girişleri:</b>\n"
                "• <i>Kahveye 120 lira verdim</i>\n"
                "• <i>Markette 750 TL harcadım</i>\n"
                "• <i>Benzin aldım 1500 tl</i>\n"
                "• <i>Maaşım yattı 85000 TL</i>\n"
                "• 📸 <i>Fiş/fatura fotoğrafı göndererek otomatik okutma</i>"
            )
            log_bot_message(paired_user_id, platform, sender_id, raw_text, reply, "paired")
            if platform == "telegram":
                send_telegram_message(sender_id, reply)
            return {
                "success": True,
                "reply": reply,
                "method": "sendMessage",
                "chat_id": sender_id,
                "text": reply
            }
        else:
            reply = "❌ <b>Geçersiz Bağlantı Kodu!</b>\nLütfen Finans Koçun web uygulamasından aldığınız güncel kodu (Örn: <code>/bagla FK-8492</code>) girin."
            if platform == "telegram":
                send_telegram_message(sender_id, reply)
            return {"success": False, "reply": reply, "method": "sendMessage", "chat_id": sender_id, "text": reply}

    # 2. Check if user is paired
    if not user_id:
        reply = (
            "👋 <b>Finans Koçun Asistanına Hoş Geldiniz!</b>\n\n"
            "Harcamalarınızı otomatik olarak hesabınıza işleyebilmemiz için önce hesabınızı bağlamanız gerekmektedir.\n\n"
            "📌 <b>Nasıl Bağlanır?</b>\n"
            "1. Finans Koçun web uygulamasını açın.\n"
            "2. 'Telegram & WhatsApp' menüsünden bağlantı kodunuzu alın.\n"
            "3. Buraya <code>/bagla &lt;KODUNUZ&gt;</code> (Örn: <code>/bagla FK-8492</code>) şeklinde gönderin."
        )
        if platform == "telegram":
            send_telegram_message(sender_id, reply)
        return {
            "success": False,
            "requires_pairing": True,
            "reply": reply,
            "method": "sendMessage",
            "chat_id": sender_id,
            "text": reply
        }

    # 3. Handle Standard Bot Commands
    cmd = raw_text.lower()
    if cmd in ["/start", "/help", "/yardim", "yardım", "merhaba"]:
        reply = (
            "👋 <b>Finans Koçun Bot Komutları</b>\n\n"
            "Harcamalarınızı kaydetmek için serbestçe yazabilir veya fiş gönderebilirsiniz:\n\n"
            "• <i>Kahveye 120 lira verdim</i>\n"
            "• <i>Bugün markette 750 TL harcadım</i>\n"
            "• <i>Maaşım yattı 75000</i>\n"
            "• 📸 Fiş fotoğrafı göndererek otomatik okutma\n\n"
            "📊 <b>Diğer Komutlar:</b>\n"
            "• <code>/durum</code> veya <code>/kasa</code>: Güncel nakit ve günlük bütçe durumunuz\n"
            "• <code>/cikis</code>: Bu sohbeti hesabınızdan ayırır"
        )
        if platform == "telegram":
            send_telegram_message(sender_id, reply)
        return {"success": True, "reply": reply, "method": "sendMessage", "chat_id": sender_id, "text": reply}

    if cmd in ["/durum", "/kasa", "/bakiye", "kasa", "durum"]:
        daily_budget = get_user_daily_remaining_budget(user_id)
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(balance) as total_cash FROM accounts WHERE user_id = ? AND is_active_cash = 1", (user_id,))
            cash_row = cursor.fetchone()
            total_cash = float(cash_row["total_cash"]) if cash_row and cash_row["total_cash"] else 0.0

        reply = (
            f"📊 <b>Finansal Durum Raporunuz</b>\n\n"
            f"💰 <b>Aktif Likit Nakit:</b> {total_cash:,.2f} ₺\n"
            f"🎯 <b>Günlük Güvenli Harcama Limiti:</b> {daily_budget:,.0f} ₺ / gün\n\n"
            f"<i>Bütçenizi korumak için günlük harcamanızı bu limitin altında tutmaya özen gösterin.</i>"
        )
        if platform == "telegram":
            send_telegram_message(sender_id, reply)
        return {"success": True, "reply": reply, "method": "sendMessage", "chat_id": sender_id, "text": reply}

    if cmd in ["/cikis", "/ayril"]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM bot_pairings WHERE platform = ? AND bot_user_id = ?", (platform, str(sender_id)))
        reply = "👋 Hesabınızın bu botla olan bağlantısı kesildi. Yeniden bağlanmak istediğinizde kodunuzu gönderebilirsiniz."
        if platform == "telegram":
            send_telegram_message(sender_id, reply)
        return {"success": True, "reply": reply, "method": "sendMessage", "chat_id": sender_id, "text": reply}

    # 4. Process Receipt Image (Vision / OCR)
    extracted_data = None
    if image_bytes and len(image_bytes) > 20:
        vision_result = process_receipt_image(image_bytes)
        if vision_result and vision_result.get("success"):
            extracted_data = vision_result
        else:
            err_msg = vision_result.get("error", "Fiş üzerindeki tutar okunamadı.")
            reply = f"⚠️ <b>Fiş Okunamadı:</b> {err_msg}\nLütfen fişin net bir fotoğrafını çekin veya tutarı metin olarak yazın."
            if platform == "telegram":
                send_telegram_message(sender_id, reply)
            return {"success": False, "reply": reply, "method": "sendMessage", "chat_id": sender_id, "text": reply}

    # 5. Process Text via NLP Parser
    if not extracted_data and raw_text:
        nlp_result = parse_turkish_financial_nlp(raw_text, user_id=user_id)
        if nlp_result and nlp_result.get("success") and nlp_result.get("amount", 0) > 0:
            extracted_data = nlp_result
        else:
            reply = (
                "⚠️ <b>Harcama Tutarı Anlaşılamadı</b>\n\n"
                "Lütfen tutarı ve harcama yerini belirterek tekrar yazın.\n"
                "Örnek: <i>'Kahveye 120 lira verdim'</i> veya <i>'Markette 750 TL harcadım'</i>\n"
                "Borç kapatmak için: <i>'Kredi kartı borcunu kapattım 1500 TL'</i>"
            )
            if platform == "telegram":
                send_telegram_message(sender_id, reply)
            return {"success": False, "reply": reply, "method": "sendMessage", "chat_id": sender_id, "text": reply}

    # 6. Save Transaction to Database
    if extracted_data and extracted_data.get("amount", 0) > 0:
        amount = float(extracted_data["amount"])
        category = extracted_data.get("category", "Diğer")
        description = extracted_data.get("description") or raw_text[:50] or "Harcama"
        trans_type = extracted_data.get("type", "expense")
        trans_date = extracted_data.get("date") or date.today().strftime("%Y-%m-%d")
        payment_method = extracted_data.get("payment_method", "cash")
        suggested_account_id = extracted_data.get("suggested_account_id")
        suggested_credit_card_id = extracted_data.get("suggested_credit_card_id")

        trans_create = TransactionCreate(
            date=trans_date,
            type=trans_type,
            category=category,
            amount=amount,
            description=description,
            payment_method=payment_method,
            account_id=suggested_account_id,
            credit_card_id=suggested_credit_card_id,
            is_nlp_generated=1,
            raw_input=raw_text or "Fiş Görseli"
        )
        saved_trans = create_transaction(trans_create, user_id=user_id)

        # 7. Calculate Updated Daily Remaining Budget
        daily_budget = get_user_daily_remaining_budget(user_id)

        # 8. User Feedback Format (Debt Payment vs Income vs Expense):
        is_debt_payment = (
            category in ["Kredi & Finans", "Borç Ödemesi"] or
            "borç" in description.lower() or
            "kapattım" in description.lower() or
            "kredi kartı" in description.lower()
        ) and suggested_credit_card_id and trans_type == "expense"

        if is_debt_payment:
            card_title = "Kredi Kartı"
            rem_debt = 0.0
            rem_cash = 0.0
            try:
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT card_name, bank_name, current_debt, statement_debt FROM credit_cards WHERE id = ?", (suggested_credit_card_id,))
                    c_row = cursor.fetchone()
                    if c_row:
                        card_title = f"{c_row.get('bank_name', '')} {c_row.get('card_name', '')}".strip()
                        rem_debt = float(c_row.get("current_debt") or 0.0)
                    cursor.execute("SELECT SUM(balance) as total_cash FROM accounts WHERE user_id = ? AND is_active_cash = 1", (user_id,))
                    cash_row = cursor.fetchone()
                    if cash_row and cash_row.get("total_cash"):
                        rem_cash = float(cash_row["total_cash"])
            except Exception as e:
                print("Bot debt feedback query notice:", e)

            reply_message = (
                f"💳 <b>Kredi Kartı Borcu Başarıyla Ödendi!</b>\n\n"
                f"🏦 <b>Kart:</b> {card_title}\n"
                f"➖ <b>Ödenen Tutar:</b> -{amount:,.2f} TL\n"
                f"📉 <b>Kalan Kart Borcu:</b> {rem_debt:,.2f} TL\n"
                f"💰 <b>Kalan Likit Nakit:</b> {rem_cash:,.2f} TL\n"
                f"🎯 <b>Günlük Güvenli Harcama Limitiniz:</b> {daily_budget:,.0f} TL / gün"
            )
        elif trans_type == "income":
            reply_message = (
                f"💰 <b>Gelir Başarıyla Eklendi!</b>\n\n"
                f"➕ <b>Tutar:</b> +{amount:,.2f} TL\n"
                f"📁 <b>Kategori:</b> {category}\n"
                f"📝 <b>Açıklama:</b> {description}\n"
                f"📈 <b>Kasa Durumu:</b> Bakiyeniz artırıldı!\n"
                f"🎯 <b>Günlük Güvenli Harcama Limitiniz:</b> {daily_budget:,.0f} TL / gün"
            )
        else:
            reply_message = (
                f"✅ <b>Harcama Başarıyla Eklendi!</b>\n\n"
                f"➖ <b>Tutar:</b> -{amount:,.2f} TL\n"
                f"📁 <b>Kategori:</b> {category}\n"
                f"📝 <b>Açıklama:</b> {description}\n"
                f"🎯 <b>Günlük Kalan Bütçeniz:</b> {daily_budget:,.0f} TL"
            )

        log_bot_message(user_id, platform, sender_id, raw_text or "Fiş Görseli", reply_message, "success")

        if platform == "telegram":
            send_telegram_message(sender_id, reply_message)

        return {
            "success": True,
            "reply": reply_message,
            "amount": amount,
            "category": category,
            "description": description,
            "type": trans_type,
            "daily_remaining_budget": daily_budget,
            "transaction_id": saved_trans.id,
            "method": "sendMessage",
            "chat_id": sender_id,
            "text": reply_message
        }

    reply = "⚠️ İşlem gerçekleştirilemedi. Lütfen geçerli bir harcama metni veya fiş görseli gönderin."
    if platform == "telegram":
        send_telegram_message(sender_id, reply)
    return {"success": False, "reply": reply, "method": "sendMessage", "chat_id": sender_id, "text": reply}
