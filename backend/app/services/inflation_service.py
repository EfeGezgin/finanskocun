from typing import List, Dict, Any
from app.database import get_db
from app.models.schemas import PersonalInflationResponse, CategoryInflationDetail

# Current category-specific annual inflation benchmarks
CATEGORY_INFLATION_BENCHMARKS = {
    "Market": 65.4,
    "Restoran & Yemek": 62.1,
    "Kira & Barınma": 74.5,
    "Faturalar": 58.0,
    "Ulaşım": 56.8,
    "Sağlık & Bakım": 52.4,
    "Eğlence & Sosyal": 45.2,
    "Giyim & Alışveriş": 34.0,
    "Eğitim & Kitap": 49.5,
    "Elektronik": 42.0,
    "Diğer": 48.6
}

OFFICIAL_ANNUAL_CPI = 48.6  # Baseline benchmark

def calculate_personal_inflation(user_id: int) -> PersonalInflationResponse:
    """Calculates user's personal inflation rate weighted by their actual category expenditures."""
    if not user_id:
        return PersonalInflationResponse(
            personal_inflation_annual_rate=OFFICIAL_ANNUAL_CPI,
            official_cpi_rate=OFFICIAL_ANNUAL_CPI,
            inflation_difference=0.0,
            purchasing_power_loss=0.0,
            primary_inflation_drivers=[],
            category_details=[],
            hedge_tips=[]
        )

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT category, SUM(amount) as total_spent
            FROM transactions
            WHERE user_id = ? AND type = 'expense'
            GROUP BY category
        """, (user_id,))
        rows = cursor.fetchall()

    category_spent: Dict[str, float] = {}
    total_expense = 0.0

    for r in rows:
        cat = r["category"]
        amt = float(r["total_spent"])
        category_spent[cat] = amt
        total_expense += amt

    # If no transactions, provide default weighted baseline
    if total_expense <= 0:
        category_spent = {"Market": 4000.0, "Kira & Barınma": 12000.0, "Faturalar": 2000.0, "Ulaşım": 2500.0}
        total_expense = sum(category_spent.values())

    details: List[CategoryInflationDetail] = []
    weighted_inflation_sum = 0.0

    for cat, amt in category_spent.items():
        weight = round(amt / total_expense, 4)
        cat_rate = CATEGORY_INFLATION_BENCHMARKS.get(cat, 48.6)
        impact = round(weight * cat_rate, 2)
        weighted_inflation_sum += impact

        details.append(CategoryInflationDetail(
            category=cat,
            weight=round(weight * 100, 1),  # in %
            spending_current_month=round(amt, 2),
            spending_prior_month=round(amt * 0.94, 2),
            category_inflation_rate=cat_rate,
            impact_points=impact
        ))

    details.sort(key=lambda x: x.impact_points, reverse=True)
    personal_rate = round(weighted_inflation_sum, 1)
    diff = round(personal_rate - OFFICIAL_ANNUAL_CPI, 1)
    purchasing_power_loss = round(- (personal_rate * 0.14), 1)

    # Top drivers
    top_drivers = [f"{d.category} (%{d.category_inflation_rate} yıllık artış)" for d in details[:2]]

    # Tips
    tips: List[str] = []
    if details:
        heaviest = details[0]
        tips.append(
            f"🛒 En yüksek bütçe payınız '%{heaviest.weight}' ile '{heaviest.category}' kategorisinde. "
            f"Bu kalemde fiyatlar ortalama %{heaviest.category_inflation_rate} arttığından kişisel enflasyonunuzu en çok burası yukarı çekiyor."
        )
    if diff > 5:
        tips.append(
            f"📈 Kişisel enflasyonunuz (%{personal_rate}), resmi TÜFE endeksinden (%{OFFICIAL_ANNUAL_CPI}) %{diff:.1f} puan daha yüksek seyrediyor. "
            "Gıda ve kira ağırlıklı harcama sepetiniz alım gücünüzü daha hızlı eritiyor."
        )
    tips.append(
        "💡 Enflasyondan korunma taktiği: Düzenli nakit birikimlerinizi vadeli mevduat, altın veya para piyasası fonlarında değerlendirerek getiri farkını telafi edebilirsiniz."
    )

    return PersonalInflationResponse(
        personal_inflation_annual_rate=personal_rate,
        official_cpi_rate=OFFICIAL_ANNUAL_CPI,
        inflation_difference=diff,
        purchasing_power_loss=purchasing_power_loss,
        primary_inflation_drivers=top_drivers,
        category_details=details,
        hedge_tips=tips
    )
