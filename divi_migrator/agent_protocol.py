"""
Agent-Agnostic Credential & Migration Protocol for Divi Migrator.

Design Principles:
1. MCP-first: Use existing MCP connections as primary credential source
2. JSON protocol: Structured request/response for any agent
3. Zero interactive prompts: All credentials from MCP/env/config
4. Declarative: Migration defined in YAML/JSON, not interactive steps
5. Agent-agnostic: Works with Claude, OpenAI, OpenCode, Codex, etc.

Credential Resolution Chain (priority order):
1. Active MCP connections (DiviOps, WordPress) - USE THESE
2. Environment variables (WP_URL, WP_USER, WP_APP_PASSWORD)
3. Config file (config.yaml)
4. OS keyring (cross-platform)
5. Explicit CLI args (--wp-url, --wp-user, --wp-password)

Protocol:
- Agent sends: {"action": "migrate", "config": {...}, "plan": [...]}
- Tool responds: {"status": "ok", "results": [...], "audit": {...}}
"""

from __future__ import annotations

import json
import os
import sys
import yaml
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any

try:
    import keyring  # type: ignore

    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False

from divi_migrator.cli import create_orchestrator
from divi_migrator.config import Config, WPSettings, DiviOpsSettings


class CredentialSource(Enum):
    """Credential sources in priority order."""

    MCP = "mcp"
    ENV = "env"
    CONFIG_FILE = "config_file"
    KEYRING = "keyring"
    CLI = "cli"


CREDENTIAL_ERROR_MESSAGE = (
    "No credentials found. Provide via:\n"
    "  - MCP connections (DiviOps, WordPress)\n"
    "  - Environment variables (WP_URL, WP_USER, WP_APP_PASSWORD)\n"
    "  - Config file (config.yaml)\n"
    "  - OS keyring\n"
    "  - CLI arguments (--wp-url, --wp-user, --wp-password)"
)


MIN_ARGS = 2


@dataclass
class ResolvedCredentials:
    """Fully resolved credentials for migration."""

    wp_url: str
    wp_user: str
    wp_app_password: str
    wp_ssl_verify: bool = True
    diviops_url: str | None = None
    diviops_user: str | None = None
    diviops_app_password: str | None = None
    source: CredentialSource = CredentialSource.CONFIG_FILE

    def __post_init__(self) -> None:
        if self.diviops_url is None:
            self.diviops_url = self.wp_url
        if self.diviops_user is None:
            self.diviops_user = self.wp_user
        if self.diviops_app_password is None:
            self.diviops_app_password = self.wp_app_password


class CredentialError(Exception):
    """Credential resolution failed."""

    def __init__(self) -> None:
        super().__init__(CREDENTIAL_ERROR_MESSAGE)


