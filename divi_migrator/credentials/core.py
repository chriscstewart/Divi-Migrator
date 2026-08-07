"""
Credential Management for Divi Migrator - Core Implementation.

Agent-agnostic credential resolution with automatic detection:
1. Agent-injected env vars (Hermes, OpenClaw, Claude, OpenAI, Codex, etc.)
2. Environment variables / .env files
3. YAML config file (config.yaml)
4. Interactive guided setup (human only)

Security principles:
- Never log credentials
- Validate URLs before use
- Sanitize all inputs
- Clear credentials from memory after use where possible
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from divi_migrator.config import Config, WPSettings, DiviOpsSettings, MigrationSettings
from divi_migrator.credentials.prompts import prompt_for_credentials

logger = logging.getLogger(__name__)

EMPTY_URL_ERROR = "URL cannot be empty"
INVALID_URL_SCHEME_ERROR = "Invalid URL scheme: {scheme}. Must be http or https"
INVALID_URL_HOST_ERROR = "Invalid URL: missing host in {url}"
EMPTY_USERNAME_ERROR = "Username cannot be empty"
EMPTY_PASSWORD_ERROR = "Application password cannot be empty"



class CredentialSource(Enum):
    """Sources for credentials, in priority order."""

    AGENT_ENV = "agent_env"      # Agent-injected env vars (highest)
    ENV_FILE = "env_file"        # .env files
    CONFIG_FILE = "config_file"  # config.yaml
    PROMPT = "prompt"            # Interactive guided setup (human only)


@dataclass
class WPConfig:
    """WordPress site configuration with validated credentials."""

    url: str
    user: str
    app_password: str
    ssl_verify: bool = True
    timeout: int = 30

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        self.url = self._validate_url(self.url)
        self.user = self._validate_username(self.user)
        self.app_password = self._validate_app_password(self.app_password)

    def _validate_url(self, url: str) -> str:
        """Validate and normalize URL."""
        if not url:
            raise ValueError(EMPTY_URL_ERROR)

        parsed = urlparse(url)
        if not parsed.scheme:
            url = f"https://{url}"
            parsed = urlparse(url)

        if parsed.scheme not in ("http", "https"):
            raise ValueError(INVALID_URL_SCHEME_ERROR.format(scheme=parsed.scheme))

        if not parsed.netloc:
            raise ValueError(INVALID_URL_HOST_ERROR.format(url=url))

        # Normalize: remove trailing slash
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"

    def _validate_username(self, user: str) -> str:
        """Validate username."""
        if not user or not user.strip():
            raise ValueError(EMPTY_USERNAME_ERROR)
        return user.strip()

    def _validate_app_password(self, password: str) -> str:
        """Validate application password format (WP app passwords have spaces)."""
        if not password or not password.strip():
            raise ValueError(EMPTY_PASSWORD_ERROR)
        # WP app passwords are typically 24 chars with spaces: "xxxx xxxx xxxx xxxx"
        # But we accept any non-empty string
        return password.strip()

    def to_config_dict(self) -> dict[str, Any]:
        """Convert to config dictionary for Config class."""
        return {
            "url": self.url,
            "user": self.user,
            "app_password": self.app_password,
            "ssl_verify": self.ssl_verify,
            "timeout": self.timeout,
        }


@dataclass
class DiviOpsConfig:
    """DiviOps configuration (can share credentials with WP)."""

    url: str | None = None
    user: str | None = None
    app_password: str | None = None
    timeout: int = 60

    def resolve_from_wp(self, wp_config: WPConfig) -> DiviOpsConfig:
        """Fill missing values from WP config."""
        return DiviOpsConfig(
            url=self.url or wp_config.url,
            user=self.user or wp_config.user,
            app_password=self.app_password or wp_config.app_password,
            timeout=self.timeout,
        )

    def to_config_dict(self) -> dict[str, Any]:
        """Convert to config dictionary."""
        return {
            "url": self.url,
            "user": self.user,
            "app_password": self.app_password,
            "timeout": self.timeout,
        }


@dataclass
class MigrationConfig:
    """Migration behavior settings."""

    rate_limit: float = 0.5
    batch_size: int = 50
    checkpoint_dir: str = "./checkpoints"
    max_retries: int = 3
    timeout: int = 30
    max_content_length: int = 10_000_000
    post_type: str = "page"

    def to_config_dict(self) -> dict[str, Any]:
        return {
            "rate_limit": self.rate_limit,
            "batch_size": self.batch_size,
            "checkpoint_dir": self.checkpoint_dir,
            "max_retries": self.max_retries,
            "timeout": self.timeout,
            "max_content_length": self.max_content_length,
            "post_type": self.post_type,
        }


@dataclass
class CompleteConfig:
    """Complete validated configuration for Divi Migrator."""

    wp: WPConfig
    diviops: DiviOpsConfig
    migration: MigrationConfig
    source: CredentialSource

    def to_config(self) -> Config:
        """Convert to legacy Config object for backward compatibility."""
        return Config(
            wp=WPSettings(**self.wp.to_config_dict()),
            diviops=DiviOpsSettings(**self.diviops.to_config_dict()),
            migration=MigrationSettings(**self.migration.to_config_dict()),
        )


CREDENTIAL_ERROR_MESSAGE = (
    "No credentials found and running in non-interactive mode.\n"
    "Provide credentials via:\n"
    "  - Agent-injected env vars (WP_URL, WP_USER, WP_APP_PASSWORD, etc.)\n"
    "  - Environment variables (.env files or shell export)\n"
    "  - Config file (config.yaml with real app_password)\n"
    "Run with --interactive for guided setup, or see --help for details."
)


class ConfigLoader:
    """Loads configuration from agent/env/config/prompt with proper priority."""

    def __init__(self, project_root: Path | None = None, non_interactive: bool = False):
        self.project_root = project_root or Path.cwd()
        self.non_interactive = non_interactive

    def load(self, config_path: str | None = None) -> CompleteConfig:
        """
        Load configuration from all sources in priority order:
        1. Agent-injected environment variables (WP_URL, WP_USER, WP_APP_PASSWORD, etc.)
        2. Environment variables / .env files
        3. YAML config file (config.yaml)
        4. Interactive guided setup (human only, skipped if non_interactive)
        """
        # 1. Agent-injected env vars (highest priority for automation)
        creds = self._from_agent_env()
        if creds:
            logger.info("Loaded credentials from agent-injected environment variables")
            return creds

        # 2. Explicit config file
        if config_path:
            creds = self._try_config_file(Path(config_path))
            if creds:
                logger.info(f"Loaded credentials from config file: {config_path}")
                return creds

        # 3. Project config.yaml
        default_config = self.project_root / "config.yaml"
        if default_config.exists():
            creds = self._try_config_file(default_config)
            if creds:
                logger.info(f"Loaded credentials from default config: {default_config}")
                return creds

        # 4. .env files
        creds = self._try_env_file()
        if creds:
            logger.info("Loaded credentials from .env file")
            return creds

        # 5. Fallback to interactive guided setup (human only)
        if not self.non_interactive:
            logger.info("No credentials found, starting guided setup...")
            return self._prompt_user()

        raise CredentialError()

    def _from_agent_env(self) -> CompleteConfig | None:
        """Check for agent-injected environment variables.

        Agents (Hermes, OpenClaw, Claude, OpenAI, Codex, etc.) should inject:
        - WP_URL, WP_USER, WP_APP_PASSWORD, WP_SSL_VERIFY
        - DIVIOPS_URL, DIVIOPS_USER, DIVIOPS_APP_PASSWORD, DIVIOPS_TIMEOUT
        - MIGRATION_RATE_LIMIT, MIGRATION_BATCH_SIZE, etc.
        """
        required = ["WP_URL", "WP_USER", "WP_APP_PASSWORD"]
        if not all(os.environ.get(k) for k in required):
            return None

        logger.debug("Found agent-injected environment variables")
        return CompleteConfig(
            wp=WPConfig(
                url=os.environ["WP_URL"],
                user=os.environ["WP_USER"],
                app_password=os.environ["WP_APP_PASSWORD"],
                ssl_verify=os.environ.get("WP_SSL_VERIFY", "true").lower() == "true",
                timeout=int(os.environ.get("WP_TIMEOUT", "30")),
            ),
            diviops=DiviOpsConfig(
                url=os.environ.get("DIVIOPS_URL"),
                user=os.environ.get("DIVIOPS_USER"),
                app_password=os.environ.get("DIVIOPS_APP_PASSWORD"),
                timeout=int(os.environ.get("DIVIOPS_TIMEOUT", "60")),
            ).resolve_from_wp(WPConfig(
                url=os.environ["WP_URL"],
                user=os.environ["WP_USER"],
                app_password=os.environ["WP_APP_PASSWORD"],
                ssl_verify=os.environ.get("WP_SSL_VERIFY", "true").lower() == "true",
            )),
            migration=MigrationConfig(
                rate_limit=float(os.environ.get("MIGRATION_RATE_LIMIT", "0.5")),
                batch_size=int(os.environ.get("MIGRATION_BATCH_SIZE", "50")),
                checkpoint_dir=os.environ.get("MIGRATION_CHECKPOINT_DIR", "./checkpoints"),
                max_retries=int(os.environ.get("MIGRATION_MAX_RETRIES", "3")),
                timeout=int(os.environ.get("MIGRATION_TIMEOUT", "30")),
                max_content_length=int(os.environ.get("MIGRATION_MAX_CONTENT_LENGTH", "10000000")),
                post_type=os.environ.get("MIGRATION_POST_TYPE", "page"),
            ),
            source=CredentialSource.AGENT_ENV,
        )

    def _try_config_file(self, path: Path) -> CompleteConfig | None:
        """Load from YAML config file."""
        try:
            with path.open() as f:
                data = yaml.safe_load(f) or {}

            wp_data = data.get("wp", {})
            diviops_data = data.get("diviops", {})
            migration_data = data.get("migration", {})

            # Check for placeholder values
            app_password = wp_data.get("app_password", "")
            if app_password.startswith("${") or app_password in ("", "your-app-password"):
                logger.debug(f"Config file {path} contains placeholder/empty password")
                return None

            wp = WPConfig(
                url=wp_data.get("url", ""),
                user=wp_data.get("user", ""),
                app_password=app_password,
                ssl_verify=wp_data.get("ssl_verify", True),
                timeout=wp_data.get("timeout", 30),
            )

            diviops = DiviOpsConfig(
                url=diviops_data.get("url"),
                user=diviops_data.get("user"),
                app_password=diviops_data.get("app_password"),
                timeout=diviops_data.get("timeout", 60),
            ).resolve_from_wp(wp)

            migration = MigrationConfig(
                rate_limit=migration_data.get("rate_limit", 0.5),
                batch_size=migration_data.get("batch_size", 50),
                checkpoint_dir=migration_data.get("checkpoint_dir", "./checkpoints"),
                max_retries=migration_data.get("max_retries", 3),
                timeout=migration_data.get("timeout", 30),
                max_content_length=migration_data.get("max_content_length", 10_000_000),
                post_type=migration_data.get("post_type", "page"),
            )

            return CompleteConfig(
                wp=wp,
                diviops=diviops,
                migration=migration,
                source=CredentialSource.CONFIG_FILE,
            )
        except Exception as e:
            logger.debug(f"Failed to load config from {path}: {e}")
            return None

    def _try_env_file(self) -> CompleteConfig | None:
        """Load from .env file."""
        env_paths = [
            self.project_root / ".env",
            self.project_root / ".env.local",
            Path.home() / ".divi-migrator.env",
        ]

        for env_path in env_paths:
            if not env_path.exists():
                continue

            try:
                env_vars = {}
                with env_path.open() as f:
                    for raw_line in f:
                        line = raw_line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, value = line.split("=", 1)
                            env_vars[key.strip()] = value.strip()

                # Check required vars
                required = ["WP_URL", "WP_USER", "WP_APP_PASSWORD"]
                if not all(k in env_vars for k in required):
                    continue

                return CompleteConfig(
                    wp=WPConfig(
                        url=env_vars["WP_URL"],
                        user=env_vars["WP_USER"],
                        app_password=env_vars["WP_APP_PASSWORD"],
                        ssl_verify=env_vars.get("WP_SSL_VERIFY", "true").lower() == "true",
                        timeout=int(env_vars.get("WP_TIMEOUT", "30")),
                    ),
                    diviops=DiviOpsConfig(
                        url=env_vars.get("DIVIOPS_URL"),
                        user=env_vars.get("DIVIOPS_USER"),
                        app_password=env_vars.get("DIVIOPS_APP_PASSWORD"),
                        timeout=int(env_vars.get("DIVIOPS_TIMEOUT", "60")),
                    ).resolve_from_wp(WPConfig(
                        url=env_vars["WP_URL"],
                        user=env_vars["WP_USER"],
                        app_password=env_vars["WP_APP_PASSWORD"],
                        ssl_verify=env_vars.get("WP_SSL_VERIFY", "true").lower() == "true",
                    )),
                    migration=MigrationConfig(
                        rate_limit=float(env_vars.get("MIGRATION_RATE_LIMIT", "0.5")),
                        batch_size=int(env_vars.get("MIGRATION_BATCH_SIZE", "50")),
                        checkpoint_dir=env_vars.get("MIGRATION_CHECKPOINT_DIR", "./checkpoints"),
                        max_retries=int(env_vars.get("MIGRATION_MAX_RETRIES", "3")),
                        timeout=int(env_vars.get("MIGRATION_TIMEOUT", "30")),
                        max_content_length=int(
                            env_vars.get("MIGRATION_MAX_CONTENT_LENGTH", "10000000")
                        ),
                        post_type=env_vars.get("MIGRATION_POST_TYPE", "page"),
                    ),
                    source=CredentialSource.ENV_FILE,
                )
            except Exception as e:
                logger.debug(f"Failed to load .env from {env_path}: {e}")
                continue

        return None

    def _prompt_user(self) -> CompleteConfig:
        """Interactive guided setup with step-by-step instructions."""
        return prompt_for_credentials()


class CredentialError(Exception):
    """Credential resolution failed."""

    def __init__(self) -> None:
        super().__init__(CREDENTIAL_ERROR_MESSAGE)


def load_config(
    config_path: str | None = None,
    project_root: Path | None = None,
    non_interactive: bool = False,
) -> CompleteConfig:
    """Convenience function to load complete configuration."""
    loader = ConfigLoader(project_root, non_interactive=non_interactive)
    return loader.load(config_path)
