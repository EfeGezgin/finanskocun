import base64
import httpx
from typing import Optional, Dict, Any
from fastapi import APIRouter, Request, Response, Depends, HTTPException, Query, UploadFile, File, Form
from app.routers.auth import get_current_user
from app.services.bot_service import (
    generate_pairing_code,
    process_bot_message,
    download_telegram_file,
    get_telegram_bot_token,
    get_app_setting,
    set_app_setting,
    sync_telegram_webhook,
    pair_bot_user,
    pair_direct,
    log_bot_message
)
from app.database import get_db

router = APIRouter(prefix="/api/bot", tags=["Bot Integration & NLP"])

@router.get("/status")
def get_bot_status(request: Request):
    """Returns the current bot integration status, webhook endpoints, and active configuration."""
    bot_token = get_telegram_bot_token()
    bot_username = get_app_setting("telegram_bot_username")
    bot_name = get_app_setting("telegram_bot_name")
    
    base_url = str(request.base_url).rstrip("/")
    host_header = request.headers.get("host", "")
    if "trycloudflare.com" in host_header:
        base_url = f"https://{host_header}"
    else:
        try:
            from pathlib import Path
            url_file = Path(__file__).resolve().parent.parent.parent.parent / "tunnel_url.txt"
            if url_file.exists():
                file_url = url_file.read_text(encoding="utf-8").strip()
                if file_url.startswith("https://"):
                    base_url = file_url
        except Exception:
            pass

    return {
        "status": "online",
        "service": "Finans Koçun Telegram / WhatsApp Bot & NLP Gateway",
        "has_telegram_token": bool(bot_token),
        "bot_username": bot_username,
        "bot_name": bot_name,
        "bot_url": f"https://t.me/{bot_username}" if bot_username else None,
        "webhook_url": f"{base_url}/api/bot/webhook",
        "supported_platforms": ["telegram", "whatsapp", "generic_webhook"],
        "instructions": {
            "telegram_set_webhook": f"https://api.telegram.org/bot<TOKEN>/setWebhook?url={base_url}/api/bot/webhook"
        }
    }

@router.get("/webhook")
def verify_whatsapp_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token")
):
    """
    Handles Meta WhatsApp Cloud API webhook challenge verification.
    """
    if hub_mode == "subscribe" and hub_challenge:
        # Default or configured verify token
        expected_token = "finanskocun_bot_secret"
        if hub_verify_token == expected_token or not hub_verify_token:
            return Response(content=hub_challenge, media_type="text/plain")
        raise HTTPException(status_code=403, detail="Verification token mismatch")
    return {"message": "Finans Koçun Bot Webhook is active and listening for POST requests."}

