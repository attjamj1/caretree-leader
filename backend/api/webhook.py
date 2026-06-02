from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from db.database import get_db
from core.race_engine import handle_incoming

router = APIRouter()


@router.post("/webhook", response_class=PlainTextResponse)
async def whatsapp_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(default=""),
    MediaUrl0: str = Form(default=None),
    db: Session = Depends(get_db),
):
    """
    Twilio sends a POST here for every incoming WhatsApp message.
    Set this URL in Twilio console → Messaging → WhatsApp Sandbox settings.
    URL: https://your-app.railway.app/webhook
    """
    await handle_incoming(
        from_number=From,
        body=Body,
        media_url=MediaUrl0,
        db=db,
    )
    return ""