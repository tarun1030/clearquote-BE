"""
ClearQuote – Configuration / JSON-based loader.
Configuration is persisted to data/config.json and can be updated via API endpoints.
"""

import os
import json
from pathlib import Path
from urllib.parse import urlparse, quote_plus
from typing import Optional

# Path to the config file
CONFIG_DIR = Path(__file__).parent / "data"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Ensure data directory exists
CONFIG_DIR.mkdir(exist_ok=True)


def sanitize_postgres_url(db_url: str) -> str:
    """
    Encode only the password portion of a PostgreSQL URL.
    """
    if not db_url:
        return None
    
    parsed = urlparse(db_url)

    username = parsed.username
    password = parsed.password
    host = parsed.hostname
    port = parsed.port
    database = parsed.path.lstrip("/")

    if password:
        password = quote_plus(password)

    return f"postgresql://{username}:{password}@{host}:{port}/{database}"


def load_config() -> dict:
    """
    Load configuration from JSON file.
    Returns default empty config if file doesn't exist.
    """
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_config(config_data: dict) -> None:
    """
    Save configuration to JSON file.
    """
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config_data, f, indent=2)


def get_config_value(key: str, default=None):
    """
    Get a configuration value from JSON storage.
    """
    config_data = load_config()
    return config_data.get(key, default)


def set_config_value(key: str, value) -> None:
    """
    Set a configuration value in JSON storage.
    """
    config_data = load_config()
    config_data[key] = value
    save_config(config_data)


# ---------- Configuration Properties ----------
# These act as dynamic properties that read from JSON storage

@property
def _get_db_url() -> Optional[str]:
    """Get the database URL from config."""
    raw_url = get_config_value("DB_URL")
    return sanitize_postgres_url(raw_url) if raw_url else None


@property
def _get_gemini_api_key() -> Optional[str]:
    """Get the Gemini API key from config."""
    return get_config_value("GEMINI_API_KEY")


@property
def _get_gemini_model() -> str:
    """Get the Gemini model from config."""
    return get_config_value("GEMINI_MODEL", "gemini-2.5-flash")


# Create a Config class to hold dynamic properties
class ConfigManager:
    """
    Configuration manager that reads from and writes to JSON storage.
    """
    
    @property
    def DB_URL(self) -> Optional[str]:
        """Get the database URL."""
        env_url = os.getenv("DB_URL") or os.getenv("DATABASE_URL")
        if env_url:
            return sanitize_postgres_url(env_url)
        raw_url = get_config_value("DB_URL")
        return sanitize_postgres_url(raw_url) if raw_url else None
    
    @DB_URL.setter
    def DB_URL(self, value: str) -> None:
        """Set the database URL."""
        set_config_value("DB_URL", value)
    
    @property
    def GEMINI_API_KEY(self) -> Optional[str]:
        """Get the Gemini API key."""
        return get_config_value("GEMINI_API_KEY")
    
    @GEMINI_API_KEY.setter
    def GEMINI_API_KEY(self, value: str) -> None:
        """Set the Gemini API key."""
        set_config_value("GEMINI_API_KEY", value)
    
    @property
    def GEMINI_MODEL(self) -> str:
        """Get the Gemini model."""
        return get_config_value("GEMINI_MODEL", "gemini-2.5-flash")
    
    @GEMINI_MODEL.setter
    def GEMINI_MODEL(self, value: str) -> None:
        """Set the Gemini model."""
        set_config_value("GEMINI_MODEL", value)
    
    def validate_config(self) -> dict:
        """
        Check if required configuration is present.
        Returns dict with status and missing items.
        """
        missing = []
        
        if not self.GEMINI_API_KEY:
            missing.append("GEMINI_API_KEY")
        
        if not self.DB_URL:
            missing.append("DB_URL")
        
        return {
            "is_valid": len(missing) == 0,
            "missing": missing
        }
    
    def get_config_status(self) -> dict:
        """
        Get current configuration status.
        """
        return {
            "gemini_api_key_set": self.GEMINI_API_KEY is not None,
            "db_url_set": self.DB_URL is not None,
            "gemini_model": self.GEMINI_MODEL
        }


# Create a singleton instance
_config_manager = ConfigManager()

# Export as module-level variables for backward compatibility
DB_URL = _config_manager.DB_URL
GEMINI_API_KEY = _config_manager.GEMINI_API_KEY
GEMINI_MODEL = _config_manager.GEMINI_MODEL


def validate_config():
    """
    Check if required configuration is present.
    Returns dict with status and missing items.
    """
    return _config_manager.validate_config()


def get_config_status():
    """
    Get current configuration status.
    """
    return _config_manager.get_config_status()


# Export the config manager for direct property access
config = _config_manager