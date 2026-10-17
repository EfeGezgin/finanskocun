from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from app.database import get_db
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])

@router.get("", response_model=List[Dict[str, Any]])
def get_user_notifications(current_user = Depends(get_current_user)):
    user_id = current_user["id"]
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, user_id, title, message, type, is_read, created_at
            FROM notifications
            WHERE user_id = ?
            ORDER BY id DESC
        """, (user_id,))
        rows = cursor.fetchall()
        return [
            {
                "id": r["id"],
                "user_id": r["user_id"],
                "title": r["title"],
                "message": r["message"],
                "type": r["type"],
                "is_read": bool(r["is_read"]),
                "created_at": str(r["created_at"]) if r["created_at"] else None
            }
            for r in rows[:30]
        ]

@router.get("/unread", response_model=List[Dict[str, Any]])
def get_unread_notifications(current_user = Depends(get_current_user)):
    user_id = current_user["id"]
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, user_id, title, message, type, is_read, created_at
            FROM notifications
            WHERE user_id = ? AND is_read = 0
            ORDER BY id ASC
        """, (user_id,))
        rows = cursor.fetchall()
        
        unread_list = [
            {
                "id": r["id"],
                "user_id": r["user_id"],
                "title": r["title"],
                "message": r["message"],
                "type": r["type"],
                "is_read": False,
                "created_at": str(r["created_at"]) if r["created_at"] else None
            }
            for r in rows
        ]

        if rows:
            cursor.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0", (user_id,))

        return unread_list

@router.post("/mark-read")
def mark_all_notifications_read(current_user = Depends(get_current_user)):
    user_id = current_user["id"]
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user_id,))
    return {"success": True, "message": "Tüm bildirimler okundu olarak işaretlendi."}

@router.post("/test")
def trigger_test_notification(current_user = Depends(get_current_user)):
    user_id = current_user["id"]
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, type, is_read)
            VALUES (?, ?, ?, ?, 0)
        """, (user_id, "🔔 Bildirim Testi", "Finans Koçun mobil bildirim sistemi başarıyla çalışıyor!", "info"))
    return {"success": True, "message": "Test bildirimi oluşturuldu."}
