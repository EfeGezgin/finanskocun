from typing import List, Optional
from datetime import datetime, date, timedelta
from app.models.schemas import WhatIfRequest, WhatIfResponse, DailyCashPoint
from app.services.simulation_engine import run_cash_flow_simulation

def simulate_what_if_scenario(user_id: int, req: WhatIfRequest) -> WhatIfResponse:
    """Simulates a hypothetical purchase or income event over a 30-day projection
    and compares it to the user's baseline cash flow trajectory."""
    # 1. Run baseline simulation
    baseline = run_cash_flow_simulation(user_id=user_id)
    base_curve = baseline.projection_curve

    if not base_curve:
        # Fallback empty curve
        today = date.today()
        base_curve = [DailyCashPoint(
            date=today.strftime("%Y-%m-%d"),
            day=today.day,
            projected_balance=baseline.current_liquid_cash,
            scheduled_income=0,
            scheduled_expense=0,
            daily_spend_estimate=0,
            credit_card_payment=0,
            loan_payment=0,
            events=[],
            is_critical=False
        )]

    installment_count = max(1, req.installment_count)
    monthly_impact = round(req.amount / installment_count, 2)
    is_expense = (req.scenario_type == "expense")

    # 2. Build What-If Curve
    whatif_curve: List[DailyCashPoint] = []
    will_enter_deficit = False
    deficit_day = None
    deficit_amount = None
    lowest_balance = float("inf")
    lowest_balance_day = base_curve[0].date

    for i, pt in enumerate(base_curve):
        # Calculate impact on day i
        # If installment: first installment deducted on day 1 (or event date)
        if i == 0:
            impact_today = monthly_impact if is_expense else -monthly_impact
            event_text = f"💡 {req.scenario_title} ({'Taksit 1/' + str(installment_count) if installment_count > 1 else 'Peşin'})"
        else:
            impact_today = 0
            event_text = None

        new_bal = pt.projected_balance - (monthly_impact if is_expense else -monthly_impact)
        new_bal = round(new_bal, 2)

        if new_bal < lowest_balance:
            lowest_balance = new_bal
            lowest_balance_day = pt.date

        if new_bal < 0 and not will_enter_deficit:
            will_enter_deficit = True
            deficit_day = pt.date
            deficit_amount = abs(new_bal)

        events_copy = list(pt.events)
        if event_text:
            events_copy.append(event_text)

        whatif_curve.append(DailyCashPoint(
            date=pt.date,
            day=pt.day,
            projected_balance=new_bal,
            scheduled_income=pt.scheduled_income,
            scheduled_expense=pt.scheduled_expense + (monthly_impact if is_expense else 0),
            daily_spend_estimate=pt.daily_spend_estimate,
            credit_card_payment=pt.credit_card_payment,
            loan_payment=pt.loan_payment,
            events=events_copy,
            is_critical=(new_bal < 0)
        ))

    current_end_bal = base_curve[-1].projected_balance
    projected_end_bal = whatif_curve[-1].projected_balance
    net_diff = round(projected_end_bal - current_end_bal, 2)

    # Determine risk grade & recommendation
    if is_expense:
        if will_enter_deficit:
            if abs(lowest_balance) > 10000:
                grade = "critical_danger"
                rec = (
                    f"🚨 Dikkat: Bu harcamayı gerçekleştirirseniz {deficit_day} tarihinde nakit dengeniz eksiye düşebilir "
                    f"(En dip: {lowest_balance:,.2f} ₺). Bu harcamayı ertelemeniz veya taksit sayısını en az 6-9 aya çıkarmanız önerilir."
                )
            else:
                grade = "high_risk"
                rec = (
                    f"⚠️ Uyarı: Harcama sonrası {deficit_day} civarında kısa süreli nakit açığı ({deficit_amount:,.2f} ₺) oluşuyor. "
                    "Kredi kartı veya ek hesap kullanmadan önce diğer vadesiz hesaplarınızdaki likiditeyi kontrol edin."
                )
        elif lowest_balance < 3000:
            grade = "moderate_risk"
            rec = (
                f"⚖️ Bu harcama sizi eksiye düşürmüyor ancak ay sonu güvenlik tamponunuzu kritik seviyeye ({lowest_balance:,.2f} ₺) çekiyor. "
                "Beklenmedik bir acil gider durumunda zorlanabilirsiniz."
            )
        else:
            grade = "low_risk"
            rec = (
                f"✅ Bütçeniz bu harcamayı rahatlıkla kaldırıyor! Ay sonu bakiyeniz {projected_end_bal:,.2f} ₺ olarak pozitif kalmaya devam ediyor."
            )
    else:
        grade = "low_risk"
        rec = f"🎉 Harika bir nakit artışı! Bu ek gelirle ay sonu birikiminiz {projected_end_bal:,.2f} ₺ seviyesine yükselecektir."

    return WhatIfResponse(
        scenario_title=req.scenario_title,
        amount=req.amount,
        installment_count=installment_count,
        monthly_installment_impact=monthly_impact,
        current_end_of_month_balance=current_end_bal,
        projected_end_of_month_balance=projected_end_bal,
        net_difference=net_diff,
        will_enter_deficit=will_enter_deficit,
        deficit_day=deficit_day,
        deficit_amount=deficit_amount,
        lowest_balance=lowest_balance,
        lowest_balance_day=lowest_balance_day,
        financial_impact_grade=grade,
        recommendation=rec,
        timeline_base=base_curve,
        timeline_whatif=whatif_curve
    )
