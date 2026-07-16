"""Layout verification engine."""

from __future__ import annotations

import logging
from typing import Any, Optional

from divi_migrator.config import Config
from divi_migrator.core.client import DiviOpsClient
from divi_migrator.models import VerificationResult

logger = logging.getLogger(__name__)


class VerificationEngine:
    """Verifies migrated page layout against expectations."""

    def __init__(self, diviops: DiviOpsClient, config: Config):
        self.diviops = diviops
        self.config = config

    def _verify_layout(
        self,
        layout: dict[str, Any],
        expected: Optional[dict[str, int]] = None,
    ) -> VerificationResult:
        """Verify page layout against expectations."""
        if not layout.get("ok"):
            return VerificationResult(
                passed=False,
                issues=[f"Layout fetch failed: {layout.get('error', 'Unknown error')}"],
            )

        data = layout.get("data", {})
        blocks = data.get("blocks", [])

        result = VerificationResult(passed=True)

        def count_blocks(blocks: list[dict[str, Any]], depth: int = 0) -> None:
            for block in blocks:
                name = block.get("block_name", "")
                result.block_tree.append(
                    {
                        "name": name,
                        "depth": depth,
                        "admin_label": block.get("admin_label", ""),
                        "text_preview": block.get("text_preview", ""),
                    }
                )

                if name == "divi/section":
                    result.sections += 1
                    attrs = block.get("attributes", {})
                    bg = attrs.get("background_color")
                    if bg:
                        result.background_colors.append(bg)
                elif name == "divi/row":
                    result.rows += 1
                elif name.startswith("divi/"):
                    result.modules += 1
                    if name == "divi/image":
                        result.images += 1
                    elif name == "divi/button":
                        result.buttons += 1

                inner = block.get("inner_blocks", [])
                if inner:
                    count_blocks(inner, depth + 1)

        count_blocks(blocks)

        issues = []

        # Check requirement for sections
        if self.config.verification.require_sections and result.sections == 0:
            issues.append("No sections found")

        # Compare with expected
        if expected:
            if expected.get("images", 0) > 0 and result.images < expected["images"]:
                issues.append(
                    f"Images: expected at least {expected['images']}, got {result.images}"
                )

            if expected.get("buttons", 0) > 0 and result.buttons < expected["buttons"]:
                issues.append(
                    f"Buttons: expected at least {expected['buttons']}, got {result.buttons}"
                )

            if expected.get("forms", 0) > 0 and result.modules == 0:
                issues.append(f"Forms: expected at least {expected['forms']}, got 0")

        # Check for primary color usage
        primary_token = "gcid-primary-color"
        has_primary = any(primary_token in str(c) for c in result.background_colors)
        if not has_primary and result.background_colors:
            issues.append(f"Primary color token '{primary_token}' not found in backgrounds")

        result.issues = issues
        result.verification_passed = len(issues) == 0

        return result


def verify_page(
    diviops: DiviOpsClient,
    config: Config,
    page_id: int,
    expected: Optional[dict[str, int]] = None,
) -> VerificationResult:
    """Convenience function to verify a page."""
    if not isinstance(diviops, DiviOpsClient):
        raise ValueError("diviops must be a DiviOpsClient instance")

    layout = diviops.get_page_layout(page_id)
    engine = VerificationEngine(diviops, config)
    return engine._verify_layout(layout, expected)