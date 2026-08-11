"""Layout verification engine."""

from __future__ import annotations

import logging
from typing import Any

from divi_migrator.config import Config
from divi_migrator.core.client import DiviOpsClient
from divi_migrator.models import VerificationResult

logger = logging.getLogger(__name__)

# Error messages
INVALID_DIVIOPS_ERROR = "diviops must be a DiviOpsClient instance"
PRIMARY_TOKEN = "gcid-primary-color"


class VerificationEngine:
    """Verifies migrated page layout against expectations."""

    def __init__(self, diviops: DiviOpsClient, config: Config):
        self.diviops = diviops
        self.config = config

    def verify_layout(
        self,
        layout: dict[str, Any],
        expected: dict[str, int] | None = None,
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
        self._count_blocks(blocks, result)

        issues = self._check_requirements(result, expected)

        result.issues = issues
        result.verification_passed = len(issues) == 0

        return result

    def _count_blocks(
        self, blocks: list[dict[str, Any]], result: VerificationResult, depth: int = 0
    ) -> None:
        """Recursively count blocks and extract info."""
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
                self._count_blocks(inner, result, depth + 1)

    def _check_requirements(
        self, result: VerificationResult, expected: dict[str, int] | None
    ) -> list[str]:
        """Check layout against requirements."""
        issues = []

        # Check requirement for sections
        if self.config.verification.require_sections and result.sections == 0:
            issues.append("No sections found")

        # Compare with expected
        if expected:
            self._check_expected(result, expected, issues)

        # Check for primary color usage
        has_primary = any(PRIMARY_TOKEN in str(c) for c in result.background_colors)
        if not has_primary and result.background_colors:
            issues.append(f"Primary color token '{PRIMARY_TOKEN}' not found in backgrounds")

        return issues

    def _check_expected(
        self, result: VerificationResult, expected: dict[str, int], issues: list[str]
    ) -> None:
        """Check expected values against actual."""
        if expected.get("images", 0) > 0 and result.images < expected["images"]:
            issues.append(f"Images: expected at least {expected['images']}, got {result.images}")

        if expected.get("buttons", 0) > 0 and result.buttons < expected["buttons"]:
            issues.append(f"Buttons: expected at least {expected['buttons']}, got {result.buttons}")

        if expected.get("forms", 0) > 0 and result.modules == 0:
            issues.append(f"Forms: expected at least {expected['forms']}, got 0")


def verify_page(
    diviops: DiviOpsClient,
    config: Config,
    page_id: int,
    expected: dict[str, int] | None = None,
) -> VerificationResult:
    """Convenience function to verify a page."""
    if not isinstance(diviops, DiviOpsClient):
        raise TypeError(INVALID_DIVIOPS_ERROR)

    layout = diviops.get_page_layout(page_id)
    engine = VerificationEngine(diviops, config)
    return engine.verify_layout(layout, expected)
