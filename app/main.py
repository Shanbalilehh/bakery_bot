from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.core.config import settings
from app.application.orchestrator import orchestrator

from app.interfaces import twilio_webhook

app = FastAPI(title=settings.PROJECT_NAME)

app.include_router(twilio_webhook.router)

class WhatsAppPayload(BaseModel):
    # Simplified payload structure for testing
    user_id: str
    message: str

@app.get("/")
def health_check():
    return {"status": "active", "system": "Bakery Bot Orchestrator"}

@app.post("/webhook/test")
async def test_chat(payload: WhatsAppPayload):
    """
    Test endpoint to simulate WhatsApp without needing Twilio yet.
    """
    response_text = await orchestrator.process_message(payload.user_id, payload.message)
    return {"response": response_text}