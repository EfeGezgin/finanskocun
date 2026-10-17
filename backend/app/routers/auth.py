from fastapi import APIRouter, Header, HTTPException, Depends
from typing import Optional
from app.models.schemas import UserRegister, UserLogin, AuthResponse, UserResponse, PlanUpgradeRequest
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["User Authentication"])

def get_current_user_optional(authorization: Optional[str] = Header(None)) -> Optional[dict]:
    if not authorization:
        return None
    token = authorization.replace("Bearer ", "").strip()
    return auth_service.get_user_by_token(token)

def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    user = get_current_user_optional(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Oturum süresi doldu veya yetkisiz erişim.")
    return user

def get_current_admin(user: dict = Depends(get_current_user)) -> dict:
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Bu işlem için Sistem Yöneticisi (Admin) yetkisi gereklidir.")
    return user


@router.post("/register", response_model=AuthResponse)
def register(payload: UserRegister):
    try:
        data = auth_service.register_user(payload.email, payload.password, payload.full_name)
        return data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/login", response_model=AuthResponse)
def login(payload: UserLogin):
    try:
        data = auth_service.login_user(payload.email, payload.password)
        return data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/demo", response_model=AuthResponse)
def demo_login():
    try:
        data = auth_service.login_or_create_demo_user()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Demo girişi oluşturulamadı: {str(e)}")

@router.get("/me", response_model=UserResponse)
def get_me(user: dict = Depends(get_current_user)):
    return user

@router.post("/logout")
def logout(authorization: Optional[str] = Header(None)):
    if authorization:
        token = authorization.replace("Bearer ", "").strip()
        auth_service.logout_user(token)
    return {"success": True, "message": "Çıkış yapıldı"}

@router.post("/upgrade-plan", response_model=UserResponse)
def upgrade_plan(payload: PlanUpgradeRequest, user: dict = Depends(get_current_user)):
    valid_plans = ["free", "pro", "vip"]
    if payload.plan not in valid_plans:
        raise HTTPException(status_code=400, detail="Geçersiz paket seçimi.")
    updated_user = auth_service.upgrade_user_plan(user["id"], payload.plan)
    return updated_user

@router.post("/reset-data")
def reset_data(user: dict = Depends(get_current_user)):
    """Zeros out all balances, accounts, cards, and transactions for this user."""
    auth_service.clear_user_finances(user_id=user["id"])
    return {"success": True, "message": "Tüm rakamlar ve finansal veriler başarıyla sıfırlandı."}

