from fastapi import APIRouter, Depends
from app.models.schemas import SubscriptionHunterResponse
from app.services.subscription_service import detect_subscriptions
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/subscriptions", tags=["Subscription Hunter"])

@router.get("/detected", response_model=SubscriptionHunterResponse)
def get_detected_subscriptions(current_user = Depends(get_current_user)):
    return detect_subscriptions(user_id=current_user["id"])
