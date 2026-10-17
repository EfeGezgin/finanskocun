from fastapi import APIRouter, Depends
from app.models.schemas import AICoachChatRequest, AICoachChatResponse
from app.services import ai_coach
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/ai", tags=["AI Financial Coach"])

@router.post("/chat", response_model=AICoachChatResponse)
def chat_with_coach(payload: AICoachChatRequest, user: dict = Depends(get_current_user)):
    return ai_coach.handle_ai_chat(payload.message, user_id=user["id"])

@router.get("/history")
def get_chat_history(user: dict = Depends(get_current_user)):
    return ai_coach.get_recent_chat_history(limit=30, user_id=user["id"])

@router.get("/score")
def get_health_score(user: dict = Depends(get_current_user)):
    return {"financial_health_score": ai_coach.compute_financial_health_score(user_id=user["id"])}
