from app.infrastructure.openai_service import OpenAIService

class Orchestrator:
    def __init__(self):
        self.ai_service = OpenAIService()

    async def process_message(self, user_id: str, message_text: str) -> str:
        # 1. Detect Intent
        intent = await self.ai_service.get_intent(message_text)
        print(f"🔍 Detected Intent: {intent}")

        # 2. Handle specific hard-coded logic (e.g., Handoff)
        if intent == "handoff":
            return "Entendido veci, ya le aviso a una persona real para que le atienda. Espere un momento 👍"

        # 3. Generate AI Response (RAG + Style)
        response = await self.ai_service.generate_response(message_text, intent)
        
        return response

# Global instance
orchestrator = Orchestrator()