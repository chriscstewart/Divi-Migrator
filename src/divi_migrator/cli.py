"""CLI entrypoint for divi-migrator."""

import sys
import json
import yaml
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from divi_migrator import __version__
from divi_migrator.config import Config
from divi_migrator.core.discovery import discover_migratable_items
from divi_migrator.core.orchestrator import MigrationOrchestrator
from divi_migrator.core.inspector import fetch_design_system
from divi_migrator.core.client import WPClient

app = typer.Typer(
    name="divi-migrate",
    help="Generic WordPress Avada/Elementor/Plain HTML to Divi 5 migration framework",
    add_completion=False,
)

console = Console()


def load_config(config_path: str | None = None) -> Config:
    """Load configuration from file and environment."""
    if config_path:
        return Config.from_yaml(Path(config_path))
    # Load from env vars only
    import os
    from divi_migrator.config import WPSettings
    return Config(
        wp=WPSettings(
            url=os.environ.get("WP_URL", ""),
            user=os.environ.get("WP_USER", ""),
            app_password=os.environ.get("WP_APP_PASSWORD", ""),
            ssl_verify=True,
            timeout=30,
        ),
    )
@app.command()
def discover(
    post_type: str = typer.Option("page", "--type", "-t", help="Post type: page or post"),
    output_format: str = typer.Option(
        "table", "--format", "-f", help="Output format: table, json, yaml"
    ),
    limit: int | None = typer.Option(None, "--limit", "-l", help="Limit items"),
    config: str | None = typer.Option(None, "--config", "-c", help="Config file path"),
) -> None:
    """Discover migratable pages or posts."""
    cfg = load_config(config)

    console.print(f"[bold]Discovering {post_type}s to migrate...[/bold]")

    wp = WPClient(cfg)
    items = discover_migratable_items(wp, post_type, limit=limit)

    if output_format == "json":
        console.print(json.dumps(items))
    elif output_format == "yaml":
        console.print(yaml.dump(items))
    else:
        table = Table(title=f"Migratable {post_type}s")
        table.add_column("ID", justify="right")
        table.add_column("Title")
        table.add_column("Format")
        table.add_column("Chars", justify="right")

        for item in items:
            table.add_row(
                str(item["id"]), item["title"][:60], item["format"], str(item["content_length"])
            )
        console.print(table)


@app.command()
def migrate(
    post_type: str = typer.Option("page", "--type", "-t", help="Post type: page or post"),
    limit: int | None = typer.Option(
        None, "--limit", "-l", help="Limit number of items to migrate"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Test without creating drafts"),
    config: str | None = typer.Option(None, "--config", "-c", help="Config file path"),
) -> None:
    """Migrate pages/posts to Divi 5."""
    cfg = load_config(config)

    if not dry_run:
        console.print("[yellow]This will create draft pages/posts. Review carefully.[/yellow]")
        if not typer.confirm("Continue?"):
            raise typer.Abort()

    console.print(f"[bold]Starting {post_type} migration...[/bold]")
    if dry_run:
        console.print("[yellow]DRY RUN MODE - no drafts will be created[/yellow]")

    orchestrator = MigrationOrchestrator(cfg)
    results = orchestrator.migrate_post_type(post_type, limit=limit, dry_run=dry_run)

    # Summary table
    table = Table(title="Migration Results")
    table.add_column("Status")
    table.add_column("Count", justify="right")

    statuses: dict[str, int] = {}
    for r in results:
        status = r.get("status", "unknown")
        statuses[status] = statuses.get(status, 0) + 1

    for status, count in statuses.items():
        style = "green" if "completed" in status else "red" if "failed" in status else "yellow"
        table.add_row(f"[{style}]{status}[/{style}]", str(count))

    console.print(table)

    if any(r.get("status") == "failed" for r in results):
        sys.exit(1)


@app.command()
def cleanup(
    post_type: str = typer.Option("page", "--type", "-t", help="Post type: page or post"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be deleted"),
    config: str | None = typer.Option(None, "--config", "-c", help="Config file path"),
) -> None:
    """Clean up duplicate migration drafts."""
    cfg = load_config(config)
    if dry_run:
        console.print("[yellow]DRY RUN - no drafts will be deleted[/yellow]")

    orchestrator = MigrationOrchestrator(cfg)
    deleted = orchestrator.cleanup_duplicates(post_type, dry_run=dry_run)
    console.print(f"[green]Cleaned up {deleted} duplicate drafts[/green]")


@app.command()
def inspect(
    config: str | None = typer.Option(None, "--config", "-c", help="Config file path"),
) -> None:
    """Inspect target site's design system."""
    cfg = load_config(config)

    console.print("[bold]Fetching design system...[/bold]")
    ds = fetch_design_system(cfg, WPClient(cfg))

    console.print(f"[green]Colors:[/green] {len(ds.colors.colors)}")
    for key, token in ds.colors.colors.items():
        console.print(f"  {key}: {token.color} ({token.label})")

    console.print(
        f"[green]Presets:[/green] {sum(len(v) for v in ds.presets.__dict__.values())} total"
    )
    for attr, items in ds.presets.__dict__.items():
        if items:
            console.print(f"  {attr}: {len(items)}")

    console.print(f"[green]Variables:[/green] {len(ds.variables.variables)}")
    console.print(f"[green]Custom CSS:[/green] {len(ds.custom_css)} chars")


@app.command()
def version() -> None:
    """Show version."""
    console.print(f"divi-migrator v{__version__}")


if __name__ == "__main__":
    app()