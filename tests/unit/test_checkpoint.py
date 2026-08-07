"""Tests for checkpoint management."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock

from divi_migrator.core.checkpoint import CheckpointManager

# Test constants
TEST_ID_1 = 123
TEST_ID_2 = 456
TEST_ID_3 = 789
TEST_ID_4 = 999
CONTENT_LEN_1 = 100
CONTENT_LEN_2 = 200
EXPECTED_PROCESSED = 2
EXPECTED_FAILED = 1


class TestCheckpointManager:
    """Tests for CheckpointManager."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def config(self):
        config = Mock()
        config.migration.checkpoint_dir = "./checkpoints"
        return config

    @pytest.fixture
    def manager(self, config, temp_dir):
        config.migration.checkpoint_dir = temp_dir
        return CheckpointManager(config)

    def test_load_empty_checkpoint(self, manager):
        """Test loading when no checkpoint exists."""
        cp = manager.load("page")
        assert cp["processed"] == []
        assert cp["failed"] == []
        assert "started_at" in cp

    def test_save_and_load_checkpoint(self, manager):
        """Test saving and loading checkpoint."""
        cp = {
            "processed": [{"id": TEST_ID_1, "title": "Test"}],
            "failed": [],
            "started_at": "2024-01-01T00:00:00",
        }
        manager.save("page", cp)

        loaded = manager.load("page")
        assert len(loaded["processed"]) == 1
        assert loaded["processed"][0]["id"] == TEST_ID_1

    def test_mark_processed(self, manager):
        """Test marking an item as processed."""
        manager.mark_processed(
            post_type="page",
            item_id=TEST_ID_1,
            title="Test Page",
            content_len=1000,
            meta={"source_format": "avada", "source_id": TEST_ID_1},
        )

        cp = manager.load("page")
        assert len(cp["processed"]) == 1
        assert cp["processed"][0]["id"] == TEST_ID_1
        assert cp["processed"][0]["title"] == "Test Page"

    def test_mark_failed(self, manager):
        """Test marking an item as failed."""
        manager.mark_failed(
            post_type="page",
            item_id=TEST_ID_2,
            title="Failed Page",
            error="Connection timeout",
        )

        cp = manager.load("page")
        assert len(cp["failed"]) == 1
        assert cp["failed"][0]["id"] == TEST_ID_2
        assert cp["failed"][0]["error"] == "Connection timeout"

    def test_is_processed(self, manager):
        """Test checking if item already processed."""
        manager.mark_processed("page", TEST_ID_3, "Processed", CONTENT_LEN_1, {})

        assert manager.is_processed("page", TEST_ID_3) is True
        assert manager.is_processed("page", TEST_ID_4) is False

    def test_get_stats(self, manager):
        """Test getting checkpoint statistics."""
        manager.mark_processed("page", 1, "One", CONTENT_LEN_1, {})
        manager.mark_processed("page", 2, "Two", CONTENT_LEN_2, {})
        manager.mark_failed("page", 3, "Three", "Error")

        stats = manager.get_stats("page")
        assert stats["processed"] == EXPECTED_PROCESSED
        assert stats["failed"] == EXPECTED_FAILED
