import asyncio
import random
from datetime import datetime, time
import pytz

from app.interfaces.IAiService import IAiService
from app.interfaces.IOrderRepository import IOrderRepository
from app.infrastructure.state_manager import state_manager, STATE_IDLE, STATE_ORDERING, STATE_CONFIRMING

# --- CONFIG ---
# Ecuador Timezone
TIMEZONE = pytz.timezone("America/Guayaquil")
BUSINESS_OPEN = time(7, 0)
BUSINESS_CLOSE = time(6, 0) # 6:00 PM

# Frustration Triggers (Requirement 3.1)
FRUSTRATION_KEYWORDS = ["molesto", "no contestan", "problema", "pesimo", "nadie responde", "queja", "mal servicio"]

BLOCKED_NUMBERS = {"+593985445631", "+593967550507"} # Add family numbers here
PAYMENT_INFO = """
## ✨ Formas de Pago – En Dulce

### 💛 Opción 1 – Banco Pichincha

* **Cuenta Corriente:** 2100038192
* **Titular:** Franklin Utreras
* **CI:** 1715211676
* **Teléfono:** 0992788266
* **Correo:** [en.dulce.ventas@gmail.com](mailto:en.dulce.ventas@gmail.com)

---

### 💚 Opción 2 – Produbanco

* **Cuenta de Ahorros:** 12095108731
* **Titular:** Carlos Peña
* **CI:** 1716869886
* **Correo:** [en.dulce.ventas@gmail.com](mailto:en.dulce.ventas@gmail.com)
"""

class Orchestrator:
    def __init__(self, ai_service: IAiService, order_repo: IOrderRepository):
        # Dependency Injection: We pass the tools we need, we don't create them here.
        self.ai_service = ai_service
        self.order_repo = order_repo

    def _is_open(self):
        """Check if current time is within business hours."""
        now = datetime.now(TIMEZONE).time()
        return BUSINESS_OPEN <= now <= BUSINESS_CLOSE

    async def process_message(self, user_id: str, message_text: str) -> str:
        # 1. BLOCKLIST CHECK
        if user_id in BLOCKED_NUMBERS:
            return "" # Ignore completely (Bot stays silent)
        
        # 2. AFTER-HOURS CHECK (Requirement 3.3)
        if not self._is_open():
             return ("En este momento no estamos atendiendo.\n\n"
                     "Mañana con gusto retomamos su mensaje 😊\n"
                     "Si desea, puede dejarnos su pedido y lo confirmamos apenas abramos.")

        # 3. FRUSTRATION CHECK (Requirement 3.1)
        if any(word in message_text.lower() for word in FRUSTRATION_KEYWORDS):
            return await self._trigger_handoff(user_id, "Cliente molesto detectado")

        # 2. LOAD STATE & HISTORY
        current_state = state_manager.get_state(user_id)
        context = state_manager.get_context(user_id)
        history = state_manager.get_history(user_id)

        # 3. HUMAN DELAY (Only for new conversations or long breaks)
        # If history is empty, it's a "First Message"
        if not history:
            await asyncio.sleep(random.uniform(2.0, 4.0))

        # 4. INTENT DETECTION
        intent = await self.ai_service.get_intent(message_text)
        print(f"[{user_id}] State: {current_state} | Intent: {intent}")

        response = ""

        # --- STATE MACHINE ---
        if current_state == STATE_ORDERING:
            response = await self._handle_active_ordering(user_id, message_text, intent, context, history)
        
        elif current_state == STATE_CONFIRMING:
            response = await self._handle_confirmation(user_id, message_text, context)

        # GLOBAL / IDLE
        elif intent == "handoff":
            response = await self._trigger_handoff(user_id, "Solicitud directa")
            # TODO: Here we would ping the Admin Dashboard technically
        
        elif "cancel" in message_text.lower():
            state_manager.clear_session(user_id)
            response = "Listo veci, pedido cancelado."

        elif intent == "order_intent":
            state_manager.set_state(user_id, STATE_ORDERING)
            response = await self._handle_active_ordering(user_id, message_text, intent, context, history)
            
        else:
            # General Chat / Menu Query
            response = await self.ai_service.generate_response(message_text, intent, history)

        # 5. SAVE HISTORY (Update memory for next turn)
        # We don't save the history if the bot was silent (blocked)
        if response:
            state_manager.add_to_history(user_id, "User", message_text)
            state_manager.add_to_history(user_id, "AI", response)

        return response

    # ------------------------------------------------------------------
    # SUB-HANDLERS (Private methods for logic isolation)
    # ----------------------------------------------------------------__

    async def _trigger_handoff(self, user_id, reason):
        print(f"🚨 HANDOFF for {user_id}: {reason}")
        return ("Para ayudarle mejor, le voy a pasar con una persona del equipo 😊\n"
                "Un momento por favor.")
    
    async def _handle_active_ordering(self, user_id, message_text, intent, context, history):
        triggers = ["listo", "eso es todo", "confirmar", "ya", "gracias", "fin"]
        if any(t == message_text.lower().strip() for t in triggers):
            state_manager.set_state(user_id, STATE_CONFIRMING)
            return self._generate_confirmation_summary(context)

        # Fix "Question Trap": If it's a question, answer it using context
        if intent == "menu_query" or "?" in message_text:
            return await self.ai_service.generate_response(message_text, intent, history)

        # Extract items using HISTORY context (fixes "one of those")
        new_items = await self.ai_service.extract_order_items(message_text, history)
        
        if new_items:
            current_items = context.get("items", [])
            current_items.extend(new_items)
            state_manager.update_context(user_id, {"items": current_items})
            added_text = ", ".join([f"{item['quantity']}x {item['product']}" for item in new_items])
            return f"✅ Anotado: {added_text}.\n\n(¿Algo más? O dígame 'listo')"
        else:
            # SILENT FAILURE / ALERT LOGIC
            # Instead of saying "I don't understand", we try to be helpful or handoff
            # For now, we return a polite confusion message. 
            # In a real "Silent Alert" system, we would log this event specifically for the dashboard.
            print(f"⚠️ [ALERT] Bot confused by: {message_text}")
            return "Mil disculpas veci, no le capté bien. ¿Me repite el nombre del producto o desea ver el menú?"

    async def _handle_confirmation(self, user_id, message_text, context):
        """Handles the final Yes/No Logic"""
        if any(w in message_text.lower() for w in ["si", "claro", "ok", "correcto", "simon"]):
            success = self.order_repo.save_order(user_id, context.get("items", []))
            if success:
                state_manager.clear_session(user_id)
                # RETURN PAYMENT INFO HERE
                return f"¡Listo veci! Su pedido está confirmado 🎉.\n\n{PAYMENT_INFO}"
            else:
                return "Uy veci, hubo un error guardando el pedido. Intente de nuevo."
        else:
            state_manager.set_state(user_id, STATE_ORDERING)
            return "Entendido veci, ¿qué desea cambiar o agregar?"

    def _generate_confirmation_summary(self, context):
        items = context.get("items", [])
        if not items:
            return "No tengo nada anotado veci. ¿Qué desea pedir?"
        summary_lines = [f"• {item.get('quantity', 1)}x {item.get('product', 'Unknown')}" for item in items]
        summary = "\n".join(summary_lines)
        return f"Perfecto veci. Confirmo su pedido:\n\n{summary}\n\n¿Está todo correcto? (Responda Sí o No)"