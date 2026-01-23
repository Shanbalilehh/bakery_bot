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
    Body: str = Form(...),
    NumMedia: int = Form(0),  # NEW: Catch media count
    MediaContentType0: str = Form(None) # NEW: Catch media type
):
    """
    Twilio Webhook endpoint.
    Retrieves the orchestrator from app.state (Dependency Injection).
    """
    print(f"\n{'='*60}")
    print(f"🔔 TWILIO WEBHOOK CALLED")
    print(f"{'='*60}")
    print(f"From: {From}")
    print(f"Body: {Body}")
    
    # ---------------------------------------------------------
    # 1. AUDIO / MEDIA GUARDRAIL (Added)
    # ---------------------------------------------------------
    if NumMedia > 0:
        print(f"⚠️ MEDIA DETECTED: {NumMedia} files. Type: {MediaContentType0}")
        # Check if it is an audio file (voice note)
        if MediaContentType0 and "audio" in MediaContentType0:
            print("🚨 ALERT: Audio received (Not yet supported). Ignoring.")
            # Polite refusal XML
            xml_response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>Mil disculpas veci, por el momento mi sistema no me deja escuchar audios 😔. ¿Me lo podría escribir? 🙏</Message>
</Response>"""
            return Response(content=xml_response, media_type="application/xml")
    # ---------------------------------------------------------

    try:
        # Log the incoming request for debugging
        logger.info(f"📨 Twilio Webhook: From={From}, Body={Body}")
        print(f"✅ Request received and logged")
        
        # 1. Get the Orchestrator instance from the App State
        orchestrator = request.app.state.orchestrator
        print(f"✅ Orchestrator retrieved: {orchestrator}")
        
        # 2. Clean inputs (Twilio sends 'whatsapp:+12345')
        user_id = From.replace("whatsapp:", "")
        message_text = Body.strip()
        print(f"✅ Cleaned - user_id: {user_id}, message: {message_text}")

        # 3. Process Logic
        print(f"⏳ Processing message...")
        response_text = await orchestrator.process_message(user_id, message_text)
        print(f"✅ Got response_text: '{response_text}'")
        print(f"   Type: {type(response_text)}, Length: {len(response_text) if response_text else 0}")
        
        logger.info(f"✅ Response to {user_id}: {response_text}")

        # 4. Return TwiML (XML) with properly escaped content
        # IMPORTANT: Special characters in response_text must be XML-escaped
        if response_text:
            escaped_text = escape(response_text)
            print(f"✅ Escaped response: '{escaped_text}'")
            xml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{escaped_text}</Message>
</Response>"""
        else:
            # Return empty response for blocked/silent cases
            print(f"⚠️  Empty response - returning silent response")
            xml_response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
</Response>"""
        
        print(f"✅ XML Response:")
        print(xml_response)
        print(f"{'='*60}\n")
        
        return Response(content=xml_response, media_type="application/xml")

    except Exception as e:
        logger.error(f"❌ Webhook Error: {e}", exc_info=True)
        print(f"❌ EXCEPTION in webhook: {e}")  # Also print to console
        import traceback
        traceback.print_exc()
        # Return empty response to stop Twilio retries in case of error
        return Response(content="<Response></Response>", media_type="application/xml")