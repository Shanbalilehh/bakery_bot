import time
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.requests import Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.exc import OperationalError  # <-- Import this
from app.core.config import settings

# 1. Infrastructure & Domain Imports
from app.domain.models import Order
from app.infrastructure.database import SessionLocal, engine, Base
from app.infrastructure.openai_service import OpenAIService
from app.infrastructure.repositories.order_repository import PostgresOrderRepository
from app.application.orchestrator import Orchestrator
from app.interfaces import twilio_webhook

app = FastAPI(title=settings.PROJECT_NAME)
templates = Jinja2Templates(directory="app/templates")

# ---------------------------------------------------------
# DATABASE CONNECTION (With Retry Logic)
# ---------------------------------------------------------
# We try to connect 5 times before giving up.
MAX_RETRIES = 10
WAIT_SECONDS = 3

for attempt in range(MAX_RETRIES):
    try:
        print(f"🔄 Attempting DB connection ({attempt + 1}/{MAX_RETRIES})...")
        Base.metadata.create_all(bind=engine)
        print("✅ DB Connected and Tables Created.")
        break  # Success! Exit loop
    except OperationalError as e:
        print(f"⚠️ DB not ready yet. Waiting {WAIT_SECONDS}s...")
        time.sleep(WAIT_SECONDS)
else:
    print("❌ Could not connect to DB after retries. Exiting.")
    # The app will likely crash here, but logs will be clear.

# ---------------------------------------------------------
# COMPOSITION ROOT
# ---------------------------------------------------------
try:
    ai_service = OpenAIService()
    order_repo = PostgresOrderRepository()
    orchestrator_instance = Orchestrator(ai_service=ai_service, order_repo=order_repo)
    app.state.orchestrator = orchestrator_instance
except Exception as e:
    print(f"❌ Error initializing services: {e}")

# Include Routers
app.include_router(twilio_webhook.router)

class WhatsAppPayload(BaseModel):
    user_id: str
    message: str

@app.get("/")
def health_check():
    # If DB is down, orchestrator might be None, so we handle that safely
    status = "active" if hasattr(app.state, "orchestrator") else "degraded"
    return {"status": status, "system": "Bakery Bot Orchestrator"}

@app.post("/webhook/test")
async def test_chat(payload: WhatsAppPayload):
    response_text = await app.state.orchestrator.process_message(payload.user_id, payload.message)
    return {"response": response_text}

@app.get("/admin/orders", response_class=HTMLResponse)
def read_orders(request: Request):
    db = SessionLocal()
    try:
        # Get latest 20 orders
        orders = db.query(Order).order_by(Order.created_at.desc()).limit(20).all()
        return templates.TemplateResponse("dashboard.html", {"request": request, "orders": orders})
    finally:
        db.close()