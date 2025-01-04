from typing import Annotated

from pydantic import EmailStr, Field, field_validator, validate_email
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    MAIL_FROM: str = "j16n's uptime robot <noreply@j16n-uptime-robot>"
    MONITOR_INTERVAL: int = Field(default=300, gt=0)
    NAME: str = "User"
    RECIPIENTS: Annotated[list[EmailStr], NoDecode] = []
    REQUEST_RETRIES: int = Field(default=10, gt=0)
    REQUEST_TIMEOUT: int = Field(default=90, gt=0)
    SEND_EMAIL_RETRIES: int = Field(default=10, gt=0)
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = Field(default=465, gt=0, lt=65536)

    @field_validator("RECIPIENTS", mode="before")
    @classmethod
    def parse_recipients(cls, value: str) -> list[EmailStr]:
        return [validate_email(email)[1] for email in value.split(",")]

    @field_validator("SMTP_USERNAME", "SMTP_PASSWORD", "RECIPIENTS", mode="before")
    @classmethod
    def check_empty(cls, value: str) -> str:
        if value:
            return value
        raise ValueError("Value is required")


if __name__ == "__main__":
    settings = Settings()
    print(settings.model_dump_json(indent=2))
