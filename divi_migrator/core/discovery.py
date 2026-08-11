"""Discovery module with audit-aware filtering."""

from __future__ import annotations

import logging
from typing import Any

from divi_migrator.core.audit import AuditManager
from divi_migrator.models import SourceFormat

logger = logging.getLogger(__name__)


def detect_format(content: str) -> SourceFormat:
    """Detect source format from content."""
    content_lower = content.lower()

    if any(
        marker in content_lower
        for marker in [
            "[fusion_builder_container",
            "[fusion_builder_row",
            "[fusion_builder_column",
            "[fusion_text",
            "[fusion_button",
            "[fusion_imageframe",
            "[fusion_title",
            "[fusion_separator",  # noqa: E501
        ]
    ):
        return SourceFormat.AVADA

    if any(
        marker in content_lower
        for marker in [
            "elementor-widget",
            "elementor-section",
            "elementor-column",
            "elementor-row",
            "data-elementor-type",
            'class="elementor',
        ]
    ):
        return SourceFormat.ELEMENTOR

    if any(
        marker in content_lower
        for marker in [
            "vc_row",
            "vc_column",
            "[vc_",
            "[et_pb_",
            "et_pb_section",
            "wp-block-",
        ]
    ):
        return SourceFormat.UNKNOWN

    if content.strip() and "<" in content and ">" in content:
        return SourceFormat.PLAIN_HTML

    return SourceFormat.UNKNOWN


def discover_migratable_items(  # noqa: C901
    wp_client: Any,
    audit_manager: AuditManager,
    post_type: str = "page",
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Discover items that need migration - ONLY originals recorded at audit-init.

    The audit system protects originals from MODIFICATION, not from MIGRATION.
    Originals are what we WANT to migrate - we create new drafts from them.
    Only items recorded as originals (author 1, 2) at audit-init should be migrated.
    """
    audit_data = audit_manager.load()
    items: list[dict[str, Any]] = []

    # Get the set of original IDs that were recorded at audit-init
    if post_type == "page":
        original_ids = set(audit_data.original_pages.keys())
    else:
        original_ids = set(audit_data.original_posts.keys())

    # Only fetch the original items we recorded
    for original_id in sorted(original_ids):
        if limit and len(items) >= limit:
            break

        try:
            item = wp_client.get_item(post_type, original_id)
            if not isinstance(item, dict) or item.get("ok") is False:
                continue

            # Skip if already successfully migrated
            record = audit_manager.get_migration_status(post_type, original_id)
            if record and record.status == "completed":
                continue

            content = item.get("content", {}).get("rendered", "")
            title = item.get("title", {}).get("rendered", "")

            if not content or not content.strip():
                continue

            # Skip -old backup pages
            if "-old" in title:
                continue

            # Skip audit system pages (private pages by AI-Dev-MCPs author containing audit data)
            if item.get("status") == "private" and item.get("author") == 292:  # noqa: PLR2004
                continue

            # Skip Divi Migrator Audit Data pages specifically
            if "Divi Migrator Audit" in title:
                continue

            fmt = detect_format(content)
            if fmt == SourceFormat.UNKNOWN:
                continue

            items.append(
                {
                    "id": item["id"],
                    "title": title,
                    "format": fmt,
                    "content_length": len(content),
                    "url": item.get("link", ""),
                    "slug": item.get("slug", ""),
                }
            )
        except Exception as e:
            logger.warning(f"Failed to fetch {post_type} {original_id}: {e}")

    return items
