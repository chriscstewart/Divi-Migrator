"""Runtime guard preventing operations on audited originals."""

from __future__ import annotations

import logging
from functools import wraps
from collections.abc import Callable
from typing import Any

from divi_migrator.core.audit import AuditManager

logger = logging.getLogger(__name__)


class AuditGuard:
    """Runtime guard that prevents dangerous operations on audited originals."""

    def __init__(self, audit: AuditManager) -> None:
        self.audit = audit

    def protect_original(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator that blocks operations on original content."""

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if len(args) >= 2:  # noqa: PLR2004
                post_type = args[0]
                item_id = args[1]
                if isinstance(post_type, str) and isinstance(item_id, int) and self.audit.is_original(post_type, item_id):  # noqa: E501
                    raise PermissionError(  # noqa: TRY003
                        f"BLOCKED: Attempt to modify original {post_type} #{item_id}. "
                        f"Original content is protected by audit."
                    )
            return func(*args, **kwargs)

        return wrapper

    def protect_migrated(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator that ensures migrated content has valid audit record."""

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if len(args) >= 2:  # noqa: PLR2004
                post_type = args[0]
                item_id = args[1]
                if isinstance(post_type, str) and isinstance(item_id, int):
                    record = self.audit.get_migration_status(post_type, item_id)
                    if not record or record.status != "completed":
                        logger.warning(
                            f"Operating on migrated {post_type} #{item_id} without completed audit record"  # noqa: E501
                        )
            return func(*args, **kwargs)

        return wrapper


def create_audit_guard(audit: AuditManager) -> AuditGuard:
    """Factory function to create audit guard."""
    return AuditGuard(audit)
