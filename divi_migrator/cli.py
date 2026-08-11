"""CLI commands for Divi Migrator."""

from __future__ import annotations

import os
import sys
import re
import json
import yaml
from pathlib import Path
from typing import Any
import typer
from rich.console import Console
from rich.table import Table
from rich.prompt import Confirm

from divi_migrator.config import (
    Config,
    WPSettings,
    MigrationSettings,
    VerificationSettings,
    DesignSystemSettings,
    AuditSettings,
)
from divi_migrator.core.client import WPClient, DiviOpsClient
from divi_migrator.core.inspector import fetch_design_system
from divi_migrator.core.orchestrator import MigrationOrchestrator
from divi_migrator.core.audit import AuditManager
from divi_migrator.core.audit_guard import AuditGuard
from divi_migrator.converters.avada import AvadaConverter
from divi_migrator.credentials import (
    load_config as load_credentials,
    CredentialError,
)

from . import __version__

app = typer.Typer(help="Divi Migrator - Avada/Fusion Builder to Divi 5 migration tool")
console = Console()


def _overlay_non_secret_config(base: Config, project_root: Path) -> Config:
    """Overlay non-secret tunables from config.yaml onto a credential-derived Config.

    Credentials (secrets/identity) come from the credential system / .env; the
    committed config.yaml is the authoritative source for non-secret knobs
    (rate_limit, min_delay, timeouts, verification, design_system, audit). This
    keeps secrets out of version control while letting tunables live in config.yaml.
    Missing or partial config.yaml is tolerated (the credential-derived defaults win).
    """
    cfg_path = project_root / "config.yaml"
    if not cfg_path.exists():
        return base
    try:
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
        return base
    for attr, model in (
        ("migration", MigrationSettings),
        ("verification", VerificationSettings),
        ("design_system", DesignSystemSettings),
        ("audit", AuditSettings),
    ):
        if attr in data and isinstance(data[attr], dict):
            current = getattr(base, attr)
            merged = {**current.model_dump(), **data[attr]}
            setattr(base, attr, model(**merged))
    return base


def load_config(
    config_path: str | None = None,
    project_root: str | None = None,
    non_interactive: bool = False,
) -> Config:
    """

    Load configuration using the new credential system.

    Falls back to old env-var only method if credentials not found.
    """
    try:
        complete = load_credentials(
            config_path,
            Path(project_root) if project_root else None,
            non_interactive=non_interactive,
        )  # noqa: E501
        cfg = Config.from_complete_config(complete)
        # config.yaml is the authoritative source for non-secret tunables.
        return _overlay_non_secret_config(cfg, Path(project_root) if project_root else Path.cwd())
    except CredentialError as e:
        # Re-raise credential errors for non-interactive mode
        if non_interactive:
            raise
        # Fallback to old env-var only method
        console.print(f"[yellow]Credential system: {e}[/yellow]")
        console.print("[yellow]Falling back to environment variables...[/yellow]")
        return Config(
            wp=WPSettings(
                url=os.environ.get("WP_URL", ""),
                user=os.environ.get("WP_USER", ""),
                app_password=os.environ.get("WP_APP_PASSWORD", ""),
                ssl_verify=os.environ.get("WP_SSL_VERIFY", "true").lower() == "true",
                timeout=int(os.environ.get("WP_TIMEOUT", "30")),
            ),
        )
    except Exception as e:
        if non_interactive:
            raise
        console.print(f"[yellow]Credential system: {e}[/yellow]")
        console.print("[yellow]Falling back to environment variables...[/yellow]")
        return Config(
            wp=WPSettings(
                url=os.environ.get("WP_URL", ""),
                user=os.environ.get("WP_USER", ""),
                app_password=os.environ.get("WP_APP_PASSWORD", ""),
                ssl_verify=os.environ.get("WP_SSL_VERIFY", "true").lower() == "true",
                timeout=int(os.environ.get("WP_TIMEOUT", "30")),
            ),
        )


def create_orchestrator(config: Config) -> MigrationOrchestrator:
    """Create orchestrator with audit guard."""
    orch = MigrationOrchestrator(config)
    # Attach audit guard to client for protection
    audit_guard = AuditGuard(orch.audit)
    orch.wp.audit_guard = audit_guard
    return orch


