from fastapi import APIRouter, Form, Request, HTTPException
from fastapi.responses import Response
import logging
from xml.sax.saxutils import escape

router = APIRouter()
logger = logging.getLogger(__name__)

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
        # Log the incoming request for debugging
        logger.info(f"📨 Twilio Webhook: From={From}, Body={Body}")
        
        # 1. Get the Orchestrator instance from the App State
        orchestrator = request.app.state.orchestrator
        
        # 2. Clean inputs (Twilio sends 'whatsapp:+12345')
        user_id = From.replace("whatsapp:", "")
        message_text = Body.strip()

        # 3. Process Logic
        response_text = await orchestrator.process_message(user_id, message_text)
        
        logger.info(f"✅ Response to {user_id}: {response_text}")

        # 4. Return TwiML (XML) with properly escaped content
        # IMPORTANT: Special characters in response_text must be XML-escaped
        if response_text:
            escaped_text = escape(response_text)
            xml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{escaped_text}</Message>
</Response>"""
        else:
            # Return empty response for blocked/silent cases
            xml_response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
</Response>"""
        
        return Response(content=xml_response, media_type="application/xml")

    except Exception as e:
        logger.error(f"❌ Webhook Error: {e}", exc_info=True)
        # Return empty response to stop Twilio retries in case of error
        return Response(content="<Response></Response>", media_type="application/xml")