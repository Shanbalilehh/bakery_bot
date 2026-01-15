from abc import ABC, abstractmethod
from typing import List, Dict

class IOrderRepository(ABC):
    @abstractmethod
    def save_order(self, user_phone: str, items: List[Dict], total_price: str) -> bool:
        pass