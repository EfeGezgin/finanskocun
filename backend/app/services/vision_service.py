import io
import re
import os
import base64
from datetime import date, datetime
from typing import Dict, Any, Optional
from PIL import Image, ImageEnhance, ImageFilter

try:
    import pytesseract
    HAS_PYTESSERACT = True
except ImportError:
    HAS_PYTESSERACT = False

try:
    import winocr
    HAS_WINOCR = True
except ImportError:
    HAS_WINOCR = False

import httpx
from app.database import get_db

KNOWN_MERCHANTS_CATEGORIES = {
    "migros": ("Market & Gıda", "Migros Market Fişi"),
    "carrefour": ("Market & Gıda", "Carrefour Market Fişi"),
    "a101": ("Market & Gıda", "A101 Market Fişi"),
    "bim": ("Market & Gıda", "BİM Market Fişi"),
    "şok": ("Market & Gıda", "ŞOK Market Fişi"),
    "sok": ("Market & Gıda", "ŞOK Market Fişi"),
    "file": ("Market & Gıda", "File Market Fişi"),
    "macrocenter": ("Market & Gıda", "Macrocenter Fişi"),
    "starbucks": ("Yeme & İçme", "Starbucks Kahve"),
    "kahve dünyası": ("Yeme & İçme", "Kahve Dünyası"),
    "espresso": ("Yeme & İçme", "Kafe Harcaması"),
    "burger king": ("Yeme & İçme", "Burger King"),
    "mcdonalds": ("Yeme & İçme", "McDonald's"),
    "tavuk dünyası": ("Yeme & İçme", "Tavuk Dünyası"),
    "köfteci yusuf": ("Yeme & İçme", "Köfteci Yusuf"),
    "shell": ("Ulaşım & Yakıt", "Shell Akaryakıt"),
    "opet": ("Ulaşım & Yakıt", "Opet Akaryakıt"),
    "bp": ("Ulaşım & Yakıt", "BP Akaryakıt"),
    "petrol ofisi": ("Ulaşım & Yakıt", "Petrol Ofisi Akaryakıt"),
    "total": ("Ulaşım & Yakıt", "Total Akaryakıt"),
    "eczane": ("Sağlık & Bakım", "Eczane Harcaması"),
    "gratis": ("Sağlık & Bakım", "Gratis Kozmetik"),
    "watsons": ("Sağlık & Bakım", "Watsons Kozmetik"),
    "rossmann": ("Sağlık & Bakım", "Rossmann"),
    "zara": ("Giyim & Alışveriş", "Zara Alışveriş"),
    "mango": ("Giyim & Alışveriş", "Mango Alışveriş"),
    "lcw": ("Giyim & Alışveriş", "LC Waikiki Alışveriş"),
    "defacto": ("Giyim & Alışveriş", "DeFacto"),
    "boyner": ("Giyim & Alışveriş", "Boyner"),
    "teknosa": ("Teknoloji & Elektronik", "Teknosa"),
    "vatan": ("Teknoloji & Elektronik", "Vatan Bilgisayar"),
    "mediamarkt": ("Teknoloji & Elektronik", "MediaMarkt"),
    "apple": ("Teknoloji & Elektronik", "Apple Store")
}

def get_gemini_api_key() -> Optional[str]:
    """Retrieves Google Gemini API key from environment or app settings."""
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if api_key:
        return api_key
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM app_settings WHERE key = 'gemini_api_key'")
            row = cursor.fetchone()
            if row:
                return row["value"] if isinstance(row, dict) else row[0]
    except Exception:
        pass
    return None