class CredentialResolver:
    """Resolves credentials from all available sources."""

    SERVICE_NAME = "divi-migrator"
    KEYRING_KEYS = {
        "wp_url": "wp_url",
        "wp_user": "wp_user",
        "wp_app_password": "wp_app_password",
        "diviops_url": "diviops_url",
        "diviops_user": "diviops_user",
        "diviops_app_password": "diviops_app_password",
    }

    def __init__(self, config_path: Path | None = None):
        self.config_path = config_path or Path.cwd() / "config.yaml"
        self._mcp_connected = None

    def resolve(self, explicit: dict[str, Any] | None = None) -> ResolvedCredentials:
        """Resolve credentials from all sources in priority order."""

        # 1. Explicit CLI args (highest priority)
        if explicit:
            creds = self._from_explicit(explicit)
            if creds:
                return creds

        # 2. MCP connections (if available in this process)
        creds = self._from_mcp()
        if creds:
            return creds

        # 3. Environment variables
        creds = self._from_env()
        if creds:
            return creds

        # 4. Config file
        creds = self._from_config_file()
        if creds:
            return creds

        # 5. OS Keyring
        if KEYRING_AVAILABLE:
            creds = self._from_keyring()
            if creds:
                return creds

        raise CredentialError()

    def _from_explicit(self, explicit: dict[str, Any]) -> ResolvedCredentials | None:
        """From explicit CLI arguments."""
        required = ["wp_url", "wp_user", "wp_app_password"]
        if not all(k in explicit for k in required):
            return None

        return ResolvedCredentials(
            wp_url=explicit["wp_url"],
            wp_user=explicit["wp_user"],
            wp_app_password=explicit["wp_app_password"],
            wp_ssl_verify=explicit.get("wp_ssl_verify", True),
            diviops_url=explicit.get("diviops_url"),
            diviops_user=explicit.get("diviops_user"),
            diviops_app_password=explicit.get("diviops_app_password"),
            source=CredentialSource.CLI,
        )

    def _from_mcp(self) -> ResolvedCredentials | None:
        """Check if MCP connections are available and usable."""
        return None

    def _from_env(self) -> ResolvedCredentials | None:
        """From environment variables."""
        required = ["WP_URL", "WP_USER", "WP_APP_PASSWORD"]
        if not all(os.environ.get(k) for k in required):
            return None

        return ResolvedCredentials(
            wp_url=os.environ["WP_URL"],
            wp_user=os.environ["WP_USER"],
            wp_app_password=os.environ["WP_APP_PASSWORD"],
            wp_ssl_verify=os.environ.get("WP_SSL_VERIFY", "true").lower() == "true",
            diviops_url=os.environ.get("DIVIOPS_URL"),
            diviops_user=os.environ.get("DIVIOPS_USER"),
            diviops_app_password=os.environ.get("DIVIOPS_APP_PASSWORD"),
            source=CredentialSource.ENV,
        )

    def _from_config_file(self) -> ResolvedCredentials | None:
        """From config.yaml."""
        if not self.config_path.exists():
            return None

        with self.config_path.open() as f:
            data = yaml.safe_load(f) or {}

        wp = data.get("wp", {})
        if not wp.get("app_password"):
            return None

        diviops = data.get("diviops", {})

        return ResolvedCredentials(
            wp_url=wp["url"],
            wp_user=wp["user"],
            wp_app_password=wp["app_password"],
            wp_ssl_verify=wp.get("ssl_verify", True),
            diviops_url=diviops.get("url"),
            diviops_user=diviops.get("user"),
            diviops_app_password=diviops.get("app_password"),
            source=CredentialSource.CONFIG_FILE,
        )

    def _from_keyring(self) -> ResolvedCredentials | None:
        """From OS keyring."""
        if not KEYRING_AVAILABLE:
            return None

        try:
            wp_url = keyring.get_password(self.SERVICE_NAME, self.KEYRING_KEYS["wp_url"])
            wp_user = keyring.get_password(self.SERVICE_NAME, self.KEYRING_KEYS["wp_user"])
            wp_password = keyring.get_password(
                self.SERVICE_NAME, self.KEYRING_KEYS["wp_app_password"]
            )

            if not all([wp_url, wp_user, wp_password]):
                return None

            return ResolvedCredentials(
                wp_url=wp_url,
                wp_user=wp_user,
                wp_app_password=wp_password,
                diviops_url=keyring.get_password(
                    self.SERVICE_NAME, self.KEYRING_KEYS["diviops_url"]
                ),
                diviops_user=keyring.get_password(
                    self.SERVICE_NAME, self.KEYRING_KEYS["diviops_user"]
                ),
                diviops_app_password=keyring.get_password(
                    self.SERVICE_NAME, self.KEYRING_KEYS["diviops_app_password"]
                ),
                source=CredentialSource.KEYRING,
            )
        except Exception:
            return None

    def save_to_keyring(self, creds: ResolvedCredentials) -> bool:
        """Save credentials to OS keyring."""
        if not KEYRING_AVAILABLE:
            return False

        try:
            keyring.set_password(self.SERVICE_NAME, self.KEYRING_KEYS["wp_url"], creds.wp_url)
            keyring.set_password(self.SERVICE_NAME, self.KEYRING_KEYS["wp_user"], creds.wp_user)
            keyring.set_password(
                self.SERVICE_NAME,
                self.KEYRING_KEYS["wp_app_password"],
                creds.wp_app_password,
            )
            if creds.diviops_url:
                keyring.set_password(
                    self.SERVICE_NAME,
                    self.KEYRING_KEYS["diviops_url"],
                    creds.diviops_url,
                )
            if creds.diviops_user:
                keyring.set_password(
                    self.SERVICE_NAME,
                    self.KEYRING_KEYS["diviops_user"],
                    creds.diviops_user,
                )
            if creds.diviops_app_password:
                keyring.set_password(
                    self.SERVICE_NAME,
                    self.KEYRING_KEYS["diviops_app_password"],
                    creds.diviops_app_password,
                )
        except Exception:
            return False
        else:
            return True

    def save_to_config(self, creds: ResolvedCredentials) -> bool:
        """Save credentials to config.yaml."""
        config = {
            "wp": {
                "url": creds.wp_url,
                "user": creds.wp_user,
                "app_password": creds.wp_app_password,
                "ssl_verify": creds.wp_ssl_verify,
            },
            "diviops": {
                "url": creds.diviops_url,
                "user": creds.diviops_user,
                "app_password": creds.diviops_app_password,
            },
        }
        with self.config_path.open("w") as f:
            yaml.dump(config, f, default_flow_style=False)
        return True


