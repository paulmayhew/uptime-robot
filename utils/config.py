from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file="../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    MONGODB_URI: str
    MONGODB_DB: str
    MONITOR_INTERVAL: int = Field(default=300, gt=0)
    DOWN_MONITOR_INTERVAL: int = Field(default=120, gt=0)
    REQUEST_RETRIES: int = Field(default=10, gt=0)
    REQUEST_TIMEOUT: int = Field(default=90, gt=0)
    SLACK_WEBHOOK_URL: str

    MYSQL_HOST: str
    MYSQL_TABLE_NAME: str
    MYSQL_TABLE_COLUMNS: str
    MYSQL_SELECT_QUERY: str
    MYSQL_DETAILS_QUERY: str


if __name__ == "__main__":
    settings = Settings()
    print(settings.model_dump_json(indent=2))
