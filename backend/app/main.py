import os
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database import init_db
from app.routers import accounts, credits, transactions, simulation, ai_assistant, auth, banks, admin, budgets, subscriptions, analytics, bot, notifications

app = FastAPI(
    title="Finans Koçun",
    description="Akıllı Kişisel Finans Asistanı, Nakit Akış Simülasyonu ve Bütçe Takip Sistemi",
    version="2.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(auth.router)
app.include_router(banks.router)
app.include_router(accounts.router)
app.include_router(credits.router)
app.include_router(transactions.router)
app.include_router(simulation.router)
app.include_router(ai_assistant.router)
app.include_router(admin.router)
app.include_router(budgets.router)
app.include_router(subscriptions.router)
app.include_router(analytics.router)
app.include_router(bot.router)
app.include_router(notifications.router)

@app.on_event("startup")
def on_app_startup():
    try:
        from app.services.telegram_poller import start_telegram_polling_thread
        start_telegram_polling_thread()
    except Exception as e:
        print("Telegram poller startup error:", e, flush=True)

# Healthcheck
@app.get("/api/health")
def healthcheck():
    return {"status": "ok", "app": "Finans Koçun", "version": "2.0.0"}

# Static and Frontend Serving
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
if not FRONTEND_DIR.exists():
    FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if not FRONTEND_DIR.exists():
    FRONTEND_DIR = Path.cwd() / "frontend"

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

@app.get("/manifest.json")
def serve_manifest():
    mf = FRONTEND_DIR / "manifest.json"
    if mf.exists():
        return FileResponse(str(mf), media_type="application/manifest+json")
    return {"error": "manifest not found"}

@app.get("/sw.js")
def serve_service_worker():
    sw = FRONTEND_DIR / "sw.js"
    if sw.exists():
        return FileResponse(str(sw), media_type="application/javascript")
    return {"error": "sw not found"}

@app.get("/favicon.ico")
def serve_favicon():
    fav = FRONTEND_DIR / "favicon.ico"
    if fav.exists():
        return FileResponse(str(fav), media_type="image/x-icon")
    return {"error": "favicon not found"}

@app.get("/app_icon.ico")
def serve_app_icon():
    ico = Path(__file__).resolve().parent.parent.parent / "app_icon.ico"
    if ico.exists():
        return FileResponse(str(ico), media_type="image/x-icon")
    fav = FRONTEND_DIR / "favicon.ico"
    if fav.exists():
        return FileResponse(str(fav), media_type="image/x-icon")
    return {"error": "icon not found"}

@app.get("/apple-touch-icon.png")
def serve_apple_touch_icon():
    f = FRONTEND_DIR / "apple-touch-icon.png"
    if f.exists():
        return FileResponse(str(f), media_type="image/png")
    return {"error": "apple-touch-icon not found"}

@app.get("/logo.svg")
def serve_logo_svg():
    f = FRONTEND_DIR / "logo.svg"
    if f.exists():
        return FileResponse(str(f), media_type="image/svg+xml")
    return {"error": "logo not found"}

@app.get("/")
def serve_index():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "Finans Koçun API is running. Frontend index.html not found."}

@app.post("/api/desktop/create-shortcut")
def create_desktop_shortcut():
    """Directly creates/refreshes the native Windows shortcut on the user's desktop."""
    import subprocess
    try:
        desktop_dir = Path(os.environ.get("USERPROFILE", "C:\\Users\\Efe")) / "Desktop"
        shortcut_path = desktop_dir / "Finans Koçun.lnk"
        project_dir = Path(__file__).resolve().parent.parent.parent
        app_desktop_script = project_dir / "app_desktop.py"
        icon_file = project_dir / "app_icon.ico"
        if not icon_file.exists():
            icon_file = FRONTEND_DIR / "favicon.ico"
            
        pythonw_path = Path("C:/Users/Efe/AppData/Local/Programs/Python/Python314/pythonw.exe")
        target_path = str(pythonw_path) if pythonw_path.exists() else str(project_dir / "Baslat_FinansKocun.bat")
        arguments = str(app_desktop_script) if pythonw_path.exists() else ""
        
        ps1_file = project_dir / "_temp_create_shortcut.ps1"
        ps1_content = f"""$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
$Shortcut.TargetPath = "{target_path}"
$Shortcut.Arguments = '"{arguments}"'
$Shortcut.WorkingDirectory = "{project_dir}"
$Shortcut.IconLocation = "{icon_file},0"
$Shortcut.Description = "Finans Koçun - Akıllı Kişisel Finans Asistanı"
$Shortcut.Save()
"""
        ps1_file.write_text(ps1_content, encoding="utf-8")
        try:
            subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1_file)], check=True, timeout=10)
        finally:
            if ps1_file.exists():
                ps1_file.unlink()

        try:
            import ctypes
            ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
        except Exception:
            pass
        return {
            "success": True, 
            "message": "Finans Koçun masaüstü kısayolu başarıyla oluşturuldu!",
            "path": str(shortcut_path)
        }
    except Exception as e:
        return {"success": False, "message": str(e)}

