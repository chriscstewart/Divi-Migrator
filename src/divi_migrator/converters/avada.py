"""Avada/Fusion Builder to Divi 5 converter."""

from __future__ import annotations

import re
from typing import Any

from divi_migrator.converters.base import BaseConverter, ExtractedAssets


class AvadaConverter(BaseConverter):
    """Convert Avada/Fusion Builder content to Divi 5."""

    format_name = "avada"

    # Fusion Builder shortcode patterns
    CONTAINER_PATTERN = re.compile(
        r"\[fusion_builder_container[^\]]*\](.*?)\[/fusion_builder_container\]", re.DOTALL
    )
    ROW_PATTERN = re.compile(r"\[fusion_builder_row[^\]]*\](.*?)\[/fusion_builder_row\]", re.DOTALL)
    COLUMN_PATTERN = re.compile(
        r"\[fusion_builder_column[^\]]*\](.*?)\[/fusion_builder_column\]", re.DOTALL
    )
    TEXT_PATTERN = re.compile(r"\[fusion_text[^\]]*\](.*?)\[/fusion_text\]", re.DOTALL)
    TITLE_PATTERN = re.compile(r"\[fusion_title[^\]]*\](.*?)\[/fusion_title\]", re.DOTALL)
    BUTTON_PATTERN = re.compile(r"\[fusion_button[^\]]*\]", re.DOTALL)
    IMAGE_PATTERN = re.compile(r"\[fusion_imageframe[^\]]*\]", re.DOTALL)
    SEPARATOR_PATTERN = re.compile(r"\[fusion_separator[^\]]*\]", re.DOTALL)
    ICON_PATTERN = re.compile(r"\[fusion_fontawesome[^\]]*\]", re.DOTALL)
    MAP_PATTERN = re.compile(r"\[fusion_map[^\]]*\]", re.DOTALL)
    VIDEO_PATTERN = re.compile(r"\[fusion_video[^\]]*\]", re.DOTALL)
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
        pattern = rf'{attr}=["\']([^"\']+)["\']'
        match = re.search(pattern, shortcode)
        return match.group(1) if match else None

    def extract_all_attrs(self, shortcode: str) -> dict[str, str]:
        """Extract all attributes from shortcode."""
        attrs = {}
        pattern = r'(\w+)=["\']([^"\']+)["\']'
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
        """Convert Fusion Builder content to Divi 5 shortcodes."""

        # Process containers (outermost)
        def replace_container(match: re.Match[str]) -> str:
            return self.convert_container(match)

        return self.CONTAINER_PATTERN.sub(replace_container, content)

    def convert_container(self, match: re.Match[str]) -> str:
        """Convert fusion_builder_container to et_pb_section."""
        full = match.group(0)
        inner = match.group(1)

        container_attrs = self.extract_container_attrs(full)
        rows = self.ROW_PATTERN.findall(inner)

        # Section background
        section_bg = container_attrs.get("background_color", "#f7f4ef")
        if container_attrs.get("background_image"):
            section_bg = f'background_image="{container_attrs["background_image"]}"'

        section_attrs = f'background_color="{section_bg}"'
        if container_attrs.get("background_image"):
            section_attrs += f' background_image="{container_attrs["background_image"]}"'
        if container_attrs.get("background_position"):
            section_attrs += f' background_position="{container_attrs["background_position"]}"'
        if container_attrs.get("background_repeat"):
            section_attrs += f' background_repeat="{container_attrs["background_repeat"]}"'

        # Process rows
        rows_html = "".join(self.convert_row(row) for row in rows)

        return f"[et_pb_section {section_attrs}]{rows_html}[/et_pb_section]"

    def convert_row(self, row_match: str) -> str:
        """Convert fusion_builder_row to et_pb_row."""
        row_attrs = self.extract_row_attrs(row_match)
        columns = self.COLUMN_PATTERN.findall(row_match)

        row_type = row_attrs.get("type", "flex")
        divi_row_type = "flex" if row_type == "flex" else "standard"

        row_attrs_str = f'layout="{divi_row_type}"'
        if row_attrs.get("background_color"):
            row_attrs_str += f' background_color="{row_attrs["background_color"]}"'
        if row_attrs.get("background_image"):
            row_attrs_str += f' background_image="{row_attrs["background_image"]}"'
        if row_attrs.get("padding_top"):
            row_attrs_str += f' padding_top="{row_attrs["padding_top"]}"'
        if row_attrs.get("padding_bottom"):
            row_attrs_str += f' padding_bottom="{row_attrs["padding_bottom"]}"'

        columns_html = "".join(self.convert_column(col) for col in columns)

        return f"[et_pb_row {row_attrs_str}]{columns_html}[/et_pb_row]"

    def convert_column(self, column_match: str) -> str:
        """Convert fusion_builder_column to et_pb_column."""
        col_attrs = self.extract_column_attrs(column_match)
        inner_content = column_match

        # Process inner content
        inner_content = self.TEXT_PATTERN.sub(self.convert_text, inner_content)
        inner_content = self.TITLE_PATTERN.sub(self.convert_title, inner_content)
        inner_content = self.BUTTON_PATTERN.sub(self.convert_button, inner_content)
        inner_content = self.IMAGE_PATTERN.sub(self.convert_image, inner_content)
        inner_content = self.SEPARATOR_PATTERN.sub(self.convert_separator, inner_content)
        inner_content = self.ICON_PATTERN.sub(self.convert_icon, inner_content)
        inner_content = self.MAP_PATTERN.sub(self.convert_map, inner_content)
        inner_content = self.VIDEO_PATTERN.sub(self.convert_video, inner_content)
        inner_content = self.GALLERY_PATTERN.sub(self.convert_gallery, inner_content)
        inner_content = self.TABS_PATTERN.sub(self.convert_tabs, inner_content)
        inner_content = self.TOGGLES_PATTERN.sub(self.convert_toggles, inner_content)
        inner_content = self.ACCORDION_PATTERN.sub(self.convert_accordion, inner_content)
        inner_content = self.PERSON_PATTERN.sub(self.convert_person, inner_content)
        inner_content = self.TESTIMONIAL_PATTERN.sub(self.convert_testimonial, inner_content)
        inner_content = self.PRICING_TABLE_PATTERN.sub(self.convert_pricing_table, inner_content)
        inner_content = self.CODE_PATTERN.sub(self.convert_code, inner_content)
        inner_content = self.RAW_PATTERN.sub(self.convert_raw, inner_content)

        divi_layout = col_attrs.get("divi_layout", "4_4")

        return f'[et_pb_column type="{divi_layout}"]{inner_content}[/et_pb_column]'

    def convert_text(self, match: re.Match[str]) -> str:
        """Convert fusion_text to et_pb_text."""
        inner = match.group(1)

        # Clean HTML content
        inner = self._clean_html(inner)

        return f'[et_pb_text _builder_version="5.0"]{inner}[/et_pb_text]'

    def _clean_html(self, content: str) -> str:
        """Clean HTML content."""
        content = content.replace("\u201c", '"').replace("\u201d", '"')
        content = content.replace("\u2018", "'").replace("\u2019", "'")
        content = content.replace("\u00d7", "x")
        content = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)
        return content.strip()

    def convert_title(self, match: re.Match[str]) -> str:
        """Convert fusion_title to et_pb_text with heading."""
        full = match.group(0)
        inner = match.group(1)
        attrs = self.extract_title_content(full)

        text = attrs.get("text", inner.strip())
        size = attrs.get("size", "")
        color = attrs.get("color", "")
        alignment = attrs.get("alignment", "left")

        heading_level = "h2"
        if "h1" in size.lower():
            heading_level = "h1"
        elif "h3" in size.lower():
            heading_level = "h3"
        elif "h4" in size.lower():
            heading_level = "h4"

        style = ""
        if color:
            style += f"color: {color};"
        if alignment:
            style += f"text-align: {alignment};"

        return (
            f'[et_pb_text _builder_version="5.0"]'
            f"<{heading_level} style=\"{style}\">{text}</{heading_level}>"
            f"[/et_pb_text]"
        )

    def convert_button(self, match: re.Match[str]) -> str:
        """Convert fusion_button to et_pb_button."""
        full = match.group(0)
        attrs = self.extract_button_attrs(full)

        text = attrs.get("text", "Button")
        link = attrs.get("link", "#")
        target = attrs.get("target", "_self")
        color = attrs.get("color", "")
        attrs.get("size", "")
        border_radius = attrs.get("border_radius", "")
        border_color = attrs.get("border_color", "")
        border_size = attrs.get("border_size", "")

        button_attrs = (
            f'button_text="{text}" button_url="{link}" '
            f'url_new_window="{target == "_blank"}"'
        )
        if color:
            button_attrs += f' button_bg_color="{color}"'
        if border_radius:
            button_attrs += f' button_border_radius="{border_radius}"'
        if border_color:
            button_attrs += f' button_border_color="{border_color}"'
        if border_size:
            button_attrs += f' button_border_width="{border_size}"'

        return f'[et_pb_button {button_attrs} _builder_version="5.0"][/et_pb_button]'

    def convert_image(self, match: re.Match[str]) -> str:
        """Convert fusion_imageframe to et_pb_image."""
        full = match.group(0)
        attrs = self.extract_image_attrs(full)

        src = attrs.get("src", "")
        alt = attrs.get("alt", "")
        title = attrs.get("title", "")
        link = attrs.get("link", "")
        attrs.get("lightbox", "no")

        image_attrs = f'src="{src}" alt="{alt}"'
        if title:
            image_attrs += f' title="{title}"'
        if link:
            image_attrs += f' url="{link}" url_new_window="off"'

        return f'[et_pb_image {image_attrs} _builder_version="5.0"][/et_pb_image]'

    def convert_separator(self, match: re.Match[str]) -> str:
        """Convert fusion_separator to et_pb_divider."""
        full = match.group(0)
        attrs = self.extract_separator_attrs(full)

        color = attrs.get("color", "")
        border_size = attrs.get("border_size", "")
        style = attrs.get("style_type", "solid")
        alignment = attrs.get("alignment", "center")

        divider_attrs = (
            f'divider_color="{color}" divider_weight="{border_size}" '
            f'divider_style="{style}" divider_alignment="{alignment}"'
        )

        return f'[et_pb_divider {divider_attrs} _builder_version="5.0"][/et_pb_divider]'

    def convert_icon(self, match: re.Match[str]) -> str:
        """Convert fusion_fontawesome to et_pb_text with icon."""
        full = match.group(0)
        # Extract icon class
        icon_class = self.extract_attr(full, "icon") or ""
        icon_color = self.extract_attr(full, "icon_color") or ""
        icon_size = self.extract_attr(full, "size") or "24px"

        style = f"font-size: {icon_size};"
        if icon_color:
            style += f"color: {icon_color};"

        return (
            f'[et_pb_text _builder_version="5.0"]'
            f'<i class="{icon_class}" style="{style}"></i>'
            f"[/et_pb_text]"
        )

    def convert_map(self, match: re.Match[str]) -> str:
        """Convert fusion_map to et_pb_map."""
        full = match.group(0)
        attrs = self.extract_all_attrs(full)

        map_attrs = ""
        for key, val in attrs.items():
            if key in [
                "address",
                "latitude",
                "longitude",
                "zoom",
                "map_type",
                "map_style",
                "marker",
                "scrollwheel",
                "draggable",
            ]:
                map_attrs += f' {key}="{val}"'

        return f'[et_pb_map {map_attrs} _builder_version="5.0"][/et_pb_map]'

    def convert_video(self, match: re.Match[str]) -> str:
        """Convert fusion_video to et_pb_video."""
        full = match.group(0)
        attrs = self.extract_all_attrs(full)

        video_attrs = ""
        for key, val in attrs.items():
            if key in [
                "mp4",
                "webm",
                "ogv",
                "preview_image",
                "width",
                "height",
                "autoplay",
                "loop",
                "muted",
                "controls",
            ]:
                video_attrs += f' {key}="{val}"'

        return f'[et_pb_video {video_attrs} _builder_version="5.0"][/et_pb_video]'

    def convert_gallery(self, match: re.Match[str]) -> str:
        """Convert fusion_gallery to et_pb_gallery."""
        full = match.group(0)
        attrs = self.extract_all_attrs(full)

        gallery_attrs = ""
        for key, val in attrs.items():
            if key in ["ids", "columns", "lightbox", "size", "captions", "orderby", "order"]:
                gallery_attrs += f' {key}="{val}"'

        return f'[et_pb_gallery {gallery_attrs} _builder_version="5.0"][/et_pb_gallery]'

    def convert_tabs(self, match: re.Match[str]) -> str:
        """Convert fusion_tabs to et_pb_tabs."""
        inner = match.group(1)

        tabs = self.TAB_PATTERN.findall(inner)
        tabs_html = ""
        for tab in tabs:
            tab_title = self.extract_attr(tab, "title") or "Tab"
            tab_content = tab
            tab_content = self.TEXT_PATTERN.sub(self.convert_text, tab_content)
            tabs_html += f'[et_pb_tab title="{tab_title}"]{tab_content}[/et_pb_tab]'

        return f'[et_pb_tabs _builder_version="5.0"]{tabs_html}[/et_pb_tabs]'

    def convert_toggles(self, match: re.Match[str]) -> str:
        """Convert fusion_toggles to et_pb_toggle."""
        inner = match.group(1)

        toggles = self.TOGGLE_PATTERN.findall(inner)
        toggles_html = ""
        for toggle in toggles:
            title = self.extract_attr(toggle, "title") or "Toggle"
            content = toggle
            content = self.TEXT_PATTERN.sub(self.convert_text, content)
            toggles_html += (
                f'[et_pb_toggle title="{title}" _builder_version="5.0"]'
                f"{content}[/et_pb_toggle]"
            )

        return f'[et_pb_toggles _builder_version="5.0"]{toggles_html}[/et_pb_toggles]'

    def convert_accordion(self, match: re.Match[str]) -> str:
        """Convert fusion_accordion to et_pb_accordion."""
        inner = match.group(1)

        items = self.ACCORDION_ITEM_PATTERN.findall(inner)
        items_html = ""
        for item in items:
            title = self.extract_attr(item, "title") or "Item"
            content = item
            content = self.TEXT_PATTERN.sub(self.convert_text, content)
            items_html += (
                f'[et_pb_accordion_item title="{title}" _builder_version="5.0"]'
                f"{content}[/et_pb_accordion_item]"
            )

        return f'[et_pb_accordion _builder_version="5.0"]{items_html}[/et_pb_accordion]'

    def convert_person(self, match: re.Match[str]) -> str:
        """Convert fusion_person to et_pb_team_member."""
        full = match.group(0)
        attrs = self.extract_all_attrs(full)

        person_attrs = f'name="{attrs.get("name", "")}"'
        if attrs.get("title"):
            person_attrs += f' job_title="{attrs["title"]}"'
        if attrs.get("image"):
            person_attrs += f' image_src="{attrs["image"]}"'
        if attrs.get("description"):
            person_attrs += f' bio="{attrs["description"]}"'

        return f'[et_pb_team_member {person_attrs} _builder_version="5.0"][/et_pb_team_member]'

    def convert_testimonial(self, match: re.Match[str]) -> str:
        """Convert fusion_testimonial to et_pb_testimonial."""
        full = match.group(0)
        attrs = self.extract_all_attrs(full)

        test_attrs = ""
        for key, val in attrs.items():
            if key in ["author", "company", "position", "image", "rating"]:
                test_attrs += f' {key}="{val}"'

        # Extract content between shortcodes
        content_match = re.search(
            r"\[fusion_testimonial[^\]]*\](.*?)\[/fusion_testimonial\]", full, re.DOTALL
        )
        content = content_match.group(1).strip() if content_match else ""

        return (
            f'[et_pb_testimonial {test_attrs} _builder_version="5.0"]'
            f'{content}[/et_pb_testimonial]'
        )

    def convert_pricing_table(self, match: re.Match[str]) -> str:
        """Convert fusion_pricing_table to et_pb_pricing_tables."""
        inner = match.group(1)

        items = self.PRICING_ITEM_PATTERN.findall(inner)
        items_html = ""
        for item in items:
            attrs = self.extract_all_attrs(item)

            item_attrs = ""
            for key, val in attrs.items():
                if key in [
                    "title",
                    "subtitle",
                    "price",
                    "currency",
                    "frequency",
                    "button_text",
                    "button_url",
                    "featured",
                ]:
                    item_attrs += f' {key}="{val}"'

            items_html += (
                f'[et_pb_pricing_table_item {item_attrs} _builder_version="5.0"]'
                f"[/et_pb_pricing_table_item]"
            )

        return f'[et_pb_pricing_tables _builder_version="5.0"]{items_html}[/et_pb_pricing_tables]'

    def convert_code(self, match: re.Match[str]) -> str:
        """Convert fusion_code to et_pb_code."""
        inner = match.group(1)
        return f'[et_pb_code _builder_version="5.0"]<![CDATA[{inner}]]>[/et_pb_code]'

    def convert_raw(self, match: re.Match[str]) -> str:
        """Convert fusion_raw to et_pb_code."""
        inner = match.group(1)
        return f'[et_pb_code _builder_version="5.0"]<![CDATA[{inner}]]>[/et_pb_code]'

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