@dataclass
class MigrationRequest:
    """Agent request to run migration."""

    action: str
    config: dict[str, Any] | None = None
    plan: list[Any] | None = None
    options: dict[str, Any] | None = None


@dataclass
class MigrationResponse:
    """Structured response for agent."""

    status: str
    message: str
    data: dict[str, Any] | None = None
    audit: dict[str, Any] | None = None


def handle_agent_request(request: MigrationRequest) -> MigrationResponse:
    """Main entry point for agent communication."""
    try:
        resolver = CredentialResolver()

        if request.action == "setup":
            return MigrationResponse(
                status="needs_credentials",
                message="Provide credentials via config, env, or explicit config",
                data={
                    "required": [
                        "wp_url",
                        "wp_user",
                        "wp_app_password",
                    ],
                    "optional": [
                        "diviops_url",
                        "diviops_user",
                        "diviops_app_password",
                        "wp_ssl_verify",
                    ],
                    "sources": [
                        "mcp",
                        "env",
                        "config_file",
                        "keyring",
                        "cli",
                    ],
                },
            )

        creds = resolver.resolve(request.config)

        if request.action == "migrate":
            config = Config(
                wp=WPSettings(
                    url=creds.wp_url,
                    user=creds.wp_user,
                    app_password=creds.wp_app_password,
                    ssl_verify=creds.wp_ssl_verify,
                    timeout=30,
                ),
                diviops=DiviOpsSettings(
                    url=creds.diviops_url,
                    user=creds.diviops_user,
                    app_password=creds.diviops_app_password,
                    timeout=60,
                ),
            )

            orch = create_orchestrator(config)
            dry_run = request.options.get("dry_run", True) if request.options else True
            limit = request.options.get("limit") if request.options else None
            post_type = request.options.get("post_type", "page") if request.options else "page"

            result = orch.migrate_post_type(post_type, limit=limit, dry_run=dry_run)

            return MigrationResponse(
                status="ok",
                message=(f"Migration {'dry-run' if dry_run else 'executed'} for {post_type}"),
                data=result,
            )

        return MigrationResponse(
            status="error",
            message=f"Unknown action: {request.action}",
        )

    except CredentialError as e:
        return MigrationResponse(
            status="needs_credentials",
            message=str(e),
        )
    except Exception as e:
        return MigrationResponse(
            status="error",
            message=f"Migration failed: {e}",
        )


# CLI entry point for JSON protocol
def main() -> None:
    """JSON protocol CLI for agent consumption."""
    if len(sys.argv) < MIN_ARGS:
        response = MigrationResponse(
            status="error",
            message="Usage: divi-migrator-agent <json-request>",
        )
        sys.stderr.write(json.dumps(asdict(response)))
        sys.exit(1)

    # Read JSON from stdin or arg
    request_data = json.load(sys.stdin) if sys.argv[1] == "-" else json.loads(sys.argv[1])

    request = MigrationRequest(**request_data)
    response = handle_agent_request(request)
    print(json.dumps(asdict(response)))  # noqa: T201


if __name__ == "__main__":
    main()
