"""Elementor to Divi 5 converter (stub - needs implementation)."""

from __future__ import annotations

from typing import Any

from divi_migrator.converters.base import BaseConverter, ExtractedAssets


class ElementorConverter(BaseConverter):
    """Convert Elementor content to Divi 5 (stub)."""

    format_name = "elementor"

    def detect(self, content: str) -> bool:
        """Check if content contains Elementor markers."""
        elementor_markers = [
            "elementor-widget",
            "elementor-section",
            "elementor-column",
            "elementor-row",
            "data-elementor-type",
            'class="elementor',
        ]
        return any(marker in content for marker in elementor_markers)

    def convert(
        self, content: str, _source_id: int, _design_system: Any = None, wp_client: Any = None  # noqa: ARG002
    ) -> str:
        """Convert Elementor content to Divi 5 (stub - wraps as plain HTML)."""
        # TODO: Implement proper Elementor -> Divi 5 conversion
        # For now, wrap as plain HTML
        return self._wrap_as_plain_html(content)

    def extract_assets(self, _content: str) -> ExtractedAssets:
        """Extract assets from Elementor content."""
        return ExtractedAssets()
        # TODO: Implement Elementor-specific extraction

    def _wrap_as_plain_html(self, content: str) -> str:
        """Wrap content in default Divi 5 structure."""
        return (
            f'[et_pb_section background_color="#f7f4ef"]'
            f'[et_pb_row][et_pb_column type="4_4"]'
            f"<![CDATA[{content}]]>[/et_pb_code]"
            f"[/et_pb_column][/et_pb_row][/et_pb_section]"
        )