@app.callback()
def callback(
    ctx: typer.Context,
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        "-n",
        help="Run in non-interactive mode (fail fast if credentials missing, no prompts)",
    ),
) -> None:
    """Divi Migrator - Avada/Fusion Builder to Divi 5 migration tool."""
    # Store non-interactive flag in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj["non_interactive"] = non_interactive


def get_non_interactive(ctx: typer.Context) -> bool:
    """Get non-interactive flag from context."""
    return ctx.obj.get("non_interactive", False) if ctx.obj else False


@app.command()
def setup(
    ctx: typer.Context,
    config: str | None = typer.Option(None, "--config", "-c", help="Config file path"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing config"),
) -> None:
    """

    Walks you through creating WordPress Application Passwords,
    configuring DiviOps, and saving to config.yaml.
    """
    if get_non_interactive(ctx):
        console.print(
            "[red]Error:[/red] Setup requires interactive mode. Remove --non-interactive flag."
        )  # noqa: E501
        raise typer.Abort()

    cfg_path = Path(config) if config else Path.cwd() / "config.yaml"

    if cfg_path.exists() and not force:
        console.print(f"[yellow]Config already exists at {cfg_path}[/yellow]")
        if not Confirm.ask("Overwrite?"):
            raise typer.Abort()

    console.print("[bold]Starting interactive setup...[/bold]")
    complete = load_credentials(config)

    # Save to config.yaml
    import yaml  # noqa: PLC0415

    config_dict = {
        "wp": complete.wp.to_config_dict(),
        "diviops": complete.diviops.to_config_dict(),
        "migration": complete.migration.to_config_dict(),
    }
    with cfg_path.open("w") as f:
        yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)

    console.print(f"[green]✓ Configuration saved to {cfg_path}[/green]")
    console.print("\nNext steps:")
    console.print("  1. Run [cyan]divi-migrate audit-init[/cyan] to record original content")
    console.print("  2. Run [cyan]divi-migrate discover[/cyan] to see migratable items")
    console.print("  3. Run [cyan]divi-migrate migrate --dry-run[/cyan] to test")
    console.print("  4. Run [cyan]divi-migrate migrate --execute[/cyan] to migrate")


@app.command()
def audit_init(
    ctx: typer.Context,
    config: str | None = typer.Option(None, "--config", "-c", help="Config file path"),
    force: bool = typer.Option(False, "--force", help="Re-initialize audit even if exists"),
) -> None:
    """Initialize audit by recording all original content (author 1 & 2 only)."""
    non_interactive = get_non_interactive(ctx)
    cfg = load_config(config, non_interactive=non_interactive)
    wp = WPClient(cfg)
    audit = AuditManager(wp, cfg)

    existing = audit.load()
    if existing.total_pages > 0 and not force:
        console.print(
            f"[yellow]Audit already exists: {existing.total_pages} pages, {existing.total_posts} posts[/yellow]"  # noqa: E501
        )
        if not Confirm.ask("Re-initialize?"):
            raise typer.Abort()

    console.print("[bold]Recording all original content (author 1 & 2 only)...[/bold]")

    # Cheap shared hosts cap `context=edit` listing at ~100 rows total, so a
    # blanket `status=any` query silently drops items past the cap. Fetch PER
    # AUTHOR (per_page=50 keeps each author's query under the cap) and merge.
    audit_per_page = 50
    all_pages: list[dict[str, Any]] = []
    all_posts: list[dict[str, Any]] = []
    for author in (1, 2):
        page_num = 1
        while True:
            pages = wp.get_items(
                "page",
                status="any",
                per_page=audit_per_page,
                page=page_num,
                context="edit",
                author=author,
            )
            if not pages:
                break
            all_pages.extend(pages)
            if len(pages) < audit_per_page:
                break
            page_num += 1
        page_num = 1
        while True:
            posts = wp.get_items(
                "post",
                status="any",
                per_page=audit_per_page,
                page=page_num,
                context="edit",
                author=author,
            )
            if not posts:
                break
            all_posts.extend(posts)
            if len(posts) < audit_per_page:
                break
            page_num += 1

    # Filter to only author 1 and 2 (author query is best-effort; enforce client-side too)
    original_pages = [p for p in all_pages if p.get("author") in (1, 2)]
    original_posts = [p for p in all_posts if p.get("author") in (1, 2)]

    audit.record_originals(original_pages, original_posts)

    console.print(
        f"[green]Audit initialized: {len(original_pages)} pages, {len(original_posts)} posts recorded[/green]"  # noqa: E501
    )


