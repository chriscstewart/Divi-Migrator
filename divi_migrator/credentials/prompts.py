"""
Interactive credential prompts with setup instructions.

Provides user-friendly prompts for WordPress credentials with
step-by-step setup instructions for users who don't know how to
create application passwords.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlparse

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

if TYPE_CHECKING:
    from divi_migrator.credentials.core import (
        CompleteConfig,
    )

console = Console()

# Test constant
MIN_PASSWORD_LENGTH = 16


def prompt_for_credentials() -> CompleteConfig:
    """Interactive prompt for credentials with setup instructions.

    Returns:
        CompleteConfig with validated credentials
    """
    # Imported lazily to avoid a circular import with the credentials package.
    from divi_migrator.credentials.core import (  # noqa: PLC0415
        CompleteConfig,
        WPConfig,
        DiviOpsConfig,
        MigrationConfig,
        CredentialSource,
    )

    console.print()
    console.print(Panel.fit(
        "[bold cyan]Divi Migrator - Credential Setup[/bold cyan]\n"
        "Let's configure your WordPress connection for the migration.",
        border_style="cyan"
    ))

    # Check if user knows how to create app passwords
    console.print()
    console.print("[bold]First, do you have a WordPress Application Password?[/bold]")
    console.print("  [green]Yes[/green] - I have one ready")
    console.print("  [yellow]No[/yellow] - I need instructions")
    console.print()

    knows_how = Confirm.ask(
        "Do you know how to create a WordPress Application Password?",
        default=False,
    )

    if not knows_how:
        _show_app_password_instructions()

    console.print()
    console.print("[bold]Let's collect your credentials:[/bold]")
    console.print()

    # WordPress URL
    wp_url = _prompt_wp_url()

    # Username
    wp_user = _prompt_username()

    # Application Password
    app_password = _prompt_app_password()

    # SSL Verify
    ssl_verify = Confirm.ask("Verify SSL certificates?", default=True)

    # DiviOps settings (usually same as WP)
    console.print()
    console.print("[bold]DiviOps Settings[/bold]")
    console.print("Usually the same as WordPress. Press Enter to use WP settings.")
    console.print()

    diviops_url = Prompt.ask(
        "DiviOps URL",
        default=wp_url,
        show_default=True
    )

    diviops_user = Prompt.ask(
        "DiviOps Username",
        default=wp_user,
        show_default=True
    )

    diviops_password = Prompt.ask(
        "DiviOps Application Password",
        default=app_password,
        show_default=False,
        password=True
    )

    # Migration settings
    console.print()
    console.print("[bold]Migration Settings[/bold]")
    console.print()

    post_type = Prompt.ask(
        "Post type to migrate",
        choices=["page", "post"],
        default="page"
    )

    rate_limit = float(Prompt.ask(
        "Rate limit (seconds between requests)",
        default="0.5"
    ))

    batch_size = int(Prompt.ask(
        "Batch size (items per API page)",
        default="50"
    ))

    # Create config objects
    wp_config = WPConfig(
        url=wp_url,
        user=wp_user,
        app_password=app_password,
        ssl_verify=ssl_verify,
        timeout=30,
    )

    diviops_config = DiviOpsConfig(
        url=diviops_url,
        user=diviops_user,
        app_password=diviops_password,
        timeout=60,
    ).resolve_from_wp(wp_config)

    migration_config = MigrationConfig(
        rate_limit=rate_limit,
        batch_size=batch_size,
        checkpoint_dir="./checkpoints",
        max_retries=3,
        timeout=30,
        max_content_length=10_000_000,
        post_type=post_type,
    )

    return CompleteConfig(
        wp=wp_config,
        diviops=diviops_config,
        migration=migration_config,
        source=CredentialSource.PROMPT,
    )


def _show_app_password_instructions() -> None:
    """Show step-by-step instructions for creating a WordPress Application Password."""
    console.print()
    console.print(Panel(
        "[bold]How to Create a WordPress Application Password[/bold]\n\n"
        "1. Log into your WordPress admin dashboard\n"
        "2. Go to [cyan]Users \u2192 Profile[/cyan] (or click your avatar \u2192 Edit Profile)\n"
        "3. Scroll down to [cyan]Application Passwords[/cyan] section\n"
        '4. Enter a name for the app (e.g., "Divi Migrator")\n'
        "5. Click [cyan]Add New Application Password[/cyan]\n"
        "6. [bold red]COPY THE PASSWORD IMMEDIATELY[/bold red] - it won't be shown again!\n"
        "   Format: [cyan]xxxx xxxx xxxx xxxx[/cyan] (24 characters with spaces)\n"
        "7. Save the password in a secure place\n\n"
        "[yellow]Note:[/yellow] You need [cyan]Administrator[/cyan] role for the migration.\n"
        "If you don't see 'Application Passwords', ask your host to enable it\n"
        "or update WordPress to 5.6+.",
        title="Setup Instructions",
        border_style="yellow",
        padding=(1, 2)
    ))
    console.print()


def _prompt_wp_url() -> str:
    """Prompt for and validate WordPress URL."""
    while True:
        url = Prompt.ask(
            "[bold]WordPress Site URL[/bold]",
            default="https://example.com"
        )

        # Normalize
        parsed = urlparse(url)
        if not parsed.scheme:
            url = f"https://{url}"
            parsed = urlparse(url)

        if parsed.scheme not in ("http", "https"):
            console.print("[red]Error:[/red] URL must use http or https")
            continue

        if not parsed.netloc:
            console.print("[red]Error:[/red] Invalid URL - missing hostname")
            continue

        # Confirm
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"
        console.print(f"  Using: [cyan]{normalized}[/cyan]")

        if Confirm.ask("Is this correct?", default=True):
            return normalized

        console.print()


def _prompt_username() -> str:
    """Prompt for WordPress username."""
    while True:
        user = Prompt.ask(
            "[bold]WordPress Username[/bold]",
            default="admin"
        ).strip()

        if user:
            return user

        console.print("[red]Error:[/red] Username cannot be empty")
        console.print()


def _prompt_app_password() -> str:
    """Prompt for WordPress Application Password."""
    console.print()
    console.print("[bold]WordPress Application Password[/bold]")
    console.print("  Format: [cyan]xxxx xxxx xxxx xxxx[/cyan] (with or without spaces)")
    console.print("  [yellow]This will be hidden as you type[/yellow]")
    console.print()

    while True:
        password = Prompt.ask(
            "Application Password",
            password=True
        ).strip()

        if not password:
            console.print("[red]Error:[/red] Password cannot be empty")
            console.print()
            continue

        # Remove spaces for validation (WP accepts with or without)
        clean = password.replace(" ", "")

        if len(clean) < MIN_PASSWORD_LENGTH:
            console.print(
                "[red]Error:[/red] Application password seems too short "
                "(expected ~24 chars)"
            )
            if not Confirm.ask("Continue anyway?", default=False):
                console.print()
                continue

        console.print("  [green]\u2713[/green] Password accepted")
        return password


def _prompt_optional(message: str, default: str = "") -> str:
    """Prompt for optional value with default."""
    value = Prompt.ask(message, default=default)
    return value.strip() if value.strip() else default
