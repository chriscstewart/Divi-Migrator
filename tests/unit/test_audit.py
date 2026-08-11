"""Tests for audit system."""

import pytest
from unittest.mock import Mock
from pathlib import Path
import tempfile
import shutil

from divi_migrator.core.audit import AuditManager, OriginalContent, MigrationRecord
from divi_migrator.core.audit_guard import AuditGuard
from divi_migrator.core.client import WPClient

# Test constants
TOTAL_PAGES = 10
TOTAL_POSTS = 20
MIGRATED_PAGES = 5
MIGRATED_POSTS = 10
FAILED_PAGES = 1
FAILED_POSTS = 2
EXPECTED_DELETED = 2
EXPECTED_RESTORED = 2
EXPECTED_MIGRATED_ID = 100
EXPECTED_TOTAL_PAGES = 2
EXPECTED_TOTAL_POSTS = 1
EXPECTED_ORIGINAL_ID_1 = 1
EXPECTED_ORIGINAL_ID_2 = 2
EXPECTED_ORIGINAL_ID_10 = 10


@pytest.fixture
def temp_backup_dir():
    """Create a temporary directory for audit backups."""
    temp_dir = Path(tempfile.mkdtemp(prefix="test_audit_backups_"))
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_wp():
    wp = Mock(spec=WPClient)
    wp.get.return_value = {"value": "{}"}
    wp.put.return_value = {"ok": True}
    wp.delete.return_value = {"ok": True}
    wp.post.return_value = {"ok": True}
    return wp


@pytest.fixture
def audit_manager(mock_wp, temp_backup_dir):
    config = Mock()
    config.audit = Mock()
    config.audit.backup_dir = temp_backup_dir
    return AuditManager(mock_wp, config)


class TestOriginalContent:
    def test_original_content_creation(self):
        content = OriginalContent(
            id=1,
            post_type="page",
            title="Test Page",
            slug="test-page",
            author=2,
            status="publish",
            date="2024-01-01",
            date_gmt="2024-01-01",
            content_hash="abc123",
        )
        assert content.id == 1
        assert content.title == "Test Page"
        assert content.post_type == "page"


class TestMigrationRecord:
    def test_migration_record_defaults(self):
        record = MigrationRecord(original_id=1)
        assert record.original_id == 1
        assert record.migrated_id is None
        assert record.status == "pending"
        assert record.retries == 0