@router.post("/webhook")
async def handle_bot_webhook(request: Request):
    """
    Unified Webhook for Telegram, WhatsApp, and REST Clients:
    - Parses Telegram Update (message, text, photo, voice)
    - Parses WhatsApp Meta Cloud API or Twilio format
    - Parses unified JSON payload
    - Extracts amount, category, description, and type
    - Saves transaction to database
    - Returns standardized confirmation message:
      '✅ Başarıyla eklendi! [120.00 TL] - [Kafe/Yemek] kategorisine işlendi. Günlük kalan bütçeniz: X TL'
    """
    content_type = request.headers.get("content-type", "")
    platform = "generic"
    sender_id = "default_sender"
    message_text = ""
    image_bytes = None
    token = request.headers.get("X-Bot-Token") or request.query_params.get("token")

    if "application/json" in content_type:
        try:
            payload = await request.json()
        except Exception:
            payload = {}

        # 1. Detect Telegram Update
        if "update_id" in payload or "message" in payload or "edited_message" in payload:
            platform = "telegram"
            msg = payload.get("message") or payload.get("edited_message", {})
            chat = msg.get("chat", {})
            from_user = msg.get("from", {})
            sender_id = str(chat.get("id") or from_user.get("id") or "unknown_tg")
            sender_username = from_user.get("username") or chat.get("username")
            message_text = msg.get("text") or msg.get("caption") or ""

            # Check if Telegram photo was attached
            photos = msg.get("photo")
            if photos and isinstance(photos, list) and len(photos) > 0:
                # Largest photo is the last item
                largest_photo = photos[-1]
                file_id = largest_photo.get("file_id")
                if file_id:
                    image_bytes = download_telegram_file(file_id)

        # 2. Detect Meta WhatsApp Cloud API
        elif "entry" in payload and isinstance(payload["entry"], list):
            platform = "whatsapp"
            sender_username = None
            try:
                entry = payload["entry"][0]
                changes = entry.get("changes", [{}])[0]
                value = changes.get("value", {})
                messages = value.get("messages", [{}])
                if messages:
                    first_msg = messages[0]
                    sender_id = str(first_msg.get("from", "unknown_wa"))
                    msg_type = first_msg.get("type", "text")
                    if msg_type == "text":
                        message_text = first_msg.get("text", {}).get("body", "")
            except Exception as e:
                print("WhatsApp payload extract error:", e)

        # 3. Direct Unified JSON (e.g. testing, Siri Shortcuts, or external apps)
        else:
            platform = payload.get("platform", "generic")
            sender_id = str(payload.get("sender_id") or payload.get("from") or payload.get("user_id") or "test_user")
            sender_username = payload.get("username")
            message_text = payload.get("message") or payload.get("text") or payload.get("body") or ""
            token = token or payload.get("token")
            
            # Base64 image support
            b64_img = payload.get("image_base64") or payload.get("photo_base64")
            if b64_img:
                if "," in b64_img:
                    b64_img = b64_img.split(",", 1)[1]
                try:
                    image_bytes = base64.b64decode(b64_img)
                except Exception:
                    pass

    # 4. Form-data or Twilio Webhook (application/x-www-form-urlencoded)
    else:
        form = await request.form()
        sender_username = None
        # Twilio WhatsApp: From=whatsapp:+90532..., Body=...
        twilio_from = form.get("From")
        if twilio_from:
            platform = "whatsapp"
            sender_id = str(twilio_from).replace("whatsapp:", "").strip()
            message_text = str(form.get("Body", ""))
        else:
            sender_id = str(form.get("sender_id", "default_sender"))
            message_text = str(form.get("message", form.get("text", "")))
            platform = str(form.get("platform", "generic"))

    result = process_bot_message(
        platform=platform,
        sender_id=sender_id,
        text=message_text,
        image_bytes=image_bytes,
        token=token,
        username=sender_username
    )

    # For Telegram Webhook responses, return response directly with method "sendMessage"
    return result

@router.post("/webhook/upload-receipt")
async def upload_receipt_webhook(
    file: UploadFile = File(...),
    sender_id: Optional[str] = Form("direct_upload"),
    platform: Optional[str] = Form("web_upload"),
    token: Optional[str] = Form(None)
):
    """
    Direct endpoint to upload and process a physical receipt / photo via multipart file upload.
    Extracts amount, merchant, date, saves to transactions, and returns confirmation.
    """
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Boş görsel dosyası yüklendi.")

    result = process_bot_message(
        platform=platform,
        sender_id=sender_id,
        text="Alışveriş Fişi Görseli",
        image_bytes=image_bytes,
        token=token
    )
    return result

@router.post("/generate-link-code")
def create_bot_pairing_code(current_user: dict = Depends(get_current_user)):
    """
    Generates or refreshes a personalized bot connection code (e.g. FK-8492)
    for the authenticated user to link Telegram or WhatsApp.
    """
    user_id = current_user["id"]
    code = generate_pairing_code(user_id=user_id, platform="telegram")
    return {
        "success": True,
        "code": code,
        "message": f"Bağlantı Kodunuz: {code}",
        "instructions": f"Telegram veya WhatsApp botuna '/bagla {code}' mesajını göndererek hesabınızı anında eşleştirebilirsiniz."
    }

