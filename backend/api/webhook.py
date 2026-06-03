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
    Latitude: str = Form(default=None),
    Longitude: str = Form(default=None),
    db: Session = Depends(get_db),
):
    await handle_incoming(
        from_number=From,
        body=Body,
        media_url=MediaUrl0,
        latitude=float(Latitude) if Latitude else None,
        longitude=float(Longitude) if Longitude else None,
        db=db,
    )
    return ""
