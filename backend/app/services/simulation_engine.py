from datetime import date, timedelta
import calendar
from typing import List, Dict, Any, Optional
from app.database import get_db
from app.models.schemas import (
    CashFlowSimulationResponse, DailyCashPoint, DangerZoneAlert, UpcomingPaymentItem
)

TR_MONTHS = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]

def format_tr_date(d: date) -> str:
    return f"{d.day} {TR_MONTHS[d.month]} {d.year}"


def calculate_average_daily_spend(days_lookback: int = 30, user_id: Optional[int] = None) -> float:
    """Calculates user's average daily discretionary spending over past N days."""
    if not user_id:
        return 0.0

    today = date.today()
    start_date = today - timedelta(days=days_lookback)

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0.0) as total_spent
            FROM transactions
            WHERE type = 'expense' 
              AND category NOT IN ('Kira & Konut', 'Kredi & Finans')
              AND date >= ? AND date <= ? AND user_id = ?
        """, (start_date.isoformat(), today.isoformat(), user_id))
        row = cursor.fetchone()
        total_spent = float(row["total_spent"] or 0.0)

        if total_spent > 0:
            return round(total_spent / days_lookback, 2)
        else:
            return 0.0

def run_cash_flow_simulation(
    custom_daily_spend: Optional[float] = None,
    extra_one_time_expense: float = 0.0,
    extra_one_time_income: float = 0.0,
    user_id: Optional[int] = None
) -> CashFlowSimulationResponse:
    today = date.today()
    year = today.year
    month = today.month

    _, last_day = calendar.monthrange(year, month)
    end_of_month = date(year, month, last_day)
    remaining_days = max(1, (end_of_month - today).days)

    if not user_id:
        return CashFlowSimulationResponse(
            current_liquid_cash=0.0,
            projected_end_of_month_balance=0.0,
            net_change_forecast=0.0,
            status="SURPLUS_SAFE",
            status_headline="Lütfen Giriş Yapın",
            status_summary="Finansal simülasyonu görüntülemek için oturum açmalısınız.",
            remaining_days_in_month=remaining_days,
            average_daily_spend=0.0,
            recommended_max_daily_spend=0.0,
            total_upcoming_inflows=0.0,
            total_upcoming_fixed_bills=0.0,
            total_upcoming_credit_payments=0.0,
            total_upcoming_loan_payments=0.0,
            total_upcoming_daily_spend=0.0,
            critical_dip_day=None,
            critical_dip_amount=None,
            alerts=[],
            projection_curve=[],
            upcoming_payments=[]
        )

    with get_db() as conn:
        cursor = conn.cursor()

        # 1. Active Liquid Cash strictly for user
        cursor.execute("""
            SELECT COALESCE(SUM(balance * exchange_rate), 0.0) as liquid 
            FROM accounts 
            WHERE is_active_cash = 1 AND user_id = ?
        """, (user_id,))
        current_liquid_cash = float(cursor.fetchone()["liquid"] or 0.0)
        current_liquid_cash = current_liquid_cash + extra_one_time_income - extra_one_time_expense

        # 2. Credit Cards with timing, debts, and past unpaid statements (MSSQL compatible GROUP BY)
        cc_query = """
            SELECT c.id, c.bank_name, c.card_name, c.current_debt, c.statement_debt, c.installment_debt, c.due_day,
                   c.min_payment_rate,
                   COALESCE(SUM(CASE WHEN s.status != 'paid' THEN s.remaining_debt ELSE 0.0 END), 0.0) as unpaid_past
            FROM credit_cards c
            LEFT JOIN credit_card_statements s ON c.id = s.credit_card_id AND s.user_id = ?
            WHERE c.user_id = ?
            GROUP BY c.id, c.bank_name, c.card_name, c.current_debt, c.statement_debt, c.installment_debt, c.due_day, c.min_payment_rate
        """
        cursor.execute(cc_query, (user_id, user_id))
        credit_cards = cursor.fetchall()

        # 3. Loans due this month
        cursor.execute("""
            SELECT id, bank_name, loan_title, monthly_installment, remaining_installments, due_day 
            FROM loans 
            WHERE user_id = ? AND remaining_installments > 0
        """, (user_id,))
        loans = cursor.fetchall()

        # 4. Recurring items
        cursor.execute("""
            SELECT title, type, category, amount, day_of_month 
            FROM recurring_items 
            WHERE is_active = 1 AND user_id = ?
        """, (user_id,))
        recurring = cursor.fetchall()

    avg_daily_spend = custom_daily_spend if custom_daily_spend is not None else calculate_average_daily_spend(30, user_id=user_id)

    # Empty State check: If user has 0 cash, 0 cards, 0 loans, 0 recurring:
    has_any_data = (current_liquid_cash != 0 or len(credit_cards) > 0 or len(loans) > 0 or len(recurring) > 0)

    horizon_days = max(remaining_days, 30)
    running_balance = current_liquid_cash
    projection_curve: List[DailyCashPoint] = []
    alerts: List[DangerZoneAlert] = []

    critical_dip_day: Optional[str] = None
    critical_dip_amount: Optional[float] = None

    total_upcoming_inflows = 0.0
    total_upcoming_fixed_bills = 0.0
    total_upcoming_credit_payments = 0.0
    total_upcoming_loan_payments = 0.0
    total_upcoming_daily_spend = 0.0

    SAFETY_THRESHOLD = 3000.0

    for i in range(horizon_days + 1):
        sim_date = today + timedelta(days=i)
        is_within_month = sim_date <= end_of_month
        day_num = sim_date.day
        events = []
        sched_income = 0.0
        sched_expense = 0.0
        cc_pay = 0.0
        loan_pay = 0.0

        # Recurring
        for rec in recurring:
            if rec["day_of_month"] == day_num and i > 0:
                amt = float(rec["amount"])
                if rec["type"] == "income":
                    sched_income += amt
                    events.append(f"Gelir: {rec['title']} (+{amt:,.0f} ₺)")
                    if is_within_month:
                        total_upcoming_inflows += amt
                else:
                    sched_expense += amt
                    events.append(f"Gider: {rec['title']} (-{amt:,.0f} ₺)")
                    if is_within_month:
                        total_upcoming_fixed_bills += amt

        # Credit Cards: due_day triggers payment of statement_debt + any past unpaid carryover
        for cc in credit_cards:
            if cc["due_day"] == day_num and i > 0:
                stmt_d = float(cc.get("statement_debt") or 0.0)
                curr_d = float(cc.get("current_debt") or 0.0)
                base_stmt = stmt_d if stmt_d > 0 else curr_d
                past_unpaid = float(cc["unpaid_past"] or 0.0)
                total_card_pay = base_stmt + past_unpaid
                if total_card_pay > 0:
                    cc_pay += total_card_pay
                    if past_unpaid > 0:
                        events.append(f"Kart Ödemesi (Ekstre + Devreden): {cc['bank_name']} {cc['card_name']} (-{total_card_pay:,.0f} ₺)")
                    else:
                        events.append(f"Kredi Kartı Ekstresi: {cc['bank_name']} {cc['card_name']} (-{total_card_pay:,.0f} ₺)")
                    if is_within_month:
                        total_upcoming_credit_payments += total_card_pay

        # Loans
        for ln in loans:
            if ln["due_day"] == day_num and i > 0:
                inst = float(ln["monthly_installment"])
                loan_pay += inst
                events.append(f"Kredi Taksiti: {ln['bank_name']} {ln['loan_title']} (-{inst:,.0f} ₺)")
                if is_within_month:
                    total_upcoming_loan_payments += inst

        spend_today = avg_daily_spend if i > 0 else 0.0
        if is_within_month and i > 0:
            total_upcoming_daily_spend += spend_today

        running_balance = running_balance + sched_income - sched_expense - cc_pay - loan_pay - spend_today

        if is_within_month:
            if critical_dip_amount is None or running_balance < critical_dip_amount:
                critical_dip_amount = running_balance
                critical_dip_day = sim_date.strftime("%d.%m.%Y")

        is_crit = False
        if running_balance < 0 and has_any_data:
            is_crit = True
            if not any(a.severity == "danger" and a.date == sim_date.strftime("%d.%m.%Y") for a in alerts):
                alerts.append(DangerZoneAlert(
                    date=sim_date.strftime("%d.%m.%Y"),
                    severity="danger",
                    title="Bütçe Açığı Uyarısı!",
                    message=f"{sim_date.strftime('%d %B')} itibarıyla kasanız eksiye ({running_balance:,.0f} ₺) düşüyor!",
                    amount_at_risk=abs(running_balance),
                    projected_balance=round(running_balance, 2)
                ))
        elif running_balance < SAFETY_THRESHOLD and (cc_pay > 0 or loan_pay > 0 or sched_expense > 0) and has_any_data:
            is_crit = True
            major_cause = events[0] if events else "Ödemeler"
            alerts.append(DangerZoneAlert(
                date=sim_date.strftime("%d.%m.%Y"),
                severity="warning",
                title="Kritik Likidite Darboğazı",
                message=f"{sim_date.strftime('%d.%m')} tarihindeki {major_cause} sonrasında kasanda sadece {running_balance:,.0f} ₺ kalacak, dikkat et!",
                amount_at_risk=round(SAFETY_THRESHOLD - running_balance, 2),
                projected_balance=round(running_balance, 2)
            ))

        projection_curve.append(DailyCashPoint(
            date=sim_date.strftime("%Y-%m-%d"),
            day=sim_date.day,
            projected_balance=round(running_balance, 2),
            scheduled_income=round(sched_income, 2),
            scheduled_expense=round(sched_expense, 2),
            daily_spend_estimate=round(spend_today, 2),
            credit_card_payment=round(cc_pay, 2),
            loan_payment=round(loan_pay, 2),
            events=events,
            is_critical=is_crit
        ))

    # Compute Detailed Upcoming Payments (Detaylı Ödeme Takvimi)
    raw_payment_candidates = []

    # 1. Credit Cards Upcoming Payments
    for cc in credit_cards:
        due_day = int(cc["due_day"])
        stmt_d = float(cc.get("statement_debt") or 0.0)
        curr_d = float(cc.get("current_debt") or 0.0)
        past_unpaid = float(cc.get("unpaid_past") or 0.0)
        base_amt = stmt_d if stmt_d > 0 else curr_d
        total_card_pay = base_amt + past_unpaid

        if total_card_pay > 0:
            min_rate = float(cc.get("min_payment_rate") or 0.20)
            min_amt = round(total_card_pay * min_rate, 2)

            if due_day >= today.day:
                target_date = date(year, month, min(due_day, calendar.monthrange(year, month)[1]))
            else:
                next_m = month + 1 if month < 12 else 1
                next_y = year if month < 12 else year + 1
                target_date = date(next_y, next_m, min(due_day, calendar.monthrange(next_y, next_m)[1]))

            days_left = max(0, (target_date - today).days)
            card_title = f"{cc['bank_name']} {cc['card_name']} Kredi Kartı"
            raw_payment_candidates.append({
                "id": f"cc_{cc['id']}",
                "title": card_title,
                "institution": cc["bank_name"],
                "payment_type": "credit_card",
                "payment_type_label": "Kredi Kartı Ekstresi",
                "category": "Kredi Kartı",
                "due_date": target_date.strftime("%Y-%m-%d"),
                "due_date_str": format_tr_date(target_date),
                "day": target_date.day,
                "days_left": days_left,
                "amount": round(total_card_pay, 2),
                "min_amount": min_amt,
                "is_income": False
            })

    # 2. Loans Upcoming Payments
    for ln in loans:
        due_day = int(ln["due_day"])
        inst = float(ln["monthly_installment"])
        if inst > 0:
            if due_day >= today.day:
                target_date = date(year, month, min(due_day, calendar.monthrange(year, month)[1]))
            else:
                next_m = month + 1 if month < 12 else 1
                next_y = year if month < 12 else year + 1
                target_date = date(next_y, next_m, min(due_day, calendar.monthrange(next_y, next_m)[1]))

            days_left = max(0, (target_date - today).days)
            loan_title = f"{ln['bank_name']} {ln['loan_title']} ({ln['remaining_installments']} Taksit Kaldı)"
            raw_payment_candidates.append({
                "id": f"loan_{ln['id']}",
                "title": loan_title,
                "institution": ln["bank_name"],
                "payment_type": "loan",
                "payment_type_label": "Kredi Taksiti",
                "category": "Kredi & Finans",
                "due_date": target_date.strftime("%Y-%m-%d"),
                "due_date_str": format_tr_date(target_date),
                "day": target_date.day,
                "days_left": days_left,
                "amount": round(inst, 2),
                "min_amount": None,
                "is_income": False
            })

    # 3. Recurring Items (Maaş, Kira, Faturalar vb.)
    for rec in recurring:
        dom = int(rec["day_of_month"])
        amt = float(rec["amount"])
        if amt > 0:
            if dom >= today.day:
                target_date = date(year, month, min(dom, calendar.monthrange(year, month)[1]))
            else:
                next_m = month + 1 if month < 12 else 1
                next_y = year if month < 12 else year + 1
                target_date = date(next_y, next_m, min(dom, calendar.monthrange(next_y, next_m)[1]))

            days_left = max(0, (target_date - today).days)
            is_inc = (rec["type"] == "income")
            type_label = "Beklenen Gelir" if is_inc else "Sabit Fatura / Kira"
            raw_payment_candidates.append({
                "id": f"rec_{dom}_{rec['title']}",
                "title": rec["title"],
                "institution": rec.get("category") or ("İşveren" if is_inc else "Düzenli"),
                "payment_type": "recurring_income" if is_inc else "recurring_expense",
                "payment_type_label": type_label,
                "category": rec.get("category") or ("Gelir" if is_inc else "Fatura"),
                "due_date": target_date.strftime("%Y-%m-%d"),
                "due_date_str": format_tr_date(target_date),
                "day": target_date.day,
                "days_left": days_left,
                "amount": round(amt, 2),
                "min_amount": None,
                "is_income": is_inc
            })

    # Chronological sort
    raw_payment_candidates.sort(key=lambda x: (x["due_date"], 0 if x["is_income"] else 1))

    upcoming_payments: List[UpcomingPaymentItem] = []
    sim_running_liquid = current_liquid_cash

    for cand in raw_payment_candidates:
        bal_before = sim_running_liquid
        amt = cand["amount"]
        if cand["is_income"]:
            sim_running_liquid += amt
            coverage_status = "sufficient"
            coverage_deficit = 0.0
            advice_note = "Bu gelir hesabınıza girdiğinde kasanızı ferahlatacak ve sonraki borçlar için güvence sağlayacaktır."
        else:
            sim_running_liquid -= amt
            if sim_running_liquid >= 3000.0:
                coverage_status = "sufficient"
                coverage_deficit = 0.0
                advice_note = "Mevcut vadesiz hesap bakiyeniz bu ödemeyi eksiksiz karşılıyor, kasanız güvende."
            elif sim_running_liquid >= 0.0:
                coverage_status = "warning"
                coverage_deficit = 0.0
                advice_note = f"Bu ödemeden sonra kasada yalnızca {sim_running_liquid:,.0f} ₺ kalıyor. Beklenmedik acil harcamalara dikkat edin."
            else:
                coverage_status = "deficit"
                coverage_deficit = round(abs(sim_running_liquid), 2)
                if cand["payment_type"] == "credit_card" and cand["min_amount"]:
                    advice_note = f"Kasada {coverage_deficit:,.0f} ₺ açık görünüyor! Gecikmeye girmemek için en az asgari tutarı ({cand['min_amount']:,.0f} ₺) ödeyebilir veya hesaba nakit aktarabilirsiniz."
                elif cand["payment_type"] == "loan":
                    advice_note = f"Kasada {coverage_deficit:,.0f} ₺ açık görünüyor! Kredi taksit gecikmesi kredi notunu olumsuz etkiler, vadesinden önce hesaba nakit takviye yapılması önerilir."
                else:
                    advice_note = f"Kasada {coverage_deficit:,.0f} ₺ açık görünüyor! Ödemeyi aksatmamak için diğer harcamalarınızı ertelemeniz önerilir."

        upcoming_payments.append(UpcomingPaymentItem(
            id=cand["id"],
            title=cand["title"],
            institution=cand["institution"],
            payment_type=cand["payment_type"],
            payment_type_label=cand["payment_type_label"],
            category=cand["category"],
            due_date=cand["due_date"],
            due_date_str=cand["due_date_str"],
            day=cand["day"],
            days_left=cand["days_left"],
            amount=cand["amount"],
            min_amount=cand["min_amount"],
            balance_before_payment=round(bal_before, 2),
            balance_after_payment=round(sim_running_liquid, 2),
            coverage_status=coverage_status,
            coverage_deficit=coverage_deficit,
            advice_note=advice_note
        ))

    end_of_month_point = next((p for p in projection_curve if p.date == end_of_month.strftime("%Y-%m-%d")), projection_curve[-1])
    projected_end_of_month = end_of_month_point.projected_balance
    net_change = projected_end_of_month - current_liquid_cash

    mandatory_outflows = total_upcoming_fixed_bills + total_upcoming_credit_payments + total_upcoming_loan_payments
    available_for_spend = current_liquid_cash + total_upcoming_inflows - mandatory_outflows - SAFETY_THRESHOLD
    recommended_daily = max(0.0, available_for_spend / remaining_days)

    if not has_any_data:
        status = "SURPLUS_SAFE"
        status_headline = "Hesaplarınızı ve Kartlarınızı Ekleyerek Başlayın"
        status_summary = "Henüz aktif banka hesabı veya harcama girilmedi. Varlıklarınızı ve kartlarınızı ekledikçe 30 günlük nakit akışı burada simüle edilecektir."
    elif projected_end_of_month < 0:
        status = "DEFICIT_RISK"
        status_headline = f"⚠️ Dikkat: Ay sonunu {abs(projected_end_of_month):,.0f} ₺ açıkla kapatma riski var!"
        status_summary = (
            f"Mevcut nakit akışınla ve günlük ortalama {avg_daily_spend:,.0f} ₺ harcamayla ay sonunu çıkartamayabilirsin. "
            f"Ay sonunu denk getirmek için günlük harcamanı en fazla {recommended_daily:,.0f} ₺ seviyesine çekmelisin."
        )
    elif critical_dip_amount is not None and critical_dip_amount < SAFETY_THRESHOLD:
        status = "LIQUIDITY_DANGER"
        status_headline = f"⚡ Ay sonunu +{projected_end_of_month:,.0f} ₺ ile kapatıyorsun fakat ara günlerde nakit sıkışıklığı var!"
        status_summary = (
            f"Genel bütçen artıda görünse de {critical_dip_day} tarihinde kart/kredi ödemeleri nedeniyle kasan "
            f"{critical_dip_amount:,.0f} ₺ seviyesine kadar geriliyor. Ara dönem likidite yönetimine dikkat etmelisin."
        )
    else:
        status = "SURPLUS_SAFE"
        status_headline = f"✅ Tebrikler! Ay sonunu +{projected_end_of_month:,.0f} ₺ artı ile kapatıyorsun."
        status_summary = (
            f"Mevcut nakit akışın ve harcama hızın oldukça sağlıklı. Kalan {remaining_days} günde günlük ortalama "
            f"{avg_daily_spend:,.0f} ₺ harcasan bile kasan güvende kalacaktır."
        )

    return CashFlowSimulationResponse(
        current_liquid_cash=round(current_liquid_cash, 2),
        projected_end_of_month_balance=round(projected_end_of_month, 2),
        net_change_forecast=round(net_change, 2),
        status=status,
        status_headline=status_headline,
        status_summary=status_summary,
        remaining_days_in_month=remaining_days,
        average_daily_spend=round(avg_daily_spend, 2),
        recommended_max_daily_spend=round(recommended_daily, 2),
        total_upcoming_inflows=round(total_upcoming_inflows, 2),
        total_upcoming_fixed_bills=round(total_upcoming_fixed_bills, 2),
        total_upcoming_credit_payments=round(total_upcoming_credit_payments, 2),
        total_upcoming_loan_payments=round(total_upcoming_loan_payments, 2),
        total_upcoming_daily_spend=round(total_upcoming_daily_spend, 2),
        critical_dip_day=critical_dip_day if has_any_data else None,
        critical_dip_amount=round(critical_dip_amount, 2) if (critical_dip_amount is not None and has_any_data) else None,
        alerts=alerts,
        projection_curve=projection_curve,
        upcoming_payments=upcoming_payments
    )

