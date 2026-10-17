import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from app.database import get_db
from app.models.schemas import DetectedSubscription, SubscriptionHunterResponse

KNOWN_SUBSCRIPTION_KEYWORDS = {
    # Streaming & Media
    "netflix": ("Netflix", "Eğlence & Medya", "kolay"),
    "spotify": ("Spotify", "Eğlence & Müzik", "kolay"),
    "youtube": ("YouTube Premium", "Eğlence & Medya", "kolay"),
    "disney": ("Disney+", "Eğlence & Medya", "kolay"),
    "prime": ("Amazon Prime", "Alışveriş & Medya", "kolay"),
    "blutv": ("BluTV", "Eğlence & Medya", "kolay"),
    "exxen": ("Exxen", "Eğlence & Medya", "kolay"),
    "tod": ("TOD / beIN Connect", "Spor & Medya", "orta"),
    "gain": ("GAİN Medya", "Eğlence & Medya", "kolay"),
    "digiturk": ("Digiturk", "TV & Medya", "zor"),
    "d-smart": ("D-Smart", "TV & İnternet", "zor"),
    
    # Software & Cloud & AI
    "icloud": ("Apple iCloud", "Bulut & Depolama", "kolay"),
    "apple.com/bill": ("Apple Aboneliği", "Yazılım & Medya", "kolay"),
    "google": ("Google One / Play", "Bulut & Depolama", "kolay"),
    "chatgpt": ("ChatGPT Plus (OpenAI)", "Yapay Zeka & Araçlar", "kolay"),
    "openai": ("OpenAI API / ChatGPT", "Yapay Zeka", "kolay"),
    "github": ("GitHub Copilot / Pro", "Yazılım Geliştirme", "kolay"),
    "midjourney": ("Midjourney AI", "Yapay Zeka & Tasarım", "kolay"),
    "adobe": ("Adobe Creative Cloud", "Tasarım & Yazılım", "orta"),
    "canva": ("Canva Pro", "Tasarım & İçerik", "kolay"),
    "microsoft": ("Microsoft 365", "Ofis Yazılımları", "kolay"),
    
    # Telecom & Internet
    "turkcell": ("Turkcell Fatura", "Telekomünikasyon", "orta"),
    "vodafone": ("Vodafone Fatura", "Telekomünikasyon", "orta"),
    "türk telekom": ("Türk Telekom", "İnternet & Hat", "orta"),
    "superonline": ("Turkcell Superonline", "Ev İnterneti", "orta"),
    "kablonet": ("Türksat Kablonet", "Ev İnterneti", "orta"),
    
    # Fitness & Living
    "macfit": ("MACFit Spor Üyeliği", "Spor & Sağlık", "orta"),
    "fitness": ("Spor Salonu Üyeliği", "Spor & Sağlık", "orta"),
    "aidat": ("Bina / Site Aidatı", "Barınma & Konut", "zor"),
    "kira": ("Ev Kirası", "Barınma & Konut", "zor")
}

