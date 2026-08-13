"""End-to-end orchestrator tests using the offline fake-WP/DiviOps harness.

These run the FULL migration pipeline (convert -> validate -> schema check ->
create draft -> verify -> publish -> rename original) with zero network access,
then assert migration integrity against the recorded writes and the in-memory
store. They replace the previously-empty placeholder tests.
"""

import pytest

from divi_migrator.core.audit import AuditManager
from divi_migrator.core.orchestrator import MigrationOrchestrator
from divi_migrator.testing.harness import AVADA_FIXTURE, build_harness

PAGE_IDS = [10, 11]
PAGE_TITLES = ["About Us", "Services"]
PAGE_SLUGS = ["about-us", "services"]


@pytest.fixture
def harness():
    originals = [
        {
            "id": PAGE_IDS[0],
            "title": PAGE_TITLES[0],
            "slug": PAGE_SLUGS[0],
            "content": AVADA_FIXTURE,
            "author": 1,
        },
        {
            "id": PAGE_IDS[1],
            "title": PAGE_TITLES[1],
            "slug": PAGE_SLUGS[1],
            "content": AVADA_FIXTURE,
            "author": 2,
        },
    ]
    wp, diviops, cfg = build_harness(originals)
    audit = AuditManager(wp, cfg)
    orch = MigrationOrchestrator(cfg, wp=wp, diviops=diviops, audit=audit)
    return {"wp": wp, "diviops": diviops, "cfg": cfg, "orch": orch, "audit": audit}


def _seed_audit(harness) -> None:
    """Record originals into the audit (mirrors `audit-init` / first migrate)."""
    pages = [harness["wp"].get_item("page", i) for i in PAGE_IDS]
    posts = []
    harness["audit"].record_originals(pages, posts)


def test_orchestrator_initialization(harness) -> None:
    assert isinstance(harness["orch"], MigrationOrchestrator)
    assert harness["orch"].wp is harness["wp"]
    assert harness["orch"].diviops is harness["diviops"]
    assert harness["orch"].audit is harness["audit"]


def test_audit_initialization_records_originals(harness) -> None:
    _seed_audit(harness)
    audit = harness["audit"].load()
    assert audit.total_pages == 2
    assert set(audit.original_pages.keys()) == set(PAGE_IDS)
    # Both authors recorded (covers the per-author fetch path).
    assert {p.author for p in audit.original_pages.values()} == {1, 2}


def test_migration_creates_new_draft_not_modify_original(harness) -> None:
    _seed_audit(harness)
    result = harness["orch"].migrate_post_type("page", limit=1, dry_run=False)
    res = result["results"][0]
    assert res["status"] == "completed"
    draft_id = res["draft_id"]
    assert draft_id is not None

    # An original was NOT modified in place: it was renamed to '-old' + draft.
    original = harness["wp"].get_item("page", PAGE_IDS[0])
    assert original["title"]["rendered"].endswith("-old")
    assert original["status"] == "draft"

    # The new draft exists, published, with original title/slug preserved.
    draft = harness["wp"].store.items[draft_id]
    assert draft["status"] == "publish"
    assert draft["title"]["rendered"] == PAGE_TITLES[0]
    assert draft["slug"] == PAGE_SLUGS[0]
    # Provenance meta marker applied.
    assert draft["meta"].get("_divi_migrator", {}).get("source_id") == PAGE_IDS[0]


def test_resume_migration_works(harness) -> None:
    _seed_audit(harness)
    # Simulate a real interruption: a draft was minted for source 10 but the
    # run crashed BEFORE complete_migration(), so the audit record is left
    # in_progress with a migrated_id set and the original NOT yet renamed.
    # We model that by creating the draft directly, then recording the
    # in_progress state via the audit (as a crash would have left it).
    created = harness["diviops"].create_content(
        PAGE_TITLES[0], "<!-- wp:divi/placeholder -->", status="draft", post_type="page"
    )
    draft1 = created["id"]
    harness["audit"].start_migration("page", PAGE_IDS[0], PAGE_TITLES[0], PAGE_SLUGS[0], "abc123")
    rec = harness["audit"].get_migration_status("page", PAGE_IDS[0])
    rec.status = "in_progress"
    rec.migrated_id = draft1
    harness["audit"].save()

    # Resume the migration.
    orch2 = MigrationOrchestrator(
        harness["cfg"], wp=harness["wp"], diviops=harness["diviops"], audit=harness["audit"]
    )
    r2 = orch2.migrate_post_type("page", limit=1, dry_run=False)
    draft2 = r2["results"][0]["draft_id"]
    # Resume must reuse the existing draft, not mint a second one.
    assert draft2 == draft1
    # Still exactly one published draft carrying the source id.
    drafts = [
        i
        for i in harness["wp"].store.items.values()
        if i.get("meta", {}).get("_divi_migrator", {}).get("source_id") == PAGE_IDS[0]
    ]
    assert len(drafts) == 1


