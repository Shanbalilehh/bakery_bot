import json
from typing import List
from app.interfaces.IOrderRepository import IOrderRepository
from app.domain.models import Order
from app.infrastructure.database import SessionLocal

class PostgresOrderRepository(IOrderRepository):
    def save_order(self, user_phone: str, items: List[dict], total_price: str = "Pending") -> bool:
        session = SessionLocal()
        try:
            # SQLAlchemy handles list-of-dicts if column is JSONB, otherwise dump to string
            new_order = Order(
                user_phone=user_phone,
                items=items, 
                status="confirmed",
                total_price=total_price
            )
            session.add(new_order)
            session.commit()
            return True
        except Exception as e:
            print(f"❌ DB Error: {e}")
            session.rollback()
            return False
        finally:
            session.close()