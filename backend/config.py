from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # AI Keys
    ANTHROPIC_API_KEY: str = ""
    PERPLEXITY_API_KEY: str = ""

    # Local MLX model (runs on Apple Silicon via mlx_lm.server)
    LOCAL_MODEL: str = "mlx-community/Qwen3-8B-4bit"
    LOCAL_BASE_URL: str = "http://localhost:8080/v1"

    # Perplexity — ONLY for tasks that need live web search
    PERPLEXITY_MODEL: str = "sonar-pro"

    # App
    APP_ENV: str = "development"
    DATABASE_URL: str = "sqlite:///./data/magicmentor.db"
    MEMORY_DIR: str = "./data/users"

    # Job scraping defaults
    DEFAULT_LOCATION: str = "Portugal"
    JOBS_MAX_RESULTS: int = 50
    JOBS_MAX_HOURS_OLD: int = 168  # 1 week

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# Ensure data dirs exist
Path(settings.MEMORY_DIR).mkdir(parents=True, exist_ok=True)
Path("data").mkdir(exist_ok=True)
