"""Tests for POST migration behaviour in the orchestrator.

These tests encode the requirements for blog-post migration:
  * featured image (featured_media) is carried over to the published post
  * categories, tags and original publish date are preserved
  * a post is migrated exactly ONCE (no duplicate drafts on re-run)
  * an interrupted (in_progress) run resumes the existing draft instead of
    creating a second one

They are written against ``MigrationOrchestrator._migrate_item`` with fully
mocked WP / DiviOps / audit so they run offline and fast. They intentionally
FAIL against the current buggy implementation (featured image lost, doubling)
and turn green once the orchestrator is fixed.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

# Ensure repo root on path when run under pytest rootdir
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from divi_migrator.converters import registry  # noqa: E402
from divi_migrator.core.orchestrator import MigrationOrchestrator  # noqa: E402
from divi_migrator.models import SourceFormat, VerificationResult  # noqa: E402


@pytest.fixture
def design_system() -> Mock:
    ds = Mock()
    ds.primary_background_color = "#ffffff"
    return ds


@pytest.fixture
def mock_wp() -> Mock:
    wp = Mock()
    # get_item returns a rich original post (with featured image + taxonomy)
    wp.get_item.return_value = {
        "id": 500,
        "title": {"rendered": "My Test Post"},
        "slug": "my-test-post",
        "content": {
            "rendered": "[fusion_builder_container][fusion_builder_row]"
            "[fusion_builder_column][fusion_text]Hello world[/fusion_text]"
            "[/fusion_builder_column][/fusion_builder_row][/fusion_builder_container]",
            "raw": "[fusion_builder_container][fusion_builder_row]"
            "[fusion_builder_column][fusion_text]Hello world[/fusion_text]"
            "[/fusion_builder_column][/fusion_builder_row][/fusion_builder_container]",
        },
        "author": 2,
        "status": "publish",
        "date": "2023-05-04T10:00:00",
        "date_gmt": "2023-05-04T10:00:00",
        "categories": [436, 435],
        "tags": [150, 18, 30],
        "featured_media": 7777,
        "meta": {},
        "link": "https://example.com/my-test-post",
    }
    wp.get.return_value = {"ok": True}
    wp.put.return_value = {"id": 99999}
    wp.post.return_value = {"ok": True, "id": 99999}
    wp.delete.return_value = {"ok": True}
    wp.update_meta.return_value = {"ok": True}
    wp.get_items.return_value = []
    return wp


@pytest.fixture
def mock_diviops() -> Mock:
    diviops = Mock()
    diviops.create_content.return_value = {"ok": True, "data": {"page_id": 99999}}
    diviops.validate_blocks.return_value = {"ok": True}
    diviops.update_page_content.return_value = {"ok": True}
    diviops.flush_cache.return_value = {"ok": True}
    diviops.get_page_layout.return_value = {}
    return diviops


@pytest.fixture
def mock_audit() -> Mock:
    """Audit mock that tracks migration state like the real AuditManager."""
    state: dict[str, Any] = {"status": "pending", "migrated_id": None}

    audit = Mock()

    def is_migrated(post_type: str, original_id: int) -> bool:
        return state["status"] == "completed"

    def get_migration_status(post_type: str, original_id: int):
        if state["status"] == "pending":
            return None
        rec = Mock()
        rec.status = state["status"]
        rec.migrated_id = state["migrated_id"]
        return rec

    def start_migration(post_type, original_id, title, slug, content_hash):
        state["status"] = "in_progress"

    def complete_migration(post_type, original_id, migrated_id):
        state["status"] = "completed"
        state["migrated_id"] = migrated_id

    def fail_migration(post_type, original_id, error):
        state["status"] = "failed"

    def get_original(post_type, original_id):
        return None

    def is_original(post_type, original_id):
        return False

    def mark_renamed(post_type, original_id, old_title, old_slug):
        pass

    audit.is_migrated.side_effect = is_migrated
    audit.get_migration_status.side_effect = get_migration_status
    audit.start_migration.side_effect = start_migration
    audit.complete_migration.side_effect = complete_migration
    audit.fail_migration.side_effect = fail_migration
    audit.get_original.side_effect = get_original
    audit.is_original.side_effect = is_original
    audit.mark_renamed.side_effect = mark_renamed
    audit.state = state  # expose for assertions
    return audit


@pytest.fixture
def orchestrator(mock_wp, mock_diviops, mock_audit, design_system, monkeypatch):
    cfg = Mock()
    cfg.migration = Mock()
    cfg.migration.rate_limit = 0.01
    cfg.migration.min_delay = 0.0
    cfg.migration.max_retries = 1
    cfg.migration.checkpoint_dir = Path("./test_checkpoints")
    cfg.wp = Mock()
    cfg.wp.url = "https://test.com"
    cfg.diviops = Mock()
    cfg.audit = Mock()
    cfg.audit.backup_dir = Path("./test_audit_backups")
    cfg.verification = Mock()

    orch = MigrationOrchestrator.__new__(MigrationOrchestrator)
    orch.config = cfg
    orch.wp = mock_wp
    orch.diviops = mock_diviops
    orch.audit = mock_audit
    orch.verification = Mock()
    orch._design_system = design_system
    orch._migration_category_id = 435

    # Patch collaborators used inside _migrate_item
    monkeypatch.setattr(
        "divi_migrator.core.orchestrator.verify_page",
        lambda diviops, config, draft_id: VerificationResult(
            passed=True, sections=1, rows=1, modules=1, images=1, buttons=0,
            background_colors=[], issues=[],
        ),
    )
    monkeypatch.setattr(
        "divi_migrator.core.orchestrator.validate_divi5_blocks",
        lambda content: (True, []),
    )
    # Deterministic converter (no network)
    fake_conv = Mock()
    fake_conv.convert.return_value = (
        '<!-- wp:divi/section {"builderVersion":"5.9.0"} -->'
        '<!-- wp:divi/heading {"title":{"innerContent":{"desktop":{"value":"Hello world"}}}} /-->'
        "<!-- /wp:divi/section -->"
    )
    monkeypatch.setattr(registry, "get_converter", lambda fmt: fake_conv)
    return orch


def _publish_put_calls(mock_wp):
    """Return the json_data of every PUT to posts/{id} that sets status=publish."""
    calls = []
    for args, kwargs in mock_wp.put.call_args_list:
        endpoint = args[0] if args else ""
        if endpoint.startswith("posts/") and "json_data" in kwargs:
            jd = kwargs["json_data"]
            if jd.get("status") == "publish":
                calls.append(jd)
    return calls


def _create_content_calls(mock_diviops):
    return mock_diviops.create_content.call_args_list


class TestPostFeaturedImageAndMeta:
    def test_featured_image_carried_to_published_post(self, orchestrator, mock_wp):
        """The published post must receive the original's featured_media (top-level)."""
        item = {"id": 500, "title": "My Test Post", "format": SourceFormat.AVADA,
                "slug": "my-test-post"}
        orchestrator._migrate_item("post", item, orchestrator._design_system, dry_run=False)

        pub = _publish_put_calls(mock_wp)
        assert pub, "no publish PUT was issued"
        assert pub[0]["featured_media"] == 7777, (
            f"featured_media not carried over: {pub[0].get('featured_media')}"
        )

    def test_categories_and_tags_preserved(self, orchestrator, mock_wp):
        item = {"id": 500, "title": "My Test Post", "format": SourceFormat.AVADA,
                "slug": "my-test-post"}
        orchestrator._migrate_item("post", item, orchestrator._design_system, dry_run=False)

        pub = _publish_put_calls(mock_wp)
        assert pub[0]["categories"] == [436, 435, 435] or 435 in pub[0]["categories"]
        assert set(pub[0]["tags"]) == {150, 18, 30}

    def test_original_publish_date_preserved(self, orchestrator, mock_wp):
        item = {"id": 500, "title": "My Test Post", "format": SourceFormat.AVADA,
                "slug": "my-test-post"}
        orchestrator._migrate_item("post", item, orchestrator._design_system, dry_run=False)

        pub = _publish_put_calls(mock_wp)
        assert pub[0]["date"] == "2023-05-04T10:00:00"
        assert pub[0]["date_gmt"] == "2023-05-04T10:00:00"


