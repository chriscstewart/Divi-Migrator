"""Design System Inspector - fetches design tokens from DiviOps/Divi Customizer."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

from divi_migrator.config import Config
from divi_migrator.core.client import WPClient
from divi_migrator.models.design_system import (
    ColorToken,
    DesignPresets,
    DesignSystem,
    DiviVariables,
    GlobalColors,
    GlobalFonts,
    FontToken,
)

if TYPE_CHECKING:
    from divi_migrator.core.client import DiviOpsClient

logger = logging.getLogger(__name__)


class DesignSystemInspector:
    """Inspects target site's Divi design system via DiviOps REST API."""

    def __init__(self, config: Config, wp_client: WPClient, diviops_client: DiviOpsClient):
        self.config = config
        self.wp = wp_client
        self.diviops = diviops_client

    def fetch_design_system(self) -> DesignSystem:
        """Fetch complete design system from DiviOps."""
        logger.info("Fetching design system from DiviOps...")

        ds = DesignSystem()

        # Fetch global colors
        ds.colors = self._fetch_global_colors()

        # Backfill any missing global colors from the current Home page
        # (secondary source — never a hardcoded hex).
        self._backfill_from_home_page(ds.colors)

        # Fetch global fonts
        ds.fonts = self._fetch_global_fonts()

        # Fetch presets
        ds.presets = self._fetch_presets()

        # Fetch variables
        ds.variables = self._fetch_variables()

        # Fetch custom CSS
        ds.custom_css = self._fetch_custom_css()

        logger.info(
            "Design system fetched: %d colors, %d presets, %d variables",
            len(ds.colors.colors),
            sum(len(v) for v in ds.presets.__dict__.values()),
            len(ds.variables.variables),
        )

        return ds

    def _fetch_global_colors(self) -> GlobalColors:
        """Fetch global color palette from DiviOps."""
        try:
            resp = self.diviops.get("global-color/list")
            if not resp.get("ok"):
                return GlobalColors()

            data = resp.get("data", {})
            customizer = data.get("customizer", {})

            gc = GlobalColors()
            for key, val in customizer.items():
                gc.colors[key] = ColorToken(
                    key=key,
                    label=val.get("label", key),
                    color=val.get("color", ""),
                    folder=val.get("folder", "customizer"),
                    status=val.get("status", "active"),
                    source=val.get("source", "wp_customizer"),
                    last_updated=val.get("lastUpdated"),
                    used_in_posts=val.get("usedInPosts", []),
                )

            # Store the raw customizer data for background color lookup
            gc.customizer_raw = customizer

            logger.info("Fetched %d global colors", len(gc.colors))
            return gc  # noqa: TRY300
        except Exception as e:
            logger.warning("Failed to fetch global colors: %s", e)
            return GlobalColors()

    def _backfill_from_home_page(self, gc: GlobalColors) -> None:
        """Use the current Home page as a secondary color source.

        Resolution order for every color token: Divi Customizer wins; the Home
        page fills any gaps. Never injects a hardcoded hex — if the Home page
        has no usable color, the token simply stays absent.
        """
        try:
            settings = self.wp.get("wp/v2/settings")
            front_id = None
            if isinstance(settings, dict):
                front_id = settings.get("page_on_front")
            if not front_id:
                return
            home = self.wp.get(f"wp/v2/pages/{front_id}")
            if not isinstance(home, dict):
                return
            content = home.get("content")
            raw = content.get("rendered", "") if isinstance(content, dict) else ""
            # Best-effort: pull a background-color from inline styles in the
            # Home page's Divi layout. This is heuristic and may yield nothing.
            for token_key, pattern in [
                ("gcid-background-color", r"background-color:\s*(#[0-9a-fA-F]{3,8})\b"),
                ("gcid-primary-color", r"color:\s*(#[0-9a-fA-F]{3,8})\b"),
            ]:
                if token_key in gc.colors:
                    continue  # Customizer already provided it
                m = re.search(pattern, raw)
                if m:
                    gc.colors[token_key] = ColorToken(
                        key=token_key,
                        label=token_key,
                        color=m.group(1),
                        source="home_page",
                    )
            # Site background specifically
            if gc.home_page_background is None:
                m = re.search(r"background-color:\s*(#[0-9a-fA-F]{3,8})\b", raw)
                if m:
                    gc.home_page_background = m.group(1)
        except Exception as e:  # noqa: BLE001
            logger.debug("Home page backfill skipped: %s", e)

    def _fetch_global_fonts(self) -> GlobalFonts:
        """Fetch global fonts from DiviOps."""
        try:
            resp = self.wp.get("diviops/v1/global-font/list")
            if not resp.get("ok"):
                return GlobalFonts()

            data = resp.get("data", {})
            fonts = data.get("fonts", {})

            gf = GlobalFonts()
            for key, val in fonts.items():
                gf.fonts[key] = FontToken(
                    key=key,
                    label=val.get("name", key),
                    font_family=val.get("fontFamily", ""),
                    font_weight=val.get("fontWeight", "400"),
                    font_style=val.get("fontStyle", "normal"),
                    is_google_font=val.get("isGoogleFont", False),
                    is_uploaded=val.get("isUploaded", False),
                )

            return gf  # noqa: TRY300
        except Exception as e:
            logger.warning("Failed to fetch global fonts: %s", e)
            return GlobalFonts()

    def _fetch_presets(self) -> DesignPresets:
        """Fetch module presets from DiviOps."""
        try:
            resp = self.wp.get("diviops/v1/preset/list")
            if not resp.get("ok"):
                return DesignPresets()

            data = resp.get("data", {})
            presets = DesignPresets()

            # Divi 5 module presets
            divi5 = data.get("divi5_presets", {})
            for module_name, module_data in divi5.items():
                if hasattr(presets, module_name.replace("divi/", "").replace("/", "_")):
                    attr = module_name.replace("divi/", "").replace("/", "_")
                    setattr(presets, attr, module_data.get("items", {}))

            # Group presets
            groups = data.get("group", {})
            presets.groups = groups

            # Background presets
            backgrounds = data.get("divi/background", {})
            presets.background = backgrounds.get("items", {})

            return presets  # noqa: TRY300
        except Exception as e:
            logger.warning("Failed to fetch presets: %s", e)
            return DesignPresets()

    def _fetch_variables(self) -> DiviVariables:
        """Fetch CSS variables from DiviOps."""
        try:
            resp = self.wp.get("diviops/v1/variable/list")
            if not resp.get("ok"):
                return DiviVariables()

            data = resp.get("data", {})
            return DiviVariables(variables=data.get("variables", []))

        except Exception as e:
            logger.warning("Failed to fetch variables: %s", e)
            return DiviVariables()

    def _fetch_custom_css(self) -> str:
        """Fetch custom CSS from theme customizer."""
        try:
            # Try theme options endpoint
            resp = self.wp.get("wp/v2/settings")
            if resp.get("ok"):
                # This might have custom CSS
                pass
            return ""  # noqa: TRY300
        except Exception:
            return ""

    def inspect_reference_pages(self, _page_ids: list[int]) -> dict[str, Any]:
        """Analyze reference pages for design patterns."""
        # Could analyze home page, header, footer for design patterns
        return {}


def fetch_design_system(
    config: Config, wp_client: WPClient, diviops_client: DiviOpsClient
) -> DesignSystem:  # noqa: E501
    """Convenience function to fetch design system."""
    inspector = DesignSystemInspector(config, wp_client, diviops_client)
    return inspector.fetch_design_system()