def preprocess_receipt_image(image_bytes: bytes) -> Image.Image:
    """Preprocesses receipt image with grayscale, contrast enhancement and slight sharpening."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    # Resize if too large
    max_dim = 1800
    if max(img.size) > max_dim:
        img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
    
    # Enhance contrast and sharpness for OCR
    gray = img.convert("L")
    enhancer = ImageEnhance.Contrast(gray)
    enhanced = enhancer.enhance(1.8)
    return enhanced

def extract_receipt_with_gemini_vision(image_bytes: bytes, api_key: str) -> Optional[Dict[str, Any]]:
    """Uses Google Gemini Vision API to accurately extract receipt metadata."""
    try:
        b64_img = base64.b64encode(image_bytes).decode("ascii")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        
        prompt = (
            "Bu bir alışveriş fişi veya fatura görselidir. Lütfen görseli analiz edip YALNIZCA aşağıdaki JSON formatında yanıt ver:\n"
            "{\n"
            '  "merchant": "İşletme/Mağaza adı (Örn: Migros)",\n'
            '  "total_amount": 125.50 (sayısal float),\n'
            '  "date": "YYYY-MM-DD",\n'
            '  "category": "Market & Gıda / Yeme & İçme / Ulaşım & Yakıt / Giyim & Alışveriş / Sağlık & Bakım / Diğer",\n'
            '  "description": "Kısa özet açıklama (Örn: Migros Market Alışverişi)",\n'
            '  "payment_method": "credit_card veya cash veya account"\n'
            "}\n"
            "Markdown formatlama veya fazladan hiçbir metin yazma, sadece saf JSON ver."
        )
        
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": b64_img
                        }
                    }
                ]
            }],
            "generationConfig": {
                "temperature": 0.1,
                "response_mime_type": "application/json"
            }
        }
        
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                import json
                parsed = json.loads(text.strip())
                return {
                    "success": True,
                    "amount": float(parsed.get("total_amount", 0.0)),
                    "merchant": parsed.get("merchant", "Bilinmeyen İşletme"),
                    "category": parsed.get("category", "Market & Gıda"),
                    "description": parsed.get("description", f"{parsed.get('merchant', 'Fiş')} Harcaması"),
                    "date": parsed.get("date", date.today().strftime("%Y-%m-%d")),
                    "payment_method": parsed.get("payment_method", "credit_card"),
                    "type": "expense",
                    "source": "gemini_vision"
                }
    except Exception as e:
        print("Gemini Vision receipt extract notice:", e)
    return None

def parse_receipt_text_heuristics(ocr_text: str) -> Dict[str, Any]:
    """
    Intelligent heuristic regex parser for Turkish POS receipts (Fiş / Fatura).
    Extracts total amount, date, and merchant from raw text.
    """
    lines = [line.strip() for line in ocr_text.splitlines() if line.strip()]
    lowered = ocr_text.lower()

    # 1. Extract Merchant
    merchant = "Alışveriş Fişi"
    category = "Diğer"
    for m_key, (m_cat, m_desc) in KNOWN_MERCHANTS_CATEGORIES.items():
        if m_key in lowered:
            merchant = m_desc
            category = m_cat
            break
            
    if merchant == "Alışveriş Fişi" and len(lines) > 0:
        # First non-trivial line often contains the store name
        for candidate in lines[:4]:
            if len(candidate) > 3 and not any(k in candidate.lower() for k in ["tarih", "saat", "fiş", "no:", "vergi"]):
                merchant = candidate[:35]
                break

    # 2. Extract Date (DD.MM.YYYY or DD/MM/YYYY or DD-MM-YYYY)
    extracted_date = date.today().strftime("%Y-%m-%d")
    date_match = re.search(r'(\d{2})[\./-](\d{2})[\./-](\d{2,4})', ocr_text)
    if date_match:
        d, m, y = date_match.groups()
        if len(y) == 2:
            y = f"20{y}"
        try:
            dt = datetime.strptime(f"{d}.{m}.{y}", "%d.%m.%Y").date()
            if dt <= date.today():
                extracted_date = dt.strftime("%Y-%m-%d")
        except Exception:
            pass

    # 3. Extract Amount
    # Typical receipt patterns:
    # TOPLAM *125,50
    # TOPLAM TUTAR : 450.00 TL
    # KREDI KARTI 750,00
    # KDV DAHIL TOPLAM 320,00
    amount = 0.0
    
    # Priority 1: Direct "TOPLAM" or "KREDİ KARTI" line
    toplam_matches = re.findall(r'(?:TOPLAM|TUTAR|KRED[Iİ]\s*KARTI|GENEL\s*TOPLAM|ODENEN|ÖDENEN)\s*[:\*]?\s*([0-9\.\,]+)', ocr_text, re.IGNORECASE)
    if toplam_matches:
        for match in reversed(toplam_matches):
            clean_str = match.strip().replace(" ", "").replace("*", "")
            # Normalize Turkish decimal comma
            if "," in clean_str and "." in clean_str:
                # E.g. 1.250,50
                clean_str = clean_str.replace(".", "").replace(",", ".")
            elif "," in clean_str:
                clean_str = clean_str.replace(",", ".")
            elif "." not in clean_str and len(clean_str) >= 4 and clean_str.endswith("00"):
                # If OCR dropped the dot before 00 kuruş (e.g. 15500 -> 155.00)
                clean_str = clean_str[:-2] + "." + clean_str[-2:]
            try:
                val = float(clean_str)
                if 1.0 <= val <= 250000.0:
                    amount = val
                    break
            except ValueError:
                continue

    # Priority 2: Fallback to largest currency number formatted as price in receipt
    if amount == 0.0:
        numbers = re.findall(r'(\d+[\,\.]\d{2})\s*(?:TL|₺)?', ocr_text)
        candidates = []
        for n in numbers:
            try:
                candidates.append(float(n.replace(".", "").replace(",", ".")))
            except Exception:
                pass
        if candidates:
            # The maximum item in a receipt is usually the final TOPLAM
            amount = max(candidates)

    payment_method = "credit_card" if any(k in lowered for k in ["kredi kartı", "kart", "pos", "visa", "mastercard"]) else "cash"

    return {
        "success": amount > 0,
        "amount": round(amount, 2),
        "merchant": merchant,
        "category": category,
        "description": f"{merchant} Fişi" if not "Fişi" in merchant else merchant,
        "date": extracted_date,
        "payment_method": payment_method,
        "type": "expense",
        "source": "ocr_heuristics",
        "raw_text": ocr_text[:300]
    }

def process_receipt_image(image_bytes: bytes) -> Dict[str, Any]:
    """
    Master receipt extractor pipeline:
    1. Try Gemini Vision LLM (if API key available)
    2. Try pytesseract OCR + Turkish receipt regex heuristics
    3. Return clean result or informative error message
    """
    if not image_bytes or len(image_bytes) < 10:
        return {"success": False, "error": "Geçersiz veya boş görsel verisi."}

    # 1. Try Gemini Vision LLM
    gemini_key = get_gemini_api_key()
    if gemini_key:
        vision_result = extract_receipt_with_gemini_vision(image_bytes, gemini_key)
        if vision_result and vision_result.get("amount", 0) > 0:
            return vision_result

    # 2. Try Windows Native Media OCR (winocr)
    if HAS_WINOCR:
        try:
            enhanced_img = preprocess_receipt_image(image_bytes)
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                ocr_future = pool.submit(winocr.recognize_pil_sync, enhanced_img, "tr")
                ocr_res = ocr_future.result(timeout=10.0)
            ocr_text = ocr_res.get("text", "")
            if ocr_text and len(ocr_text.strip()) > 5:
                parsed = parse_receipt_text_heuristics(ocr_text)
                if parsed["success"]:
                    parsed["source"] = "windows_native_ocr"
                    return parsed
        except Exception as winocr_err:
            print("Windows Native OCR notice:", winocr_err)

    # 3. Try Local Tesseract OCR
    ocr_text = ""
    if HAS_PYTESSERACT:
        try:
            enhanced_img = preprocess_receipt_image(image_bytes)
            # Try Turkish + English if available, or default
            try:
                ocr_text = pytesseract.image_to_string(enhanced_img, lang="tur+eng", config="--psm 6")
            except Exception:
                ocr_text = pytesseract.image_to_string(enhanced_img)
        except Exception as ocr_err:
            print("Local Tesseract notice:", ocr_err)

    if ocr_text and len(ocr_text.strip()) > 5:
        parsed = parse_receipt_text_heuristics(ocr_text)
        if parsed["success"]:
            return parsed

    # 3. If OCR found no text or Tesseract not installed, try basic sample extraction
    # or return mock for testing receipts
    return {
        "success": False,
        "amount": 0.0,
        "merchant": "Alışveriş Fişi",
        "category": "Market & Gıda",
        "description": "Fiş okunamadı veya bulanık",
        "date": date.today().strftime("%Y-%m-%d"),
        "error": "Fiş üzerindeki tutar okunamadı. Lütfen fişin net ve aydınlık bir fotoğrafını çekin veya metin olarak tutarı yazın."
    }
