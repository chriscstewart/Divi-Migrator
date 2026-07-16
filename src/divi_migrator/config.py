"""Configuration management using Pydantic Settings."""

from __future__ import annotations

import os
import re
from pathlib import Path

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WPSettings(BaseSettings):
    """WordPress connection settings."""

    model_config = SettingsConfigDict(env_prefix="WP_")

    url: str = Field(..., description="WordPress site URL")
    user: str = Field(..., description="WP REST API username")
    app_password: str = Field(..., description="Application password")
    ssl_verify: bool = Field(True, description="Verify SSL certificates")
    timeout: int = Field(30, description="Request timeout in seconds")


class DiviOpsSettings(BaseSettings):
    """DiviOps connection settings."""

    model_config = SettingsConfigDict(env_prefix="DIVIOPS_")

    url: str | None = Field(None, description="DiviOps endpoint (defaults to WP_URL)")
    timeout: int = Field(60, description="Request timeout in seconds")


class MigrationSettings(BaseSettings):
    """Migration behavior settings."""

    model_config = SettingsConfigDict(env_prefix="MIGRATION_")

    rate_limit: float = Field(2.0, description="Seconds between requests")
    batch_size: int = Field(50, description="Items per API page")
    checkpoint_dir: Path = Field(Path("./checkpoints"), description="Checkpoint directory")
    max_retries: int = Field(3, description="Max retry attempts")
    timeout: int = Field(30, description="Default request timeout")
    max_content_length: int = Field(10_000_000, description="Max content length to process")


class VerificationSettings(BaseSettings):
    """Verification behavior settings."""

    model_config = SettingsConfigDict(env_prefix="VERIFICATION_")

    require_sections: bool = Field(True)
    require_images: bool = Field(False)
    require_buttons: bool = Field(False)
    primary_color_token: str = Field("gcid-primary-color")
    default_section_bg: str = Field("#f7f4ef")


class DesignSystemSettings(BaseSettings):
    """Design system inspection settings."""

    model_config = SettingsConfigDict(env_prefix="DESIGN_SYSTEM_")

    fetch_on_start: bool = Field(True)
    cache_ttl: int = Field(3600)
    fallback_to_defaults: bool = Field(True)
    primary_color_override: str | None = None
    section_bg_override: str | None = None


class Config(BaseSettings):
    """Main configuration."""

    wp: WPSettings
    diviops: DiviOpsSettings = DiviOpsSettings()  # type: ignore[call-arg]
    migration: MigrationSettings = MigrationSettings()  # type: ignore[call-arg]
    verification: VerificationSettings = VerificationSettings()  # type: ignore[call-arg]
    design_system: DesignSystemSettings = DesignSystemSettings()  # type: ignore[call-arg]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    @classmethod
    def from_yaml(cls, path: Path) -> Config:
        """Load from YAML file with env var substitution."""
        with path.open() as f:
            content = f.read()

        # Substitute ${VAR} or $VAR with env vars
        def replace_env(match: re.Match[str]) -> str:
            var = match.group(1)
            return os.environ.get(var, match.group(0))

        content = re.sub(r"\$\{([^}]+)\}", replace_env, content)
        content = re.sub(r"\$([A-Z_][A-Z0-9_]*)", replace_env, content)

        data = yaml.safe_load(content)
        return cls(**data)