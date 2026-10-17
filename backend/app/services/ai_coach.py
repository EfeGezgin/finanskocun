import json
import os
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional
from datetime import date
from app.database import get_db
from app.models.schemas import AICoachChatResponse
from app.services.account_service import get_net_worth_summary
from app.services.credit_service import get_all_credit_cards, get_all_loans
from app.services.transaction_service import get_monthly_category_comparison
from app.services.simulation_engine import run_cash_flow_simulation

def compute_financial_health_score(user_id: Optional[int] = None) -> int:
    """Computes an algorithmic financial health score between 0 and 100 based on actual metrics."""
    net_worth = get_net_worth_summary(user_id=user_id)
    cards = get_all_credit_cards(user_id=user_id)
    sim = run_cash_flow_simulation(user_id=user_id)

    # Empty data base score
    if net_worth.total_liquid_cash_try == 0 and len(cards) == 0:
        return 100  # Clean slate

    score = 70

    # 1. Liquid cash buffer
    if net_worth.total_liquid_cash_try > 30000:
        score += 15
    elif net_worth.total_liquid_cash_try > 10000:
        score += 10
    elif net_worth.total_liquid_cash_try < 2000 and net_worth.total_liquid_cash_try > 0:
        score -= 20

    # 2. Credit Card Limit Utilization
    if cards:
        avg_util = sum(c.utilization_rate for c in cards) / len(cards)
        if avg_util < 25:
            score += 10
        elif avg_util > 70:
            score -= 20
        elif avg_util > 50:
            score -= 10

    # 3. Simulation Liquidity Status
    if sim.status == "SURPLUS_SAFE":
        score += 10
    elif sim.status == "LIQUIDITY_DANGER":
        score -= 10
    elif sim.status == "DEFICIT_RISK":
        score -= 25

    return max(10, min(100, score))

def generate_financial_context(user_id: Optional[int] = None) -> Dict[str, Any]:
    net_worth = get_net_worth_summary(user_id=user_id)
    cards = get_all_credit_cards(user_id=user_id)
    loans = get_all_loans(user_id=user_id)
    sim = run_cash_flow_simulation(user_id=user_id)
    comparison = get_monthly_category_comparison(user_id=user_id)

    return {
        "net_worth": net_worth.dict(),
        "credit_cards": [c.dict() for c in cards],
        "loans": [l.dict() for l in loans],
        "cash_flow_simulation": {
            "status": sim.status,
            "projected_end_of_month": sim.projected_end_of_month_balance,
            "critical_dip_day": sim.critical_dip_day,
            "critical_dip_amount": sim.critical_dip_amount,
            "recommended_max_daily_spend": sim.recommended_max_daily_spend,
            "average_daily_spend": sim.average_daily_spend,
            "total_upcoming_credit_payments": sim.total_upcoming_credit_payments,
            "total_upcoming_loan_payments": sim.total_upcoming_loan_payments,
            "total_upcoming_fixed_bills": sim.total_upcoming_fixed_bills,
            "remaining_days_in_month": sim.remaining_days_in_month
        },
        "monthly_spending_comparison": comparison
    }

def try_external_llm(user_message: str, context: Dict[str, Any]) -> Optional[str]:
    """If OPENAI_API_KEY or GEMINI_API_KEY is available, queries external LLM."""
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        try:
            req_data = {
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Sen Finans Koçun uygulamasının kıdemli kişisel finans koçu ve bütçe danışmanısın. "
                            "Kullanıcının gerçek finansal verilerini derinlemesine analiz edip samimi, profesyonel, "
                            "yorumlayıcı ve somut öneriler içeren Türkçe cevaplar verirsin. Rakamlara atıfta bulunarak "
                            "durumu değerlendir. Markdown formatında kalın başlıklar ve maddeler kullan.\n\n"
                            f"Kullanıcı Finansal Verisi:\n{json.dumps(context, ensure_ascii=False)}"
                        )
                    },
                    {"role": "user", "content": user_message}
                ],
                "temperature": 0.7
            }
            req_obj = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=json.dumps(req_data).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {openai_key}"
                },
                method="POST"
            )
            with urllib.request.urlopen(req_obj, timeout=10) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result["choices"][0]["message"]["content"]
        except Exception:
            pass
    return None

