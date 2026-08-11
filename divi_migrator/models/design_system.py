"""Design system inspection and data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ColorToken:
    """A single color token from Divi Customizer."""

    key: str
    label: str
    color: str
    folder: str = "customizer"
    status: str = "active"
    source: str = "wp_customizer"
    last_updated: str | None = None
    used_in_posts: list[int] = field(default_factory=list)


@dataclass
class FontToken:
    """A font token from Divi Customizer."""

    key: str
    label: str
    font_family: str
    font_weight: str = "400"
    font_style: str = "normal"
    is_google_font: bool = False
    is_uploaded: bool = False


@dataclass
class GlobalColors:
    """Global color palette from Divi Customizer."""

    colors: dict[str, ColorToken] = field(default_factory=dict)
    # Store raw customizer data for background color lookup
    customizer_raw: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: str | None = None) -> str | None:
        """Get color hex by token key."""
        token = self.colors.get(key)
        return token.color if token else default

    def primary(self) -> str:
        """Get primary color."""
        return self.get("gcid-primary-color", "#770000") or "#770000"

    def secondary(self) -> str:
        return self.get("gcid-secondary-color", "#6b6b4c") or "#6b6b4c"

    def heading(self) -> str:
        return self.get("gcid-heading-color", "#613335") or "#613335"

    def body(self) -> str:
        return self.get("gcid-body-color", "#4a3f35") or "#4a3f35"

    def link(self) -> str:
        return self.get("gcid-link-color", "#7c7c4c") or "#7c7c4c"

    def primary_background(self) -> str:
        """Get the site background color from customizer."""
        # Try to get from customizer data
        # Common keys for site background in Divi customizer
        for key in ["background_color", "site_background", "gcid-background-color"]:
            if key in self.customizer_raw:
                val = self.customizer_raw[key]
                color: str = val.get("color", "") if isinstance(val, dict) else str(val)
                if color:
                    return color
        # Fallback to white
        return "#ffffff"


@dataclass
class GlobalFonts:
    """Global font settings from Divi Customizer."""

    fonts: dict[str, FontToken] = field(default_factory=dict)

    def heading_font(self) -> str:
        return "inherit"

    def body_font(self) -> str:
        return "inherit"


@dataclass
class DesignPresets:
    """Module presets from Divi."""

    section: dict[str, Any] = field(default_factory=dict)
    row: dict[str, Any] = field(default_factory=dict)
    column: dict[str, Any] = field(default_factory=dict)
    text: dict[str, Any] = field(default_factory=dict)
    button: dict[str, Any] = field(default_factory=dict)
    image: dict[str, Any] = field(default_factory=dict)
    blurb: dict[str, Any] = field(default_factory=dict)
    accordion: dict[str, Any] = field(default_factory=dict)
    accordion_item: dict[str, Any] = field(default_factory=dict)
    background: dict[str, Any] = field(default_factory=dict)
    modules: dict[str, Any] = field(default_factory=dict)
    groups: dict[str, Any] = field(default_factory=dict)


@dataclass
class DiviVariables:
    """Divi 5 CSS variables."""

    variables: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class CustomCSS:
    """Custom CSS from theme customizer."""

    css: str = ""


@dataclass
class DesignSystem:
    """Complete design system snapshot."""

    colors: GlobalColors = field(default_factory=GlobalColors)
    fonts: GlobalFonts = field(default_factory=GlobalFonts)
    presets: DesignPresets = field(default_factory=DesignPresets)
    variables: DiviVariables = field(default_factory=DiviVariables)
    custom_css: str = ""
    fetched_at: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def defaults(cls) -> DesignSystem:
        """Fallback defaults when inspection fails."""
        ds = cls()
        ds.colors.colors = {
            "gcid-primary-color": ColorToken(
                key="gcid-primary-color", label="Primary Color", color="#770000"
            ),
            "gcid-secondary-color": ColorToken(
                key="gcid-secondary-color", label="Secondary Color", color="#6b6b4c"
            ),
            "gcid-heading-color": ColorToken(
                key="gcid-heading-color", label="Heading Text Color", color="#613335"
            ),
            "gcid-body-color": ColorToken(
                key="gcid-body-color", label="Body Text Color", color="#4a3f35"
            ),
            "gcid-link-color": ColorToken(
                key="gcid-link-color", label="Link Color", color="#7c7c4c"
            ),
        }
        return ds


@dataclass
class DesignContext:
    """Context for a specific page migration."""

    design_system: DesignSystem
    page_id: int
    page_title: str
    source_format: str
    content_hash: str
    analyzed_at: datetime = field(default_factory=datetime.utcnow)