def detect_subscriptions(user_id: int) -> SubscriptionHunterResponse:
    """Scans past transactions and recurring rules to detect all active subscriptions,
    computes monthly and annual financial drain, and generates optimization tips."""
    if not user_id:
        return SubscriptionHunterResponse(
            total_monthly_cost=0.0,
            total_annual_cost=0.0,
            subscription_count=0,
            subscriptions=[],
            smart_tips=[]
        )

    detected_dict: Dict[str, Dict[str, Any]] = {}
    now = datetime.now()

    with get_db() as conn:
        cursor = conn.cursor()

        # 1. Check configured recurring items
        cursor.execute("""
            SELECT id, title, type, category, amount, day_of_month
            FROM recurring_items
            WHERE user_id = ? AND type = 'expense' AND is_active = 1
        """, (user_id,))
        recurring_rows = cursor.fetchall()
        for r in recurring_rows:
            title_lower = r["title"].lower()
            amount = float(r["amount"])
            matched_key = None
            category = r["category"]
            cancellation_diff = "orta"

            for kw, (official_name, cat, diff) in KNOWN_SUBSCRIPTION_KEYWORDS.items():
                if kw in title_lower:
                    matched_key = official_name
                    category = cat
                    cancellation_diff = diff
                    break
            
            if not matched_key:
                matched_key = r["title"].strip().title()

            next_due_day = min(r["day_of_month"], 28)
            next_due = now.replace(day=next_due_day)
            if next_due < now:
                next_due = (next_due + timedelta(days=32)).replace(day=next_due_day)

            detected_dict[matched_key.lower()] = {
                "id": f"rec_{r['id']}",
                "title": matched_key,
                "category": category,
                "amount": amount,
                "billing_cycle": "monthly",
                "last_paid_date": f"{now.year}-{now.month:02d}-{r['day_of_month']:02d}",
                "next_due_date": next_due.strftime("%Y-%m-%d"),
                "confidence": 0.95,
                "status": "active",
                "source": "Düzenli Kural",
                "annual_cost": round(amount * 12, 2),
                "cancellation_difficulty": cancellation_diff
            }

        # 2. Scan past transactions for subscription keywords and periodic pattern
        cursor.execute("""
            SELECT id, date, description, amount, category
            FROM transactions
            WHERE user_id = ? AND type = 'expense'
            ORDER BY date DESC
        """, (user_id,))
        transactions = cursor.fetchall()

        grouped_by_kw: Dict[str, List[Dict[str, Any]]] = {}
        for t in transactions:
            desc_lower = t["description"].lower()
            for kw, (official_name, cat, diff) in KNOWN_SUBSCRIPTION_KEYWORDS.items():
                if kw in desc_lower:
                    if official_name not in grouped_by_kw:
                        grouped_by_kw[official_name] = []
                    grouped_by_kw[official_name].append({
                        "id": t["id"],
                        "date": t["date"],
                        "amount": float(t["amount"]),
                        "category": cat,
                        "diff": diff
                    })
                    break

        # Process grouped transaction patterns
        for official_name, tx_list in grouped_by_kw.items():
            key = official_name.lower()
            if key in detected_dict:
                # Already captured via recurring item with high confidence
                continue

            latest = tx_list[0]
            avg_amount = round(sum(item["amount"] for item in tx_list) / len(tx_list), 2)
            
            try:
                last_dt = datetime.strptime(latest["date"], "%Y-%m-%d")
            except Exception:
                last_dt = now - timedelta(days=15)
            
            # Predict next billing (approx 30 days after last)
            next_billing_dt = last_dt + timedelta(days=30)
            if next_billing_dt < now:
                next_billing_dt = now + timedelta(days=12)

            detected_dict[key] = {
                "id": f"tx_{latest['id']}",
                "title": official_name,
                "category": latest["category"],
                "amount": avg_amount,
                "billing_cycle": "monthly",
                "last_paid_date": latest["date"],
                "next_due_date": next_billing_dt.strftime("%Y-%m-%d"),
                "confidence": 0.88 if len(tx_list) > 1 else 0.75,
                "status": "active",
                "source": "İşlem Geçmişi Analizi",
                "annual_cost": round(avg_amount * 12, 2),
                "cancellation_difficulty": latest["diff"]
            }

    # Compile result list
    subs_list: List[DetectedSubscription] = []
    total_monthly = 0.0

    for item in sorted(detected_dict.values(), key=lambda x: x["amount"], reverse=True):
        subs_list.append(DetectedSubscription(**item))
        total_monthly += item["amount"]

    total_annual = round(total_monthly * 12, 2)

    # Generate Smart Tips
    smart_tips = []
    if subs_list:
        streaming_subs = [s for s in subs_list if "Medya" in s.category or "Eğlence" in s.category]
        if len(streaming_subs) >= 2:
            stream_total = sum(s.amount for s in streaming_subs)
            cheapest = min(streaming_subs, key=lambda s: s.amount)
            smart_tips.append(
                f"📺 {len(streaming_subs)} adet dijital yayın aboneliğiniz var (aylık {stream_total:,.2f} ₺). "
                f"Kullanmadığınız 1 tanesini dondurarak yılda {cheapest.amount * 12:,.2f} ₺ tasarruf edebilirsiniz."
            )
        smart_tips.append(
            f"💡 Tespit edilen tüm aboneliklerin yıllık toplam maliyeti {total_annual:,.2f} ₺'dir. "
            f"Kredi kartı ekstrelerinizdeki gizli harcama kaçaklarını önlemek için düzenli kontrol edin."
        )
    else:
        smart_tips.append("🔍 Henüz düzenli bir abonelik ödemesi tespit edilmedi. Netflix, Spotify veya faturalarınızı eklediğinizde otomatik taranacaktır.")

    return SubscriptionHunterResponse(
        total_monthly_cost=round(total_monthly, 2),
        total_annual_cost=total_annual,
        subscription_count=len(subs_list),
        subscriptions=subs_list,
        smart_tips=smart_tips
    )