def test_discovery_excludes_originals_and_migrated(harness) -> None:
    _seed_audit(harness)
    # Before migration: both originals discoverable.
    disc = harness["orch"].audit  # noqa: F841
    from divi_migrator.core.discovery import discover_migratable_items

    items = discover_migratable_items(harness["wp"], harness["audit"], "page")
    assert len(items) == 2

    # Migrate one; it should then be excluded from discovery.
    harness["orch"].migrate_post_type("page", limit=1, dry_run=False)
    items = discover_migratable_items(harness["wp"], harness["audit"], "page")
    assert len(items) == 1
    assert items[0]["id"] == PAGE_IDS[1]


def test_duplicate_detection_uses_audit(harness) -> None:
    _seed_audit(harness)
    harness["orch"].migrate_post_type("page", limit=2, dry_run=False)
    # Audit map has exactly 2 completed migrations.
    audit = harness["audit"].load()
    completed = [k for k, v in audit.migration_map.items() if v.status == "completed"]
    assert len(completed) == 2
    # A re-run (no limit) finds nothing left to migrate.
    from divi_migrator.core.discovery import discover_migratable_items

    items = discover_migratable_items(harness["wp"], harness["audit"], "page")
    assert items == []


def test_rollback_restores_original_exactly(harness) -> None:
    _seed_audit(harness)
    harness["orch"].migrate_post_type("page", limit=1, dry_run=False)
    original_title = PAGE_TITLES[0]
    original_slug = PAGE_SLUGS[0]

    ok = harness["audit"].rollback_migration("page", PAGE_IDS[0])
    assert ok is True

    # Original restored to its exact title/slug/status.
    original = harness["wp"].get_item("page", PAGE_IDS[0])
    assert original["title"]["rendered"] == original_title
    assert original["slug"] == original_slug
    assert original["status"] == "publish"
    # Migrated draft removed.
    drafts = [
        i
        for i in harness["wp"].store.items.values()
        if i.get("meta", {}).get("_divi_migrator", {}).get("source_id") == PAGE_IDS[0]
    ]
    assert drafts == []
    # Audit record rolled back.
    rec = harness["audit"].get_migration_status("page", PAGE_IDS[0])
    assert rec.status == "rolled_back"


def test_bulk_rollback_removes_all_migrated(harness) -> None:
    _seed_audit(harness)
    harness["orch"].migrate_post_type("page", limit=2, dry_run=False)
    result = harness["audit"].bulk_rollback("page", harness["wp"])
    assert result["deleted"] == 2
    assert result["restored"] == 2
    # No migrated drafts remain.
    drafts = [
        i for i in harness["wp"].store.items.values() if i.get("meta", {}).get("_divi_migrator")
    ]
    assert drafts == []


def test_originals_never_force_deleted(harness) -> None:
    _seed_audit(harness)
    harness["orch"].migrate_post_type("page", limit=1, dry_run=False)
    # The Delete recorded for the original rename is forced=False (trash, not delete).
    deletes = [w for w in harness["wp"].writes if w["method"] == "DELETE"]
    # Original is trashed (force False); assert no force=True appears anywhere.
    for d in deletes:
        assert d["payload"].get("force") is not True
    # Original still present (renamed to -old, drafted), never removed.
    assert PAGE_IDS[0] in harness["wp"].store.items
    original = harness["wp"].store.items[PAGE_IDS[0]]
    assert original["slug"].endswith("-old")
    assert original["status"] == "draft"


def test_full_pipeline_integrity_scorecard(harness) -> None:
    """Full pipeline: every original -> draft, provenance + verification."""
    _seed_audit(harness)
    result = harness["orch"].migrate_post_type("page", limit=2, dry_run=False)
    assert result["status"] == "completed"

    for res in result["results"]:
        assert res["status"] == "completed"
        assert res["verification"] is True
        draft = harness["wp"].store.items[res["draft_id"]]
        meta = draft["meta"]["_divi_migrator"]
        # Schema-valid Divi5 markup was produced (validation passed upstream).
        assert meta["source_format"] == "avada"
        assert meta["divi_blocks_count"] >= 1
        assert meta["sections_count"] >= 1
    # Exactly 2 originals, 2 drafts, 0 originals destroyed.
    assert (
        len(
            [
                i
                for i in harness["wp"].store.items.values()
                if i.get("meta", {}).get("_divi_migrator")
            ]
        )
        == 2
    )


def test_dry_run_writes_nothing(harness) -> None:
    _seed_audit(harness)
    before_ids = set(harness["wp"].store.items.keys())
    before_statuses = {iid: it["status"] for iid, it in harness["wp"].store.items.items()}
    result = harness["orch"].migrate_post_type("page", limit=2, dry_run=True)
    # All reported dry-run.
    assert all(r["status"] == "dry_run" for r in result["results"])
    after_ids = set(harness["wp"].store.items.keys())
    # No NEW content created (audit post save aside, no drafts minted).
    assert after_ids == before_ids
    # Originals are NOT renamed/republished/drafted — they keep their state.
    for iid in PAGE_IDS:
        assert harness["wp"].store.items[iid]["status"] == before_statuses[iid]
        assert not harness["wp"].store.items[iid]["title"]["rendered"].endswith("-old")
    # No provenance meta assigned to any item (nothing was migrated).
    assert not any(
        i.get("meta", {}).get("_divi_migrator") for i in harness["wp"].store.items.values()
    )
