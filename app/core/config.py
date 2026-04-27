import os


class Settings:
    def __init__(self) -> None:
        self.app_name = os.getenv("APP_NAME", "Green Saver API")
        self.app_version = os.getenv("APP_VERSION", "1.0.0")
        self.database_url = os.getenv("DATABASE_URL", "")
        self.welcome_message = os.getenv(
            "WELCOME_MESSAGE",
            "Bienvenido a Green Saver API",
        )

        cors_raw = os.getenv("CORS_ORIGINS", "*")
        self.cors_origins = [origin.strip() for origin in cors_raw.split(",") if origin.strip()]

        self.smtp_host = os.getenv("SMTP_HOST", "")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.smtp_from = os.getenv("SMTP_FROM", self.smtp_user)
        self.smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"


settings = Settings()
