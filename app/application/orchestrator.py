from app.interfaces.IAiService import IAiService
from app.interfaces.IOrderRepository import IOrderRepository
from app.infrastructure.state_manager import state_manager, STATE_IDLE, STATE_ORDERING, STATE_CONFIRMING

class Orchestrator:
    def __init__(self, ai_service: IAiService, order_repo: IOrderRepository):
        # Dependency Injection: We pass the tools we need, we don't create them here.
        self.ai_service = ai_service
        self.order_repo = order_repo

    async def process_message(self, user_id: str, message_text: str) -> str:
        current_state = state_manager.get_state(user_id)
        context = state_manager.get_context(user_id)

        # 1. Get Intent (We need this to decide strategy)
        intent = await self.ai_service.get_intent(message_text)
        print(f"[{user_id}] State: {current_state} | Intent: {intent}")

        # --- PRIORITY 1: STATE SPECIFIC HANDLERS ---
        # We check state FIRST to prevent "Listo" from triggering global handoff incorrectly
        
        if current_state == STATE_ORDERING:
            return await self._handle_active_ordering(user_id, message_text, intent, context)

        elif current_state == STATE_CONFIRMING:
            return await self._handle_confirmation(user_id, message_text, context)

        # --- PRIORITY 2: GLOBAL INTENTS (Only if IDLE or State didn't capture) ---
        if intent == "handoff":
            return "Entendido veci, ya le aviso a una persona real. Espere un momento 👍"
        
        if "cancel" in message_text.lower():
            state_manager.clear_session(user_id)
            return "Listo veci, pedido cancelado."

        # --- PRIORITY 3: DEFAULT (IDLE) ---
        if intent == "order_intent":
            state_manager.set_state(user_id, STATE_ORDERING)
            # Recursively call ordering handler to process this first item immediately
            return await self._handle_active_ordering(user_id, message_text, intent, context)
            
        # Fallback: Just chat/answer questions
        return await self.ai_service.generate_response(message_text, intent)

    # ------------------------------------------------------------------
    # SUB-HANDLERS (Private methods for logic isolation)
    # ------------------------------------------------------------------

    async def _handle_active_ordering(self, user_id, message_text, intent, context):
        """
        Handles logic when user is in the middle of building a cart.
        Fixes the bug where questions were treated as orders.
        """
        # 1. Check for Exit Triggers
        triggers = ["listo", "eso es todo", "confirmar", "ya", "gracias", "fin"]
        if any(t == message_text.lower().strip() for t in triggers):
            state_manager.set_state(user_id, STATE_CONFIRMING)
            return self._generate_confirmation_summary(context)

        # 2. Check if user is asking a Question instead of ordering
        # If the intent is CLEARLY a menu query (price, ingredients), answer it.
        if intent == "menu_query" or "?" in message_text:
            return await self.ai_service.generate_response(message_text, intent)

        # 3. Process as Order Item
        new_items = await self.ai_service.extract_order_items(message_text)
        
        if new_items:
            current_items = context.get("items", [])
            current_items.extend(new_items)
            state_manager.update_context(user_id, {"items": current_items})
            
            # Helper to show what was added
            added_text = ", ".join([f"{item['quantity']}x {item['product']}" for item in new_items])
            return f"✅ Anotado: {added_text}.\n\n(¿Algo más? O dígame 'listo')"
        else:
            # If AI couldn't find items and it wasn't a question
            return "Mmm, no le entendí veci. ¿Qué producto desea? (O pregúnteme precios)"

    async def _handle_confirmation(self, user_id, message_text, context):
        """Handles the final Yes/No Logic"""
        if any(w in message_text.lower() for w in ["si", "claro", "ok", "correcto", "simon"]):
            # Use the Repository to save (SRP violation fixed)
            success = self.order_repo.save_order(user_id, context.get("items", []))
            
            if success:
                state_manager.clear_session(user_id)
                return "¡Listo veci! Su pedido está confirmado 🎉. Ya lo empezamos a preparar."
            else:
                return "Uy veci, hubo un error guardando el pedido. Intente de nuevo."
        else:
            # User said No
            state_manager.set_state(user_id, STATE_ORDERING)
            return "Entendido veci, ¿qué desea cambiar o agregar?"

    def _generate_confirmation_summary(self, context):
        items = context.get("items", [])
        if not items:
            return "No tengo nada anotado veci. ¿Qué desea pedir?"
        
        summary_lines = []
        for item in items:
            qty = item.get('quantity', 1)
            prod = item.get('product', 'Unknown')
            summary_lines.append(f"• {qty}x {prod}")

        summary = "\n".join(summary_lines)
        return f"Perfecto veci. Confirmo su pedido:\n\n{summary}\n\n¿Está todo correcto? (Responda Sí o No)"