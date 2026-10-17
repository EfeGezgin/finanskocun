from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

# ----------------- Auth Schemas -----------------
class UserRegister(BaseModel):
    email: str
    password: str
    full_name: str

class UserLogin(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    is_admin: bool = False
    plan: str = "free"
    created_at: Optional[str] = None

class PlanUpgradeRequest(BaseModel):
    plan: str  # 'pro' or 'vip'

class AuthResponse(BaseModel):
    token: str
    user: UserResponse



# ----------------- Bank Schemas -----------------
class BankInfo(BaseModel):
    name: str
    code: str
    color: str
    icon: str

# ----------------- Account Schemas -----------------
class AccountBase(BaseModel):
    name: str
    type: str  # 'bank_checking', 'cash', 'foreign_currency', 'gold', 'investment', 'crypto'
    currency: str = "TRY"
    balance: float = 0.0
    exchange_rate: float = 1.0
    is_active_cash: int = 1
    bank_name: Optional[str] = None
    bank_code: Optional[str] = None
    account_number: Optional[str] = None
    color: Optional[str] = "#10b981"
    icon: Optional[str] = "wallet"

class AccountCreate(AccountBase):
    pass

class AccountResponse(AccountBase):
    id: int
    user_id: Optional[int] = None
    balance_try: float  # balance * exchange_rate
    updated_at: Optional[str] = None

class NetWorthResponse(BaseModel):
    total_net_worth_try: float
    total_liquid_cash_try: float
    total_investment_try: float
    total_credit_debt_try: float
    total_loan_debt_try: float
    total_liabilities_try: float
    accounts_by_type: Dict[str, float]

# ----------------- Credit Card Schemas (Enhanced Limits & Debts) -----------------
class CreditCardBase(BaseModel):
    bank_name: str
    bank_code: Optional[str] = None
    card_name: str
    total_limit: float
    current_debt: float = 0.0          # Güncel dönem içi harcamalar
    statement_debt: float = 0.0        # Kesilen son ekstre borcu (Bu ay ödenecek asıl tutar)
    installment_debt: float = 0.0      # Gelecek aylara sarkan taksitli borçlar
    cutoff_day: int = Field(..., ge=1, le=31)  # Hesap kesim günü (1-31)
    due_day: int = Field(..., ge=1, le=31)     # Son ödeme günü (1-31)
    min_payment_rate: float = 0.20
    interest_rate: float = 4.25        # Akdi faiz oranı %
    color: Optional[str] = "#6366f1"

class CreditCardCreate(CreditCardBase):
    pass

class CardLimitAndDebtUpdate(BaseModel):
    total_limit: Optional[float] = None
    statement_debt: Optional[float] = None
    current_debt: Optional[float] = None
    installment_debt: Optional[float] = None
    min_payment_rate: Optional[float] = None
    interest_rate: Optional[float] = None

class CreditCardResponse(CreditCardBase):
    id: int
    user_id: Optional[int] = None
    total_debt_load: float              # statement_debt + current_debt + installment_debt
    available_limit: float
    utilization_rate: float
    min_payment_amount: float
    days_until_due: int
    days_until_cutoff: int
    due_date_str: str
    cutoff_date_str: str
    urgency_level: str  # 'due_urgent' (<=3 gün), 'due_soon' (<=7 gün), 'normal'
    unpaid_past_statements_total: float = 0.0
    created_at: Optional[str] = None

# ----------------- Credit Card Statement History Schemas -----------------
class CreditCardStatementBase(BaseModel):
    credit_card_id: int
    period: str  # e.g. "Ekim 2026", "Eylül 2026", "2026-09"
    statement_date: Optional[str] = None  # YYYY-MM-DD
    due_date: Optional[str] = None        # YYYY-MM-DD
    statement_amount: float               # Ekstre tutarı
    min_payment_amount: Optional[float] = None
    paid_amount: float = 0.0              # Ödenen tutar
    remaining_debt: Optional[float] = None # Otomatik: statement_amount - paid_amount
    interest_rate: float = 4.25           # Akdi faiz %
    status: Optional[str] = "unpaid"      # 'paid', 'partially_paid', 'unpaid'
    notes: Optional[str] = None

class CreditCardStatementCreate(CreditCardStatementBase):
    pass

class CreditCardStatementResponse(CreditCardStatementBase):
    id: int
    user_id: Optional[int] = None
    card_name: Optional[str] = None
    bank_name: Optional[str] = None
    estimated_interest: float = 0.0       # Devreden borca binecek tahmini aylık faiz
    created_at: Optional[str] = None

class CreditCardAnalyticsResponse(BaseModel):
    total_limits_all_cards: float
    total_statement_debt_all: float
    total_current_debt_all: float
    total_installment_debt_all: float
    total_combined_debt: float
    total_available_limit_all: float
    overall_utilization_rate: float
    total_past_unpaid_debt: float
    estimated_monthly_interest_load: float

# ----------------- Loan Schemas -----------------
class LoanBase(BaseModel):
    bank_name: str
    bank_code: Optional[str] = None
    loan_title: str
    total_amount: float
    monthly_installment: float
    remaining_installments: int
    total_installments: int
    due_day: int = Field(..., ge=1, le=31)
    interest_rate: float = 0.0
    color: Optional[str] = "#f59e0b"

class LoanCreate(LoanBase):
    pass

class LoanResponse(LoanBase):
    id: int
    user_id: Optional[int] = None
    remaining_principal: float
    paid_installments: int
    days_until_due: int
    due_date_str: str
    end_date_estimate: str
    created_at: Optional[str] = None

# ----------------- Recurring Items Schemas -----------------
class RecurringItemBase(BaseModel):
    title: str
    type: str
    category: str
    amount: float
    day_of_month: int = Field(..., ge=1, le=31)
    account_id: Optional[int] = None
    is_active: int = 1
    notes: Optional[str] = None

class RecurringItemCreate(RecurringItemBase):
    pass

class RecurringItemResponse(RecurringItemBase):
    id: int
    user_id: Optional[int] = None

# ----------------- Transaction Schemas -----------------
class TransactionBase(BaseModel):
    date: str
    type: str
    category: str
    amount: float
    description: str
    payment_method: str = "cash"
    account_id: Optional[int] = None
    credit_card_id: Optional[int] = None
    is_nlp_generated: int = 0
    raw_input: Optional[str] = None
    emotion_tag: Optional[str] = "essential"  # 'essential', 'impulsive', 'reward', 'social', 'investment'

class TransactionCreate(TransactionBase):
    pass

class TransactionResponse(TransactionBase):
    id: int
    user_id: Optional[int] = None
    created_at: Optional[str] = None
    account_name: Optional[str] = None
    card_name: Optional[str] = None
    emotion_tag: Optional[str] = "essential"

# ----------------- NLP Extraction Schemas -----------------
class NLPExtractRequest(BaseModel):
    text: str
    auto_save: bool = False

class NLPExtractResponse(BaseModel):
    success: bool
    amount: float
    currency: str = "TRY"
    category: str
    type: str
    date: str
    description: str
    payment_method: str
    suggested_account_id: Optional[int] = None
    suggested_credit_card_id: Optional[int] = None
    confidence: float
    saved_transaction_id: Optional[int] = None
    explanation: Optional[str] = None

# ----------------- Cash Flow & Simulation Schemas -----------------
class DailyCashPoint(BaseModel):
    date: str
    day: int
    projected_balance: float
    scheduled_income: float
    scheduled_expense: float
    daily_spend_estimate: float
    credit_card_payment: float
    loan_payment: float
    events: List[str]
    is_critical: bool

class DangerZoneAlert(BaseModel):
    date: str
    severity: str
    title: str
    message: str
    amount_at_risk: float
    projected_balance: float

class UpcomingPaymentItem(BaseModel):
    id: str
    title: str
    institution: str
    payment_type: str
    payment_type_label: str
    category: str
    due_date: str
    due_date_str: str
    day: int
    days_left: int
    amount: float
    min_amount: Optional[float] = None
    balance_before_payment: float
    balance_after_payment: float
    coverage_status: str
    coverage_deficit: float
    advice_note: str

class CashFlowSimulationResponse(BaseModel):
    current_liquid_cash: float
    projected_end_of_month_balance: float
    net_change_forecast: float
    status: str
    status_headline: str
    status_summary: str
    remaining_days_in_month: int
    average_daily_spend: float
    recommended_max_daily_spend: float
    total_upcoming_inflows: float
    total_upcoming_fixed_bills: float
    total_upcoming_credit_payments: float
    total_upcoming_loan_payments: float
    total_upcoming_daily_spend: float
    critical_dip_day: Optional[str] = None
    critical_dip_amount: Optional[float] = None
    alerts: List[DangerZoneAlert]
    projection_curve: List[DailyCashPoint]
    upcoming_payments: List[UpcomingPaymentItem] = []


# ----------------- AI Coach Schemas -----------------
class AICoachChatRequest(BaseModel):
    message: str

class AICoachChatResponse(BaseModel):
    reply: str
    financial_health_score: int
    actionable_tips: List[str]
    detected_intent: Optional[str] = None

# ----------------- Admin Schemas -----------------
class AdminOverviewResponse(BaseModel):
    total_users: int
    total_accounts: int
    total_cards: int
    total_loans: int
    total_system_assets_try: float
    total_system_card_debt_try: float
    total_system_loan_debt_try: float
    total_system_net_worth_try: float
    mssql_status: str

class AdminUserSummary(BaseModel):
    id: int
    email: str
    full_name: str
    is_admin: bool
    created_at: Optional[str] = None
    accounts_count: int = 0
    cards_count: int = 0
    loans_count: int = 0
    total_assets_try: float = 0.0
    total_debt_try: float = 0.0
    net_worth_try: float = 0.0

class AdminUserDetail(BaseModel):
    user: AdminUserSummary
    accounts: List[AccountResponse]
    credit_cards: List[CreditCardResponse]
    loans: List[LoanResponse]
    transactions: List[TransactionResponse]


# ==========================================
# MODULE 1: CATEGORY BUDGET SCHEMAS
# ==========================================
class CategoryBudgetBase(BaseModel):
    category: str
    monthly_limit: float

class CategoryBudgetCreate(CategoryBudgetBase):
    pass

class CategoryBudgetResponse(BaseModel):
    id: int
    user_id: int
    category: str
    monthly_limit: float
    current_spent: float = 0.0
    percentage_spent: float = 0.0
    remaining_budget: float = 0.0
    status: str = "safe"  # 'safe' (<80%), 'warning' (80-99%), 'exceeded' (>=100%)
    color: str = "#10b981"
    created_at: Optional[str] = None


# ==========================================
# MODULE 2: SUBSCRIPTION HUNTER SCHEMAS
# ==========================================
class DetectedSubscription(BaseModel):
    id: str
    title: str
    category: str
    amount: float
    billing_cycle: str = "monthly"
    last_paid_date: str
    next_due_date: str
    frequency_months: int = 1
    confidence: float
    status: str = "active"  # 'active', 'review', 'cancel_candidate'
    source: str = "pattern"
    annual_cost: float
    cancellation_difficulty: str = "kolay"  # 'kolay', 'orta', 'zor'

class SubscriptionHunterResponse(BaseModel):
    total_monthly_cost: float
    total_annual_cost: float
    subscription_count: int
    subscriptions: List[DetectedSubscription]
    smart_tips: List[str]


# ==========================================
# MODULE 3: SPENDING PSYCHOLOGY & EMOTIONS
# ==========================================
class EmotionSpendingBreakdown(BaseModel):
    tag: str
    tag_label: str
    color: str
    icon: str
    total_amount: float
    transaction_count: int
    percentage_of_total: float

class SpendingPsychologyResponse(BaseModel):
    total_analyzed_spent: float
    impulsive_ratio: float
    essential_ratio: float
    reward_ratio: float
    social_ratio: float
    investment_ratio: float
    psychological_health_score: int  # 0 - 100
    health_verdict: str
    behavioral_insights: List[str]
    breakdown: List[EmotionSpendingBreakdown]


# ==========================================
# MODULE 4: WHAT-IF SCENARIO SIMULATION
# ==========================================
class WhatIfRequest(BaseModel):
    scenario_title: str
    scenario_type: str = "expense"  # 'expense' or 'income'
    amount: float
    installment_count: int = 1  # 1 for cash/peşin, 3, 6, 9, 12 etc.
    start_date: Optional[str] = None

class WhatIfResponse(BaseModel):
    scenario_title: str
    amount: float
    installment_count: int
    monthly_installment_impact: float
    current_end_of_month_balance: float
    projected_end_of_month_balance: float
    net_difference: float
    will_enter_deficit: bool
    deficit_day: Optional[str] = None
    deficit_amount: Optional[float] = None
    lowest_balance: float
    lowest_balance_day: str
    financial_impact_grade: str  # 'low_risk', 'moderate_risk', 'high_risk', 'critical_danger'
    recommendation: str
    timeline_base: List[DailyCashPoint]
    timeline_whatif: List[DailyCashPoint]


# ==========================================
# MODULE 5: PERSONAL INFLATION INDEX
# ==========================================
class CategoryInflationDetail(BaseModel):
    category: str
    weight: float
    spending_current_month: float
    spending_prior_month: float
    category_inflation_rate: float
    impact_points: float

class PersonalInflationResponse(BaseModel):
    personal_inflation_annual_rate: float
    official_cpi_rate: float = 48.6
    inflation_difference: float
    purchasing_power_loss: float
    primary_inflation_drivers: List[str]
    category_details: List[CategoryInflationDetail]
    hedge_tips: List[str]


