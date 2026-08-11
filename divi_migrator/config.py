"""Configuration management using Pydantic Settings."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from divi_migrator.credentials.core import CompleteConfig


class WPSettings(BaseSettings):
    """WordPress connection settings."""

    model_config = SettingsConfigDict(env_prefix="WP_")

    url: str = Field(..., description="WordPress site URL")
    user: str = Field(..., description="WP REST API username")
    app_password: str = Field(default="", description="Application password")
    ssl_verify: bool = Field(True, description="Verify SSL certificates")
    timeout: int = Field(60, description="Request timeout in seconds (raise for slow hosting)")


class DiviOpsSettings(BaseSettings):
    """DiviOps connection settings."""

    model_config = SettingsConfigDict(env_prefix="DIVIOPS_")

    url: str | None = Field(None, description="DiviOps endpoint (defaults to WP_URL)")
    user: str | None = Field(None, description="DiviOps WP REST API username")
    app_password: str | None = Field(None, description="DiviOps application password (no spaces)")
    timeout: int = Field(90, description="Request timeout in seconds (raise for slow hosting)")


class MigrationSettings(BaseSettings):
    """Migration behavior settings."""

    model_config = SettingsConfigDict(env_prefix="MIGRATION_")

    # rate_limit is REQUESTS PER SECOND (token-bucket). For cheap shared
    # hosting, keep this low: 0.33 ≈ 1 request every 3 seconds. The token
    # bucket is shared by BOTH the WP client and the DiviOps client so all
    # traffic to the site is throttled together. A 'min_delay' floor is
    # applied on top so two calls can never fire closer than min_delay apart.
    rate_limit: float = Field(0.33, description="Requests/sec for WP+DiviOps (0.33 = 3s apart).")
    min_delay: float = Field(2.0, description="Hard floor (seconds) between any two requests.")
    batch_size: int = Field(50, description="Items per API page")
    checkpoint_dir: Path = Field(Path.cwd() / "checkpoints", description="Checkpoint directory")
    max_retries: int = Field(5, description="Max retry attempts on transient 5xx/429")
    timeout: int = Field(60, description="Default request timeout (raise for slow shared hosting)")
    post_type: str = Field("page", description="Post type: page or post")


class AuditSettings(BaseSettings):
    """Audit system settings."""

    model_config = SettingsConfigDict(env_prefix="AUDIT_")

    backup_dir: Path = Field(Path("./audit_backups"), description="Local audit backup directory")
    wp_option_key: str = Field("divi_migrator_audit", description="WP option key for audit storage")
    auto_backup: bool = Field(True, description="Auto-create local JSON backups")
    max_backups: int = Field(10, description="Maximum local backups to keep")


class VerificationSettings(BaseSettings):
    """Verification behavior settings."""

    model_config = SettingsConfigDict(env_prefix="VERIFICATION_")

    require_sections: bool = Field(True)
    require_images: bool = Field(False)
    require_buttons: bool = Field(False)
    primary_color_token: str = Field("gcid-primary-color")


class DesignSystemSettings(BaseSettings):
    """Design system inspection settings."""

    model_config = SettingsConfigDict(env_prefix="DESIGN_SYSTEM_")

    fetch_on_start: bool = Field(True)
    cache_ttl: int = Field(3600)
    fallback_to_defaults: bool = Field(True)
    background_color_token: str = Field("primary_background_color")


class Config(BaseSettings):
    """Main configuration."""

    wp: WPSettings
    diviops: DiviOpsSettings = DiviOpsSettings()  # type: ignore[call-arg]
    migration: MigrationSettings = MigrationSettings()  # type: ignore[call-arg]
    audit: AuditSettings = AuditSettings()  # type: ignore[call-arg]
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

    @classmethod
    def from_complete_config(cls, complete: CompleteConfig) -> Config:
        """Create Config from CompleteConfig (new credential system)."""
        return cls(
            wp=WPSettings(**complete.wp.to_config_dict()),
            diviops=DiviOpsSettings(**complete.diviops.to_config_dict()),
            migration=MigrationSettings(**complete.migration.to_config_dict()),
        )