@app.command()
def audit_status(
    ctx: typer.Context,
    config: str | None = typer.Option(None, "--config", "-c", help="Config file path"),
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json"),  # noqa: A002
) -> None:
    """Show audit status."""
    non_interactive = get_non_interactive(ctx)
    cfg = load_config(config, non_interactive=non_interactive)
    wp = WPClient(cfg)
    from divi_migrator.core.audit import AuditManager  # noqa: PLC0415

    audit = AuditManager(wp, cfg)

    stats = audit.get_stats()
    audit_data = audit.load()

    if format == "json":
        import json  # noqa: PLC0415

        console.print_json(json.dumps(stats, indent=2))
        return

    table = Table(title="Audit Status")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Total Pages", str(stats["total_pages"]))
    table.add_row("Total Posts", str(stats["total_posts"]))
    table.add_row("Migrated Pages", str(stats["migrated_pages"]))
    table.add_row("Migrated Posts", str(stats["migrated_posts"]))
    table.add_row("Failed Pages", str(stats["failed_pages"]))
    table.add_row("Failed Posts", str(stats["failed_posts"]))
    table.add_row("Pending Pages", str(stats["pending_pages"]))
    table.add_row("Pending Posts", str(stats["pending_posts"]))
    console.print(table)

    # Show migration map summary
    if audit_data.migration_map:
        console.print("\n[bold]Recent Migrations:[/bold]")
        recent = sorted(
            [(k, v) for k, v in audit_data.migration_map.items() if v.status == "completed"],
            key=lambda x: x[1].completed_at or "",
            reverse=True,
        )[:10]
        table2 = Table()
        table2.add_column("Type:ID")
        table2.add_column("Title")
        table2.add_column("Migrated ID")
        table2.add_column("Completed")
        for key, record in recent:
            table2.add_row(
                key, record.title[:50], str(record.migrated_id), record.completed_at or ""
            )  # noqa: E501
        console.print(table2)


@app.command()
def audit_rollback(
    ctx: typer.Context,
    post_type: str = typer.Option("page", "--type", "-t", help="Post type: page or post"),
    original_id: int | None = typer.Option(None, "--id", help="Specific original ID to rollback"),
    all: bool = typer.Option(False, "--all", help="Rollback ALL migrations for post type"),  # noqa: A002
    config: str | None = typer.Option(None, "--config", "-c", help="Config file path"),
) -> None:
    """Rollback migrations - delete migrated content, restore originals."""
    non_interactive = get_non_interactive(ctx)
    cfg = load_config(config, non_interactive=non_interactive)
    from divi_migrator.core.audit import AuditManager  # noqa: PLC0415

    audit = AuditManager(WPClient(cfg), cfg)

    if original_id:
        if not Confirm.ask(
            f"Rollback {post_type} #{original_id}? This deletes migrated content and restores original."  # noqa: E501
        ):
            raise typer.Abort()
        success = audit.rollback_migration(post_type, original_id)
        console.print(f"[green]Rollback {'successful' if success else 'failed'}[/green]")
    elif all:
        if not Confirm.ask(
            f"Rollback ALL {post_type} migrations? This deletes ALL migrated content and restores ALL originals."  # noqa: E501
        ):
            raise typer.Abort()
        result = audit.bulk_rollback(
            post_type, WPClient(load_config(config, non_interactive=non_interactive))
        )  # noqa: E501
        console.print(
            f"[green]Rollback complete: {result['deleted']} deleted, {result['restored']} restored[/green]"  # noqa: E501
        )
        if result["errors"]:
            for err in result["errors"]:
                console.print(f"[red]Error: {err}[/red]")
    else:
        console.print("[red]Specify --id or --all[/red]")


