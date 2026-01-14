from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Bakery WhatsApp Bot"
    API_V1_STR: str = "/api/v1"
    
    # Database & Redis
    DATABASE_URL: str
    REDIS_URL: str
    
    # AI Providers
    # OPENAI_API_KEY is no longer needed!
    DEEPSEEK_API_KEY: str
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    
    # WhatsApp / Twilio (Optional)
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_PHONE_NUMBER: Optional[str] = None
    
    class Config:
        env_file = ".env"

settings = Settings()