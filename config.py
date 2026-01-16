"""
Configuration management for Telegram Secretary Bot.
Loads environment variables and provides typed access to settings.
"""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class TelegramConfig:
    """Telegram API configuration."""
    api_id: int
    api_hash: str
    phone: str
    bot_token: str
    client_user_id: int


@dataclass
class DatabaseConfig:
    """Database configuration."""
    url: str


@dataclass
class SchedulerConfig:
    """Scheduler configuration."""
    summary_interval_hours: int
    max_messages_per_summary: int
    min_priority_score: int
    timezone: str
    warning_threshold_score: int  # Score threshold for real-time warnings


@dataclass
class Config:
    """Main configuration container."""
    telegram: TelegramConfig
    database: DatabaseConfig
    scheduler: SchedulerConfig
    log_level: str


def _get_required_env(key: str) -> str:
    """Get a required environment variable or raise an error."""
    value = os.getenv(key)
    if not value:
        raise ValueError(f"Missing required environment variable: {key}")
    return value


def _get_optional_env(key: str, default: str) -> str:
    """Get an optional environment variable with a default value."""
    return os.getenv(key, default)


def load_config() -> Config:
    """Load and validate all configuration from environment variables."""
    
    telegram = TelegramConfig(
        api_id=int(_get_required_env("TELEGRAM_API_ID")),
        api_hash=_get_required_env("TELEGRAM_API_HASH"),
        phone=_get_required_env("TELEGRAM_PHONE"),
        bot_token=_get_required_env("BOT_TOKEN"),
        client_user_id=int(_get_required_env("CLIENT_USER_ID")),
    )
    
    database = DatabaseConfig(
        url=_get_required_env("DATABASE_URL"),
    )
    
    scheduler = SchedulerConfig(
        summary_interval_hours=int(_get_optional_env("SUMMARY_INTERVAL_HOURS", "4")),
        max_messages_per_summary=int(_get_optional_env("MAX_MESSAGES_PER_SUMMARY", "15")),
        min_priority_score=int(_get_optional_env("MIN_PRIORITY_SCORE", "1")),
        timezone=_get_optional_env("TIMEZONE", "America/Sao_Paulo"),
        warning_threshold_score=int(_get_optional_env("WARNING_THRESHOLD_SCORE", "5")),
    )
    
    return Config(
        telegram=telegram,
        database=database,
        scheduler=scheduler,
        log_level=_get_optional_env("LOG_LEVEL", "INFO"),
    )


# Global config instance (lazy loaded)
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = load_config()
    return _config

