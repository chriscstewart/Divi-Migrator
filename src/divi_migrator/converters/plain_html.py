"""Plain HTML to Divi 5 converter."""

from __future__ import annotations

import re
from typing import Any

from divi_migrator.converters.base import BaseConverter, ExtractedAssets


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

    def convert(self, content: str, _source_id: int, _design_system: Any = None) -> str:
        """Convert plain HTML to Divi 5 structure."""
        # Clean HTML
        content = self._clean_html(content)

        # Wrap in Divi structure
        return (
            f'[et_pb_section background_color="#f7f4ef"]'
            f'[et_pb_row][et_pb_column type="4_4"]'
            f'[et_pb_text _builder_version="5.0"]{content}[/et_pb_text]'
            f"[/et_pb_column][/et_pb_row][/et_pb_section]"
        )

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
        content = re.sub(
            r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL | re.IGNORECASE
        )
        return re.sub(
            r"<style[^>]*>.*?</style>", "", content, flags=re.DOTALL | re.IGNORECASE
        )

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