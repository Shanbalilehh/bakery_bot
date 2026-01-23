import asyncio
import random
from datetime import datetime, time
import pytz

from app.interfaces.IAiService import IAiService
from app.interfaces.IOrderRepository import IOrderRepository
from app.infrastructure.state_manager import state_manager, STATE_IDLE, STATE_ORDERING, STATE_CONFIRMING
# Ensure you have the NotificationService imported (even if passing via Type Hint only)
# from app.infrastructure.notification_service import NotificationService 

# --- CONFIG ---
TIMEZONE = pytz.timezone("America/Guayaquil")
BUSINESS_OPEN = time(7, 0)
BUSINESS_CLOSE = time(18, 0)
FRUSTRATION_KEYWORDS = ["molesto", "no contestan", "problema", "pesimo", "nadie responde", "queja"]
BLOCKED_NUMBERS = {"+593967550507"}

PAYMENT_INFO = """
## ✨ Formas de Pago – En Dulce
### 💛 Opción 1 – Banco Pichincha
* **Cuenta:** 2100038192 (Cte)
* **Titular:** Franklin Utreras
* **CI:** 1715211676
### 💚 Opción 2 – Produbanco
* **Cuenta:** 12095108731 (Aho)
* **Titular:** Carlos Peña
"""

class Orchestrator:
    def __init__(self, ai_service: IAiService, order_repo: IOrderRepository, notifier):
        self.ai_service = ai_service
        self.order_repo = order_repo
        self.notifier = notifier # Injected NotificationService

    async def process_message(self, user_id: str, message_text: str) -> str:
        print(f"\n[ORCHESTRATOR] Processing message from {user_id}")
        
        # 1. CHECKS
        if user_id in BLOCKED_NUMBERS: return ""
        if any(w in message_text.lower() for w in FRUSTRATION_KEYWORDS):
            return await self._trigger_handoff(user_id, "Cliente molesto")

        # 2. STATE
        current_state = state_manager.get_state(user_id)
        context = state_manager.get_context(user_id) or {} # Ensure dict
        history = state_manager.get_history(user_id)

        if not history: await asyncio.sleep(random.uniform(2.0, 4.0))

        # 3. INTENT
        intent = await self.ai_service.get_intent(message_text)
        print(f"[ORCHESTRATOR] State: {current_state} | Intent: {intent}")

        # --- STATE MACHINE ---
        response = ""
        
        # Priority: Check for "Cancel" globally
        if "cancel" in message_text.lower():
            state_manager.clear_session(user_id)
            return "Listo veci, pedido cancelado."

        if current_state == STATE_ORDERING:
            response = await self._handle_active_ordering(user_id, message_text, intent, context, history)
        
        elif current_state == STATE_CONFIRMING:
            response = await self._handle_confirmation(user_id, message_text, context)

        elif intent == "handoff":
            response = await self._trigger_handoff(user_id, "Solicitud directa")
        
        elif intent == "order_intent":
            state_manager.set_state(user_id, STATE_ORDERING)
            response = await self._handle_active_ordering(user_id, message_text, intent, context, history)
            
        else:
            response = await self.ai_service.generate_response(message_text, intent, history)

        if response:
            state_manager.add_to_history(user_id, "User", message_text)
            state_manager.add_to_history(user_id, "AI", response)
        
        return response

    # --- HANDLERS ---

    async def _trigger_handoff(self, user_id, reason):
        # Notify Admin
        self.notifier.notify_admin_new_order(user_id, [{"product": f"⚠️ HANDOFF: {reason}"}])
        return "Para ayudarle mejor, le voy a pasar con una persona del equipo 😊\nUn momento por favor."

    async def _handle_active_ordering(self, user_id, message_text, intent, context, history):
        triggers = ["listo", "eso es todo", "confirmar", "ya", "gracias", "fin"]
        
        # 1. EXTRACT DATA
        extraction_data = await self.ai_service.extract_order_items(message_text, history)
        new_items = extraction_data.get("items", [])
        new_modifiers = extraction_data.get("modifiers", {})
        new_delivery = extraction_data.get("delivery_info", {})

        # 2. UPDATE CART (The "Smart" Logic)
        current_items = context.get("items", [])
        
        for item in new_items:
            action = item.get("action", "add")
            product_name = item.get("product", "").lower()
            
            if action == "add":
                # Check if exists to merge, or append? Simple append for now.
                current_items.append(item)
                
            elif action == "remove":
                # Filter out items that match the product name (fuzzy match)
                current_items = [i for i in current_items if product_name not in i.get("product", "").lower()]
                
            elif action == "update":
                # Find and update quantity
                found = False
                for i in current_items:
                    if product_name in i.get("product", "").lower():
                        i["quantity"] = item.get("quantity", 1)
                        found = True
                # If not found, assume it's an add
                if not found:
                    current_items.append(item)

        # Update Modifiers & Delivery (Merge)
        current_modifiers = context.get("modifiers", {})
        current_modifiers.update({k: v for k, v in new_modifiers.items() if v}) # Only update if not null
        
        current_delivery = context.get("delivery_info", {})
        current_delivery.update({k: v for k, v in new_delivery.items() if v})

        # Save Context
        updated_context = {
            "items": current_items,
            "modifiers": current_modifiers,
            "delivery_info": current_delivery
        }
        state_manager.update_context(user_id, updated_context)

        # 3. TRANSITION & RESPONSE
        if any(t == message_text.lower().strip() for t in triggers):
            state_manager.set_state(user_id, STATE_CONFIRMING)
            return self._generate_confirmation_summary(updated_context)

        # Dynamic Response based on Action
        if new_items:
            action = new_items[0].get("action", "add")
            if action == "remove":
                return f"👍 Listo, quitado del pedido. ¿Algo más?"
            elif action == "update":
                return f"👍 Corregido: {new_items[0]['quantity']}x {new_items[0]['product']}. ¿Algo más?"
            else:
                added_text = ", ".join([f"{item['quantity']}x {item['product']}" for item in new_items])
                return f"✅ Anotado: {added_text}.\n\n(¿Algo más? ¿Algún sabor en especial?)"
        
        elif new_modifiers:
             return f"Perfecto, anotado el detalle. 👍"

        elif new_delivery.get("method"):
             return f"Entendido, será para {new_delivery['method']}. ¿Algo más?"

        # Fallback to AI Chat
        return await self.ai_service.generate_response(message_text, intent, history)


    async def _handle_confirmation(self, user_id, message_text, context):
        """Smart Checkout Gate"""
        
        # 1. If user says YES to summary
        if any(w in message_text.lower() for w in ["si", "claro", "ok", "correcto", "simon"]):
            
            # --- VALIDATION GATES ---
            delivery_info = context.get("delivery_info", {})
            method = delivery_info.get("method")
            address = delivery_info.get("address")

            # Gate 1: Method undefined?
            if not method:
                return "Perfecto. ¿Sería para **retirar** en el local o **entrega** a domicilio? 🛵"

            # Gate 2: Delivery but no Address?
            if method == "delivery" and not address:
                # Check if address was just provided in this message?
                # (Simple check, otherwise ask)
                return "Listo. Ayúdeme con su **dirección exacta** y referencia para el envío 📍"

            # --- ALL GOOD: FINALIZE ---
            final_order_data = context.get("items", [])
            # TODO: Ideally save modifiers/delivery to DB too. 
            # For now passing items list.
            
            success = self.order_repo.save_order(user_id, final_order_data)
            
            if success:
                state_manager.clear_session(user_id)
                self.notifier.notify_admin_new_order(user_id, final_order_data)
                return f"¡Listo veci! Su pedido está confirmado 🎉.\n\n{PAYMENT_INFO}"
            else:
                return "Uy veci, hubo un error guardando el pedido. Intente de nuevo."

        # 2. If user provides missing info (Address/Method) logic
        # We re-run extraction to see if they answered the Gate question
        extraction = await self.ai_service.extract_order_items(message_text, "")
        new_delivery = extraction.get("delivery_info", {})
        
        if new_delivery.get("method") or new_delivery.get("address"):
            # Update context and re-ask confirmation
            current_delivery = context.get("delivery_info", {})
            if new_delivery.get("method"): current_delivery["method"] = new_delivery["method"]
            if new_delivery.get("address"): current_delivery["address"] = new_delivery["address"]
            
            state_manager.update_context(user_id, {"delivery_info": current_delivery})
            
            # Re-summarize to confirm the new details
            return self._generate_confirmation_summary(state_manager.get_context(user_id))

        # 3. If user says NO or wants changes
        state_manager.set_state(user_id, STATE_ORDERING)
        return "Entendido veci, ¿qué desea cambiar o agregar?"

    def _generate_confirmation_summary(self, context):
        items = context.get("items", [])
        modifiers = context.get("modifiers", {})
        delivery = context.get("delivery_info", {})

        if not items:
            return "No tengo nada anotado veci. ¿Qué desea pedir?"
        
        # Build Summary
        summary = "📝 *Resumen del Pedido:*\n"
        for item in items:
            summary += f"• {item.get('quantity', 1)}x {item.get('product', 'Unknown')}\n"
        
        if modifiers.get("flavor"): summary += f"  - Sabor: {modifiers['flavor']}\n"
        if modifiers.get("dedication"): summary += f"  - Texto: \"{modifiers['dedication']}\"\n"
        
        method = delivery.get("method", "Por definir")
        summary += f"\n🚚 **Entrega:** {method.capitalize() if method else '?'}"
        if delivery.get("address"): summary += f" ({delivery['address']})"

        return f"{summary}\n\n¿Está todo correcto? (Responda Sí o No)"