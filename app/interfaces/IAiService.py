from abc import ABC, abstractmethod
from typing import List, Dict, Any

class IAiService(ABC):
    @abstractmethod
    async def get_intent(self, user_message: str) -> str:
        pass

    @abstractmethod
    async def generate_response(self, user_message: str, intent: str) -> str:
        pass

    @abstractmethod
    async def extract_order_items(self, user_message: str) -> List[Dict[str, Any]]:
        pass