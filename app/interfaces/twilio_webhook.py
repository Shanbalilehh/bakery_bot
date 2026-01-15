from fastapi import APIRouter, Form, Request, HTTPException
from fastapi.responses import Response

router = APIRouter()

@router.post("/webhook/twilio")
async def whatsapp_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...)
):
    """
    Twilio Webhook endpoint.
    Retrieves the orchestrator from app.state (Dependency Injection).
    """
    try:
        # 1. Get the Orchestrator instance from the App State
        orchestrator = request.app.state.orchestrator
        
        # 2. Clean inputs (Twilio sends 'whatsapp:+12345')
        user_id = From.replace("whatsapp:", "")
        message_text = Body.strip()

        # 3. Process Logic
        response_text = await orchestrator.process_message(user_id, message_text)

        # 4. Return TwiML (XML)
        # Twilio requires XML response. We use a simple f-string for speed.
        xml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Message>{response_text}</Message>
        </Response>"""
        
        return Response(content=xml_response, media_type="application/xml")

    except Exception as e:
        print(f"❌ Webhook Error: {e}")
        # Return empty response to stop Twilio retries in case of error
        return Response(content="<Response></Response>", media_type="application/xml")