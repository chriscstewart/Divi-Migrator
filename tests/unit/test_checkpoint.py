"""Tests for checkpoint management."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock

from divi_migrator.core.checkpoint import CheckpointManager


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
            "processed": [{"id": 123, "title": "Test"}],
            "failed": [],
            "started_at": "2024-01-01T00:00:00",
        }
        manager.save("page", cp)

        loaded = manager.load("page")
        assert len(loaded["processed"]) == 1
        assert loaded["processed"][0]["id"] == 123

    def test_mark_processed(self, manager):
        """Test marking an item as processed."""
        manager.mark_processed(
            post_type="page",
            item_id=123,
            title="Test Page",
            content_len=1000,
            meta={"source_format": "avada", "source_id": 123},
        )

        cp = manager.load("page")
        assert len(cp["processed"]) == 1
        assert cp["processed"][0]["id"] == 123
        assert cp["processed"][0]["title"] == "Test Page"

    def test_mark_failed(self, manager):
        """Test marking an item as failed."""
        manager.mark_failed(
            post_type="page",
            item_id=456,
            title="Failed Page",
            error="Connection timeout",
        )

        cp = manager.load("page")
        assert len(cp["failed"]) == 1
        assert cp["failed"][0]["id"] == 456
        assert cp["failed"][0]["error"] == "Connection timeout"

    def test_is_processed(self, manager):
        """Test checking if item already processed."""
        manager.mark_processed("page", 789, "Processed", 100, {})

        assert manager.is_processed("page", 789) is True
        assert manager.is_processed("page", 999) is False

    def test_get_stats(self, manager):
        """Test getting checkpoint statistics."""
        manager.mark_processed("page", 1, "One", 100, {})
        manager.mark_processed("page", 2, "Two", 200, {})
        manager.mark_failed("page", 3, "Three", "Error")

        stats = manager.get_stats("page")
        assert stats["processed"] == 2
        assert stats["failed"] == 1
