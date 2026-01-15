from fastapi import FastAPI
from pydantic import BaseModel
from app.core.config import settings

# 1. Infrastructure & Domain Imports
from app.infrastructure.database import engine, Base
from app.infrastructure.openai_service import OpenAIService
from app.infrastructure.repositories.order_repository import PostgresOrderRepository
from app.application.orchestrator import Orchestrator

# 2. Interface Adapters (Webhooks)
from app.interfaces import twilio_webhook

# Create Database Tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.PROJECT_NAME)

# ---------------------------------------------------------
# COMPOSITION ROOT (Dependency Injection)
# ---------------------------------------------------------
# 1. Create the concrete tools
ai_service = OpenAIService()
order_repo = PostgresOrderRepository()

# 2. Inject them into the Orchestrator
orchestrator_instance = Orchestrator(ai_service=ai_service, order_repo=order_repo)

# 3. Save Orchestrator to Global App State 
# (So twilio_webhook.py can access it via request.app.state.orchestrator)
app.state.orchestrator = orchestrator_instance

# 4. Include Routers
app.include_router(twilio_webhook.router)

# ---------------------------------------------------------
# Routes
# ---------------------------------------------------------

class WhatsAppPayload(BaseModel):
    user_id: str
    message: str

@app.get("/")
def health_check():
    return {"status": "active", "system": "Bakery Bot Orchestrator"}

@app.post("/webhook/test")
async def test_chat(payload: WhatsAppPayload):
    """
    Test endpoint to simulate WhatsApp locally.
    Uses the injected orchestrator instance.
    """
    response_text = await orchestrator_instance.process_message(payload.user_id, payload.message)
    return {"response": response_text}