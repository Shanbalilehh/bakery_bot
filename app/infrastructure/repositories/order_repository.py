import json
from typing import List
from sqlalchemy import desc # <-- Added for sorting
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

    def get_all_orders(self, limit: int = 50) -> List[Order]:
        """
        Retrieves the latest orders from the database.
        Ordered by created_at DESC (Newest first).
        """
        session = SessionLocal()
        try:
            orders = session.query(Order).order_by(desc(Order.created_at)).limit(limit).all()
            return orders
        except Exception as e:
            print(f"❌ DB Read Error: {e}")
            return []
        finally:
            session.close()