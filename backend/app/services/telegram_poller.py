import time
import threading
import httpx
from typing import Optional
from app.services.bot_service import (
    get_telegram_bot_token,
    process_bot_message,
    download_telegram_file
)

_polling_thread: Optional[threading.Thread] = None
_stop_polling = False

def poll_telegram_updates():
    global _stop_polling
    last_offset = 0
    print("🤖 Telegram Long Polling Worker started in background...", flush=True)

    # First, remove any dangling webhook so getUpdates works cleanly
    try:
        initial_token = get_telegram_bot_token()
        if initial_token:
            httpx.post(f"https://api.telegram.org/bot{initial_token}/deleteWebhook", timeout=10.0)
    except Exception as e:
        print("Telegram deleteWebhook notice:", e, flush=True)

    while not _stop_polling:
        token = get_telegram_bot_token()
        if not token:
            time.sleep(3)
            continue

        try:
            url = f"https://api.telegram.org/bot{token}/getUpdates"
            params = {"timeout": 20, "limit": 25}
            if last_offset > 0:
                params["offset"] = last_offset

            with httpx.Client(timeout=30.0) as client:
                resp = client.get(url, params=params)
                if resp.status_code != 200:
                    time.sleep(2)
                    continue

                data = resp.json()
                if not data.get("ok"):
                    time.sleep(2)
                    continue

                updates = data.get("result", [])
                for u in updates:
                    update_id = u.get("update_id")
                    if update_id:
                        last_offset = max(last_offset, update_id + 1)

                    msg = u.get("message") or u.get("edited_message", {})
                    if not msg:
                        continue

                    chat = msg.get("chat", {})
                    from_user = msg.get("from", {})
                    sender_id = str(chat.get("id") or from_user.get("id") or "unknown_tg")
                    username = from_user.get("username") or chat.get("username")
                    message_text = msg.get("text") or msg.get("caption") or ""
                    
                    image_bytes = None
                    photos = msg.get("photo")
                    if photos and isinstance(photos, list) and len(photos) > 0:
                        largest_photo = photos[-1]
                        file_id = largest_photo.get("file_id")
                        if file_id:
                            image_bytes = download_telegram_file(file_id, bot_token=token)

                    # Process the message through our NLP engine and database recorder
                    try:
                        process_bot_message(
                            platform="telegram",
                            sender_id=sender_id,
                            text=message_text,
                            image_bytes=image_bytes,
                            username=username
                        )
                    except Exception as err:
                        print("Error processing Telegram message in poller:", err, flush=True)

        except httpx.TimeoutException:
            # Normal long-polling timeout, continue loop
            pass
        except Exception as e:
            # Graceful retry on transient network errors
            time.sleep(2)

def start_telegram_polling_thread():
    global _polling_thread, _stop_polling
    if _polling_thread and _polling_thread.is_alive():
        return _polling_thread
    _stop_polling = False
    _polling_thread = threading.Thread(target=poll_telegram_updates, daemon=True)
    _polling_thread.start()
    return _polling_thread
