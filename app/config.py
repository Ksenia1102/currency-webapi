import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Application
    APP_NAME = os.getenv("APP_NAME", "Currency API")
    VERSION = os.getenv("VERSION", "1.0.0")
    DEBUG = os.getenv("DEBUG", "true").lower() == "true"
    
    # API
    API_PREFIX = os.getenv("API_PREFIX", "/api/v1")
    
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./currency.db")
    
    # External API
    CBR_API_URL = os.getenv("CBR_API_URL", "https://www.cbr-xml-daily.ru/daily_json.js")
    BACKGROUND_INTERVAL = int(os.getenv("BACKGROUND_INTERVAL", "600"))  # 10 минут
    
    # WebSocket
    WS_PATH = os.getenv("WS_PATH", "/ws")
    
    # NATS
    NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
    NATS_UPDATES_CHANNEL = os.getenv("NATS_UPDATES_CHANNEL", "currency.updates")
    NATS_EVENTS_CHANNEL = os.getenv("NATS_EVENTS_CHANNEL", "currency.events")
    NATS_ENABLED = os.getenv("NATS_ENABLED", "false").lower() == "true"
    
    # Добавьте в класс Settings:
    CRYPTO_API_URL = os.getenv("CRYPTO_API_URL", "https://api.coingecko.com/api/v3/simple/price")
    CRYPTO_CURRENCIES = os.getenv("CRYPTO_CURRENCIES", "bitcoin,ethereum").split(",")
    CRYPTO_VS_CURRENCY = os.getenv("CRYPTO_VS_CURRENCY", "usd")

    # Features
    ENABLE_CRYPTO = os.getenv("ENABLE_CRYPTO", "true").lower() == "true"
    ENABLE_TRADITIONAL = os.getenv("ENABLE_TRADITIONAL", "true").lower() == "true"

settings = Settings()