class TestAuditManager:
    def test_record_originals(self, audit_manager):
        pages = [
            {
                "id": 1,
                "title": {"rendered": "Page 1"},
                "slug": "page-1",
                "author": 2,
                "status": "publish",
                "date": "2024-01-01",
                "date_gmt": "2024-01-01",
                "content": {"rendered": "content1"},
            },
            {
                "id": 2,
                "title": {"rendered": "Page 2"},
                "slug": "page-2",
                "author": 1,
                "status": "draft",
                "date": "2024-01-02",
                "date_gmt": "2024-01-02",
                "content": {"rendered": "content2"},
            },
        ]
        posts = [
            {
                "id": 10,
                "title": {"rendered": "Post 1"},
                "slug": "post-1",
                "author": 2,
                "status": "publish",
                "date": "2024-01-03",
                "date_gmt": "2024-01-03",
                "content": {"rendered": "content3"},
            },
        ]

        audit_manager.record_originals(pages, posts)

        audit = audit_manager.load()
        assert audit.total_pages == EXPECTED_TOTAL_PAGES
        assert audit.total_posts == EXPECTED_TOTAL_POSTS
        assert EXPECTED_ORIGINAL_ID_1 in audit.original_pages
        assert EXPECTED_ORIGINAL_ID_2 in audit.original_pages
        assert EXPECTED_ORIGINAL_ID_10 in audit.original_posts

    def test_is_original(self, audit_manager):
        audit = audit_manager.load()
        audit.original_pages[1] = OriginalContent(
            id=1,
            post_type="page",
            title="Test",
            slug="test",
            author=2,
            status="publish",
            date="2024-01-01",
            date_gmt="2024-01-01",
            content_hash="abc123",
        )
        audit.original_posts[10] = OriginalContent(
            id=10,
            post_type="post",
            title="Test",
            slug="test",
            author=2,
            status="publish",
            date="2024-01-01",
            date_gmt="2024-01-01",
            content_hash="abc123",
        )

        assert audit_manager.is_original("page", 1) is True
        assert audit_manager.is_original("post", 10) is True
        assert audit_manager.is_original("page", 999) is False

    def test_start_migration(self, audit_manager):
        audit = audit_manager.load()
        audit.original_pages[1] = OriginalContent(
            id=1,
            post_type="page",
            title="Test",
            slug="test",
            author=2,
            status="publish",
            date="2024-01-01",
            date_gmt="2024-01-01",
            content_hash="abc123",
        )

        record = audit_manager.start_migration("page", 1, "Test", "test", "abc123")

        assert record.original_id == 1
        assert record.status == "in_progress"
        # Use public method to check migration map
        status = audit_manager.get_migration_status("page", 1)
        assert status is not None
        assert status.original_id == 1

    def test_complete_migration(self, audit_manager):
        audit = audit_manager.load()
        audit.original_pages[1] = OriginalContent(
            id=1,
            post_type="page",
            title="Test",
            slug="test",
            author=2,
            status="publish",
            date="2024-01-01",
            date_gmt="2024-01-01",
            content_hash="abc123",
        )
        audit_manager.start_migration("page", 1, "Test", "test", "abc123")

        audit_manager.complete_migration("page", 1, EXPECTED_MIGRATED_ID)

        record = audit_manager.get_migration_status("page", 1)
        assert record is not None
        assert record.status == "completed"
        assert record.migrated_id == EXPECTED_MIGRATED_ID

        # Check migrated_pages via stats
        stats = audit_manager.get_stats()
        assert stats["migrated_pages"] == 1

    def test_fail_migration(self, audit_manager):
        audit = audit_manager.load()
        audit.original_pages[1] = OriginalContent(
            id=1,
            post_type="page",
            title="Test",
            slug="test",
            author=2,
            status="publish",
            date="2024-01-01",
            date_gmt="2024-01-01",
            content_hash="abc123",
        )
        audit_manager.start_migration("page", 1, "Test", "test", "abc123")

        audit_manager.fail_migration("page", 1, "Validation error")

        record = audit_manager.get_migration_status("page", 1)
        assert record is not None
        assert record.status == "failed"
        assert record.error == "Validation error"

        # Check failed_pages via stats
        stats = audit_manager.get_stats()
        assert stats["failed_pages"] == 1

    def test_is_migrated(self, audit_manager):
        audit = audit_manager.load()
        audit.original_pages[1] = OriginalContent(
            id=1,
            post_type="page",
            title="Test",
            slug="test",
            author=2,
            status="publish",
            date="2024-01-01",
            date_gmt="2024-01-01",
            content_hash="abc123",
        )
        audit_manager.start_migration("page", 1, "Test", "test", "abc123")

        assert audit_manager.is_migrated("page", 1) is False

        audit_manager.complete_migration("page", 1, EXPECTED_MIGRATED_ID)

        assert audit_manager.is_migrated("page", 1) is True
        assert audit_manager.get_migrated_id("page", 1) == EXPECTED_MIGRATED_ID

    def test_rollback_migration(self, audit_manager):
        audit = audit_manager.load()
        audit.original_pages[1] = OriginalContent(
            id=1,
            post_type="page",
            title="Original",
            slug="original",
            author=2,
            status="publish",
            date="2024-01-01",
            date_gmt="2024-01-01",
            content_hash="abc123",
        )
        audit_manager.start_migration("page", 1, "Test", "test", "abc123")
        audit_manager.complete_migration("page", 1, EXPECTED_MIGRATED_ID)

        audit_manager.wp.delete.return_value = {"ok": True}
        audit_manager.wp.put.return_value = {"ok": True, "id": 1}

        success = audit_manager.rollback_migration("page", 1)

        assert success is True
        record = audit_manager.get_migration_status("page", 1)
        assert record is not None
        assert record.status == "rolled_back"
        assert record.migrated_id is None
        audit_manager.wp.delete.assert_called_with("pages/100", force=False)
        audit_manager.wp.put.assert_called()

    def test_bulk_rollback(self, audit_manager):
        audit = audit_manager.load()
        audit.original_pages[1] = OriginalContent(
            id=1,
            post_type="page",
            title="Original 1",
            slug="original-1",
            author=2,
            status="publish",
            date="2024-01-01",
            date_gmt="2024-01-01",
            content_hash="abc123",
        )
        audit.original_pages[2] = OriginalContent(
            id=2,
            post_type="page",
            title="Original 2",
            slug="original-2",
            author=2,
            status="publish",
            date="2024-01-01",
            date_gmt="2024-01-01",
            content_hash="def456",
        )

        audit_manager.start_migration("page", 1, "Test 1", "test-1", "abc123")
        audit_manager.complete_migration("page", 1, EXPECTED_MIGRATED_ID)
        audit_manager.start_migration("page", 2, "Test 2", "test-2", "def456")
        audit_manager.complete_migration("page", 2, 200)

        audit_manager.wp.delete.return_value = {"ok": True}
        audit_manager.wp.put.return_value = {"ok": True, "id": 1}

        result = audit_manager.bulk_rollback("page", audit_manager.wp)

        assert result["deleted"] == EXPECTED_DELETED
        assert result["restored"] == EXPECTED_RESTORED
        assert result["errors"] == []

    def test_get_stats(self, audit_manager):
        audit = audit_manager.load()
        audit.total_pages = TOTAL_PAGES
        audit.total_posts = TOTAL_POSTS
        audit.migrated_pages = MIGRATED_PAGES
        audit.migrated_posts = MIGRATED_POSTS
        audit.failed_pages = FAILED_PAGES
        audit.failed_posts = FAILED_POSTS

        stats = audit_manager.get_stats()

        assert stats["total_pages"] == TOTAL_PAGES
        assert stats["total_posts"] == TOTAL_POSTS
        assert stats["migrated_pages"] == MIGRATED_PAGES
        assert stats["migrated_posts"] == MIGRATED_POSTS
        assert stats["failed_pages"] == FAILED_PAGES
        assert stats["failed_posts"] == FAILED_POSTS


class TestAuditGuard:
    def test_protect_original_blocks_delete(self):
        audit = Mock()
        audit.is_original.return_value = True
        guard = AuditGuard(audit)

        @guard.protect_original
        def delete_item(_post_type, _item_id):
            return "deleted"

        with pytest.raises(PermissionError):
            delete_item("page", 1)

        audit.is_original.assert_called_with("page", 1)

    def test_protect_original_allows_non_original(self):
        audit = Mock()
        audit.is_original.return_value = False
        guard = AuditGuard(audit)

        @guard.protect_original
        def delete_item(_post_type, _item_id):
            return "deleted"

        result = delete_item("page", 999)
        assert result == "deleted"
