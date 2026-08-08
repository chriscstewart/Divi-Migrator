"""Avada/Fusion Builder to Divi 5 converter."""

from __future__ import annotations

import re
import html
from typing import Any

from divi_migrator.converters.base import BaseConverter, ExtractedAssets
from divi_migrator.converters.divi5_blocks import _clean_html


class AvadaConverter(BaseConverter):
    """Convert Avada/Fusion Builder content to Divi 5."""

    format_name = "avada"

    # Fusion Builder shortcode patterns
    CONTAINER_PATTERN = re.compile(
        r"\[fusion_builder_container[^\]]*\](.*?)\[/fusion_builder_container\]", re.DOTALL
    )
    ROW_PATTERN = re.compile(r"\[fusion_builder_row[^\]]*\](.*?)\[/fusion_builder_row\]", re.DOTALL)  # noqa: E501
    COLUMN_PATTERN = re.compile(
        r"\[fusion_builder_column[^\]]*\](.*?)\[/fusion_builder_column\]", re.DOTALL
    )
    TEXT_PATTERN = re.compile(r"\[fusion_text[^\]]*\](.*?)\[/fusion_text\]", re.DOTALL)
    TITLE_PATTERN = re.compile(r"\[fusion_title[^\]]*\](.*?)\[/fusion_title\]", re.DOTALL)
    BUTTON_PATTERN = re.compile(
        r"\[fusion_button\b[^\]]*\](.*?)(?:\[/fusion_button\])?", re.DOTALL
    )
    IMAGE_PATTERN = re.compile(
        r"\[fusion_imageframe\b[^\]]*\](?:.*?\[/fusion_imageframe\])?", re.DOTALL
    )
    SEPARATOR_PATTERN = re.compile(r"\[fusion_separator[^\]]*\]", re.DOTALL)
    ICON_PATTERN = re.compile(r"\[fusion_fontawesome[^\]]*\]", re.DOTALL)
    MAP_PATTERN = re.compile(r"\[fusion_map[^\]]*\]", re.DOTALL)
    VIDEO_PATTERN = re.compile(r"\[fusion_video\b[^\]]*\](?:.*?\[/fusion_video\])?", re.DOTALL)
    GALLERY_PATTERN = re.compile(r"\[fusion_gallery[^\]]*\]", re.DOTALL)
    TABS_PATTERN = re.compile(r"\[fusion_tabs[^\]]*\](.*?)\[/fusion_tabs\]", re.DOTALL)
    TAB_PATTERN = re.compile(r"\[fusion_tab[^\]]*\](.*?)\[/fusion_tab\]", re.DOTALL)
    TOGGLES_PATTERN = re.compile(r"\[fusion_toggles[^\]]*\](.*?)\[/fusion_toggles\]", re.DOTALL)
    TOGGLE_PATTERN = re.compile(r"\[fusion_toggle[^\]]*\](.*?)\[/fusion_toggle\]", re.DOTALL)
    ACCORDION_PATTERN = re.compile(
        r"\[fusion_accordion[^\]]*\](.*?)\[/fusion_accordion\]", re.DOTALL
    )
    ACCORDION_ITEM_PATTERN = re.compile(
        r"\[fusion_accordion_item[^\]]*\](.*?)\[/fusion_accordion_item\]", re.DOTALL
    )
    PERSON_PATTERN = re.compile(r"\[fusion_person[^\]]*\]", re.DOTALL)
    TESTIMONIAL_PATTERN = re.compile(r"\[fusion_testimonial[^\]]*\]", re.DOTALL)
    PRICING_TABLE_PATTERN = re.compile(
        r"\[fusion_pricing_table[^\]]*\](.*?)\[/fusion_pricing_table\]", re.DOTALL
    )
    PRICING_ITEM_PATTERN = re.compile(
        r"\[fusion_pricing_item[^\]]*\](.*?)\[/fusion_pricing_item\]", re.DOTALL
    )
    CODE_PATTERN = re.compile(r"\[fusion_code[^\]]*\](.*?)\[/fusion_code\]", re.DOTALL)
    RAW_PATTERN = re.compile(r"\[fusion_raw[^\]]*\](.*?)\[/fusion_raw\]", re.DOTALL)

    YOUTUBE_PATTERN = re.compile(r"\[fusion_youtube\b[^\]]*\](?:.*?\[/fusion_youtube\])?", re.DOTALL)  # noqa: E501
    VIMEO_PATTERN = re.compile(r"\[fusion_vimeo[^\]]*]", re.DOTALL)
    TESTIMONIALS_PATTERN = re.compile(r"\[fusion_testimonials[^\]]*](.*?)[/fusion_testimonials]", re.DOTALL)  # noqa: E501
    CONTENT_BOX_PATTERN = re.compile(r"\[fusion_content_box[^\]]*]", re.DOTALL)
    CONTENT_BOXES_PATTERN = re.compile(r"\[fusion_content_boxes[^\]]*](.*?)[/fusion_content_boxes]", re.DOTALL)  # noqa: E501
    FAQ_PATTERN = re.compile(r"\[fusion_faq[^\]]*](.*?)[/fusion_faq]", re.DOTALL)
    FAQ_ITEM_PATTERN = re.compile(r"\[fusion_faq_item[^\]]*](.*?)[/fusion_faq_item]", re.DOTALL)
    COUNTDOWN_PATTERN = re.compile(r"\[fusion_countdown[^\]]*]", re.DOTALL)
    CHECKLIST_PATTERN = re.compile(r"\[fusion_checklist[^\]]*]", re.DOTALL)
    CHECKLIST_FULL_PATTERN = re.compile(r"\[fusion_checklist\b.*?\[/fusion_checklist\]", re.DOTALL)
    CHECKLIST_ITEM_PATTERN = re.compile(r"\[fusion_li_item\b.*?\[/fusion_li_item\]", re.DOTALL)
    BLOG_PATTERN = re.compile(r"\[fusion_blog[^\]]*]", re.DOTALL)
    CONTENT_BOX_ITEM_PATTERN = re.compile(r"\[fusion_content_box[^\]]*]", re.DOTALL)
    LINK_PATTERN = re.compile(r"\[fusion_link[^\]]*]", re.DOTALL)
    IMAGES_PATTERN = re.compile(r"\[fusion_images[^\]]*]", re.DOTALL)
    SOCIAL_LINKS_PATTERN = re.compile(r"\[fusion_social_links[^\]]*]", re.DOTALL)

    # Column fraction to Divi layout mapping
    COLUMN_MAP = {
        "1_1": "4_4",
        "1_2": "2_4",
        "1_3": "3_12",
        "2_3": "6_12",
        "1_4": "2_12",
        "3_4": "9_12",
        "1_5": "1_5",
        "2_5": "2_5",
        "3_5": "3_5",
        "4_5": "4_5",
        "1_6": "1_6",
    }

    def detect(self, content: str) -> bool:
        """Check if content contains Fusion Builder shortcodes."""
        return bool(
            "[fusion_builder_container" in content
            or "[fusion_builder_row" in content
            or "[fusion_builder_column" in content
            or "[fusion_text" in content
            or "[fusion_button" in content
            or "[fusion_imageframe" in content
            or "[fusion_title" in content
            or "[fusion_separator" in content
        )

    def extract_attr(self, shortcode: str, attr: str) -> str | None:
        """Extract attribute value from shortcode."""
        shortcode = html.unescape(shortcode)
        # Match both regular quotes and smart quotes
        pattern = rf'{attr}\s*=\s*["\'\u201c\u201d]([^"\'\u201c\u201d]*)["\'\u201c\u201d]'
        match = re.search(pattern, shortcode)
        return match.group(1) if match else None

    def extract_all_attrs(self, shortcode: str) -> dict[str, str]:
        """Extract all attributes from shortcode."""
        attrs = {}
        shortcode = html.unescape(shortcode)
        # Match both regular quotes and smart quotes
        pattern = r'(\w+)\s*=\s*["\'\u201c\u201d]([^"\'\u201c\u201d]*)["\'\u201c\u201d]'
        for match in re.finditer(pattern, shortcode):
            attrs[match.group(1)] = match.group(2)
        return attrs

    def clean_attrs(self, attrs: dict[str, str]) -> dict[str, str]:
        """Clean and normalize attributes."""
        cleaned = {}
        for k, v in attrs.items():
            # Fix smart quotes
            val = v.replace("\u201c", '"').replace("\u201d", '"')
            val = val.replace("\u2018", "'").replace("\u2019", "'")
            # Fix dimension multiplication sign
            val = val.replace("\u00d7", "x")
            cleaned[k] = val
        return cleaned

    def extract_column_attrs(self, shortcode: str) -> dict[str, str]:
        """Extract and normalize column attributes."""
        attrs = {}
        for key in [
            "type",
            "layout",
            "spacing",
            "center_content",
            "hide_on_mobile",
            "min_height",
            "padding_top",
            "padding_bottom",
            "padding_left",
            "padding_right",
            "margin_top",
            "margin_bottom",
        ]:
            val = self.extract_attr(shortcode, key)
            if val:
                attrs[key] = val

        # Map column type to Divi layout
        col_type = attrs.get("type", "1_1")
        attrs["divi_layout"] = self.COLUMN_MAP.get(col_type, "4_4")
        return attrs

    def extract_row_attrs(self, shortcode: str) -> dict[str, str]:
        """Extract row attributes."""
        attrs = {}
        for key in [
            "type",
            "background_color",
            "background_image",
            "padding_top",
            "padding_bottom",
            "padding_left",
            "padding_right",
            "margin_top",
            "margin_bottom",
            "background_position",
            "background_repeat",
            "parallax_speed",
            "video_mp4",
            "video_ogv",
            "video_webm",
            "video_preview_image",
        ]:
            val = self.extract_attr(shortcode, key)
            if val:
                attrs[key] = val
        return attrs

    def extract_container_attrs(self, shortcode: str) -> dict[str, str]:
        """Extract container attributes."""
        attrs = {}
        for key in [
            "hundred_percent",
            "equal_height_columns",
            "menu_anchor",
            "hide_on_mobile",
            "background_color",
            "background_image",
            "background_position",
            "background_repeat",
            "parallax_speed",
            "video_mp4",
            "video_ogv",
            "video_webm",
            "video_preview_image",
            "fade",
            "overlay_color",
            "overlay_opacity",
            "border_size",
            "border_color",
            "border_style",
            "border_radius",
        ]:
            val = self.extract_attr(shortcode, key)
            if val:
                attrs[key] = val
        return attrs

    def extract_text_content(self, shortcode: str) -> str:
        """Extract content from fusion_text shortcode."""
        match = self.TEXT_PATTERN.search(shortcode)
        if match:
            return match.group(1).strip()
        return ""

    def extract_title_content(self, shortcode: str) -> dict[str, Any]:
        """Extract title attributes."""
        return {
            "text": self.extract_attr(shortcode, "title") or "",
            "size": self.extract_attr(shortcode, "size") or "",
            "color": self.extract_attr(shortcode, "color") or "",
            "alignment": self.extract_attr(shortcode, "alignment") or "left",
            "font": self.extract_attr(shortcode, "font") or "",
        }

    def extract_button_attrs(self, shortcode: str) -> dict[str, str]:
        """Extract button attributes."""
        attrs = {}
        for key in [
            "text",
            "link",
            "target",
            "color",
            "size",
            "shape",
            "icon",
            "icon_position",
            "class",
            "id",
            "font",
            "font_size",
            "border_radius",
            "border_color",
            "border_size",
            "background_color",
            "hover_color",
            "hover_text_color",
        ]:
            val = self.extract_attr(shortcode, key)
            if val:
                attrs[key] = val
        return attrs

    def extract_image_attrs(self, shortcode: str) -> dict[str, str]:
        """Extract image attributes."""
        attrs = {}
        for key in [
            "src",
            "image_id",  # Fusion uses image_id instead of src sometimes
            "alt",
            "title",
            "link",
            "lightbox",
            "style_type",
            "bordercolor",
            "bordersize",
            "borderradius",
            "align",
            "hover_type",
            "animation_type",
            "animation_direction",
            "animation_speed",
            "max_width",
            "max_height",
        ]:
            val = self.extract_attr(shortcode, key)
            if val:
                attrs[key] = val
        # Map image_id to src for compatibility
        if "image_id" in attrs and "src" not in attrs:
            attrs["src"] = attrs["image_id"]
        return attrs

    def extract_separator_attrs(self, shortcode: str) -> dict[str, str]:
        """Extract separator attributes."""
        attrs = {}
        for key in [
            "style_type",
            "color",
            "border_size",
            "icon",
            "icon_color",
            "icon_size",
            "alignment",
            "hide_on_mobile",
        ]:
            val = self.extract_attr(shortcode, key)
            if val:
                attrs[key] = val
        return attrs

    def convert(self, content: str, _source_id: int, _design_system: Any = None) -> str:
        """Convert Fusion Builder content to Divi 5 block markup."""

        # Import new block generators

        # Process containers (outermost)
        def replace_container(match: re.Match[str]) -> str:
            return self._convert_container_to_blocks(match)

        return self.CONTAINER_PATTERN.sub(replace_container, content)

    def _convert_container_to_blocks(self, match: re.Match[str]) -> str:
        """Convert fusion_builder_container to Divi 5 blocks."""
        from divi_migrator.converters.divi5_blocks import (  # noqa: PLC0415
            section, placeholder
        )

        full = match.group(0)
        inner = match.group(1)

        rows = self.ROW_PATTERN.findall(inner)

        # Section background (canonical Divi 5 shape via build_background,
        # called inside section()). Real Divi 5 omits the `background` key
        # when there is none; when a source Avada container has a color/image
        # we migrate it. NOTE: the correct shape POSTs cleanly (HTTP 201, no
        # fatal), but DiviOps's headless renderer does not apply section/row
        # backgrounds set via the API (verified 2026-08-08: module_update
        # stores the attr but the published page renders no background-color).
        # Markup is emitted correctly / future-proof; see DiviOps limitation.
        container_attrs = self.extract_container_attrs(full)
        bg_color = container_attrs.get("background_color")
        bg_image = container_attrs.get("background_image")

        # Process rows
        row_blocks = []
        for row_match in rows:
            row_block = self._convert_row_to_blocks(row_match)
            if row_block:
                row_blocks.append(row_block)

        if not row_blocks:
            return ""

        section_html = "".join(row_blocks)

        s = section(
            section_html,
            bg_color=bg_color,
            bg_image={"src": bg_image} if bg_image else None,
        )

        return placeholder(s)

    def _convert_row_to_blocks(self, row_match: str) -> str:
        """Convert fusion_builder_row to Divi 5 row block."""
        from divi_migrator.converters.divi5_blocks import row, row_flex  # noqa: PLC0415

        row_attrs = self.extract_row_attrs(row_match)
        columns = self.COLUMN_PATTERN.findall(row_match)

        # Process columns
        col_blocks = []
        for col_match in columns:
            col_block = self._convert_column_to_blocks(col_match)
            if col_block:
                col_blocks.append(col_block)

        if not col_blocks:
            return ""

        columns_html = "".join(col_blocks)

        # Row background migrated from source (canonical shape via build_background
        # inside row_flex). The correct shape POSTs cleanly (HTTP 201, no fatal),
        # but DiviOps's headless renderer does not apply section/row backgrounds
        # set via the API (verified 2026-08-08: module_update stores the attr but
        # the published page renders no background-color). Markup emitted correctly.
        bg_color = row_attrs.get("background_color")
        bg_image = row_attrs.get("background_image")
        if bg_color or bg_image:
            return row_flex(
                columns_html,
                background_color=bg_color,
                background_image=({"src": bg_image} if bg_image else None),
            )
        return row(columns_html, layout="4_4")

    def _convert_column_to_blocks(self, column_match: str) -> str:
        """Convert fusion_builder_column to Divi 5 column block."""
        from divi_migrator.converters.divi5_blocks import column  # noqa: PLC0415

        col_attrs = self.extract_column_attrs(column_match)
        inner_content = column_match

        # Process inner content - convert to Divi 5 blocks
        # IMPORTANT: Process WRAPPER patterns FIRST (they contain individual items)
        inner_content = self.TESTIMONIALS_PATTERN.sub(self._convert_testimonials_to_block, inner_content)  # noqa: E501
        inner_content = self.CONTENT_BOXES_PATTERN.sub(self._convert_content_boxes_to_block, inner_content)  # noqa: E501
        inner_content = self.FAQ_PATTERN.sub(self._convert_faq_to_block, inner_content)
        inner_content = self.TABS_PATTERN.sub(self._convert_tabs_to_block, inner_content)

        # Then process individual items
        inner_content = self.TEXT_PATTERN.sub(self._convert_text_to_block, inner_content)
        inner_content = self.TITLE_PATTERN.sub(self._convert_title_to_block, inner_content)
        inner_content = self.BUTTON_PATTERN.sub(self._convert_button_to_block, inner_content)
        inner_content = self.IMAGE_PATTERN.sub(self._convert_image_to_block, inner_content)
        inner_content = self.SEPARATOR_PATTERN.sub(self._convert_separator_to_block, inner_content)
        inner_content = self.YOUTUBE_PATTERN.sub(self._convert_youtube_to_block, inner_content)
        inner_content = self.VIMEO_PATTERN.sub(self._convert_vimeo_to_block, inner_content)
        inner_content = self.VIDEO_PATTERN.sub(self._convert_video_to_block, inner_content)
        inner_content = self.TESTIMONIAL_PATTERN.sub(self._convert_testimonial_to_block, inner_content)  # noqa: E501
        inner_content = self.PERSON_PATTERN.sub(self._convert_person_to_block, inner_content)
        inner_content = self.MAP_PATTERN.sub(self._convert_map_to_block, inner_content)
        inner_content = self.CONTENT_BOX_PATTERN.sub(self._convert_content_box_to_block, inner_content)  # noqa: E501
        inner_content = self.COUNTDOWN_PATTERN.sub(self._convert_countdown_to_block, inner_content)
        inner_content = self.CHECKLIST_FULL_PATTERN.sub(self._convert_checklist_to_block, inner_content)  # noqa: E501
        inner_content = self.BLOG_PATTERN.sub(self._convert_blog_to_block, inner_content)

        # Clean remaining fusion shortcodes
        patterns = [
            r"\[fusion_builder_container[^\]]*\].*?\[/fusion_builder_container\]",
            r"\[fusion_builder_row[^\]]*\].*?\[/fusion_builder_row\]",
            r"\[fusion_builder_column[^\]]*\].*?\[/fusion_builder_column\]",
            r"\[fusion_text[^\]]*\].*?\[/fusion_text\]",
            r"\[fusion_title[^\]]*\].*?\[/fusion_title\]",
            r"\[fusion_button[^\]]*\]",
            r"\[fusion_imageframe[^\]]*\]",
            r"\[fusion_separator[^\]]*\]",
            r"\[fusion_youtube[^\]]*\]",
            r"\[fusion_vimeo[^\]]*\]",
            r"\[fusion_video[^\]]*\]",
            r"\[fusion_testimonial[^\]]*\].*?\[/fusion_testimonial\]",
            r"\[fusion_testimonials[^\]]*\].*?\[/fusion_testimonials\]",
            r"\[fusion_person[^\]]*\]",
            r"\[fusion_map[^\]]*\]",
            r"\[fusion_content_box[^\]]*\]",
            r"\[fusion_content_boxes[^\]]*\].*?\[/fusion_content_boxes\]",
            r"\[fusion_faq[^\]]*\].*?\[/fusion_faq\]",
            r"\[fusion_faq_item[^\]]*\].*?\[/fusion_faq_item\]",
            r"\[fusion_tabs[^\]]*\].*?\[/fusion_tabs\]",
            r"\[fusion_tab[^\]]*\].*?\[/fusion_tab\]",
            r"\[fusion_countdown[^\]]*\]",
            r"\[fusion_checklist[^\]]*\]",
            r"\[fusion_checklist[^\]]*\]",
            r"\[/fusion_checklist\]",
            r"\[fusion_li_item[^\]]*\]",
            r"\[/fusion_li_item\]",
            r"\[fusion_blog[^\]]*\]",
            r"\[fusion_imageframe[^\]]*\]",
            r"\[fusion_image[^\]]*\]",
            r"\[fusion_images[^\]]*\]",
            r"\[fusion_link[^\]]*\]",
            r"\[fusion_fontawesome[^\]]*\]",
            r"\[fusion_images[^\]]*\]",
            r"\[fusion_social_links[^\]]*\]",
            r"\[fusion_social_link[^\]]*\]",
            # Closing-tag backstops (in case any module's open/close pair slips through)
            r"\[/fusion_button\]",
            r"\[/fusion_imageframe\]",
            r"\[/fusion_video\]",
            r"\[/fusion_youtube\]",
            r"\[/fusion_vimeo\]",
        ]
        for pattern in patterns:
            inner_content = re.sub(pattern, "", inner_content, flags=re.DOTALL)

        divi_layout = col_attrs.get("divi_layout", "4_4")

        if not inner_content.strip():
            return column("", layout=divi_layout)

        return column(inner_content, layout=divi_layout)

    def _convert_text_to_block(self, match: re.Match[str]) -> str:
        """Convert fusion_text to Divi 5 text block."""
        from divi_migrator.converters.divi5_blocks import text, _clean_html  # noqa: PLC0415
        inner = match.group(1)
        return text(_clean_html(inner))

    def _convert_title_to_block(self, match: re.Match[str]) -> str:
        """Convert fusion_title to Divi 5 heading block."""
        from divi_migrator.converters.divi5_blocks import heading  # noqa: PLC0415
        full = match.group(0)
        attrs = self.extract_all_attrs(full)

        title_text = attrs.get("title", match.group(1).strip())
        size = attrs.get("size", "")
        color = attrs.get("color", "")
        alignment = attrs.get("alignment", "left")

        level_map = {"small": "h4", "medium": "h3", "large": "h2", "h1": "h1", "h2": "h2", "h3": "h3", "h4": "h4"}  # noqa: E501
        level = level_map.get(size, "h2")

        return heading(title_text, level, color=color, alignment=alignment)

    def _convert_button_to_block(self, match: re.Match[str]) -> str:
        """Convert fusion_button to a native anchor styled as a Divi button.

        DiviOps's headless API does not reliably render the divi/button module
        from raw markup (and update_page_content is flaky on shared hosting),
        so we emit a styled <a> inside a divi/text block, which renders
        reliably on the front-end.
        """
        from divi_migrator.converters.divi5_blocks import text  # noqa: PLC0415

        full = match.group(0)
        # Inner text (between open/close) is the real label when present.
        inner = match.group(1).strip() if match.lastindex else ""
        attrs = self.extract_all_attrs(full)
        btn_text = inner or attrs.get("text", "Button")
        btn_text = _clean_html(btn_text).strip() or "Button"
        link = attrs.get("link", "#")
        btn_html = f'<a href="{link}" class="et_pb_button et_pb_bg_layout_light">{btn_text}</a>'
        return text(f"<p>{btn_html}</p>")

    def _convert_image_to_block(self, match: re.Match[str]) -> str:
        """Convert fusion_imageframe to a native <img> inside a divi/text block.

        The divi/image module does not render from raw post_content markup on
        this host, so a native <img> (optionally wrapped in a link) is emitted
        inside a divi/text block, which renders reliably.
        """
        from divi_migrator.converters.divi5_blocks import text  # noqa: PLC0415

        full = match.group(0)
        attrs = self.extract_image_attrs(full)

        src = attrs.get("src", "")
        alt = attrs.get("alt", "")
        link = attrs.get("link", "")
        if not src:
            return ""

        img_tag = f'<img src="{src}" alt="{alt}" style="max-width:100%;height:auto;">'
        inner = f'<a href="{link}">{img_tag}</a>' if link else img_tag
        return text(f"<p>{inner}</p>")

    def _convert_separator_to_block(self, match: re.Match[str]) -> str:
        """Convert fusion_separator to Divi 5 divider block."""
        from divi_migrator.converters.divi5_blocks import divider  # noqa: PLC0415
        full = match.group(0)
        attrs = self.extract_all_attrs(full)

        style = attrs.get("style_type", "solid")
        color = attrs.get("color", "")

        return divider(style=style, color=color if color else None)

    def _convert_youtube_to_block(self, match: re.Match[str]) -> str:
        """Convert fusion_youtube to a native YouTube <iframe> in a divi/text block.

        The divi/video module does not render from raw post_content markup on
        this host, so a native embed <iframe> is emitted inside a divi/text
        block, which renders reliably on the front-end.
        """
        from divi_migrator.converters.divi5_blocks import text  # noqa: PLC0415

        full = match.group(0)
        attrs = self.extract_all_attrs(full)

        yt_url = attrs.get("id", "")
        if not yt_url:
            return ""
        vid_match = re.search(r"(?:youtu\.be/|youtube\.com/watch\?v=|youtube\.com/embed/)([\w-]{11})", yt_url)  # noqa: E501
        if not vid_match:
            vid_match = re.search(r"^([\w-]{11})$", yt_url.strip())
        if vid_match:
            vid = vid_match.group(1)
            embed = f"https://www.youtube.com/embed/{vid}"
            return text(
                f'<p><iframe width="640" height="360" src="{embed}" '
                f'frameborder="0" allowfullscreen></iframe></p>'
            )
        return ""

    def _convert_vimeo_to_block(self, match: re.Match[str]) -> str:
        """Convert fusion_vimeo to a native Vimeo <iframe> in a divi/text block."""
        from divi_migrator.converters.divi5_blocks import text  # noqa: PLC0415

        full = match.group(0)
        attrs = self.extract_all_attrs(full)

        vimeo_url = attrs.get("id", "")
        if vimeo_url:
            vm = re.search(r"vimeo\.com/(\d+)", vimeo_url)
            vid = vm.group(1) if vm else vimeo_url.strip()
            embed = f"https://player.vimeo.com/video/{vid}"
            return text(
                f'<p><iframe width="640" height="360" src="{embed}" '
                f'frameborder="0" allowfullscreen></iframe></p>'
            )
        return ""

    def _convert_video_to_block(self, match: re.Match[str]) -> str:
        """Convert fusion_video (self-hosted) to a native <video> in a divi/text block."""
        from divi_migrator.converters.divi5_blocks import text  # noqa: PLC0415

        full = match.group(0)
        attrs = self.extract_all_attrs(full)

        vid_url = attrs.get("mp4", "") or attrs.get("webm", "") or attrs.get("ogv", "")
        if vid_url:
            return text(
                f'<p><video width="640" height="360" controls>'
                f'<source src="{vid_url}" type="video/mp4"></video></p>'
            )
        return ""

    def _convert_testimonial_to_block(self, match: re.Match[str]) -> str:
        """Convert fusion_testimonial to Divi 5 blurb block."""
        from divi_migrator.converters.divi5_blocks import blurb  # noqa: PLC0415
        full = match.group(0)
        attrs = self.extract_all_attrs(full)

        # Try to get content from between tags first
        content_match = re.search(r"\[fusion_testimonial[^\]]*\](.*?)\[/fusion_testimonial\]", full, re.DOTALL)  # noqa: E501
        content = _clean_html(content_match.group(1)) if content_match else ""

        # If no content between tags, check content attribute (self-closing)
        if not content:
            content = attrs.get("content", "") or attrs.get("testimonial", "")

        author = attrs.get("name", "")
        company = attrs.get("company", "") or attrs.get("title", "")
        image = attrs.get("image", "") or attrs.get("avatar", "") or attrs.get("image_id", "")

        blurb_content = content
        if company:
            blurb_content = f'<p class="testimonial-title">{company}</p>' + blurb_content

        return blurb(title=author, content=blurb_content, image=image if image else None)

    def _convert_testimonials_to_block(self, match: re.Match[str]) -> str:
        """Convert fusion_testimonials wrapper to Divi blurb modules in rows."""
        from divi_migrator.converters.divi5_blocks import blurb, row, column, section, placeholder, _clean_html  # noqa: E501,PLC0415

        inner = match.group(1)
        testimonials = []

        t_pattern = re.compile(r"\[fusion_testimonial[^\]]*\](.*?)\[/fusion_testimonial\]", re.DOTALL)  # noqa: E501
        for m in t_pattern.finditer(inner):
            t_shortcode = m.group(0)
            t_content = m.group(1)
            t_attrs = self.extract_all_attrs(t_shortcode)

            testimonials.append({
                "name": t_attrs.get("name", ""),
                "title": t_attrs.get("title", "") or t_attrs.get("company", ""),
                "content": _clean_html(t_content),
                "image": t_attrs.get("image", "")
            })

        s_pattern = re.compile(r"\[fusion_testimonial[^\]]*\]")
        for m in s_pattern.finditer(inner):
            t_attrs = self.extract_all_attrs(m.group(0))
            if t_attrs.get("name") or t_attrs.get("content"):
                testimonials.append({
                    "name": t_attrs.get("name", ""),
                    "title": t_attrs.get("title", "") or t_attrs.get("company", ""),
                    "content": t_attrs.get("content", "") or t_attrs.get("testimonial", ""),
                    "image": t_attrs.get("image", "")
                })

        if not testimonials:
            return ""

        blurb_blocks = []
        for t in testimonials:
            blurb_content = t["content"]
            if t.get("title"):
                blurb_content = f'<p class="testimonial-title">{t["title"]}</p>' + blurb_content
            blurb_blocks.append(blurb(
                title=t["name"],
                content=blurb_content,
                image=t["image"] if t.get("image") else None,
            ))

        rows = []
        for i in range(0, len(blurb_blocks), 3):
            row_blurbs = blurb_blocks[i:i+3]
            col_blocks = [column(b, layout="4_4") for b in row_blurbs]
            rows.append(row("".join(col_blocks)))

        return placeholder(section("".join(rows)))

    def _convert_person_to_block(self, match: re.Match[str]) -> str:
        from divi_migrator.converters.divi5_blocks import team_member  # noqa: PLC0415
        full = match.group(0)
        attrs = self.extract_all_attrs(full)

        name = attrs.get("name", "")
        title = attrs.get("title", "") or attrs.get("position", "")
        image = attrs.get("image", "")
        description = attrs.get("description", "")
        social = {}
        for key in ["facebook", "twitter", "linkedin", "instagram", "pinterest", "youtube", "vimeo"]:  # noqa: E501
            val = attrs.get(key, "")
            if val:
                social[key + "Url"] = val

        content = description
        if title:
            content = f'<p class="person-title">{title}</p>' + content

        return team_member(name=name, position=title, content=content, image=image or "", social=social or None)  # noqa: E501

    def _convert_content_box_to_block(self, match: re.Match[str]) -> str:
        from divi_migrator.converters.divi5_blocks import blurb  # noqa: PLC0415
        full = match.group(0)
        attrs = self.extract_all_attrs(full)

        title = attrs.get("title", "")
        icon = attrs.get("icon", "")
        image = attrs.get("image", "")
        link = attrs.get("link", "")
        content = attrs.get("content", "")

        return blurb(title=title, content=content, icon=icon if icon else None, image=image if image else None, url=link if link else None)  # noqa: E501

    def _convert_content_boxes_to_block(self, match: re.Match[str]) -> str:
        from divi_migrator.converters.divi5_blocks import blurb, row, column, section, placeholder  # noqa: PLC0415
        inner = match.group(1)
        boxes = []
        box_pattern = re.compile(r"\[fusion_content_box[^\]]*\]", re.DOTALL)
        for m in box_pattern.finditer(inner):
            attrs = self.extract_all_attrs(m.group(0))
            boxes.append({
                "title": attrs.get("title", ""),
                "icon": attrs.get("icon", ""),
                "image": attrs.get("image", ""),
                "link": attrs.get("link", ""),
                "content": attrs.get("content", "")
            })
        if not boxes:
            return ""
        blurb_blocks = []
        for b in boxes:
            blurb_blocks.append(blurb(
                title=b["title"],
                content=b["content"],
                icon=b["icon"] if b.get("icon") else None,
                image=b["image"] if b.get("image") else None,
                url=b["link"] if b.get("link") else None,
            ))
        rows = []
        for i in range(0, len(blurb_blocks), 3):
            row_blurbs = blurb_blocks[i:i+3]
            col_blocks = [column(b, layout="4_4") for b in row_blurbs]
            rows.append(row("".join(col_blocks)))

        return placeholder(section("".join(rows)))

    def _convert_faq_to_block(self, match: re.Match[str]) -> str:
        from divi_migrator.converters.divi5_blocks import accordion, accordion_item  # noqa: PLC0415
        inner = match.group(1)
        faq_items = []
        item_pattern = re.compile(r"\[fusion_faq_item[^\]]*\](.*?)\[/fusion_faq_item\]", re.DOTALL)
        for m in item_pattern.finditer(inner):
            item_attrs = self.extract_all_attrs(m.group(0))
            item_content = m.group(1)
            faq_items.append({
                "title": item_attrs.get("title", ""),
                "content": _clean_html(item_content)
            })
        if not faq_items:
            return ""
        accordion_items = []
        for item in faq_items:
            accordion_items.append(accordion_item(title=item["title"], content=item["content"]))
        return accordion("".join(accordion_items))

    def _convert_tabs_to_block(self, match: re.Match[str]) -> str:
        from divi_migrator.converters.divi5_blocks import tabs, tab  # noqa: PLC0415
        inner = match.group(1)
        tab_items = []
        tab_pattern = re.compile(r"\[fusion_tab[^\]]*\](.*?)\[/fusion_tab\]", re.DOTALL)
        for m in tab_pattern.finditer(inner):
            tab_attrs = self.extract_all_attrs(m.group(0))
            tab_content = m.group(1)
            tab_items.append({
                "title": tab_attrs.get("title", ""),
                "content": _clean_html(tab_content)
            })
        if not tab_items:
            return ""
        tab_blocks = []
        for item in tab_items:
            tab_blocks.append(tab(title=item["title"], content=item["content"]))
        return tabs("".join(tab_blocks))

    def _convert_countdown_to_block(self, match: re.Match[str]) -> str:
        from divi_migrator.converters.divi5_blocks import countdown_timer  # noqa: PLC0415
        full = match.group(0)
        attrs = self.extract_all_attrs(full)
        date = attrs.get("date", "")
        label = attrs.get("label", "days")
        separator = attrs.get("separator", "on")
        return countdown_timer(number=date, label=label, separator=separator)

    def _convert_checklist_to_block(self, match: re.Match[str]) -> str:
        """Convert a fusion_checklist into a native Divi 5 text-block list.

        DiviOps's headless API does not populate the divi/icon-list module
        from raw markup (it drops module content it cannot parse), so we
        render the checklist as a standard <ul><li> list inside a divi/text
        block, which DiviOps reliably renders. Each [fusion_li_item] becomes
        one <li>; its inner text (wrapped in <p> by Avada) is unwrapped and
        HTML entities decoded.
        """
        from divi_migrator.converters.divi5_blocks import text  # noqa: PLC0415

        full = match.group(0)
        items: list[str] = []
        for li in self.CHECKLIST_ITEM_PATTERN.finditer(full):
            body = re.sub(r"\[/?fusion_li_item\b[^\]]*\]", "", li.group(0), flags=re.DOTALL)
            body = re.sub(r"<[^>]+>", "", body)  # strip <p> and any tags
            body = html.unescape(body).strip()
            if body:
                items.append(body)
        if not items:
            return ""
        lis = "".join(f"<li>{item}</li>" for item in items)
        return text(f"<ul>{lis}</ul>")

    def _convert_blog_to_block(self, match: re.Match[str]) -> str:  # noqa: ARG002
        from divi_migrator.converters.divi5_blocks import blog  # noqa: PLC0415
        return blog()

    def _convert_map_to_block(self, match: re.Match[str]) -> str:
        from divi_migrator.converters.divi5_blocks import map_module  # noqa: PLC0415
        full = match.group(0)
        attrs = self.extract_all_attrs(full)
        center: dict[str, float] = {"lat": 0.0, "lng": 0.0}
        if attrs.get("latitude") and attrs.get("longitude"):
            center = {"lat": float(attrs["latitude"]), "lng": float(attrs["longitude"])}
        zoom = int(attrs.get("zoom", 10))
        return map_module(center=center, zoom=zoom)

    def extract_assets(self, content: str) -> ExtractedAssets:
        """Extract images, buttons, forms from Avada content."""
        assets = ExtractedAssets()

        # Extract images
        for match in self.IMAGE_PATTERN.finditer(content):
            attrs = self.extract_image_attrs(match.group(0))
            assets.images.append({
                "src": attrs.get("src", ""),
                "alt": attrs.get("alt", ""),
                "title": attrs.get("title", ""),
                "type": "fusion_imageframe",
            })

        # Extract buttons
        for match in self.BUTTON_PATTERN.finditer(content):
            attrs = self.extract_button_attrs(match.group(0))
            assets.buttons.append({
                "text": attrs.get("text", ""),
                "url": attrs.get("link", ""),
                "type": "fusion_button",
            })

        # Extract forms (if any)
        # Fusion forms would be [fusion_form] shortcodes

        return assets