@app.command()
def audit_cleanup_ai(
    ctx: typer.Context,
    config: str | None = typer.Option(None, "--config", "-c", help="Config file path"),
    author_id: int = typer.Option(
        292, "--author", help="Author ID to cleanup (default: 292 = AI-Dev-MCPs)"
    ),  # noqa: E501
    post_type: str = typer.Option("page", "--type", "-t", help="Post type: page or post"),
    force: bool = typer.Option(False, "--force", help="Actually delete (default: dry run)"),
) -> None:
    """Clean up AI-generated content by author ID."""
    non_interactive = get_non_interactive(ctx)
    cfg = load_config(config, non_interactive=non_interactive)
    wp = WPClient(cfg)

    if force:
        console.print(
            "[yellow]This will TRASH all content by author ID. Cannot be undone.[/yellow]"
        )  # noqa: E501
        if not Confirm.ask("Continue?"):
            raise typer.Abort()

    deleted = wp.bulk_delete_by_author(post_type, author_id, force=False)
    console.print(
        f"[green]Cleaned up {deleted} items by author {author_id} (trashed, not deleted)[/green]"
    )  # noqa: E501


@app.command()
def discover(
    ctx: typer.Context,
    post_type: str = typer.Option("page", "--type", "-t", help="Post type: page or post"),
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json, yaml"),  # noqa: A002
    limit: int | None = typer.Option(None, "--limit", "-l", help="Limit items"),
    config: str | None = typer.Option(None, "--config", "-c", help="Config file path"),
) -> None:
    """Discover migratable pages or posts (audit-aware)."""
    non_interactive = get_non_interactive(ctx)
    cfg = load_config(config, non_interactive=non_interactive)
    wp = WPClient(cfg)
    from divi_migrator.core.audit import AuditManager  # noqa: PLC0415
    from divi_migrator.core.discovery import discover_migratable_items  # noqa: PLC0415

    audit = AuditManager(wp, cfg)
    audit.load()

    items = discover_migratable_items(wp, audit, post_type, limit)

    if format == "json":
        console.print_json(json.dumps(items, indent=2, default=str))
    elif format == "yaml":
        console.print(yaml.dump(items))
    else:
        table = Table(title=f"Migratable {post_type}s (audit-filtered)")
        table.add_column("ID", style="cyan")
        table.add_column("Title")
        table.add_column("Format", style="green")
        table.add_column("Chars", justify="right", style="yellow")
        for item in items:
            table.add_row(
                str(item["id"]), item["title"], item["format"].value, str(item["content_length"])
            )  # noqa: E501
        console.print(table)


@app.command()
def migrate(
    ctx: typer.Context,
    post_type: str = typer.Option("page", "--type", "-t", help="Post type: page or post"),
    limit: int | None = typer.Option(None, "--limit", "-l", help="Limit items"),
    dry_run: bool = typer.Option(True, "--dry-run/--execute", help="Dry run by default (safe)"),
    config: str | None = typer.Option(None, "--config", "-c", help="Config file path"),
) -> None:
    """Migrate pages/posts to Divi 5."""
    non_interactive = get_non_interactive(ctx)
    cfg = load_config(config, non_interactive=non_interactive)
    orch = MigrationOrchestrator(cfg)
    # Attach audit guard
    from divi_migrator.core.audit_guard import AuditGuard  # noqa: PLC0415

    orch.wp.audit_guard = AuditGuard(orch.audit)

    if not dry_run:
        console.print("[yellow]This will create draft pages/posts. Review carefully.[/yellow]")
        if not Confirm.ask("Continue?"):
            raise typer.Abort()

    console.print(f"[bold]Starting {post_type} migration...[/bold]")
    if dry_run:
        console.print("[yellow]DRY RUN MODE - no drafts will be created[/yellow]")

    result = orch.migrate_post_type(post_type, limit=limit, dry_run=dry_run)
    results = result.get("results", [])

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
def rollback(
    ctx: typer.Context,
    post_type: str = typer.Option("page", "--type", "-t", help="Post type: page or post"),
    config: str | None = typer.Option(None, "--config", "-c", help="Config file path"),
) -> None:
    """Rollback ALL migrations for a post type."""
    non_interactive = get_non_interactive(ctx)
    cfg = load_config(config, non_interactive=non_interactive)
    orch = MigrationOrchestrator(cfg)
    from divi_migrator.core.audit_guard import AuditGuard  # noqa: PLC0415

    orch.wp.audit_guard = AuditGuard(orch.audit)

    console.print(f"[bold red]Rolling back ALL {post_type} migrations...[/bold red]")
    if not Confirm.ask("This deletes ALL migrated content and restores ALL originals. Continue?"):
        raise typer.Abort()

    result = orch.rollback_post_type(post_type)
    console.print(
        f"[green]Rollback complete: {result['deleted']} deleted, {result['restored']} restored[/green]"  # noqa: E501
    )
    if result["errors"]:
        for err in result["errors"]:
            console.print(f"[red]Error: {err}[/red]")


