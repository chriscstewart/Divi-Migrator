"""Elementor to Divi 5 converter (NOT YET IMPLEMENTED).

Registered so the framework can recognise Elementor content and refuse it
loudly rather than silently producing broken output. ``detect()`` returns
False so the auto-detection path never selects this converter for a real
migration; ``convert()`` emits a clearly-marked Divi 5 placeholder instead of
fabricating Divi 4 (``et_pb_*``) shortcodes, which would not render in Divi 5.

Real Elementor -> Divi 5 conversion is a future enhancement, not part of the
v0.1.0 Avada-focused release.
"""

from __future__ import annotations

from typing import Any

from divi_migrator.converters.base import BaseConverter, ExtractedAssets


class ElementorConverter(BaseConverter):
    """Convert Elementor content to Divi 5 (not yet implemented)."""

    format_name = "elementor"
    supported = False

    def detect(self, _content: str) -> bool:
        """Elementor detection is intentionally disabled for v0.1.0.

        The converter is not implemented, so we must never auto-select it and
        silently ship unconverted content. Returning False keeps the working
        Avada/Plain-HTML converters as the only auto-detected paths.
        """
        return False

    def convert(
        self,
        _content: str,
        _source_id: int,
        _design_system: Any = None,
        wp_client: Any = None,  # noqa: ARG002
    ) -> str:
        """Return a clearly-marked placeholder; Elementor is unsupported in v0.1.0."""
        section_bg = '{"module":{"background":{"color":{"desktop":{"value":"#f7f4ef"}}}}}'
        return (
            "<!-- divi-migrator: ELEMENTOR SOURCE NOT SUPPORTED IN v0.1.0 "
            "(Avada and Plain HTML are supported). Content left unconverted. -->\n"
            f"<!-- wp:divi/section {section_bg} -->"
            "<!-- wp:divi/row -->"
            "<!-- wp:divi/column -->"
            "<!-- wp:divi/text -->"
            f"<p>{_content}</p>"
            "<!-- /wp:divi/text -->"
            "<!-- /wp:divi/column -->"
            "<!-- /wp:divi/row -->"
            "<!-- /wp:divi/section -->"
        )

    def extract_assets(self, _content: str) -> ExtractedAssets:
        """Extract assets from Elementor content (unsupported)."""
        return ExtractedAssets()
