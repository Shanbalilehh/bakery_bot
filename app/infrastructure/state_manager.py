import json
import redis
from redis.exceptions import ConnectionError, TimeoutError, RedisError
from app.core.config import settings

# Define our States
STATE_IDLE = "IDLE"
STATE_ORDERING = "ORDERING"
STATE_CONFIRMING = "CONFIRMING"

class StateManager:
    def __init__(self):
        # 1. Primary Memory (Redis)
        try:
            self.redis = redis.from_url(
                settings.REDIS_URL, 
                decode_responses=True, 
                socket_connect_timeout=1  # Fail fast if Redis is down
            )
            # Test connection immediately
            self.redis.ping()
            self.redis_available = True
            print("✅ StateManager: Connected to Redis.")
        except Exception as e:
            print(f"⚠️ StateManager: Redis unreachable ({e}). Using RAM fallback.")
            self.redis_available = False

        # 2. Fallback Memory (RAM)
        self._memory_store = {}
        self.ttl = 3600  # Sessions expire after 1 hour

    def get_state(self, user_id: str) -> str:
        """Get user's current state. Default to IDLE."""
        key = f"user:{user_id}:state"
        
        # Try Redis
        if self.redis_available:
            try:
                state = self.redis.get(key)
                return state if state else STATE_IDLE
            except RedisError as e:
                self._handle_redis_error(e)

        # Fallback to RAM
        return self._memory_store.get(key, STATE_IDLE)

    def set_state(self, user_id: str, new_state: str):
        """Update the user's state."""
        key = f"user:{user_id}:state"
        
        # Try Redis
        if self.redis_available:
            try:
                self.redis.setex(key, self.ttl, new_state)
            except RedisError as e:
                self._handle_redis_error(e)
        
        # Always write to RAM (to keep sync in case Redis comes back and fails again)
        self._memory_store[key] = new_state

    def get_context(self, user_id: str) -> dict:
        """Get the temporary cart/order details."""
        key = f"user:{user_id}:context"
        data = None

        # Try Redis
        if self.redis_available:
            try:
                data = self.redis.get(key)
            except RedisError as e:
                self._handle_redis_error(e)

        # Parse Data (Redis returns string, RAM returns dict/string)
        if data:
            return json.loads(data)
        
        # Fallback to RAM if Redis returned nothing or failed
        ram_data = self._memory_store.get(key)
        # RAM might store it as a dict directly, or json string depending on how we saved it.
        # For consistency with Redis logic, let's assume we store the object in RAM.
        return ram_data if ram_data else {"items": []}

    def update_context(self, user_id: str, updates: dict):
        """Merge new data into the existing context."""
        key = f"user:{user_id}:context"
        
        # 1. Get current (Handles fallback logic internally)
        current = self.get_context(user_id)
        current.update(updates)
        
        json_data = json.dumps(current)

        # 2. Save to Redis
        if self.redis_available:
            try:
                self.redis.setex(key, self.ttl, json_data)
            except RedisError as e:
                self._handle_redis_error(e)

        # 3. Save to RAM (Store as dict for easier retrieval, or JSON for consistency)
        self._memory_store[key] = current

    def clear_session(self, user_id: str):
        """Reset everything (after order is complete)."""
        state_key = f"user:{user_id}:state"
        context_key = f"user:{user_id}:context"

        if self.redis_available:
            try:
                self.redis.delete(state_key)
                self.redis.delete(context_key)
            except RedisError as e:
                self._handle_redis_error(e)
        
        # Clear RAM
        self._memory_store.pop(state_key, None)
        self._memory_store.pop(context_key, None)

    def _handle_redis_error(self, e):
        """Log error and switch flag to False to stop trying Redis for a while."""
        print(f"❌ Redis Error: {e}. Switching to RAM mode.")
        self.redis_available = False

# Global Instance
state_manager = StateManager()