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
    # Background color scraped from the current Home page (secondary source)
    home_page_background: str | None = None

    def get(self, key: str, default: str | None = None) -> str | None:
        """Get color hex by token key."""
        token = self.colors.get(key)
        return token.color if token else default

    def primary(self) -> str | None:
        """Get primary color from the fetched design system (no hardcoded fallback)."""
        return self.get("gcid-primary-color")

    def secondary(self) -> str | None:
        return self.get("gcid-secondary-color")

    def heading(self) -> str | None:
        return self.get("gcid-heading-color")

    def body(self) -> str | None:
        return self.get("gcid-body-color")

    def link(self) -> str | None:
        return self.get("gcid-link-color")

    def primary_background(self) -> str | None:
        """Site background color.

        Resolution order (never a hardcoded hex):
          1. Divi Customizer raw values
          2. The current Home page's background (fetched by the inspector)
        Returns None if neither source yields a color.
        """
        for key in ["background_color", "site_background", "gcid-background-color"]:
            if key in self.customizer_raw:
                val = self.customizer_raw[key]
                color: str = val.get("color", "") if isinstance(val, dict) else str(val)
                if color:
                    return color
        return self.home_page_background


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
        """Empty fallback when inspection fails.

        Intentionally contains NO hardcoded hex colors — callers must handle
        missing design-system values gracefully (the migrated content carries
        its own source colors; this is only a verification/reference aid).
        """
        return cls()

    @property
    def primary_background_color(self) -> str | None:
        """Site background color resolved from the live design system.

        Chains Customizer raw values then the Home page background. Never a
        hardcoded hex; returns None if neither source has a color.
        """
        return self.colors.primary_background()


@dataclass
class DesignContext:
    """Context for a specific page migration."""

    design_system: DesignSystem
    page_id: int
    page_title: str
    source_format: str
    content_hash: str
    analyzed_at: datetime = field(default_factory=datetime.utcnow)
