"""Immutable audit system for migration tracking."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from hashlib import sha256

from divi_migrator.config import Config

if TYPE_CHECKING:
    from divi_migrator.core.client import WPClient

logger = logging.getLogger(__name__)


@dataclass
class OriginalContent:
    """Immutable record of original content."""

    id: int
    post_type: str
    title: str
    slug: str
    author: int
    status: str
    date: str
    date_gmt: str
    content_hash: str
    recorded_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class MigrationRecord:
    """Migration tracking record."""

    original_id: int
    migrated_id: int | None = None
    status: str = "pending"
    title: str = ""
    slug: str = ""
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str | None = None
    error: str | None = None
    retries: int = 0
    content_hash: str = field(default="")
    renamed_original: bool = False
    original_old_title: str = ""
    original_old_slug: str = ""

    def __post_init__(self) -> None:
        """Ensure content_hash is 16 chars (SHA256 truncated)."""
        if self.content_hash and len(self.content_hash) != 16:  # noqa: PLR2004
            self.content_hash = self.content_hash[:16]


@dataclass
class AuditData:
    """Complete audit data structure."""

    version: int = 1
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    original_pages: dict[int, OriginalContent] = field(default_factory=dict)
    original_posts: dict[int, OriginalContent] = field(default_factory=dict)
    migration_map: dict[str, MigrationRecord] = field(default_factory=dict)

    total_pages: int = 0
    total_posts: int = 0
    migrated_pages: int = 0
    migrated_posts: int = 0
    failed_pages: int = 0
    failed_posts: int = 0


class AuditManager:
    """Manages the immutable audit - survives DB restores via wp_options + local JSON."""

    AUDIT_POST_TYPE = "page"
    AUDIT_POST_SLUG = "divi-migrator-audit"
    AUDIT_POST_TITLE = "Divi Migrator Audit Data"

    def __init__(self, wp_client: WPClient, config: Config):
        self.wp = wp_client
        self.config = config
        self.backup_dir = (
            Path(config.audit.backup_dir) if hasattr(config, "audit") else Path("./audit_backups")
        )  # noqa: E501
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self._audit: AuditData | None = None
        self._loaded = False

    def _get_audit_post_id(self) -> int | None:
        """Find the audit post by slug or title."""
        try:
            # First try to get by slug
            pages = self.wp.get_items(
                "page", status="any", per_page=10, search=self.AUDIT_POST_SLUG
            )  # noqa: E501
            for page in pages:
                if page.get("slug") == self.AUDIT_POST_SLUG:
                    return int(page["id"])
        except Exception as e:
            logger.warning(f"Failed to find audit post by search: {e}")

        # Fallback: search by title among private pages by author 292
        try:
            pages = self.wp.get_items("page", status="private", per_page=100)
            for page in pages:
                if (
                    page.get("author") == 292  # noqa: PLR2004
                    and page.get("title", {}).get("rendered") == self.AUDIT_POST_TITLE
                ):
                    return int(page["id"])
        except Exception as e:
            logger.warning(f"Failed to find audit post by title: {e}")

        return None

    def _create_audit_post(self) -> int:
        """Create the audit storage post."""
        try:
            # Create a draft page to store audit data
            result = self.wp.post(
                "pages",
                json_data={
                    "title": self.AUDIT_POST_TITLE,
                    "slug": self.AUDIT_POST_SLUG,
                    "status": "private",
                    "content": "{}",
                },
            )
            if isinstance(result, dict) and result.get("id"):
                logger.info(f"Created audit storage post: {result['id']}")
                return int(result["id"])
        except Exception as e:
            logger.error(f"Failed to create audit post: {e}")  # noqa: TRY400
        return 0

    def _ensure_audit_post(self) -> int:
        """Ensure audit post exists, return its ID. Clean up duplicates first."""
        post_id = self._get_audit_post_id()
        if post_id:
            # Clean up any duplicate audit posts
            self._cleanup_duplicate_audit_posts()
            return post_id
        return self._create_audit_post()

    def _cleanup_duplicate_audit_posts(self) -> None:
        """Remove duplicate audit posts, keeping only the first one."""
        try:
            # Find all audit posts by title and author
            # Use pagination to get all private pages by author 292
            audit_posts = []
            page_num = 1
            per_page = 100
            while True:
                pages = self.wp.get_items(
                    "page", status="private", per_page=per_page, page=page_num
                )  # noqa: E501
                if not pages:
                    break
                for p in pages:
                    if (
                        p.get("author") == 292  # noqa: PLR2004
                        and p.get("title", {}).get("rendered") == self.AUDIT_POST_TITLE
                    ):
                        audit_posts.append(p)
                if len(pages) < per_page:
                    break
                page_num += 1

            if len(audit_posts) > 1:
                # Keep the first one (oldest), trash the rest
                for post in audit_posts[1:]:
                    post_id = post["id"]
                    logger.warning(f"Removing duplicate audit post: {post_id}")
                    self.wp.delete(f"pages/{post_id}", force=False)
        except Exception as e:
            logger.warning(f"Failed to cleanup duplicate audit posts: {e}")

    def _load_from_wp(self) -> AuditData | None:
        """Load audit from WP post content."""
        post_id = self._get_audit_post_id()
        if not post_id:
            return None
        try:
            post = self.wp.get_item("page", post_id)
            if post and post.get("content", {}).get("raw"):
                content = post["content"]["raw"]
                data = json.loads(content)
                return self._deserialize(data)
        except Exception as e:
            logger.warning(f"Failed to load audit from WP post: {e}")
        return None

    def _save_to_wp(self, data: dict[str, Any]) -> bool:
        """Save audit to WP post content."""
        post_id = self._ensure_audit_post()
        if not post_id:
            return False
        try:
            content = json.dumps(data, indent=2)
            self.wp.put(f"pages/{post_id}", json_data={"content": content})
            return True  # noqa: TRY300
        except Exception as e:
            logger.error(f"Failed to save audit to WP post: {e}")  # noqa: TRY400
            return False

    def load(self) -> AuditData:
        """Load audit from WP post (primary) or local backup (fallback)."""
        if self._loaded and self._audit:
            return self._audit

        # Try WP post first (survives DB restores if post exists)
        audit = self._load_from_wp()
        if audit:
            self._audit = audit
            self._loaded = True
            return self._audit

        # Fallback to local backup
        self._audit = self._load_local_backup()
        self._loaded = True
        return self._audit

    def _load_local_backup(self) -> AuditData:
        """Load from most recent local backup."""
        backups = sorted(self.backup_dir.glob("audit_*.json"))
        if backups:
            try:
                with backups[-1].open() as f:
                    data = json.load(f)
                    return self._deserialize(data)
            except Exception as e:
                logger.warning(f"Failed to load local audit backup: {e}")
        return AuditData()

    def _deserialize(self, data: dict[str, Any]) -> AuditData:
        """Deserialize audit data."""
        audit = AuditData(
            version=data.get("version", 1),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            updated_at=data.get("updated_at", datetime.now(timezone.utc).isoformat()),
            total_pages=data.get("total_pages", 0),
            total_posts=data.get("total_posts", 0),
            migrated_pages=data.get("migrated_pages", 0),
            migrated_posts=data.get("migrated_posts", 0),
            failed_pages=data.get("failed_pages", 0),
            failed_posts=data.get("failed_posts", 0),
        )

        for k, v in data.get("original_pages", {}).items():
            audit.original_pages[int(k)] = OriginalContent(**v)

        for k, v in data.get("original_posts", {}).items():
            audit.original_posts[int(k)] = OriginalContent(**v)

        for k, v in data.get("migration_map", {}).items():
            audit.migration_map[k] = MigrationRecord(**v)

        return audit

    def save(self) -> bool:
        """Save to WP post AND local backup (dual persistence)."""
        if not self._audit:
            return False

        self._audit.updated_at = datetime.now(timezone.utc).isoformat()
        data = self._serialize()

        success = True

        # Save to WP post (survives DB restores if post exists)
        try:
            self._save_to_wp(data)
        except Exception as e:
            logger.error(f"Failed to save audit to WP post: {e}")  # noqa: TRY400
            success = False

        # Save local backup
        try:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            backup_path = self.backup_dir / f"audit_{timestamp}.json"
            with backup_path.open("w") as f:
                json.dump(data, f, indent=2)
            self._prune_backups()
        except Exception as e:
            logger.error(f"Failed to save local audit backup: {e}")  # noqa: TRY400
            success = False

        return success

    def _serialize(self) -> dict[str, Any]:
        """Serialize audit to JSON-serializable dict."""
        audit = self._audit
        if audit is None:
            return {}
        return {
            "version": audit.version,
            "created_at": audit.created_at,
            "updated_at": audit.updated_at,
            "total_pages": audit.total_pages,
            "total_posts": audit.total_posts,
            "migrated_pages": audit.migrated_pages,
            "migrated_posts": audit.migrated_posts,
            "failed_pages": audit.failed_pages,
            "failed_posts": audit.failed_posts,
            "original_pages": {str(k): asdict(v) for k, v in audit.original_pages.items()},
            "original_posts": {str(k): asdict(v) for k, v in audit.original_posts.items()},
            "migration_map": {k: asdict(v) for k, v in audit.migration_map.items()},
        }

    def _prune_backups(self, keep: int = 10) -> None:
        """Keep only N most recent backups."""
        backups = sorted(self.backup_dir.glob("audit_*.json"))
        for old in backups[:-keep]:
            old.unlink(missing_ok=True)

    # --- Audit Operations ---

    def record_originals(self, pages: list[dict[str, Any]], posts: list[dict[str, Any]]) -> None:
        """Record all original content ONCE at migration start."""
        audit = self.load()

        for p in pages:
            if p.get("author") in (1, 2):
                content = p.get("content", {}).get("raw", "")
                audit.original_pages[p["id"]] = OriginalContent(
                    id=p["id"],
                    post_type="page",
                    title=p["title"]["rendered"],
                    slug=p["slug"],
                    author=p["author"],
                    status=p["status"],
                    date=p["date"],
                    date_gmt=p["date_gmt"],
                    content_hash=sha256(content.encode()).hexdigest()[:16],
                )

        for p in posts:
            if p.get("author") in (1, 2):
                content = p.get("content", {}).get("raw", "")
                audit.original_posts[p["id"]] = OriginalContent(
                    id=p["id"],
                    post_type="post",
                    title=p["title"]["rendered"],
                    slug=p["slug"],
                    author=p["author"],
                    status=p["status"],
                    date=p["date"],
                    date_gmt=p["date_gmt"],
                    content_hash=sha256(content.encode()).hexdigest()[:16],
                )

        audit.total_pages = len(audit.original_pages)
        audit.total_posts = len(audit.original_posts)
        audit.created_at = datetime.now(timezone.utc).isoformat()
        self.save()

    def is_original(self, post_type: str, item_id: int) -> bool:
        """Check if item is an original (never migrate/block)."""
        audit = self.load()
        if post_type == "page":
            return item_id in audit.original_pages
        return item_id in audit.original_posts

    def get_original(self, post_type: str, item_id: int) -> OriginalContent | None:
        """Get original content record."""
        audit = self.load()
        if post_type == "page":
            return audit.original_pages.get(item_id)
        return audit.original_posts.get(item_id)

    def start_migration(
        self, post_type: str, original_id: int, title: str, slug: str, content_hash: str
    ) -> MigrationRecord:  # noqa: E501
        """Start tracking a migration."""
        audit = self.load()
        key = f"{post_type}:{original_id}"

        record = MigrationRecord(
            original_id=original_id,
            title=title,
            slug=slug,
            status="in_progress",
            content_hash=content_hash,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        audit.migration_map[key] = record
        self.save()
        return record

    def complete_migration(self, post_type: str, original_id: int, migrated_id: int) -> None:
        """Mark migration as completed."""
        audit = self.load()
        key = f"{post_type}:{original_id}"
        if key in audit.migration_map:
            record = audit.migration_map[key]
            record.migrated_id = migrated_id
            record.status = "completed"
            record.completed_at = datetime.now(timezone.utc).isoformat()

            if post_type == "page":
                audit.migrated_pages += 1
            else:
                audit.migrated_posts += 1
            self.save()

    def mark_renamed(self, post_type: str, original_id: int, old_title: str, old_slug: str) -> None:
        """Record that the original was renamed to '{slug}-old' after migration.

        The audit always retains the immutable original title/slug, so rollback
        restores them regardless.
        """
        audit = self.load()
        key = f"{post_type}:{original_id}"
        if key in audit.migration_map:
            record = audit.migration_map[key]
            record.renamed_original = True
            record.original_old_title = old_title
            record.original_old_slug = old_slug
            self.save()

    def fail_migration(self, post_type: str, original_id: int, error: str) -> None:
        """Mark migration as failed."""
        audit = self.load()
        key = f"{post_type}:{original_id}"
        if key in audit.migration_map:
            record = audit.migration_map[key]
            record.status = "failed"
            record.error = error
            record.retries += 1

            if post_type == "page":
                audit.failed_pages += 1
            else:
                audit.failed_posts += 1
            self.save()

    def get_migration_status(self, post_type: str, original_id: int) -> MigrationRecord | None:
        """Get migration status for an original."""
        audit = self.load()
        return audit.migration_map.get(f"{post_type}:{original_id}")

    def is_migrated(self, post_type: str, original_id: int) -> bool:
        """Check if already successfully migrated."""
        record = self.get_migration_status(post_type, original_id)
        return record is not None and record.status == "completed"

    def get_migrated_id(self, post_type: str, original_id: int) -> int | None:
        """Get the migrated ID if completed."""
        record = self.get_migration_status(post_type, original_id)
        return record.migrated_id if record and record.status == "completed" else None

    def rollback_migration(self, post_type: str, original_id: int) -> bool:
        """Rollback a completed migration - delete migrated, restore original."""
        audit = self.load()
        key = f"{post_type}:{original_id}"
        record = audit.migration_map.get(key)

        if not record or record.status != "completed" or not record.migrated_id:
            return False

        try:
            # Delete migrated content
            self.wp.delete(f"{post_type}s/{record.migrated_id}", force=False)

            # Restore original (remove -old suffix)
            original = self.get_original(post_type, original_id)
            if original:
                restore_data = {
                    "title": original.title,
                    "slug": original.slug,
                    "status": original.status,
                }
                self.wp.put(f"{post_type}s/{original_id}", json_data=restore_data)

            # Mark as rolled back
            record.status = "rolled_back"
            record.migrated_id = None
            record.completed_at = None

            if post_type == "page":
                audit.migrated_pages -= 1
            else:
                audit.migrated_posts -= 1

            self.save()
            return True  # noqa: TRY300
        except Exception as e:
            logger.error(f"Rollback failed for {post_type}:{original_id}: {e}")  # noqa: TRY400
            return False

    def bulk_rollback(self, post_type: str, wp_client: Any) -> dict[str, Any]:
        """Rollback ALL migrations for a post type - for cleanup."""
        audit = self.load()
        results: dict[str, Any] = {"deleted": 0, "restored": 0, "errors": []}

        for key, record in list(audit.migration_map.items()):
            if not key.startswith(f"{post_type}:"):
                continue
            if record.status == "completed" and record.migrated_id:
                try:
                    wp_client.delete(f"{post_type}s/{record.migrated_id}", force=False)
                    results["deleted"] += 1

                    original = self.get_original(post_type, record.original_id)
                    if original:
                        wp_client.put(
                            f"{post_type}s/{record.original_id}",
                            json_data={
                                "title": original.title,
                                "slug": original.slug,
                                "status": original.status,
                            },
                        )
                        results["restored"] += 1

                    record.status = "rolled_back"
                    record.migrated_id = None
                except Exception as e:
                    results["errors"].append(f"{key}: {e}")

        if post_type == "page":
            audit.migrated_pages = 0
        else:
            audit.migrated_posts = 0

        self.save()
        return results

    def get_stats(self) -> dict[str, Any]:
        """Get migration statistics."""
        audit = self.load()
        return {
            "total_pages": audit.total_pages,
            "total_posts": audit.total_posts,
            "migrated_pages": audit.migrated_pages,
            "migrated_posts": audit.migrated_posts,
            "failed_pages": audit.failed_pages,
            "failed_posts": audit.failed_posts,
            "pending_pages": sum(
                1
                for k, r in audit.migration_map.items()
                if k.startswith("page:") and r.status == "in_progress"
            ),
            "pending_posts": sum(
                1
                for k, r in audit.migration_map.items()
                if k.startswith("post:") and r.status == "in_progress"
            ),
        }