def generate_smart_ai_reply(user_message: str, context: Dict[str, Any], user_id: Optional[int] = None) -> AICoachChatResponse:
    """Intelligent Financial Advisory Engine with multi-intent reasoning and tailored commentary."""
    lowered = user_message.lower().strip()
    sim = context["cash_flow_simulation"]
    comp = context["monthly_spending_comparison"]
    cards = context["credit_cards"]
    loans = context["loans"]
    nw = context["net_worth"]
    score = compute_financial_health_score(user_id=user_id)

    # 0. Check external LLM first if configured
    llm_reply = try_external_llm(user_message, context)
    if llm_reply:
        return AICoachChatResponse(
            reply=llm_reply,
            financial_health_score=score,
            actionable_tips=["Bütçe hedeflerini düzenli takip et.", "Haftalık harcama limitini aşma."],
            detected_intent="llm_generative"
        )

    # Clean empty account check
    if nw["total_liquid_cash_try"] == 0 and len(cards) == 0 and len(loans) == 0:
        reply = (
            "👋 **Merhaba! Ben Finans Koçun.**\n\n"
            "Şu an finansal tablonuz tertemiz görünüyor (Tüm veriler sıfırlandı).\n\n"
            "🎯 **Hızlıca Başlamak İçin 3 Basit Adım:**\n"
            "1. **Banka Hesabı Ekle**: Vadesiz mevduatınızı ve nakit paranızı girin.\n"
            "2. **Kredi Kartı Tanımla**: Kart limitinizi, hesap kesim ve son ödeme günlerini kaydedin.\n"
            "3. **Harcama Gir**: 'Gelir & Giderler' sekmesinden veya üstteki akıllı algılama kutusundan günlük harcamalarınızı ekleyin.\n\n"
            "Verilerinizi girdikçe harcama alışkanlıklarınızı analiz edecek, ay sonu nakit akışınızı simüle edecek ve size özel tasarruf tavsiyeleri üreteceğim!"
        )
        return AICoachChatResponse(
            reply=reply,
            financial_health_score=score,
            actionable_tips=[
                "Aktif banka hesaplarınızı ekleyin.",
                "Kredi kartı ekstre ve son ödeme günlerinizi kaydedin.",
                "Maaş ve kira gibi düzenli gelir/gider kurallarınızı oluşturun."
            ],
            detected_intent="empty_onboarding"
        )

    # 1. DEBT STRATEGY & CREDIT CARDS ("borç", "kredi kartı", "faiz", "nasıl öderim", "kapatmak", "asgari", "ekstre", "çığ", "kartopu")
    if any(k in lowered for k in ["borç", "kart borcu", "kredi kartı", "nasıl öderim", "kapatmak", "kapatırım", "faiz", "asgari", "ekstre"]):
        total_cc_debt = sum(c.get("statement_debt", 0) + c.get("current_debt", 0) for c in cards)
        total_loan_debt = sum(l.get("remaining_principal", 0) for l in loans)
        total_debt = total_cc_debt + total_loan_debt
        total_limit = sum(c.get("total_limit", 0) for c in cards)
        avg_util = (total_cc_debt / total_limit * 100.0) if total_limit > 0 else 0

        # Sort cards by statement debt descending
        sorted_cards = sorted(cards, key=lambda x: (x.get("statement_debt", 0) or x.get("current_debt", 0)), reverse=True)
        top_card = sorted_cards[0] if sorted_cards else None

        reply = (
            f"💳 **Kredi Kartı & Borç Kapatma Stratejisi Analizi:**\n\n"
            f"Toplam borç yükünüz **{total_debt:,.0f} ₺** seviyesinde (Kredi Kartları: **{total_cc_debt:,.0f} ₺**, Krediler: **{total_loan_debt:,.0f} ₺**).\n"
            f"Kart limit doluluğunuz: **%{avg_util:.1f}**.\n\n"
        )

        if avg_util > 60:
            reply += "⚠️ **Kritik Uyarı:** Kart limit doluluğunuz %50 eşiğini aşmış durumda. Bu durum kredi notunuzu baskılar ve yüksek faiz riski oluşturur.\n\n"

        if top_card:
            card_debt = top_card.get("statement_debt") or top_card.get("current_debt") or 0
            reply += (
                f"🎯 **Öncelikli Hedef Kartınız:**\n"
                f"• **{top_card.get('bank_name')} {top_card.get('card_name')}**: Ekstre borcu **{card_debt:,.0f} ₺** (Son ödeme: ayın {top_card.get('due_day')}. günü).\n\n"
            )

        reply += (
            "🛠️ **Koçluk Önerisi - Hangi Yöntemle Kapatmalısınız?**\n"
            "1. **Çığ Yöntemi (Matematiksel Olarak En Kârlı - Tavsiyem):**\n"
            "   Aylık %4.25 akdi faiz yükünden kurtulmak için en yüksek ekstre borcu olan kartın tamamını kapatın, diğer kartlara asgari ödeme yapın.\n"
            "2. **Asgari Ödeme Tuzağına Düşmeyin:**\n"
            "   Sadece asgari tutarı (%20) öderseniz kalan %80'lik borca bileşik faiz biner ve borcun ömrü 3 katına çıkar.\n"
            "3. **Taksitli Alışverişleri Durdurun:**\n"
            "   Mevcut kart doluluğu %30 altına inene kadar yeni taksitli harcama yapmayın."
        )

        tips = [
            f"En yüksek ekstreye sahip {top_card.get('card_name') if top_card else 'kartınızın'} borcunu son ödeme gününden önce kapatın.",
            "Asgari tutar yerine ekstre borcunun tamamını ödemeye odaklanın.",
            "Yeni ayın hesap kesim gününe kadar kartla büyük harcama yapmayın."
        ]
        return AICoachChatResponse(
            reply=reply,
            financial_health_score=score,
            actionable_tips=tips,
            detected_intent="debt_reduction_strategy"
        )

    # 2. CASH FLOW & SURVIVAL ("ay sonu", "param yetecek", "kasa", "kurtarır mıyım", "bütçe açığı", "darboğaz", "ne kadar harcayabilirim", "günlük limit")
    if any(k in lowered for k in ["ay sonu", "param yetecek", "yetir", "kasa bakiyesi", "kasada", "çıkartabilir", "darboğaz", "bütçe açığı", "günlük harca", "ne kadar harca", "kurtarır mı", "nakit akışı"]):
        status = sim["status"]
        proj = sim["projected_end_of_month"]
        dip_day = sim["critical_dip_day"]
        dip_amt = sim["critical_dip_amount"]
        rec_daily = sim["recommended_max_daily_spend"]
        avg_daily = sim["average_daily_spend"]
        rem_days = sim["remaining_days_in_month"]

        if status == "SURPLUS_SAFE":
            reply = (
                f"🟢 **Mükemmel Durumdasınız! Ay Sonunu Güvenle Artıda Kapatıyorsunuz.**\n\n"
                f"Nakit akışı simülasyonunuza göre ay sonu tahmini kasa bakiyeniz: **+{proj:,.0f} ₺**.\n\n"
                f"• Kalan Gün Sayısı: **{rem_days} gün**\n"
                f"• Güvenli Günlük Harcama Üst Sınırınız: **{rec_daily:,.0f} ₺ / gün**\n"
                f"• Mevcut Ortalama Günlük Harcamanız: **{avg_daily:,.0f} ₺ / gün**\n\n"
                f"💡 **Finansal Koç Tavsiyesi:**\n"
                f"Ay sonu öngörülen **{proj:,.0f} ₺** fazlalığı vadesiz hesapta boşta tutmak yerine para piyasası fonuna veya altın hesabına aktararak enflasyona karşı koruyun."
            )
            tips = [
                f"Günlük harcamalarınızı {rec_daily:,.0f} ₺ tavanının altında tutmaya devam edin.",
                f"Ay sonu fazlalığı olan {proj:,.0f} ₺ ile acil durum fonu oluşturun."
            ]
        elif status == "LIQUIDITY_DANGER":
            reply = (
                f"🟡 **Önemli Uyarı: Ay Sonunu Artıda Kapatıyorsunuz Ancak Ara Dönemde Likidite Darboğazı Var!**\n\n"
                f"Ay sonu toplam bakiyeniz **+{proj:,.0f} ₺** görünse de, kredi ve kart ödemelerinizin yoğunlaştığı "
                f"**{dip_day}** tarihinde kasadaki aktif nakdiniz **{dip_amt:,.0f} ₺** seviyesine kadar geriliyor!\n\n"
                f"⚠️ **Olası Risk:**\n"
                f"{dip_day} civarında beklenmeyen 1.000-2.000 TL'lik bir masraf çıkarsa eksi hesaba (KMH/Avans Hesap) girmek ve faiz ödemek zorunda kalabilirsiniz.\n\n"
                f"💡 **Eylem Planı:**\n"
                f"{dip_day} tarihine kadar keyfi harcamaları sıfırlayın ve fatura/kart ödemelerinden önce hesabınızda en az 3.000 ₺ likidite tamponu bırakın."
            )
            tips = [
                f"{dip_day} tarihinden önceki günlerde harcama yapmaktan kaçının.",
                "Yaklaşan kart ödemeleri için vadesiz hesabınızda ek nakit tutun."
            ]
        else:
            reply = (
                f"🔴 **Bütçe Açığı Alarmı: Mevcut Harcama Hızıyla Ay Sonunda Kasa Eksiye Düşüyor!**\n\n"
                f"Simülasyon motorumuz, mevcut harcama temposu devam ederse ay sonunu **-{abs(proj):,.0f} ₺** bütçe açığıyla kapatacağınızı öngörüyor.\n\n"
                f"📉 **Durum Tespiti:**\n"
                f"Ay sonuna kadar ödenecek toplam kart ve kredi borçları nakit girişlerinizin üzerinde kalıyor.\n\n"
                f"🛠️ **Acil Kurtarma Tavsiyeleri:**\n"
                f"1. Kalan {rem_days} gün boyunca günlük harcamanızı kesinlikle **{rec_daily:,.0f} ₺** seviyesine indirin.\n"
                f"2. Zorunlu olmayan dışarıda yemek, giyim ve eğlence harcamalarını yeni aya kadar dondurun.\n"
                f"3. Varsa yatırım veya döviz hesaplarınızdan bir miktar nakit takviyesi yapmayı değerlendirin."
            )
            tips = [
                f"Günlük harcama limitinizi derhal {rec_daily:,.0f} ₺ seviyesine düşürün.",
                "Yeni aya kadar kredi kartı ile harcama yapmayı bırakın."
            ]

        return AICoachChatResponse(
            reply=reply,
            financial_health_score=score,
            actionable_tips=tips,
            detected_intent="cash_flow_simulation"
        )

    # 3. SAVINGS, BUDGETING & COST CUTTING ("tasarruf", "birikim", "para biriktir", "kıs", "nereden kıs", "bütçe", "50/30/20")
    if any(k in lowered for k in ["tasarruf", "birikim", "para biriktir", "kıs", "nereden", "bütçe", "kenara koy", "50/30/20", "tavsiye"]):
        categories = comp.get("categories", [])
        sorted_cats = sorted([c for c in categories if c.get("this_month", 0) > 0], key=lambda x: x.get("this_month", 0), reverse=True)
        top_cat = sorted_cats[0] if sorted_cats else None
        second_cat = sorted_cats[1] if len(sorted_cats) > 1 else None

        reply = (
            "💰 **Kişiselleştirilmiş Tasarruf & Bütçe İyileştirme Raporu:**\n\n"
            "Harcama verilerinizi analiz ettiğimde en hızlı ve acısız tasarruf sağlayabileceğiniz alanlar:\n\n"
        )

        if top_cat:
            top_amt = top_cat.get("this_month", 0)
            savings_20 = round(top_amt * 0.20)
            reply += (
                f"1. 📌 **En Büyük Harcama Kaleminiz: {top_cat.get('category')} ({top_amt:,.0f} ₺)**\n"
                f"   Bu kalemde yalnızca **%20'lik** bir optimizasyon yaparak ayda **+{savings_20:,.0f} ₺** net birikim oluşturabilirsiniz.\n"
            )

        if second_cat:
            sec_amt = second_cat.get("this_month", 0)
            reply += f"2. 📌 **İkinci Sırada: {second_cat.get('category')} ({sec_amt:,.0f} ₺)**\n"

        reply += (
            "\n📐 **Altın Standart: 50/30/20 Bütçe Kuralını Uygulayın:**\n"
            "• **%50 Zorunlu İhtiyaçlar:** Kira, faturalar, asgari borçlar ve mutfak alışverişi.\n"
            "• **%30 Sosyal Yaşam & İstekler:** Kafe, restoran, hobiler ve tatil harcamaları.\n"
            "• **%20 Gelecek & Birikim:** Kartopu/Çığ yöntemiyle borç eritme ve acil durum fonu.\n\n"
            "💡 **Uygulama İpucu:** Maaş veya gelir yatar yatmaz önce %20'lik payı ayırıp farklı bir hesaba aktarın, kalan parayla ayı yönetin ('Önce Kendine Öde' prensibi)."
        )

        tips = [
            f"{top_cat.get('category') if top_cat else 'Temel harcamalarınızda'} %20 tasarruf hedefi koyun.",
            "Geliriniz yatar yatmaz önce birikim payını ayrı bir hesaba çekin.",
            "Haftalık harcama bütçenizi pazar akşamından planlayın."
        ]
        return AICoachChatResponse(
            reply=reply,
            financial_health_score=score,
            actionable_tips=tips,
            detected_intent="savings_strategy"
        )

    # 4. UPCOMING PAYMENTS & CALENDAR ("önümüzdeki ay", "gelecek", "en büyük masraf", "ödeme takvimi", "hangi gün")
    if any(k in lowered for k in ["önümüzdeki", "gelecek", "en büyük masraf", "ödeme takvimi", "hangi gün", "yaklaşan"]):
        upcoming_items = []
        for c in cards:
            stmt = c.get("statement_debt") or c.get("current_debt") or 0
            if stmt > 0:
                upcoming_items.append({
                    "title": f"💳 {c.get('bank_name')} {c.get('card_name')}",
                    "amount": stmt,
                    "day": c.get("due_day"),
                    "days_left": c.get("days_until_due"),
                    "type": "Kart Ekstresi"
                })
        for l in loans:
            upcoming_items.append({
                "title": f"🏦 {l.get('bank_name')} {l.get('loan_title')}",
                "amount": l.get("monthly_installment", 0),
                "day": l.get("due_day"),
                "days_left": l.get("days_until_due"),
                "type": "Kredi Taksiti"
            })

        upcoming_items = sorted(upcoming_items, key=lambda x: x["days_left"])

        reply = "📅 **Yaklaşan Kritik Ödeme Takviminiz:**\n\n"
        if not upcoming_items:
            reply += "Kayıtlı bekleyen kart ekstresi veya kredi taksiti bulunmuyor. Nakit akışınız oldukça rahat!\n"
        else:
            for item in upcoming_items[:5]:
                urgency_icon = "🚨" if item["days_left"] <= 3 else "⏰" if item["days_left"] <= 7 else "🗓️"
                reply += f"{urgency_icon} **{item['title']}**: **{item['amount']:,.0f} ₺** (Her ayın {item['day']}. günü — **{item['days_left']} gün kaldı**)\n"

            reply += (
                f"\n💡 **Koçluk Tavsiyesi:**\n"
                f"En yakın ödemeniz olan **{upcoming_items[0]['title']}** için vadesiz hesabınızda yeterli bakiye "
                f"bulunduğundan emin olun; gecikme faizi ve kredi notu kaybının önüne geçin."
            )

        tips = [
            f"En yakın ödeme: {upcoming_items[0]['title'] if upcoming_items else 'Yok'}",
            "Otomatik ödeme talimatlarınızı vadesiz hesap bakiyenizle eşleştirin."
        ]
        return AICoachChatResponse(
            reply=reply,
            financial_health_score=score,
            actionable_tips=tips,
            detected_intent="upcoming_calendar"
        )

    # 5. INVESTMENTS & EMERGENCY FUNDS ("yatırım", "altın", "döviz", "borsa", "paramı ne yapayım", "acil durum fonu")
    if any(k in lowered for k in ["yatırım", "altın", "döviz", "borsa", "paramı ne", "acil durum", "faiz oranı"]):
        liquid = nw.get("total_liquid_cash_try", 0)
        debt = nw.get("total_liabilities_try", 0)

        reply = (
            "📈 **Yatırım & Varlık Büyütme Değerlendirmesi:**\n\n"
            f"• **Mevcut Likit Nakdiniz:** {liquid:,.0f} ₺\n"
            f"• **Toplam Borç Yükünüz:** {debt:,.0f} ₺\n\n"
        )

        if debt > liquid and debt > 10000:
            reply += (
                "⚠️ **1 Numaralı Yatırım Kuralı: Önce Yüksek Faizli Borçları Kapatın!**\n"
                "Kredi kartlarında uygulanan aylık %4.25 faiz, yıllık bileşikte **%65'in üzerinde** bir maliyet demektir. "
                "Piyasadaki hiçbir garantili yatırım bu oranda getiri sunamaz. Dolayısıyla kredi kartı borcunuzu kapatmak, "
                "anında **%65 garantili getiri** elde etmekle eşdeğerdir!\n\n"
            )
        else:
            reply += (
                "🛡️ **Adım 1: Acil Durum Fonu (3-6 Aylık Tampon)**\n"
                "Herhangi bir hisse senedi veya gayrimenkul yatırımından önce, en az 3 aylık temel giderlerinizi "
                "gecelik faiz getiren para piyasası fonunda veya vadesiz döviz/altında hazır tutmalısınız.\n\n"
            )

        reply += (
            "💡 **Adım 2: Çeşitlendirme (Sepet Modeli)**\n"
            "Borçlarınız kontrol altındaysa ve acil durum tamponunuz tamamsa, aylık düzenli olarak Gram Altın, "
            "BIST/Global hisse senedi fonları ve Eurobond sepeti yaparak enflasyon karşısında paranızın değerini katlayabilirsiniz."
        )

        tips = [
            "Kredi kartı borcu varken riskli yatırımlara girmeyin.",
            "3 aylık zorunlu harcamalarınızı likit acil durum fonunda saklayın.",
            "Aylık düzenli altın veya fon alımıyla maliyet ortalaması yapın."
        ]
        return AICoachChatResponse(
            reply=reply,
            financial_health_score=score,
            actionable_tips=tips,
            detected_intent="investment_advice"
        )

    # 6. GENERAL EXECUTIVE OVERVIEW & OPEN-ENDED QUESTIONS (Fallback with thorough analysis)
    liquid = nw.get("total_liquid_cash_try", 0)
    debt = nw.get("total_liabilities_try", 0)
    net_val = nw.get("total_net_worth_try", 0)
    sim_status = sim.get("status")
    proj = sim.get("projected_end_of_month", 0)

    status_str = "Güvenli Bölgede (Artıda)" if sim_status == "SURPLUS_SAFE" else "Ara Dönem Likidite Riski" if sim_status == "LIQUIDITY_DANGER" else "Bütçe Açığı Riski"

    reply = (
        f"👋 **Finans Koçun Değerlendirmesi:**\n\n"
        f"Finansal durumunuzun genel röntgeni ve koçluk yorumu:\n\n"
        f"📊 **Temel Finansal Göstergeleriniz:**\n"
        f"• **Net Değer (Net Worth):** {net_val:,.0f} ₺\n"
        f"• **Kasadaki Aktif Nakit:** {liquid:,.0f} ₺\n"
        f"• **Toplam Borç (Kart + Kredi):** {debt:,.0f} ₺\n"
        f"• **Nakit Akışı Durumu:** {status_str} (Ay sonu: {proj:+,.0f} ₺)\n"
        f"• **Finansal Sağlık Puanı:** **{score} / 100**\n\n"
        f"🔍 **Finans Koçunun Değerlendirmesi:**\n"
    )

    if net_val >= 0 and liquid > debt:
        reply += (
            "Finansal profiliniz son derece sağlam ve likit. Varlıklarınız borçlarınızı fazlasıyla karşılıyor. "
            "Önceliğiniz nakit akışını disiplinli tutmak ve artan nakdi uzun vadeli birikim enstrümanlarına yönlendirmek olmalıdır.\n\n"
        )
    elif debt > liquid:
        reply += (
            "Borç yükünüz aktif nakdinizin üzerinde seyrediyor. Özellikle kredi kartı ekstre son ödeme günlerini "
            "yakından takip etmeli ve ekstre borcunun tamamını kapatacak şekilde nakit planlaması yapmalısınız.\n\n"
        )
    else:
        reply += (
            "Nakit ve borç dengeniz dengede görünüyor. Beklenmedik ani harcamalara karşı güvenlik marjınızı artırmanızı öneririm.\n\n"
        )

    reply += (
        "💡 **Size Özel 3 Eylem Tavsiyesi:**\n"
        "1. Kredi kartı ekstrelerinizin son ödeme günlerini 'Kartlar & Krediler' sekmesinden kontrol edin.\n"
        "2. Ay sonuna kadar günlük güvenli harcama limitinizi aşmamaya özen gösterin.\n"
        "3. Bana dilediğiniz zaman *'Kart borçlarımı nasıl kapatırım?'*, *'Nasıl tasarruf ederim?'* veya *'Ay sonu durumum nasıl?'* gibi spesifik sorular sorabilirsiniz!"
    )

    tips = [
        "Kredi kartı limit doluluğunuzu %30'un altında tutun.",
        "Ay sonu simülasyonunu haftada en az bir kez kontrol edin.",
        "Günlük harcamalarınızı anında kaydederek nakit projeksiyonunuzu güncel tutun."
    ]

    return AICoachChatResponse(
        reply=reply,
        financial_health_score=score,
        actionable_tips=tips,
        detected_intent="general_overview"
    )

def handle_ai_chat(message: str, user_id: Optional[int] = None) -> AICoachChatResponse:
    if not user_id:
        return AICoachChatResponse(
            reply="Finansal AI Koç tavsiyeleri için lütfen oturum açınız.",
            financial_health_score=50,
            actionable_tips=["Giriş yaparak tüm özelliklere erişebilirsiniz."],
            detected_intent="auth_required"
        )

    context = generate_financial_context(user_id=user_id)

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO ai_chat_history (user_id, role, message) VALUES (?, ?, ?)", (user_id, "user", message))

    response = generate_smart_ai_reply(message, context, user_id=user_id)

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO ai_chat_history (user_id, role, message) VALUES (?, ?, ?)", (user_id, "assistant", response.reply))

    return response

def get_recent_chat_history(limit: int = 25, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    if not user_id:
        return []

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM ai_chat_history 
            WHERE user_id = ? 
            ORDER BY id DESC 
            OFFSET 0 ROWS FETCH NEXT ? ROWS ONLY
        """, (user_id, limit))
        rows = cursor.fetchall()
        return [{"id": r["id"], "role": r["role"], "message": r["message"], "created_at": str(r["created_at"]) if r.get("created_at") else None} for r in reversed(rows)]

