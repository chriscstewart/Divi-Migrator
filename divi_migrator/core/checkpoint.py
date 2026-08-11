"""Checkpoint management for resumable migrations."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from divi_migrator.config import Config


class CheckpointManager:
    """Manages checkpoint persistence for resumable migrations."""

    def __init__(self, config: Config) -> None:
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

    def save(self, post_type: str, items: list[dict[str, Any]] | dict[str, Any]) -> None:
        """Save checkpoint data.

        Accepts either:
        - New format: list of items with 'status' key (from orchestrator)
        - Old format: dict with 'processed' and 'failed' keys (from tests)
        """
        # Handle old format (dict with processed/failed keys)
        if isinstance(items, dict):
            checkpoint_data = {
                "processed": items.get("processed", []),
                "failed": items.get("failed", []),
                "started_at": items.get("started_at", datetime.now(timezone.utc).isoformat()),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        else:
            # Handle new format (list of items with status)
            checkpoint_data = {
                "processed": [],
                "failed": [],
                "started_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

            for item in items:
                if isinstance(item, dict):
                    meta = item.get("meta", {})
                    if item.get("status") in ("completed", "dry_run"):
                        checkpoint_data["processed"].append(
                            {
                                "id": item.get("id"),
                                "title": item.get("title"),
                                "content_length": meta.get("source_content_hash", ""),
                                "meta": meta,
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            }
                        )
                    elif item.get("status") == "failed":
                        checkpoint_data["failed"].append(
                            {
                                "id": item.get("id"),
                                "title": item.get("title"),
                                "error": item.get("error"),
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            }
                        )

        path = self._checkpoint_path(post_type)
        tmp_path = path.with_suffix(".tmp")
        with tmp_path.open("w") as f:
            json.dump(checkpoint_data, f, indent=2)
        # Windows: use os.replace with retry for file locking issues
        max_retries = 5
        for i in range(max_retries):
            try:
                Path(tmp_path).replace(path)
                break
            except PermissionError:
                if i == max_retries - 1:
                    raise
                import time  # noqa: PLC0415

                time.sleep(0.1 * (i + 1))

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
