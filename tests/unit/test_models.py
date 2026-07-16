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


def test_design_system_defaults():
    ds = DesignSystem.defaults()
    assert ds.colors.get("gcid-primary-color") == "#770000"
    assert ds.colors.get("gcid-secondary-color") == "#6b6b4c"
    assert ds.colors.get("gcid-heading-color") == "#613335"
    assert ds.colors.get("gcid-body-color") == "#4a3f35"
    assert ds.colors.get("gcid-link-color") == "#7c7c4c"


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
    from divi_migrator.models import MigrationMeta

    meta = MigrationMeta(source_id=123, source_title="Test")
    record = CheckpointRecord(
        id=123,
        title="Test Page",
        content_len=1000,
        meta=meta,
    )
    assert record.id == 123
    assert record.title == "Test Page"
    assert record.content_len == 1000


def test_checkpoint_data():
    cp = CheckpointData()
    assert cp.processed == []
    assert cp.failed == []
    assert cp.started_at is not None


def test_verification_result():
    vr = VerificationResult(passed=True, sections=2, rows=3, modules=5)
    assert vr.passed is True
    assert vr.sections == 2
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