@router.get("/pairings")
def list_user_pairings(current_user: dict = Depends(get_current_user)):
    """Lists all active Telegram and WhatsApp connections for the logged-in user."""
    user_id = current_user["id"]
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, platform, bot_user_id, pairing_code, is_verified, created_at
            FROM bot_pairings
            WHERE user_id = ? AND is_verified = 1
        """, (user_id,))
        pairings = cursor.fetchall()
        
    return {
        "user_id": user_id,
        "pairings": [
            {
                "id": p["id"],
                "platform": p["platform"],
                "sender_id": p["bot_user_id"],
                "created_at": str(p["created_at"])
            }
            for p in pairings
        ]
    }

@router.delete("/pairings/{pairing_id}")
def delete_user_pairing(pairing_id: int, current_user: dict = Depends(get_current_user)):
    """Disconnects a Telegram or WhatsApp connection."""
    user_id = current_user["id"]
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM bot_pairings WHERE id = ? AND user_id = ?", (pairing_id, user_id))
    return {"success": True, "message": "Bot bağlantısı başarıyla kaldırıldı."}

@router.post("/setup-telegram")
async def setup_telegram_bot(payload: Dict[str, Any], request: Request, current_user: dict = Depends(get_current_user)):
    """
    Validates a Telegram Bot API token via getMe, stores it in app_settings,
    and automatically registers the Telegram webhook with the active tunnel URL.
    """
    bot_token = (payload.get("bot_token") or "").strip()
    if not bot_token:
        set_app_setting("telegram_bot_token", "")
        set_app_setting("telegram_bot_username", "")
        set_app_setting("telegram_bot_name", "")
        return {"success": True, "message": "Telegram bot token kaldırıldı."}

    try:
        res = httpx.get(f"https://api.telegram.org/bot{bot_token}/getMe", timeout=12.0)
        data = res.json()
        if not data.get("ok"):
            err_msg = data.get("description", "Telegram API tokenı onaylamadı.")
            return {"success": False, "detail": f"Geçersiz Bot Token: {err_msg}"}
        
        result = data.get("result", {})
        bot_username = result.get("username", "")
        bot_name = result.get("first_name", "")
        
        set_app_setting("telegram_bot_token", bot_token)
        set_app_setting("telegram_bot_username", bot_username)
        set_app_setting("telegram_bot_name", bot_name)
        
        # Determine live webhook URL
        base_url = str(request.base_url).rstrip("/")
        host_header = request.headers.get("host", "")
        if "trycloudflare.com" in host_header:
            base_url = f"https://{host_header}"
        else:
            try:
                from pathlib import Path
                url_file = Path(__file__).resolve().parent.parent.parent.parent / "tunnel_url.txt"
                if url_file.exists():
                    file_url = url_file.read_text(encoding="utf-8").strip()
                    if file_url.startswith("https://"):
                        base_url = file_url
            except Exception:
                pass

        webhook_res = sync_telegram_webhook(tunnel_url=base_url)
        
        return {
            "success": True,
            "bot_username": bot_username,
            "bot_name": bot_name,
            "bot_url": f"https://t.me/{bot_username}",
            "webhook": webhook_res,
            "message": f"@{bot_username} botu başarıyla bağlandı ve webhook aktif edildi!"
        }
    except Exception as e:
        return {"success": False, "detail": f"Telegram bağlantı hatası: {str(e)}"}

@router.post("/pair-direct")
def pair_user_direct(payload: Dict[str, Any], current_user: dict = Depends(get_current_user)):
    """
    Directly pairs the authenticated user with a code, Telegram username (@username), or Chat ID.
    """
    identifier = (payload.get("identifier") or payload.get("code") or "").strip()
    if not identifier:
        raise HTTPException(status_code=400, detail="Lütfen bir eşleştirme kodu veya Telegram kullanıcı adı/ID girin.")
    
    user_id = current_user["id"]
    
    # Check if identifier is a pairing code format (e.g. FK-1234 or 1234)
    cleaned = identifier.upper().replace("_", "-")
    is_code = cleaned.startswith("FK-") or (len(cleaned) == 4 and cleaned.isdigit()) or (cleaned.startswith("FK") and len(cleaned) == 6)
    
    if is_code:
        result_user = pair_bot_user("telegram", f"direct_{user_id}", identifier)
        if result_user:
            return {"success": True, "message": f"{identifier} kodu ile başarıyla eşleştirildi!"}
        else:
            pair_direct(user_id, "telegram", identifier)
            return {"success": True, "message": f"{identifier} kodu hesabınız için aktifleştirildi!"}
    else:
        clean_username = identifier.lstrip("@").strip()
        pair_direct(user_id, "telegram", clean_username)
        return {"success": True, "message": f"@{clean_username} Telegram hesabı başarıyla bağlandı! Artık doğrudan bottan harcama girebilirsiniz."}
