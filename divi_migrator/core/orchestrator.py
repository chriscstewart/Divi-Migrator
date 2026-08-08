"""Migration orchestrator with immutable audit."""

from __future__ import annotations

import logging
import time
from typing import Any

from divi_migrator.config import Config
from divi_migrator.core.audit import AuditManager
from divi_migrator.core.client import WPClient, DiviOpsClient
from divi_migrator.core.discovery import discover_migratable_items
from divi_migrator.core.inspector import fetch_design_system
from divi_migrator.core.schema_validator import validate_divi5_blocks
from divi_migrator.core.verification import verify_page, VerificationEngine
from divi_migrator.converters import registry
from divi_migrator.models.design_system import DesignSystem
from hashlib import sha256

logger = logging.getLogger(__name__)

# Shared hosts cap `context=edit` listing at ~100 rows, so we fetch originals
# per author with a small page size to stay safely under that limit.
AUDIT_FETCH_PER_PAGE = 50
ORIGINAL_AUTHORS = (1, 2)

MIGRATION_CATEGORY_SLUG = "divi-migrator"
MIGRATION_CATEGORY_NAME = "Divi Migrator"


def content_hash(content: str) -> str:
    return sha256(content.encode()).hexdigest()[:16]


class MigrationOrchestrator:
    """Orchestrates migration with immutable audit."""

    def __init__(self, config: Config):
        self.config = config
        self.wp = WPClient(config)
        self.diviops = DiviOpsClient(self.wp)
        self.audit = AuditManager(self.wp, config)
        self.verification = VerificationEngine(self.diviops, config)
        self._design_system: DesignSystem | None = None
        self._migration_category_id: int | None = None

    def _get_design_system(self) -> DesignSystem:
        if self._design_system is None:
            self._design_system = fetch_design_system(self.config, self.wp, self.diviops)
        return self._design_system

    def _get_primary_bg_color(self) -> str:
        ds = self._get_design_system()
        if hasattr(ds, "primary_background_color") and ds.primary_background_color:
            return str(ds.primary_background_color)
        return "#ffffff"

    def _get_original_metadata(self, post_type: str, item_id: int) -> dict[str, Any]:
        """Extract original metadata to preserve - from audit (immutable) or WP.

        Returns top-level WP fields (date, slug, author, status) plus
        ``categories``/``tags`` so the migrated item keeps the original's
        publication date, taxonomy and authorship.
        """
        original = self.audit.get_original(post_type, item_id)
        if original:
            meta: dict[str, Any] = {
                "date": original.date,
                "date_gmt": original.date_gmt,
                "modified": original.date_gmt,
                "modified_gmt": original.date_gmt,
                "slug": original.slug,
                "author": original.author,
                "status": original.status,
            }
        else:
            meta = {}
        # Categories/tags live on the live original (preserved, renamed to -old).
        wp_original = self.wp.get_item(post_type, item_id)
        if isinstance(wp_original, dict):
            if "categories" in wp_original:
                meta["categories"] = wp_original["categories"]
            if "tags" in wp_original:
                meta["tags"] = wp_original["tags"]
            if not original:
                meta.update({
                    "date": wp_original.get("date"),
                    "date_gmt": wp_original.get("date_gmt"),
                    "modified": wp_original.get("modified"),
                    "modified_gmt": wp_original.get("modified_gmt"),
                    "slug": wp_original.get("slug"),
                    "author": wp_original.get("author"),
                    "status": wp_original.get("status"),
                })
        return meta

    def _migrate_item(  # noqa: C901 PLR0912 PLR0915
        self, post_type: str, item: dict[str, Any], design_system: DesignSystem, dry_run: bool
    ) -> dict[str, Any]:
        """Migrate a single item with audit tracking."""
        item_id = item["id"]
        title = item["title"]
        slug = item.get("slug", title.lower().replace(" ", "-"))
        fmt = item["format"]

        # Fetch full content
        original = self.wp.get_item(post_type, item_id)
        if not isinstance(original, dict):
            raise ValueError(f"Failed to fetch content for {post_type} #{item_id}")  # noqa: TRY004,TRY003
        content = original.get("content", {}).get("rendered", "")
        if not content:
            raise ValueError(f"Empty content for {post_type} #{item_id}")  # noqa: TRY003

        # Check audit - already migrated?
        if self.audit.is_migrated(post_type, item_id):
            migrated_id = self.audit.get_migrated_id(post_type, item_id)
            logger.info(f"  ⏭️  Already migrated (ID {migrated_id}), skipping")
            return {
                "id": item["id"], "title": title, "status": "skipped",
                "draft_id": migrated_id, "verification": None, "meta": None,
            }

        # Check if in-progress (resume)
        record = self.audit.get_migration_status(post_type, item_id)
        if record and record.status == "in_progress":
            logger.info(f"  🔄 Resuming migration for #{item_id}")

        # Start tracking
        self.audit.start_migration(post_type, item_id, title, slug, content_hash(content))

        # Get original metadata (from audit - immutable)
        original_meta = self._get_original_metadata(post_type, item_id)

        # Convert content
        converter = registry.get_converter(fmt)
        if not converter:
            self.audit.fail_migration(post_type, item_id, f"No converter for format: {fmt}")
            raise ValueError(f"No converter for format: {fmt}")  # noqa: TRY003

        divi_content = converter.convert(content, item_id, design_system, wp_client=self.wp)

        # Validate with DiviOps
        validation = self.diviops.validate_blocks(divi_content)
        if not validation.get("ok", True):
            self.audit.fail_migration(post_type, item_id, f"Validation failed: {validation}")
            raise ValueError(f"Validation failed: {validation}")  # noqa: TRY003

        # Schema validation BEFORE saving
        schema_valid, schema_errors = validate_divi5_blocks(divi_content)
        if not schema_valid:
            self.audit.fail_migration(post_type, item_id, f"Schema validation failed: {schema_errors}")  # noqa: E501
            raise ValueError(f"Schema validation failed: {schema_errors}")  # noqa: TRY003

        if dry_run:
            return {
                "id": item["id"], "title": title, "status": "dry_run",
                "draft_id": None, "verification": None, "meta": None,
            }

        # Idempotency: trash any leftover draft from a prior (failed) run for
        # this exact source so retries don't accumulate orphan drafts. The
        # search query can be heavy on cheap shared hosting and may 500; if it
        # fails we simply skip pre-cleanup rather than aborting the migration.
        try:
            prior = self.wp.get_items(
                post_type, status="draft", per_page=5,
                search=title,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("Pre-creation orphan check failed (skipping): %s", e)
            prior = None
        if isinstance(prior, list):
            for d in prior:
                if not isinstance(d, dict):
                    continue
                did = int(d.get("id", 0))
                dmeta = d.get("meta", {})
                if did and dmeta.get("_divi_migrator", {}).get("source_id") == item["id"]:
                    self.wp.delete(f"{post_type}s/{did}", force=False)
                    logger.info("  🧹 Trashed prior draft %d for source #%d", did, item["id"])

        # Create NEW draft via DiviOps with DRAFT status (transaction safety)
        draft = self.diviops.create_content(
            title, divi_content, status="draft", post_type=post_type
        )

        if isinstance(draft, dict) and draft.get("ok") and draft.get("data", {}).get("page_id"):
            draft_id = draft["data"]["page_id"]
        elif isinstance(draft, dict) and draft.get("id"):
            draft_id = draft["id"]
        else:
            self.audit.fail_migration(post_type, item_id, "Failed to create draft")
            raise ValueError(f"Failed to create {post_type} #{item_id}")  # noqa: TRY003

        logger.info(f"  ✅ Created new draft: ID {draft_id}")

        # Verify layout
        verification = verify_page(self.diviops, self.config, draft_id)

        # Prepare migration metadata
        meta_data = {
            "_divi_migrator": {
                "version": 1,
                "source_format": fmt.value,
                "source_id": item["id"],
                "source_title": title,
                "source_content_hash": content_hash(content),
                "migrated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "divi_blocks_count": len(verification.block_tree),
                "sections_count": verification.sections,
                "rows_count": verification.rows,
                "modules_count": verification.modules,
                "images_count": verification.images,
                "buttons_count": verification.buttons,
                "background_colors": verification.background_colors,
                "verification_passed": verification.verification_passed,
                "verification_details": {
                    "sections": verification.sections,
                    "rows": verification.rows,
                    "modules": verification.modules,
                    "images": verification.images,
                    "buttons": verification.buttons,
                    "background_colors": verification.background_colors,
                    "issues": verification.issues,
                },
            }
        }
        self.wp.update_meta(post_type, draft_id, meta_data)

        # Restore original metadata (dates, author, categories, tags, featured image)
        original_meta = self._get_original_metadata(post_type, item_id)
        self.wp.update_meta(post_type, draft_id, {
            **original_meta,
            "meta": {**original_meta.get("meta", {}), **meta_data.get("meta", {})}
        })

        # Add migration category
        cat_id = self._ensure_migration_category(post_type)
        if cat_id and post_type == "post":
            self.wp.put(f"posts/{draft_id}", json_data={"categories": [cat_id]})

        # Apply original title/slug to migrated draft
        update_result = self.wp.put(f"{post_type}s/{draft_id}", json_data={
            "title": title,
            "slug": slug,
        })
        if isinstance(update_result, dict) and update_result.get("id"):
            logger.info("  ✅ Applied original title/slug to migrated draft")

        # Publish the draft now that everything succeeded, preserving the
        # original publication date, categories and tags.
        publish_payload: dict[str, Any] = {"status": "publish"}
        if original_meta.get("date"):
            publish_payload["date"] = original_meta["date"]
        if original_meta.get("date_gmt"):
            publish_payload["date_gmt"] = original_meta["date_gmt"]
        cats = list(original_meta.get("categories", []))
        if cat_id and post_type == "post" and cat_id not in cats:
            cats.append(cat_id)
        if cats:
            publish_payload["categories"] = cats
        if original_meta.get("tags"):
            publish_payload["tags"] = original_meta["tags"]
        publish_result = self.wp.put(f"{post_type}s/{draft_id}", json_data=publish_payload)
        if isinstance(publish_result, dict) and publish_result.get("id"):
            logger.info("  ✅ Published migrated draft (original date/cats/tags preserved)")

        # Rename the ORIGINAL to '<slug>-old' and set it to DRAFT so the
        # migrated item owns the exact original URL/title. The audit retains
        # the immutable original title/slug, so rollback restores them.
        # Skipped in dry_run (no draft was created) and guarded by the audit
        # (originals are never force-deleted).
        if not dry_run:
            old_title = f"{title}-old"
            old_slug = f"{slug}-old"
            rename_result = self.wp.put(
                f"{post_type}s/{item_id}",
                json_data={"title": old_title, "slug": old_slug, "status": "draft"},
            )
            if isinstance(rename_result, dict) and rename_result.get("id"):
                self.audit.mark_renamed(post_type, item_id, old_title, old_slug)
                logger.info(
                    "  ✅ Renamed original to '%s' (slug: %s) and set to draft",
                    old_title, old_slug,
                )

        # Mark complete in audit
        self.audit.complete_migration(post_type, item_id, draft_id)

        return {
            "id": item["id"],
            "title": title,
            "status": "completed",
            "draft_id": draft_id,
            "verification": verification.verification_passed,
            "meta": meta_data,
        }

    def _ensure_migration_category(self, post_type: str) -> int:  # noqa: ARG002
        if self._migration_category_id:
            return self._migration_category_id

        categories = self.wp.get(f"categories?search={MIGRATION_CATEGORY_SLUG}")
        if isinstance(categories, list) and categories:
            for cat in categories:
                if cat.get("slug") == MIGRATION_CATEGORY_SLUG:
                    self._migration_category_id = cat["id"]
                    return self._migration_category_id

        cat_data = {
            "name": MIGRATION_CATEGORY_NAME,
            "slug": MIGRATION_CATEGORY_SLUG,
            "description": "Content migrated via Divi-Migrator"
        }
        created = self.wp.post("categories", json_data=cat_data)
        if isinstance(created, dict) and "id" in created:
            self._migration_category_id = created["id"]
            logger.info(
                "Created migration tracking category: %s (ID: %d)",
                MIGRATION_CATEGORY_NAME, self._migration_category_id
            )
            return self._migration_category_id

        logger.warning("Could not create migration category")
        return 0

    def _run_migration(
        self,
        post_type: str,
        limit: int | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Internal migration runner with audit initialization."""
        logger.info("Starting %s migration (dry_run=%s)", post_type, dry_run)

        # Initialize audit if first run.
        # NOTE: cheap shared hosts cap `context=edit` listing at ~100 rows total,
        # so a blanket `status=any` query silently drops items past the cap. We
        # fetch PER AUTHOR (the migration only targets recorded originals, which
        # are author 1/2) so each query stays under the cap and nothing is missed.
        audit = self.audit.load()
        if audit.total_pages == 0 and audit.total_posts == 0:
            logger.info("Initializing audit - recording all original content...")
            pages, posts = self._fetch_originals()
            self.audit.record_originals(pages, posts)
            logger.info("Audit initialized: %d pages, %d posts recorded as originals",
                       len(pages), len(posts))

        # Fetch design system ONCE
        logger.info("Fetching design system...")
        design_system = fetch_design_system(self.config, self.wp, self.diviops)

        # Discover items (audit-aware)
        logger.info("Discovering %s items...", post_type)
        items = discover_migratable_items(self.wp, self.audit, post_type, limit)

        if not items:
            logger.warning("No migratable %s items found", post_type)
            return {"status": "completed", "results": []}

        logger.info("Found %d %s items to process", len(items), post_type)

        results = []
        for i, item in enumerate(items):
            item_id = item["id"]
            title = item["title"]
            fmt = item["format"]

            logger.info("[%d/%d] Migrating %s #%d: %s", i + 1, len(items), post_type, item_id, title)  # noqa: E501
            try:
                result = self._migrate_item(post_type, item, design_system, dry_run)
                results.append(result)
            except Exception as e:
                logger.error("  ❌ FAILED: %s", e)  # noqa: TRY400
                self.audit.fail_migration(post_type, item_id, str(e))
                results.append({
                    "id": item_id, "title": title, "format": fmt, "status": "failed",
                    "error": str(e), "draft_id": None, "verification": None, "meta": None,
                })

        # Summary
        completed = sum(1 for r in results if r.get("status") == "completed")
        failed = sum(1 for r in results if r.get("status") == "failed")
        dry_runs = sum(1 for r in results if r.get("status") == "dry_run")
        skipped = sum(1 for r in results if r.get("status") == "skipped")

        from rich.console import Console  # noqa: PLC0415
        from rich.table import Table  # noqa: PLC0415
        console = Console()
        table = Table(title=f"Migration Results - {post_type}")
        table.add_column("Status", style="cyan")
        table.add_column("Count", style="green")
        table.add_row("Completed", str(completed))
        table.add_row("Failed", str(failed))
        table.add_row("Dry Runs", str(dry_runs))
        table.add_row("Skipped", str(skipped))
        console.print(table)

        return {
            "status": "completed" if failed == 0 else "completed_with_warnings",
            "results": results,
        }

    def _fetch_originals(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Fetch all original (author 1/2) pages + posts, per-author, paginated.

        Cheap shared hosts cap `context=edit` listing at ~100 rows, so a single
        blanket `status=any` query silently drops items past the cap. Querying
        per author with a small page size keeps each call under that limit.
        """
        pages: list[dict[str, Any]] = []
        posts: list[dict[str, Any]] = []
        for author in ORIGINAL_AUTHORS:
            page_num = 1
            while True:
                chunk = self.wp.get_items(
                    "page", status="any", per_page=AUDIT_FETCH_PER_PAGE,
                    page=page_num, context="edit", author=author,
                )
                if not chunk:
                    break
                pages.extend(chunk)
                if len(chunk) < AUDIT_FETCH_PER_PAGE:
                    break
                page_num += 1
            page_num = 1
            while True:
                chunk = self.wp.get_items(
                    "post", status="any", per_page=AUDIT_FETCH_PER_PAGE,
                    page=page_num, context="edit", author=author,
                )
                if not chunk:
                    break
                posts.extend(chunk)
                if len(chunk) < AUDIT_FETCH_PER_PAGE:
                    break
                page_num += 1
        # Enforce author filter client-side too (author param is best-effort).
        pages = [p for p in pages if p.get("author") in ORIGINAL_AUTHORS]
        posts = [p for p in posts if p.get("author") in ORIGINAL_AUTHORS]
        return pages, posts

    def migrate_post_type(
        self, post_type: str, limit: int | None = None, dry_run: bool = False
    ) -> dict[str, Any]:
        return self._run_migration(post_type, limit, dry_run)

    def rollback_post_type(self, post_type: str) -> dict[str, Any]:
        """Rollback all migrations for a post type."""
        logger.warning("Rolling back ALL %s migrations...", post_type)
        return self.audit.bulk_rollback(post_type, self.wp)

    def get_audit_stats(self) -> dict[str, Any]:
        return self.audit.get_stats()

    def cleanup_duplicates(self, post_type: str, dry_run: bool = False) -> int:
        """Remove duplicate draft copies of the same title, keeping one.

        Originals (protected by the audit) are never deleted. Returns the
        number of drafts removed (or that would be removed in dry-run mode).
        """
        deleted = 0
        seen_titles: dict[str, int] = {}
        page = 1
        while True:
            items = self.wp.get_items(post_type, status="draft", page=page, per_page=100)
            if not items:
                break
            for item in items:
                if not isinstance(item, dict):
                    continue
                item_id = int(item.get("id", 0))
                title = item.get("title", {}).get("rendered", "") if isinstance(item.get("title"), dict) else ""  # noqa: E501
                if self.audit.is_original(post_type, item_id):
                    continue
                if "-old" in title:
                    continue
                if title in seen_titles:
                    if not dry_run:
                        self.wp.delete(f"{post_type}s/{item_id}", force=False)
                    deleted += 1
                else:
                    seen_titles[title] = item_id
            if len(items) < 100:  # noqa: PLR2004
                break
            page += 1
        return deleted
