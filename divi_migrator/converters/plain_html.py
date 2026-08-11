"""Plain HTML to Divi 5 block markup converter."""

from __future__ import annotations

import re
from typing import Any

from divi_migrator.converters.base import BaseConverter, ExtractedAssets
from divi_migrator.converters.divi5_blocks import (
    placeholder,
    section,
    section_bg_color,
    row_flex,
    column,
    text,
    RowBackground,
)


class PlainHTMLConverter(BaseConverter):
    """Convert plain HTML content to Divi 5 structure."""

    format_name = "plain_html"

    # HTML patterns
    IMG_PATTERN = re.compile(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>', re.IGNORECASE)
    LINK_PATTERN = re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]+)</a>', re.IGNORECASE)
    BUTTON_PATTERN = re.compile(
        r'<(button|input)[^>]+type=["\']button["\'][^>]*>([^<]+)</button>', re.IGNORECASE
    )
    IFRAME_PATTERN = re.compile(r'<iframe[^>]+src=["\']([^"\']+)["\'][^>]*>', re.IGNORECASE)
    FORM_PATTERN = re.compile(r"<form[^>]*>.*?</form>", re.IGNORECASE | re.DOTALL)

    def detect(self, content: str) -> bool:
        """Check if content is plain HTML (no builder shortcodes)."""
        # If it has builder shortcodes, it's not plain HTML
        builder_markers = [
            "[fusion_",
            "[et_pb_",
            "[vc_",
            "elementor-",
            "data-elementor",
            "wp-block-",
        ]
        if any(marker in content for marker in builder_markers):
            return False

        # If it has HTML tags, it's likely plain HTML
        return bool(re.search(r"<[a-z][^>]*>", content))

    def convert(  # noqa: E501
        self, content: str, _source_id: int, _design_system: Any = None, _wp_client: Any = None
    ) -> str:
        """Convert plain HTML to Divi 5 block markup."""
        # Clean HTML
        content = self._clean_html(content)

        # Plain HTML source has no per-section background, so we emit none
        # here (real Divi 5 omits the `background` key when there is none).
        # The correct background shape POSTs cleanly (HTTP 201, no fatal),
        # but DiviOps's headless renderer does not apply section/row
        # backgrounds set via the API (verified 2026-08-08). Avada sources
        # WITH a background do emit the canonical shape (see avada.py).
        bg_color = None

        # Wrap in Divi 5 structure
        inner = text(content)
        col = column(inner=inner, layout="4_4")
        r = row_flex(col, background=RowBackground(color=bg_color))
        s = section_bg_color(bg_color, r) if bg_color else section(r)
        return placeholder(s)

    def _clean_html(self, content: str) -> str:
        """Clean HTML content for safe embedding."""
        # Remove HTML comments
        content = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)

        # Fix smart quotes in URLs
        content = content.replace("\u201c", '"').replace("\u201d", '"')
        content = content.replace("\u2018", "'").replace("\u2019", "'")

        # Fix dimension multiplication sign
        content = content.replace("\u00d7", "x")

        # Remove script/style tags
        content = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL | re.IGNORECASE)
        return re.sub(r"<style[^>]*>.*?</style>", "", content, flags=re.DOTALL | re.IGNORECASE)

    def extract_assets(self, content: str) -> ExtractedAssets:
        """Extract images, buttons, forms from HTML."""
        assets = ExtractedAssets()

        # Extract images
        for match in self.IMG_PATTERN.finditer(content):
            full_tag = match.group(0)
            src = self._extract_attr(full_tag, "src")
            alt = self._extract_attr(full_tag, "alt", "")
            title = self._extract_attr(full_tag, "title", "")
            assets.images.append(
                {
                    "src": src,
                    "alt": alt,
                    "title": title,
                    "type": "plain_html",
                }
            )

        # Extract links as buttons
        for match in self.LINK_PATTERN.finditer(content):
            full_tag = match.group(0)
            url = match.group(1)
            text = match.group(2).strip()
            if text and url:
                assets.buttons.append(
                    {
                        "text": text,
                        "url": url,
                        "type": "plain_html_link",
                    }
                )

        # Extract buttons
        for match in self.BUTTON_PATTERN.finditer(content):
            full_tag = match.group(0)
            text = match.group(2).strip()
            assets.buttons.append(
                {
                    "text": text,
                    "url": "",
                    "type": "plain_html_button",
                }
            )

        # Extract forms
        for match in self.FORM_PATTERN.finditer(content):
            full_form = match.group(0)
            action = self._extract_attr(full_form, "action")
            method = self._extract_attr(full_form, "method", "POST")
            assets.forms.append(
                {
                    "action": action,
                    "method": method,
                    "html": full_form[:500],  # truncated
                }
            )

        return assets

    def _extract_attr(self, tag: str, attr: str, default: str = "") -> str:
        """Extract attribute value from HTML tag."""
        pattern = rf'{attr}=["\']([^"\']+)["\']'
        match = re.search(pattern, tag, re.IGNORECASE)
        return match.group(1) if match else default
