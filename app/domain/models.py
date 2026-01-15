from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey
from sqlalchemy.sql import func
from app.infrastructure.database import Base

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_phone = Column(String, index=True)
    status = Column(String, default="pending")  # pending, confirmed, cancelled
    
    # We store the list of items as a JSON for speed in this MVP.
    # In a larger app, you'd make a separate OrderItems table.
    items = Column(JSON) 
    
    total_price = Column(String) # Storing as string to keep it simple (e.g. "$25.50")
    created_at = Column(DateTime(timezone=True), server_default=func.now())