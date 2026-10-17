import re
import sys
import time
import subprocess
import threading
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CLOUDFLARED_EXE = Path("C:/Users/Efe/.gemini/antigravity/scratch/cloudflared.exe")
TUNNEL_URL_FILE = BASE_DIR / "tunnel_url.txt"

def get_live_tunnel_url():
    if TUNNEL_URL_FILE.exists():
        url = TUNNEL_URL_FILE.read_text(encoding="utf-8").strip()
        if url.startswith("https://"):
            return url
    return "http://127.0.0.1:8000"

def notify_url_updated(url: str):
    try:
        backend_dir = str(BASE_DIR / "backend")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)
        from app.services.bot_service import sync_telegram_webhook
        sync_telegram_webhook(tunnel_url=url)
    except Exception as e:
        print("Webhook auto-sync notice:", e)

def is_cloudflared_running():
    try:
        out = subprocess.check_output(["tasklist", "/FI", "IMAGENAME eq cloudflared.exe"], text=True, errors="replace")
        return "cloudflared.exe" in out
    except Exception:
        return False

def run_tunnel():
    if not CLOUDFLARED_EXE.exists():
        print("cloudflared.exe not found at", CLOUDFLARED_EXE)
        return

    # If cloudflared is already active and tunnel_url.txt has an active URL, reuse it
    if is_cloudflared_running() and TUNNEL_URL_FILE.exists():
        existing_url = TUNNEL_URL_FILE.read_text(encoding="utf-8").strip()
        if existing_url.startswith("https://"):
            print(">>> REUSING ACTIVE CLOUDFLARE TUNNEL:", existing_url, flush=True)
            threading.Thread(target=notify_url_updated, args=(existing_url,), daemon=True).start()
            return

    cmd = [
        str(CLOUDFLARED_EXE),
        "tunnel",
        "--url", "http://127.0.0.1:8000",
        "--no-autoupdate"
    ]
    
    while True:
        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding="utf-8",
                errors="replace"
            )
            
            for line in proc.stdout:
                line_str = line.strip()
                if "trycloudflare.com" in line_str:
                    m = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line_str)
                    if m:
                        url = m.group(0)
                        print(">>> ACTIVE TUNNEL URL:", url, flush=True)
                        TUNNEL_URL_FILE.write_text(url, encoding="utf-8")
                        threading.Thread(target=notify_url_updated, args=(url,), daemon=True).start()
            proc.wait()
        except Exception as e:
            print("Tunnel manager error:", e, flush=True)
        time.sleep(3)

def start_tunnel_thread():
    t = threading.Thread(target=run_tunnel, daemon=True)
    t.start()
    return t

if __name__ == "__main__":
    run_tunnel()
