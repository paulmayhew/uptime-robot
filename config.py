from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import os
load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    MONGODB_URL: str = os.getenv("MONGODB_URL")
    MONGODB_DB: str = "tracker"
    MONITOR_INTERVAL: int = Field(default=300, gt=0)
    NAME: str = "Devs"
    REQUEST_RETRIES: int = Field(default=10, gt=0)
    REQUEST_TIMEOUT: int = Field(default=90, gt=0)
    SLACK_WEBHOOK_URL: str = os.getenv("SLACK_WEBHOOK_URL")


if __name__ == "__main__":
    settings = Settings()
    print(settings.model_dump_json(indent=2))
