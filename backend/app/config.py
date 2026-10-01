import os
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    PROJECT_NAME: str = "StudyGenie"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"

    # ==============================
    # AI API
    # ==============================

    GROQ_API_KEY: str = os.getenv(
        "GROQ_API_KEY",
        ""
    )

    GROQ_CHAT_MODEL: str = os.getenv(
        "GROQ_CHAT_MODEL",
        "openai/gpt-oss-20b"
    )

    # Local embedding model
    EMBEDDING_MODEL: str = (
        "sentence-transformers/all-MiniLM-L6-v2"
    )

    # ==============================
    # Database
    # ==============================

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'data' / 'studygenie.db'}"
    )

    # ==============================
    # JWT Settings
    # ==============================

    JWT_SECRET_KEY: str = os.getenv(
        "JWT_SECRET_KEY",
        "studygenie_super_secret_jwt_key_2026_change_in_production"
    )

    JWT_ALGORITHM: str = os.getenv(
        "JWT_ALGORITHM",
        "HS256"
    )

    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv(
            "ACCESS_TOKEN_EXPIRE_MINUTES",
            "1440"
        )
    )

    # ==============================
    # Qdrant Vector Database
    # ==============================

    QDRANT_URL: str = os.getenv(
        "QDRANT_URL",
        ""
    )

    QDRANT_API_KEY: str = os.getenv(
        "QDRANT_API_KEY",
        ""
    )

    # ==============================
    # File Storage
    # ==============================

    UPLOAD_DIR: str = os.getenv(
        "UPLOAD_DIR",
        str(BASE_DIR / "uploads")
    )

    class Config:
        env_file = str(BASE_DIR / ".env")
        env_file_encoding = "utf-8"
        extra = "allow"


settings = Settings()


# ==============================
# Ensure required directories exist
# ==============================

os.makedirs(
    settings.UPLOAD_DIR,
    exist_ok=True
)

os.makedirs(
    BASE_DIR / "data",
    exist_ok=True
)