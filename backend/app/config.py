import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = BASE_DIR / "backend"
DATA_DIR = BACKEND_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "smartfinance.db"

# Database Configuration (MSSQL Server)
MSSQL_DRIVER = os.getenv("MSSQL_DRIVER", "ODBC Driver 17 for SQL Server")
MSSQL_SERVER = os.getenv("MSSQL_SERVER", ".\\SQLEXPRESS")
MSSQL_DATABASE = os.getenv("MSSQL_DATABASE", "SmartFinanceDB")
MSSQL_TRUSTED_CONNECTION = os.getenv("MSSQL_TRUSTED_CONNECTION", "yes")

# Financial Defaults
DEFAULT_CURRENCY = "TRY"
DEFAULT_CURRENCY_SYMBOL = "₺"

# Default Exchange Rates to TRY
DEFAULT_EXCHANGE_RATES = {
    "TRY": 1.0,
    "USD": 35.20,
    "EUR": 38.40,
    "GAU": 3150.0,  # Gram Altın (TRY)
    "BTC": 2400000.0
}

# Comprehensive Turkish Banks Catalog (Tüm Bankalar)
TURKISH_BANKS = [
    {"name": "Ziraat Bankası", "code": "ziraat", "color": "#e11d48", "icon": "landmark"},
    {"name": "Türkiye İş Bankası", "code": "isbank", "color": "#1d4ed8", "icon": "landmark"},
    {"name": "Garanti BBVA", "code": "garanti", "color": "#059669", "icon": "landmark"},
    {"name": "Yapı Kredi", "code": "yapikredi", "color": "#2563eb", "icon": "landmark"},
    {"name": "Akbank", "code": "akbank", "color": "#dc2626", "icon": "landmark"},
    {"name": "VakıfBank", "code": "vakifbank", "color": "#d97706", "icon": "landmark"},
    {"name": "Halkbank", "code": "halkbank", "color": "#0284c7", "icon": "landmark"},
    {"name": "QNB (QNB Finansbank)", "code": "qnb", "color": "#7c3aed", "icon": "landmark"},
    {"name": "DenizBank", "code": "denizbank", "color": "#0369a1", "icon": "landmark"},
    {"name": "TEB (Türk Ekonomi Bankası)", "code": "teb", "color": "#047857", "icon": "landmark"},
    {"name": "Kuveyt Türk", "code": "kuveytturk", "color": "#b45309", "icon": "landmark"},
    {"name": "Enpara.com", "code": "enpara", "color": "#9333ea", "icon": "landmark"},
    {"name": "Papara", "code": "papara", "color": "#0f172a", "icon": "wallet"},
    {"name": "Albaraka Türk", "code": "albaraka", "color": "#b91c1c", "icon": "landmark"},
    {"name": "Türkiye Finans", "code": "turkiyefinans", "color": "#15803d", "icon": "landmark"},
    {"name": "Fibabanka", "code": "fibabanka", "color": "#ea580c", "icon": "landmark"},
    {"name": "ING Türkiye", "code": "ing", "color": "#f97316", "icon": "landmark"},
    {"name": "Şekerbank", "code": "sekerbank", "color": "#16a34a", "icon": "landmark"},
    {"name": "Odeabank", "code": "odeabank", "color": "#eab308", "icon": "landmark"},
    {"name": "Burgan Bank", "code": "burgan", "color": "#0284c7", "icon": "landmark"},
    {"name": "Alternatif Bank", "code": "alternatif", "color": "#dc2626", "icon": "landmark"},
    {"name": "Aktif Bank", "code": "aktifbank", "color": "#4f46e5", "icon": "landmark"},
    {"name": "Hayat Finans", "code": "hayatfinans", "color": "#0d9488", "icon": "landmark"},
    {"name": "Anadolubank", "code": "anadolubank", "color": "#d97706", "icon": "landmark"},
    {"name": "Paycell", "code": "paycell", "color": "#0284c7", "icon": "wallet"},
    {"name": "İninal", "code": "ininal", "color": "#dc2626", "icon": "wallet"},
    {"name": "Diğer / Özel Banka", "code": "other", "color": "#64748b", "icon": "landmark"}
]

# Transaction Categories
CATEGORIES = [
    {"name": "Market & Gıda", "icon": "shopping-cart", "type": "expense"},
    {"name": "Yeme & İçme", "icon": "utensils", "type": "expense"},
    {"name": "Ulaşım & Yakıt", "icon": "car", "type": "expense"},
    {"name": "Kira & Konut", "icon": "home", "type": "expense"},
    {"name": "Faturalar & Abonelikler", "icon": "receipt", "type": "expense"},
    {"name": "Kredi & Finans", "icon": "credit-card", "type": "expense"},
    {"name": "Sağlık & Bakım", "icon": "heart-pulse", "type": "expense"},
    {"name": "Giyim & Alışveriş", "icon": "shopping-bag", "type": "expense"},
    {"name": "Eğlence & Sosyal", "icon": "film", "type": "expense"},
    {"name": "Teknoloji & Elektronik", "icon": "laptop", "type": "expense"},
    {"name": "Maaş & Gelir", "icon": "banknote", "type": "income"},
    {"name": "Yatırım & Ek Gelir", "icon": "trending-up", "type": "income"},
    {"name": "Diğer", "icon": "more-horizontal", "type": "expense"}
]

# AI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
