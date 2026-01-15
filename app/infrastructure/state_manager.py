import json
import redis
from app.core.config import settings

# Define our States
STATE_IDLE = "IDLE"
STATE_ORDERING = "ORDERING"
STATE_CONFIRMING = "CONFIRMING"

class StateManager:
    def __init__(self):
        self.redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
        self.ttl = 3600  # Sessions expire after 1 hour

    def get_state(self, user_id: str) -> str:
        """Get user's current state. Default to IDLE."""
        state = self.redis.get(f"user:{user_id}:state")
        return state if state else STATE_IDLE

    def set_state(self, user_id: str, new_state: str):
        """Update the user's state."""
        self.redis.setex(f"user:{user_id}:state", self.ttl, new_state)

    def get_context(self, user_id: str) -> dict:
        """Get the temporary cart/order details."""
        data = self.redis.get(f"user:{user_id}:context")
        return json.loads(data) if data else {"items": []}

    def update_context(self, user_id: str, updates: dict):
        """Merge new data into the existing context."""
        current = self.get_context(user_id)
        current.update(updates)
        self.redis.setex(f"user:{user_id}:context", self.ttl, json.dumps(current))

    def clear_session(self, user_id: str):
        """Reset everything (after order is complete)."""
        self.redis.delete(f"user:{user_id}:state")
        self.redis.delete(f"user:{user_id}:context")

# Global Instance
state_manager = StateManager()