@app.get("/api/desktop/download-launcher")
def download_launcher():
    """Directly downloads the Windows launcher script."""
    launcher_bat = Path(__file__).resolve().parent.parent.parent / "Baslat_FinansKocun.bat"
    if launcher_bat.exists():
        return FileResponse(
            str(launcher_bat),
            media_type="application/octet-stream",
            filename="Finans_Kocun_Baslat.bat"
        )
    return {"error": "Launcher not found"}

@app.get("/api/mobile/apple-profile")
@app.get("/FinansKocun.mobileconfig")
def serve_apple_mobileconfig(request: Request):
    """Generates an official Apple iOS WebClip Configuration Profile with embedded 512x512 logo.
    When downloaded on an iPhone, iOS prompts to install Finans Koçun as a native home screen app!"""
    import base64
    icon_path = FRONTEND_DIR / "icon-512.png"
    icon_b64 = ""
    if icon_path.exists():
        icon_b64 = base64.b64encode(icon_path.read_bytes()).decode("ascii")

    base_url = str(request.base_url).rstrip("/")
    host_header = request.headers.get("host", "")
    if "trycloudflare.com" in host_header:
        base_url = f"https://{host_header}"
    elif "127.0.0.1" in base_url or "localhost" in base_url:
        try:
            from tunnel_manager import get_live_tunnel_url
            base_url = get_live_tunnel_url()
        except Exception:
            base_url = "https://two-broadband-music-parallel.trycloudflare.com"

    xml_profile = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>PayloadContent</key>
    <array>
        <dict>
            <key>FullScreen</key>
            <true/>
            <key>Icon</key>
            <data>{icon_b64}</data>
            <key>IsRemovable</key>
            <true/>
            <key>Label</key>
            <string>Finans Koçun</string>
            <key>PayloadDescription</key>
            <string>Finans Koçun Akıllı Finans Asistanı</string>
            <key>PayloadDisplayName</key>
            <string>Finans Koçun</string>
            <key>PayloadIdentifier</key>
            <string>com.finanskocun.webclip</string>
            <key>PayloadType</key>
            <string>com.apple.webClip.managed</string>
            <key>PayloadUUID</key>
            <string>8A7B6C5D-4E3F-2A1B-0C9D-8E7F6A5B4C3D</string>
            <key>PayloadVersion</key>
            <integer>1</integer>
            <key>Precomposed</key>
            <true/>
            <key>URL</key>
            <string>{base_url}/</string>
        </dict>
    </array>
    <key>PayloadDisplayName</key>
    <string>Finans Koçun Uygulaması</string>
    <key>PayloadIdentifier</key>
    <string>com.finanskocun.profile</string>
    <key>PayloadOrganization</key>
    <string>Finans Koçun</string>
    <key>PayloadRemovalDisallowed</key>
    <false/>
    <key>PayloadType</key>
    <string>Configuration</string>
    <key>PayloadUUID</key>
    <string>1A2B3C4D-5E6F-7A8B-9C0D-1E2F3A4B5C6D</string>
    <key>PayloadVersion</key>
    <integer>1</integer>
</dict>
</plist>"""
    return Response(
        content=xml_profile,
        media_type="application/x-apple-aspen-config",
        headers={"Content-Disposition": 'attachment; filename="Finans_Kocun.mobileconfig"'}
    )

@app.get("/api/mobile/live-url")
def get_mobile_live_url(request: Request):
    """Returns the active live URL for mobile devices to connect to."""
    host_header = request.headers.get("host", "")
    if "trycloudflare.com" in host_header:
        return {"url": f"https://{host_header}"}
    try:
        from tunnel_manager import get_live_tunnel_url
        return {"url": get_live_tunnel_url()}
    except Exception:
        return {"url": "http://127.0.0.1:8000"}

@app.get("/api/mobile/qr-code")
def generate_mobile_qr(request: Request, text: str = None):
    """Generates an emerald fintech styled QR code for instant phone scanning."""
    import io
    import qrcode
    
    target_url = text
    if not target_url:
        host_header = request.headers.get("host", "")
        if "trycloudflare.com" in host_header:
            target_url = f"https://{host_header}"
        else:
            try:
                from tunnel_manager import get_live_tunnel_url
                target_url = get_live_tunnel_url()
            except Exception:
                target_url = "https://two-broadband-music-parallel.trycloudflare.com"
            
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(target_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#00F59B", back_color="#0B0F19")
    
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")

@app.on_event("startup")
def on_startup():
    print("🚀 Finans Koçun starting up...")
    init_db()
    print("✅ Database initialized.")
    try:
        from tunnel_manager import start_tunnel_thread
        start_tunnel_thread()
        print("🌐 Cloudflare tunnel manager launched in background.")
    except Exception as e:
        print("Tunnel start notice:", e)