class TestPostSinglePass:
    def test_no_duplicate_draft_on_second_run(self, orchestrator, mock_diviops, mock_audit):
        """A second migrate of an already-completed post creates NO new draft."""
        item = {"id": 500, "title": "My Test Post", "format": SourceFormat.AVADA,
                "slug": "my-test-post"}

        # First run: completes successfully
        orchestrator._migrate_item("post", item, orchestrator._design_system, dry_run=False)
        assert mock_audit.state["status"] == "completed"
        first_create_calls = len(_create_content_calls(mock_diviops))

        # Second run: audit says completed -> should skip, no new draft
        result = orchestrator._migrate_item("post", item, orchestrator._design_system, dry_run=False)
        assert result["status"] == "skipped"
        second_create_calls = len(_create_content_calls(mock_diviops))
        assert second_create_calls == first_create_calls, "second run created a duplicate draft"

    def test_interrupted_in_progress_resumes_existing_draft(
        self, orchestrator, mock_diviops, mock_audit
    ):
        """If a prior run left status 'in_progress' (interrupted), a re-run must
        resume the existing draft, not create a second one."""
        item = {"id": 500, "title": "My Test Post", "format": SourceFormat.AVADA,
                "slug": "my-test-post"}

        # Simulate an interrupted prior run: status stuck at in_progress,
        # a draft (88888) was already created.
        mock_audit.state["status"] = "in_progress"
        mock_audit.state["migrated_id"] = 88888

        before = len(_create_content_calls(mock_diviops))
        orchestrator._migrate_item("post", item, orchestrator._design_system, dry_run=False)
        after = len(_create_content_calls(mock_diviops))

        # Resumed: no NEW draft created (the existing 88888 is reused).
        assert after == before, "interrupted run created a duplicate draft instead of resuming"
        assert mock_audit.state["status"] == "completed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
