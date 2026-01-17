from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # --- Required Fields ---
    PROJECT_NAME: str = "Bakery_Bot"
    DEEPSEEK_API_KEY: str
    DATABASE_URL: str
    REDIS_URL: str
    
    # --- Optional / Default Fields ---
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"

    # --- Fix for the Crash ---
    # We explicitly add these so Pydantic knows they exist in .env
    POSTGRES_USER: str | None = None
    POSTGRES_PASSWORD: str | None = None
    POSTGRES_DB: str | None = None

    # --- Configuration ---
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"  # CRITICAL: This tells Pydantic to ignore any other unknown variables in .env instead of crashing
    )

settings = Settings()