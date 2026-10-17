from typing import List, Dict, Any
from app.database import get_db
from app.models.schemas import SpendingPsychologyResponse, EmotionSpendingBreakdown

EMOTION_META = {
    "essential": {
        "label": "Zorunlu İhtiyaç",
        "color": "#10b981",
        "icon": "shield-check",
        "desc": "Kira, fatura, temel gıda ve sağlık gibi vazgeçilemez harcamalar"
    },
    "impulsive": {
        "label": "Dürtüsel / Stres",
        "color": "#f43f5e",
        "icon": "zap",
        "desc": "Anlık heves, stres anında rahatlama veya kampanya etkisiyle yapılan harcamalar"
    },
    "reward": {
        "label": "Kendime Ödül",
        "color": "#8b5cf6",
        "icon": "gift",
        "desc": "Yoğun çalışma veya başarı sonrası kendini ödüllendirme motivasyonlu harcamalar"
    },
    "social": {
        "label": "Sosyal / Çevre",
        "color": "#f59e0b",
        "icon": "users",
        "desc": "Arkadaş ortamı, hediye veya sosyal baskı kaynaklı harcamalar"
    },
    "investment": {
        "label": "Gelişim / Yatırım",
        "color": "#06b6d4",
        "icon": "trending-up",
        "desc": "Kitap, eğitim, spor ve geleceğe değer katan harcamalar"
    }
}

def analyze_spending_psychology(user_id: int) -> SpendingPsychologyResponse:
    """Analyzes the emotional and psychological triggers behind user transactions."""
    if not user_id:
        return SpendingPsychologyResponse(
            total_analyzed_spent=0.0,
            impulsive_ratio=0.0,
            essential_ratio=0.0,
            reward_ratio=0.0,
            social_ratio=0.0,
            investment_ratio=0.0,
            psychological_health_score=100,
            health_verdict="Veri bulunamadı",
            behavioral_insights=[],
            breakdown=[]
        )

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COALESCE(emotion_tag, 'essential') as tag, 
                   COUNT(*) as cnt, 
                   SUM(amount) as total_amt
            FROM transactions
            WHERE user_id = ? AND type = 'expense'
            GROUP BY COALESCE(emotion_tag, 'essential')
        """, (user_id,))
        rows = cursor.fetchall()

    totals_by_tag: Dict[str, Dict[str, Any]] = {k: {"count": 0, "amount": 0.0} for k in EMOTION_META}
    overall_total = 0.0

    for r in rows:
        tag = (r["tag"] or "essential").lower()
        if tag not in totals_by_tag:
            tag = "essential"
        amt = float(r["total_amt"])
        totals_by_tag[tag]["amount"] += amt
        totals_by_tag[tag]["count"] += int(r["cnt"])
        overall_total += amt

    # Calculate ratios
    breakdown: List[EmotionSpendingBreakdown] = []
    ratios: Dict[str, float] = {}

    for tag, meta in EMOTION_META.items():
        data = totals_by_tag[tag]
        ratio = round((data["amount"] / overall_total * 100), 1) if overall_total > 0 else 0.0
        ratios[tag] = ratio
        breakdown.append(EmotionSpendingBreakdown(
            tag=tag,
            tag_label=meta["label"],
            color=meta["color"],
            icon=meta["icon"],
            total_amount=round(data["amount"], 2),
            transaction_count=data["count"],
            percentage_of_total=ratio
        ))

    # Calculate Psychological Health Score (0-100)
    # Baseline 100.
    # Impulsive > 15% drops score significantly
    # Social > 25% drops score slightly
    # Investment & Essential boosts stability
    impulsive_pct = ratios.get("impulsive", 0.0)
    essential_pct = ratios.get("essential", 0.0)
    reward_pct = ratios.get("reward", 0.0)
    social_pct = ratios.get("social", 0.0)
    investment_pct = ratios.get("investment", 0.0)

    score = 100
    if impulsive_pct > 10:
        score -= int((impulsive_pct - 10) * 1.8)
    if social_pct > 25:
        score -= int((social_pct - 25) * 0.8)
    if reward_pct > 30:
        score -= int((reward_pct - 30) * 1.0)
    if investment_pct >= 5:
        score += int(investment_pct * 0.4)

    score = max(20, min(100, score))

    if score >= 85:
        verdict = "🧘 Yüksek Finansal Farkındalık (Bilinçli Tüketici)"
    elif score >= 70:
        verdict = "⚖️ Dengeli Harcama Psikolojisi"
    elif score >= 50:
        verdict = "⚠️ Dikkat: Dürtüsel Harcama Riski Yükseliyor"
    else:
        verdict = "🚨 Finansal Stres & Duygusal Harcama Baskısı"

    insights: List[str] = []
    if impulsive_pct >= 15:
        insights.append(
            f"⚡ Harcamalarınızın %{impulsive_pct:.1f}'i 'Dürtüsel / Stres' etiketiyle yapılmış. "
            "Sepete ürün eklediğinizde satın almadan önce '24 Saat Bekleme Kuralı' uygulamak harcamalarınızı ciddi oranda dizginler."
        )
    if reward_pct >= 20:
        insights.append(
            f"🎁 Kendinizi ödüllendirme harcamalarınız (%{reward_pct:.1f}) sağlıklı bir seviyede. "
            "Ancak küçük ödüllerin birikerek nakit akışını daraltmamasına dikkat edin."
        )
    if investment_pct > 0:
        insights.append(
            f"🚀 Harcamalarınızın %{investment_pct:.1f}'i geleceğe ve kişisel gelişiminize yönelik. "
            "Bu kalemler bir gider değil, uzun vadeli birer getiri yatırımıdır."
        )
    if not insights:
        insights.append(
            "🧠 Harcamalarınız ağırlıklı olarak temel zorunlu ihtiyaçlardan oluşuyor. "
            "Bütçenizin kontrolü tamamen elinizde görünüyor."
        )

    return SpendingPsychologyResponse(
        total_analyzed_spent=round(overall_total, 2),
        impulsive_ratio=impulsive_pct,
        essential_ratio=essential_pct,
        reward_ratio=reward_pct,
        social_ratio=social_pct,
        investment_ratio=investment_pct,
        psychological_health_score=score,
        health_verdict=verdict,
        behavioral_insights=insights,
        breakdown=breakdown
    )
