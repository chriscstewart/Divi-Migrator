"""Data models for migration framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from divi_migrator.models.design_system import (
    ColorToken as ColorToken,
    DesignContext as DesignContext,
    DesignPresets as DesignPresets,
    DesignSystem as DesignSystem,
    DiviVariables as DiviVariables,
    GlobalColors as GlobalColors,
)

CustomCSS = "CustomCSS"


__all__ = [
    "ColorToken",
    "DesignContext",
    "DesignPresets",
    "DesignSystem",
    "DiviVariables",
    "GlobalColors",
    "CustomCSS",
    "SourceFormat",
    "MigrationStatus",
    "DiscoveredItem",
    "ExtractedAssets",
    "VerificationResult",
    "MigrationMeta",
    "CheckpointRecord",
    "CheckpointData",
    "OriginalContent",
    "MigrationRecord",
    "AuditData",
]


class SourceFormat(str, Enum):
    """Supported source content formats."""

    AVADA = "avada"
    ELEMENTOR = "elementor"
    PLAIN_HTML = "plain_html"
    UNKNOWN = "unknown"


class MigrationStatus(str, Enum):
    """Migration status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class DiscoveredItem:
    """A discovered migratable item."""

    id: int
    title: str
    format: SourceFormat
    content_length: int
    url: str | None = None
    slug: str | None = None


@dataclass
class ExtractedAssets:
    """Assets extracted from source content."""

    images: list[dict[str, Any]] = field(default_factory=list)
    buttons: list[dict[str, Any]] = field(default_factory=list)
    forms: list[dict[str, Any]] = field(default_factory=list)
    videos: list[dict[str, Any]] = field(default_factory=list)
    other: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class VerificationResult:
    """Verification results."""

    passed: bool = False
    sections: int = 0
    rows: int = 0
    modules: int = 0
    images: int = 0
    buttons: int = 0
    background_colors: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    block_tree: list[dict[str, Any]] = field(default_factory=list)

    @property
    def verification_passed(self) -> bool:
        return self.passed

    @verification_passed.setter
    def verification_passed(self, value: bool) -> None:
        self.passed = value

    @property
    def verification_details(self) -> dict[str, Any]:
        return {
            "sections": self.sections,
            "rows": self.rows,
            "modules": self.modules,
            "images": self.images,
            "buttons": self.buttons,
            "background_colors": self.background_colors,
            "issues": self.issues,
        }

    @verification_details.setter
    def verification_details(self, value: dict[str, Any]) -> None:
        self.sections = value.get("sections", 0)
        self.rows = value.get("rows", 0)
        self.modules = value.get("modules", 0)
        self.images = value.get("images", 0)
        self.buttons = value.get("buttons", 0)
        self.background_colors = value.get("background_colors", [])
        self.issues = value.get("issues", [])

    @property
    def summary(self) -> str:
        if self.passed:
            return f"PASSED: {self.sections} sections, {self.rows} rows, {self.modules} modules"
        return f"FAILED: {len(self.issues)} issues"


@dataclass
class MigrationMeta:
    """Migration metadata stored on draft."""

    version: int = 1
    source_format: str = ""
    source_id: int = 0
    source_title: str = ""
    source_content_hash: str = ""
    migrated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    divi_blocks_count: int = 0
    sections_count: int = 0
    rows_count: int = 0
    modules_count: int = 0
    images_count: int = 0
    buttons_count: int = 0
    background_colors: list[str] = field(default_factory=list)
    verification_passed: bool = False
    verification_details: dict[str, Any] = field(default_factory=dict)


@dataclass
class CheckpointRecord:
    """Single checkpoint record."""

    id: int
    title: str
    content_len: int
    draft_id: int = 0
    meta: MigrationMeta = field(default_factory=MigrationMeta)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class CheckpointData:
    """Checkpoint file structure."""

    processed: list[CheckpointRecord] = field(default_factory=list)
    failed: list[dict[str, Any]] = field(default_factory=list)
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# Audit models
@dataclass
class OriginalContent:
    """Immutable record of original content (stored in audit)."""

    id: int
    post_type: str
    title: str
    slug: str
    author: int
    status: str
    date: str
    date_gmt: str
    content_hash: str
    recorded_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class MigrationRecord:
    """Migration tracking record."""

    original_id: int
    migrated_id: int | None = None
    status: str = "pending"  # pending, in_progress, completed, failed, rolled_back
    title: str = ""
    slug: str = ""
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    completed_at: str | None = None
    error: str | None = None
    retries: int = 0
    content_hash: str = ""
    renamed_original: bool = False
    original_old_title: str = ""
    original_old_slug: str = ""


@dataclass
class AuditData:
    """Complete audit data structure."""

    version: int = 1
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    original_pages: dict[int, OriginalContent] = field(default_factory=dict)
    original_posts: dict[int, OriginalContent] = field(default_factory=dict)
    migration_map: dict[str, MigrationRecord] = field(default_factory=dict)

    total_pages: int = 0
    total_posts: int = 0
    migrated_pages: int = 0
    migrated_posts: int = 0
    failed_pages: int = 0
    failed_posts: int = 0
