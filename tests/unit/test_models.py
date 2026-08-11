from divi_migrator.models import (
    DesignSystem,
    GlobalColors,
    ColorToken,
    MigrationMeta,
    CheckpointRecord,
    CheckpointData,
    VerificationResult,
    ExtractedAssets,
    SourceFormat,
    MigrationStatus,
)

# Test constants
TEST_SOURCE_ID = 123
TEST_CONTENT_LEN = 1000
EXPECTED_SECTIONS = 2
EXPECTED_ROWS = 3
EXPECTED_MODULES = 5


def test_design_system_defaults():
    # defaults() must contain NO hardcoded hex colors — callers handle
    # missing design-system values gracefully.
    ds = DesignSystem.defaults()
    assert ds.colors.get("gcid-primary-color") is None
    assert ds.colors.get("gcid-secondary-color") is None
    assert ds.colors.get("gcid-heading-color") is None
    assert ds.colors.get("gcid-body-color") is None
    assert ds.colors.get("gcid-link-color") is None


def test_global_colors_fallback_is_none():
    # When a token is absent, the helper returns None (never a hardcoded hex).
    gc = GlobalColors()
    assert gc.primary() is None
    assert gc.primary_background() is None


def test_global_colors_get():
    gc = GlobalColors()
    gc.colors["test"] = ColorToken(key="test", label="Test", color="#ff0000")
    assert gc.get("test") == "#ff0000"
    assert gc.get("missing", "default") == "default"


def test_color_token():
    token = ColorToken(key="primary", label="Primary", color="#770000")
    assert token.color == "#770000"
    assert token.label == "Primary"


def test_migration_meta_defaults():
    meta = MigrationMeta()
    assert meta.version == 1
    assert meta.source_id == 0
    assert meta.source_content_hash == ""


def test_checkpoint_record():
    meta = MigrationMeta(source_id=TEST_SOURCE_ID, source_title="Test")
    record = CheckpointRecord(
        id=TEST_SOURCE_ID,
        title="Test Page",
        content_len=TEST_CONTENT_LEN,
        meta=meta,
    )
    assert record.id == TEST_SOURCE_ID
    assert record.title == "Test Page"
    assert record.content_len == TEST_CONTENT_LEN


def test_checkpoint_data():
    cp = CheckpointData()
    assert cp.processed == []
    assert cp.failed == []
    assert cp.started_at is not None


def test_verification_result():
    vr = VerificationResult(
        passed=True, sections=EXPECTED_SECTIONS, rows=EXPECTED_ROWS, modules=EXPECTED_MODULES
    )
    assert vr.passed is True
    assert vr.sections == EXPECTED_SECTIONS
    assert "PASSED" in vr.summary


def test_extracted_assets():
    assets = ExtractedAssets(
        images=[{"src": "img.jpg", "alt": "test"}],
        buttons=[{"text": "Click", "url": "/link"}],
    )
    assert len(assets.images) == 1
    assert len(assets.buttons) == 1


def test_source_format_enum():
    assert SourceFormat.AVADA == "avada"
    assert SourceFormat.ELEMENTOR == "elementor"
    assert SourceFormat.PLAIN_HTML == "plain_html"
    assert SourceFormat.UNKNOWN == "unknown"


def test_migration_status_enum():
    assert MigrationStatus.COMPLETED == "completed"
    assert MigrationStatus.FAILED == "failed"
    assert MigrationStatus.SKIPPED == "skipped"
