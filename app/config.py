import os
from dataclasses import dataclass


@dataclass
class Settings:
    database_url: str = "sqlite:///./certs.db"
    storage_dir: str = "./storage"
    max_recipients: int = 5000


def get_settings() -> Settings:
    """Read settings from environment variables (with sensible defaults)."""
    return Settings(
        database_url=os.getenv("DATABASE_URL", "sqlite:///./certs.db"),
        storage_dir=os.getenv("CERT_STORAGE_DIR", "./storage"),
        max_recipients=int(os.getenv("MAX_RECIPIENTS", "5000")),
    )
