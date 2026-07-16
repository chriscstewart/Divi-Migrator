"""Discovery module for finding migratable content."""

from __future__ import annotations

from typing import Any

from divi_migrator.models import SourceFormat


def detect_format(content: str) -> SourceFormat:
    """Detect source format from content."""
    content_lower = content.lower()

    # Check for Avada/Fusion Builder
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
            "[fusion_separator",
        ]
    ):
        return SourceFormat.AVADA

    # Check for Elementor
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

    # Check for other builders
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

    # Plain HTML (has HTML tags but no builder markers)
    if content.strip() and "<" in content and ">" in content:
        return SourceFormat.PLAIN_HTML

    return SourceFormat.UNKNOWN


def discover_migratable_items(
    wp_client: Any,
    post_type: str = "page",
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Discover all items with migratable content."""
    items: list[dict[str, Any]] = []
    page = 1
    per_page = 50

    while True:
        batch = wp_client.get_items(
            post_type,
            page=page,
            per_page=per_page,
            status="publish",
        )

        if not batch:
            break

        for item in batch:
            content = item.get("content", {}).get("rendered", "")
            title = item.get("title", {}).get("rendered", "")

            if not content or not content.strip():
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
                }
            )

            if limit and len(items) >= limit:
                return items

        if len(batch) < per_page:
            break
        page += 1

    return items