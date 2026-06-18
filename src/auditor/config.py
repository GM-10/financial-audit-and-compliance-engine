from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

class Settings(BaseSettings):
    # LLM Configuration
    openrouter_model: str = "openrouter:meta-llama/llama-3.1-8b-instruct:free"

    # Gmail Configuration
    gmail_user: str | None = None
    gmail_app_password: str | None = None

    # Paths
    # We use the project root for data files
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent
    CONTRACTS_DIR: Path = PROJECT_ROOT / "contracts"
    DB_PATH: Path = PROJECT_ROOT / "ap_ledger.db"
    DELIVERY_LOG_PATH: Path = PROJECT_ROOT / "warehouse_receipts_fy26.csv"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
