"""Checkpoint management for resumable migrations."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class CheckpointManager:
    """Manages checkpoint persistence for resumable migrations."""

    def __init__(self, config: Any) -> None:
        self.checkpoint_dir = Path(config.migration.checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def _checkpoint_path(self, post_type: str) -> Path:
        return self.checkpoint_dir / f"migration_checkpoint_{post_type}.json"

    def load(self, post_type: str) -> dict[str, Any]:
            """Load checkpoint data for post type."""
            path = self._checkpoint_path(post_type)
            if path.exists():
                with path.open() as f:
                    data: dict[str, Any] = json.load(f)
                    return data
            return {
                "processed": [],
                "failed": [],
                "started_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

    def save(self, post_type: str, data: dict[str, Any]) -> None:
        """Save checkpoint data."""
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        path = self._checkpoint_path(post_type)
        tmp_path = path.with_suffix(".tmp")
        with tmp_path.open("w") as f:
            json.dump(data, f, indent=2)
        tmp_path.replace(path)

    def mark_processed(
        self, post_type: str, item_id: int, title: str, content_len: int, meta: dict[str, Any]
    ) -> None:
        """Mark an item as successfully processed."""
        data = self.load(post_type)
        record = {
            "id": item_id,
            "title": title,
            "content_length": content_len,
            "meta": meta,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        data["processed"].append(record)
        self.save(post_type, data)

    def mark_failed(self, post_type: str, item_id: int, title: str, error: str) -> None:
        """Mark an item as failed."""
        data = self.load(post_type)
        record = {
            "id": item_id,
            "title": title,
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        data["failed"].append(record)
        self.save(post_type, data)

    def is_processed(self, post_type: str, item_id: int) -> bool:
        """Check if item already processed."""
        data = self.load(post_type)
        return any(r["id"] == item_id for r in data.get("processed", []))

    def get_stats(self, post_type: str) -> dict[str, Any]:
        """Get migration statistics."""
        data = self.load(post_type)
        return {
            "processed": len(data.get("processed", [])),
            "failed": len(data.get("failed", [])),
            "started_at": data.get("started_at"),
            "updated_at": data.get("updated_at"),
        }

    def clear(self, post_type: str) -> None:
        """Clear checkpoint for post type."""
        path = self._checkpoint_path(post_type)
        if path.exists():
            path.unlink()