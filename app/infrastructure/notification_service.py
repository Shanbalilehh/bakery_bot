from twilio.rest import Client
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        self.client = None
        self.enabled = False
        
        # Only initialize if credentials exist in .env
        if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
            try:
                self.client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                self.enabled = True
                print("✅ NotificationService: Twilio Client Initialized")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Twilio Client: {e}")
                print(f"❌ NotificationService Error: {e}")
        else:
            print("⚠️ NotificationService: Credentials missing in .env. Notifications disabled.")

    def notify_admin_new_order(self, user_phone: str, items: list):
        """Sends a WhatsApp message to the Admin."""
        if not self.enabled or not settings.ADMIN_PHONE_NUMBER:
            print("⚠️ NotificationService disabled or Admin number missing.")
            return

        # Format the message
        order_summary = "\n".join([f"- {item.get('quantity', 1)}x {item.get('product', 'Unknown')}" for item in items])
        message_body = (
            f"🔔 *NUEVO PEDIDO CONFIRMADO*\n\n"
            f"👤 Cliente: {user_phone}\n"
            f"🛒 Pedido:\n{order_summary}\n\n"
            f"💡 *Acción:* Revise el Dashboard o contacte al cliente."
        )

        try:
            # Twilio requires the "whatsapp:" prefix
            from_number = f"whatsapp:{settings.TWILIO_FROM_NUMBER}" if "whatsapp:" not in settings.TWILIO_FROM_NUMBER else settings.TWILIO_FROM_NUMBER
            to_number = f"whatsapp:{settings.ADMIN_PHONE_NUMBER}" if "whatsapp:" not in settings.ADMIN_PHONE_NUMBER else settings.ADMIN_PHONE_NUMBER

            self.client.messages.create(
                from_=from_number,
                body=message_body,
                to=to_number
            )
            print(f"✅ Admin Notification Sent to {settings.ADMIN_PHONE_NUMBER}")
        except Exception as e:
            logger.error(f"❌ Failed to send Admin Notification: {e}")
            print(f"❌ Notification Failed: {e}")