import os
import sys
import uvicorn
from pathlib import Path

# Fix Windows console encoding for UTF-8 / emojis
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.database import init_db
from seed_data import seed_demo_data

def main():
    print("=" * 60)
    print("🚀 Finans Koçun (Akıllı Kişisel Finans Asistanı)")
    print("=" * 60)
    
    # 1. Initialize Microsoft SQL Server Database
    init_db()
    print("✅ Microsoft SQL Server 2022 (SmartFinanceDB) bağlandı ve tablolar hazır.")
    
    print("\n🌐 Uygulama Adresleri:")
    print("👉 Web Arayüzü:     http://127.0.0.1:8000")
    print("👉 API Swagger UI:   http://127.0.0.1:8000/docs")
    print("👉 ReDoc Dökümantasyon: http://127.0.0.1:8000/redoc")
    print("=" * 60)
    print("Durdurmak için Ctrl + C tuşlarına basabilirsiniz.\n")

    # 2. Start Cloudflare Tunnel for Remote & Mobile Access
    try:
        from tunnel_manager import start_tunnel_thread
        start_tunnel_thread()
    except Exception as e:
        print("Tunnel start notice:", e)

    # 3. Start Uvicorn Server
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        app_dir=str(BACKEND_DIR)
    )

if __name__ == "__main__":
    main()
