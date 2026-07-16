"""Migration orchestrator - ties all components together."""

from __future__ import annotations

import logging
import time
from typing import Any

from divi_migrator.config import Config
from divi_migrator.core.client import WPClient, DiviOpsClient
from divi_migrator.core.checkpoint import CheckpointManager
from divi_migrator.core.discovery import discover_migratable_items
from divi_migrator.core.inspector import fetch_design_system
from divi_migrator.core.verification import verify_page
from divi_migrator.converters import registry
from divi_migrator.converters.base import ExtractedAssets
from divi_migrator.models import MigrationMeta
from divi_migrator.models.design_system import DesignSystem
from dataclasses import asdict
from hashlib import sha256

logger = logging.getLogger(__name__)

MIGRATION_CATEGORY_SLUG = "divi-migrator"
MIGRATION_CATEGORY_NAME = "Divi Migrator"


def content_hash(content: str) -> str:
    """Generate hash of content."""
    return sha256(content.encode()).hexdigest()[:16]


class MigrationOrchestrator:
    """Orchestrates the complete migration pipeline."""

    def __init__(self, config: Config):
        self.config = config
        self.wp = WPClient(config)
        self.diviops = DiviOpsClient(self.wp)
        self.checkpoint = CheckpointManager(config)
        self.verification = VerificationEngine(self.diviops, config)
        self._migration_category_id: int | None = None

    def _ensure_migration_category(self, post_type: str) -> int:
        """Ensure the migration tracking category exists and return its ID."""
        if self._migration_category_id:
            return self._migration_category_id

        # Check if category exists
        categories = self.wp.get(f"categories?search={MIGRATION_CATEGORY_SLUG}")
        if isinstance(categories, list) and categories:
            for cat in categories:
                if cat.get("slug") == MIGRATION_CATEGORY_SLUG:
                    self._migration_category_id = cat["id"]
                    return self._migration_category_id

        # Create category
        cat_data = {
            "name": MIGRATION_CATEGORY_NAME,
            "slug": MIGRATION_CATEGORY_SLUG,
            "description": "Content migrated via Divi-Migrator",
        }
        created = self.wp.post("categories", json_data=cat_data)
        if isinstance(created, dict) and "id" in created:
            self._migration_category_id = created["id"]
            logger.info(
                "Created migration tracking category: %s (ID: %d)",
                MIGRATION_CATEGORY_NAME,
                self._migration_category_id,
            )
            return self._migration_category_id

        logger.warning("Could not create migration category")
        return 0

    def _prepare_existing_content(self, post_type: str, title: str, slug: str) -> int | None:
        """
        Handle existing content with same title/slug conflict.

        Process:
        1. Duplicate the existing page/post
        2. Rename original: append '-old' to slug and title
        3. Move original to Draft
        4. Return the original ID so we can use its slug/title for migrated version
        """
        # Find existing content with same slug
        existing = self.wp.get(f"{post_type}s?slug={slug}&status=any")
        if not isinstance(existing, list) or not existing:
            return None

        original = existing[0]
        original_id = original.get("id")
        if not original_id:
            return None

        logger.info("  ⚠️  Conflict detected: '%s' (ID: %d) exists - creating backup", title, original_id)

        # Duplicate the original
        duplicate_data = {
            "title": f"{original['title']['rendered']} -old",
            "slug": f"{slug}-old",
            "status": "draft",
            "content": original.get("content", {}).get("rendered", ""),
        }
        duplicate = self.wp.post(f"{post_type}s", json_data=duplicate_data)
        if not isinstance(duplicate, dict) or "id" not in duplicate:
            logger.warning("  Failed to create backup duplicate")
            return None

        backup_id = duplicate["id"]
        logger.info("  ✅ Backup created: ID %d (slug: %s-old, status: draft)", backup_id, slug)

        # Move original to draft
        update_data = {
            "title": f"{original['title']['rendered']} -old",
            "slug": f"{slug}-old",
            "status": "draft",
        }
        result = self.wp.put(f"{post_type}s/{original_id}", json_data=update_data)
        if isinstance(result, dict) and result.get("id"):
            logger.info("  ✅ Original moved to draft with -old suffix")
        else:
            logger.warning("  Failed to move original to draft")

        return original_id

    def _get_original_metadata(self, post_type: str, item_id: int) -> dict[str, Any]:
        """Extract original metadata to preserve."""
        original = self.wp.get_item(post_type, item_id)
        if not isinstance(original, dict):
            return {}

        return {
            "date": original.get("date"),
            "date_gmt": original.get("date_gmt"),
            "modified": original.get("modified"),
            "modified_gmt": original.get("modified_gmt"),
            "author": original.get("author"),
            "categories": original.get("categories", []),
            "tags": original.get("tags", []),
            "featured_media": original.get("featured_media", 0),
        }

    def migrate_post_type(
        self, post_type: str = "page", limit: int | None = None, dry_run: bool = False
    ) -> list[dict[str, Any]]:
        """Migrate all items of a post type."""
        logger.info("Starting %s migration (limit=%s, dry_run=%s)", post_type, limit, dry_run)

        # Fetch design system first
        logger.info("Fetching design system...")
        design_system = fetch_design_system(self.config, self.wp)
        logger.info(
            "Design system loaded: %d colors, %d preset groups",
            len(design_system.colors.colors),
            len(design_system.presets.__dict__),
        )

        # Ensure migration category exists
        self._ensure_migration_category(post_type)

        # Discover items
        logger.info("Discovering %ss to migrate...", post_type)
        items = discover_migratable_items(
            self.wp, post_type, limit=limit
        )
        logger.info("Found %d %ss with builder content", len(items), post_type)

        # Load checkpoint
        checkpoint_data = self.checkpoint.load(post_type)
        processed_ids = {r["id"] for r in checkpoint_data.get("processed", [])}
        skipped = 0

        results: list[dict[str, Any]] = []

        for i, item in enumerate(items):
            if limit and len(results) >= limit:
                break

            item_id = item["id"]
            if item_id in processed_ids:
                logger.info("  ⏭️  Skipping #%d: %s (already processed)", item_id, item["title"])
                skipped += 1
                continue

            logger.info("\n%s", "=" * 60)
            logger.info(
                "[%d/%d] Migrating %s #%d: %s",
                i + 1,
                len(items),
                post_type,
                item_id,
                item["title"][:60],
            )
            logger.info("    Format: %s | Content: %d chars", item["format"], item["content_length"])

            try:
                result = self._migrate_item(
                    post_type=post_type,
                    item=item,
                    design_system=design_system,
                    dry_run=dry_run,
                )
                results.append(result)

                # Checkpoint after each successful migration
                if not dry_run and result.get("draft_id"):
                    self.checkpoint.mark_processed(
                        post_type=post_type,
                        item_id=item["id"],
                        title=item["title"],
                        content_len=item["content_length"],
                        meta=result.get("meta", {}),
                    )

            except Exception as e:
                logger.exception("  ❌ FAILED: %s", e)
                self.checkpoint.mark_failed(
                    post_type=post_type,
                    item_id=item["id"],
                    title=item["title"],
                    error=str(e),
                )
                results.append(
                    {
                        "id": item["id"],
                        "title": item["title"],
                        "status": "failed",
                        "error": str(e),
                    }
                )

            # Rate limiting
            time.sleep(self.config.migration.rate_limit)

        # Summary
        completed = len([r for r in results if r.get("status") == "completed"])
        warnings = len([r for r in results if r.get("status") == "completed_with_warnings"])
        failed = len([r for r in results if r.get("status") == "failed"])

        logger.info("\n%s", "=" * 60)
        logger.info(
            "Migration Summary: %d completed, %d warnings, %d failed, %d skipped",
            completed,
            warnings,
            failed,
            skipped,
        )

        return results

    def _migrate_item(
        self, post_type: str, item: dict[str, Any], design_system: DesignSystem, dry_run: bool
    ) -> dict[str, Any]:
        """Migrate a single item with metadata preservation and conflict handling."""
        item_id = item["id"]
        title = item["title"]
        content = item["content"]
        slug = item.get("slug", title.lower().replace(" ", "-"))
        fmt = item["format"]

        # Get original metadata to preserve
        original_meta = self._get_original_metadata(post_type, item_id)

        # Get converter
        converter = registry.get_converter(fmt)
        if not converter:
            raise ValueError(f"No converter for format: {fmt}")

        # Convert content
        divi_content = converter.convert(content, item_id, design_system)

        # Validate
        validation = self.diviops.validate_blocks(divi_content)
        if not validation.get("ok", True):
            raise ValueError(f"Validation failed: {validation}")

        if dry_run:
            return {
                "id": item["id"],
                "title": title,
                "status": "dry_run",
                "draft_id": None,
                "verification": None,
                "meta": None,
            }

        # Handle existing content conflict
        original_id = self._prepare_existing_content(post_type, title, slug)

        # Create draft with original title/slug (after backup)
        draft_title = title
        draft = self.diviops.create_page(
            draft_title, "<!-- Divi 5 Migration Placeholder -->", status="draft"
        )
        draft_id = draft.get("page_id") or draft.get("id")
        if not draft_id:
            raise RuntimeError("Failed to create draft")

        logger.info("  ✅ Draft created: #%d", draft_id)

        # Push content
        push_result = self.diviops.update_page_content(draft_id, divi_content)
        if not push_result.get("ok"):
            raise RuntimeError(f"Push failed: {push_result}")

        logger.info("  ✅ Content pushed")

        # Flush cache
        self.diviops.flush_cache(draft_id)

        # Verify
        self.diviops.get_page_layout(draft_id)
        verification_result = verify_page(self.diviops, self.config, draft_id)
        passed = verification_result.verification_passed
        details = verification_result.verification_details

        # Add migration category
        cat_id = self._ensure_migration_category(post_type)
        if cat_id:
            self.wp.put(f"{post_type}s/{draft_id}", json_data={"categories": [cat_id]})

        # Build migration meta with preserved original data
        meta = MigrationMeta(
            source_format=item["format"],
            source_id=item["id"],
            source_title=title,
            source_content_hash=content_hash(item["content"]),
            divi_blocks_count=details.get("modules", 0),
            sections_count=details.get("sections", 0),
            rows_count=details.get("rows", 0),
            modules_count=details.get("modules", 0),
            images_count=details.get("images", 0),
            buttons_count=details.get("buttons", 0),
            background_colors=details.get("background_colors", []),
            verification_passed=passed,
            verification_details=details,
        )

        return {
            "id": item["id"],
            "title": title,
            "status": "completed" if passed else "completed_with_warnings",
            "draft_id": draft_id,
            "verification": {"passed": passed, "details": details},
            "meta": asdict(meta),
            "preserved_metadata": original_meta,
        }

    def finalize_migration(self, post_type: str, draft_id: int, original_meta: dict[str, Any]) -> bool:
        """
        Finalize migration: publish with original date/author.
        Called after user confirms verification.
        """
        update_data = {
            "status": "publish",
        }

        # Preserve original date
        if original_meta.get("date"):
            update_data["date"] = original_meta["date"]
        if original_meta.get("date_gmt"):
            update_data["date_gmt"] = original_meta["date_gmt"]

        # Preserve original author
        if original_meta.get("author"):
            update_data["author"] = original_meta["author"]

        # Preserve categories (excluding migration tracking category)
        if original_meta.get("categories"):
            cat_id = self._ensure_migration_category(post_type)
            filtered_cats = [c for c in original_meta["categories"] if c != cat_id]
            if filtered_cats:
                update_data["categories"] = [str(c) for c in filtered_cats]  # type: ignore[assignment]

        # Preserve tags
        if original_meta.get("tags"):
            update_data["tags"] = original_meta["tags"]

        # Preserve featured image
        if original_meta.get("featured_media"):
            update_data["featured_media"] = original_meta["featured_media"]

        result = self.wp.put(f"{post_type}s/{draft_id}", json_data=update_data)
        if isinstance(result, dict) and result.get("id"):
            logger.info("  ✅ Published with original metadata (ID: %d)", draft_id)
            return True

        logger.error("  ❌ Failed to publish: %s", result)
        return False

    def safe_delete_migrated(self, post_type: str, draft_id: int) -> bool:
        """
        Safely delete migrated content - moves to Trash only.
        Never permanently deletes.
        """
        result = self.wp.delete(f"{post_type}s/{draft_id}", force=False)
        if isinstance(result, dict):
            logger.info("  🗑️ Moved to trash: %s #%d", post_type, draft_id)
            return True
        logger.warning("  Failed to move to trash: %s #%d", post_type, draft_id)
        return False

    def cleanup_duplicates(self, post_type: str = "page", dry_run: bool = False) -> int:
        """
        Clean up duplicate migration drafts.
        Returns count of deleted drafts.
        """
        logger.info("Cleaning up duplicate %s drafts...", post_type)
        items = discover_migratable_items(self.wp, post_type)
        deleted = 0

        for item in items:
            # Find all drafts with migration suffix
            existing = self.wp.get(f"{post_type}s?slug={item.get('slug', '')}-old&status=any")
            if isinstance(existing, list) and existing:
                for draft in existing:
                    if "(Divi 5 Migration)" in draft.get("title", {}).get("rendered", ""):
                        if not dry_run:
                            self.safe_delete_migrated(post_type, draft["id"])
                        deleted += 1

        return deleted


class VerificationEngine:
    """Verifies migrated page structure."""

    def __init__(self, diviops: DiviOpsClient, config: Config):
        self.diviops = diviops
        self.config = config

    def verify(self, page_id: int, expected: dict[str, int]) -> tuple[bool, dict[str, Any]]:
        """Verify a migrated page."""
        verification_result = verify_page(self.diviops, self.config, page_id, expected)
        return verification_result.verification_passed, verification_result.verification_details


MIGRATION_CATEGORY_SLUG = "divi-migrator"
MIGRATION_CATEGORY_NAME = "Divi Migrator"