"""全域設定管理：從 .env 或環境變數讀取所有設定"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Config:
    # Alpaca
    ALPACA_API_KEY    = os.getenv("ALPACA_API_KEY", "")
    ALPACA_API_SECRET = os.getenv("ALPACA_API_SECRET", "")
    ALPACA_BASE_URL   = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets/v2")

    # Email
    SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
    EMAIL_FROM       = os.getenv("EMAIL_FROM", "")
    EMAIL_TO         = os.getenv("EMAIL_TO", "")
    SMTP_HOST        = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT        = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER        = os.getenv("SMTP_USER", "")
    SMTP_PASS        = os.getenv("SMTP_PASS", "")

    # Market Data
    POLYGON_API_KEY = os.getenv("POLYGON_API_KEY", "")

    # Paths
    REPORT_DIR     = BASE_DIR / os.getenv("REPORT_DIR", "reports")
    ACCOUNTS_DIR   = BASE_DIR / os.getenv("ACCOUNTS_DIR", "accounts")
    STRATEGIES_DIR = BASE_DIR / os.getenv("STRATEGIES_DIR", "strategies")

    # App
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def validate_alpaca(cls) -> None:
        if not cls.ALPACA_API_KEY or not cls.ALPACA_API_SECRET:
            raise EnvironmentError(
                "缺少 Alpaca API Key 或 Secret，請設定環境變數 "
                "ALPACA_API_KEY 與 ALPACA_API_SECRET"
            )

    @classmethod
    def is_paper(cls) -> bool:
        return "paper" in cls.ALPACA_BASE_URL

config = Config()
