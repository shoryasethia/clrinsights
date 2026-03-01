import os
from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # API Keys
    gemini_api_key: str = Field(..., description="Google Gemini API key")
    groq_api_key: str = Field(..., description="Groq API key")

    # MongoDB
    mongodb_uri: str = Field(..., description="MongoDB Atlas connection URI")
    
    # Model Configuration
    gemini_model: str = Field(..., description="Primary Gemini model name")
    gemini_fallback_model: str = Field(..., description="Fallback Gemini model name")
    groq_model: str = Field(..., description="Primary Groq model name")
    groq_fallback_model: str = Field(..., description="Fallback Groq model name")
    
    # Data Configuration
    csv_path: str = Field(..., description="Path to CSV data file")
    schema_path: str = Field(..., description="Path to schema definition JSON file")
    
    # Sandbox Configuration
    code_timeout_seconds: int = Field(..., description="Timeout for code execution in seconds")
    max_memory_mb: int = Field(..., description="Maximum memory allocation in MB")
    
    # API Configuration
    api_host: str = Field(..., description="API host address")
    api_port: int = Field(..., description="API port number")
    cors_origins: list[str] = Field(..., description="Allowed CORS origins")
    
    # Memory Configuration
    max_conversation_history: int = Field(..., description="Maximum number of messages to keep in history")
    context_window_size: int = Field(..., description="Maximum context window size in tokens")
    
    # LLM Configuration
    default_temperature: float = Field(..., description="Default LLM temperature for deterministic responses")
    max_retries: int = Field(..., description="Maximum retry attempts for LLM calls")
    request_timeout: int = Field(..., description="Request timeout in seconds")
    
    @property
    def csv_absolute_path(self) -> str:
        """Get absolute path to CSV file."""
        if os.path.isabs(self.csv_path):
            return self.csv_path
        # Resolve relative paths from the clrinsights directory (where config.py is)
        return str((Path(__file__).parent / self.csv_path).resolve())
    
    @property
    def schema_absolute_path(self) -> str:
        """Get absolute path to schema file."""
        if os.path.isabs(self.schema_path):
            return self.schema_path
        # Resolve relative paths from the clrinsights directory (where config.py is)
        return str((Path(__file__).parent / self.schema_path).resolve())


settings = Settings()
