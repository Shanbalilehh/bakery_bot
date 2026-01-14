from fastapi import APIRouter, Form, Response # <--- Added Response here
from twilio.twiml.messaging_response import MessagingResponse
from app.application.orchestrator import orchestrator

router = APIRouter()

@router.post("/webhook/twilio")
async def twilio_webhook(
    From: str = Form(...),
    Body: str = Form(...)
):
    try:
        user_id = From.replace("whatsapp:", "")
        
        # Process the message
        bot_response_text = await orchestrator.process_message(user_id, Body)
        
        # Create TwiML
        resp = MessagingResponse()
        resp.message(bot_response_text)
        
        # CRITICAL FIX: Return as XML, not plain string
        return Response(content=str(resp), media_type="application/xml")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return Response(content=str(MessagingResponse()), media_type="application/xml")