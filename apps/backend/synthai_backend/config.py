"""
Configuration settings for SynthAI backend.
"""

import os
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    # LLM API Keys
    openai_api_key: Optional[str] = Field(default=None, validation_alias="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, validation_alias="ANTHROPIC_API_KEY")

    # NCBI E-utilities API Key
    ncbi_api_key: Optional[str] = Field(default=None, validation_alias="NCBI_API_KEY")

    # Contact
    contact_email: Optional[str] = Field(default="research@synthai.ai", validation_alias="CONTACT_EMAIL")

    # Data directories
    nhanes_cache_dir: str = Field(default="./data/nhanes", validation_alias="NHANES_CACHE_DIR")
    data_dir: str = Field(default="./data", validation_alias="DATA_DIR")

    # Feature Flags
    enable_synthetic: bool = Field(default=True, validation_alias="ENABLE_SYNTHETIC")

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    @property
    def has_ai_provider(self) -> bool:
        """Check if any AI provider is configured."""
        return bool(self.openai_api_key or self.anthropic_api_key)


# Create settings instance
settings = Settings()