@app.command()
def cleanup(
    ctx: typer.Context,
    post_type: str = typer.Option("page", "--type", "-t", help="Post type: page or post"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be deleted"),
    config: str | None = typer.Option(None, "--config", "-c", help="Config file path"),
) -> None:
    """Clean up duplicate migration drafts."""
    non_interactive = get_non_interactive(ctx)
    cfg = load_config(config, non_interactive=non_interactive)
    orch = MigrationOrchestrator(cfg)
    if dry_run:
        console.print("[yellow]DRY RUN - no drafts will be deleted[/yellow]")

    deleted = orch.cleanup_duplicates(post_type, dry_run=dry_run)
    console.print(f"[green]Cleaned up {deleted} duplicate drafts[/green]")


@app.command()
def inspect(
    ctx: typer.Context,
    config: str | None = typer.Option(None, "--config", "-c", help="Config file path"),
) -> None:
    """Inspect target site design system."""
    non_interactive = get_non_interactive(ctx)
    cfg = load_config(config, non_interactive=non_interactive)

    console.print("[bold]Fetching design system...[/bold]")
    ds = fetch_design_system(cfg, WPClient(cfg), DiviOpsClient(WPClient(cfg)))

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
def preflight(
    ctx: typer.Context,
    post_type: str = typer.Option("page", "--type", "-t", help="Post type: page or post"),
    config: str | None = typer.Option(None, "--config", "-c", help="Config file path"),
) -> None:
    """Pre-flight loss audit: list exactly which Avada shortcodes would be silently
    stripped on a full migration.

    Scans every item, runs the converter, and reports any `fusion_*` shortcode that
    survives conversion (i.e. would be deleted by the cleanup-strip list). This is
    the red-team check before pointing the migrator at the whole site.
    """
    non_interactive = get_non_interactive(ctx)
    cfg = load_config(config, non_interactive=non_interactive)
    orch = MigrationOrchestrator(cfg)
    orch.wp.audit_guard = AuditGuard(orch.audit)

    ds = orch._get_design_system()  # noqa: SLF001

    console.print(f"[bold]Pre-flight loss scan: {post_type}s[/bold]")
    page = 1
    per_page = 50
    total = 0
    items_with_loss = 0
    loss_by_shortcode: dict[str, int] = {}
    while True:
        raw_items: Any = orch.wp.get(
            post_type + "s",
            params={
                "per_page": per_page,
                "page": page,
                "context": "edit",
                "_fields": "id,title,content",
            },
        )
        items: list[dict[str, Any]] = list(raw_items) if raw_items else []
        if not items:
            break
        for item in items:
            content = item.get("content", {}).get("rendered", "")
            if "fusion_" not in content:
                continue
            conv = AvadaConverter()
            converted = conv.convert(content, item["id"], ds, wp_client=orch.wp)
            # Any fusion_ shortcode surviving in the output = would be stripped
            survivors = set(re.findall(r"\[/?fusion_([a-z_]+)", converted))
            if survivors:
                items_with_loss += 1
                names = sorted(survivors)
                for n in names:
                    loss_by_shortcode[n] = loss_by_shortcode.get(n, 0) + 1
                console.print(
                    f"  [red]{post_type} {item['id']}[/red] "
                    f"({item.get('title', {}).get('rendered', '?')}): "
                    f"{', '.join(names)}"
                )
        total += len(items)
        if len(items) < per_page:
            break
        page += 1

    console.print()
    console.print(f"[bold]Scanned:[/bold] {total} {post_type}s")
    if items_with_loss == 0:
        console.print(
            "[green]No silent content loss detected — all Avada shortcodes are covered.[/green]"
        )  # noqa: E501
    else:
        console.print(
            f"[red]{items_with_loss} {post_type}(s) would lose content.[/red] Shortcodes at risk:"
        )
        for sc, cnt in sorted(loss_by_shortcode.items(), key=lambda x: -x[1]):
            console.print(f"  [yellow]fusion_{sc}[/yellow]: {cnt} occurrence(s)")


@app.command()
def version_command() -> None:
    """Show version."""
    console.print(f"divi-migrator v{__version__}")


if __name__ == "__main__":
    app()
