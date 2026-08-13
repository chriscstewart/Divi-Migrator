"""Offline simulation harness: in-memory fakes for WP + DiviOps clients.

These mirror the *real* ``divi_migrator.core.client`` method contracts closely
enough to run the full :class:`MigrationOrchestrator` pipeline with
``dry_run=False`` and no live site. Every write (create/update/rename/delete)
is recorded so tests can assert migration integrity.

The harness is intentionally faithful to the real client surface used by the
orchestrator:

* ``get_items`` / ``get_item`` serve seeded fixture content (originals +
  design-system records).
* ``post`` / ``put`` / ``delete`` mutate an in-memory page/post store and
  record the call in ``writes``.
* ``DiviOpsClient`` serves design-system endpoints and block validation the
  same way the live plugin would (so schema validation + verification run for
  real against generated markup).

This gives a true start-to-finish simulation: convert -> validate -> schema
check -> create draft -> verify -> publish -> rename original, all offline.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from divi_migrator.config import Config, WPSettings
from divi_migrator.core.client import DiviOpsClient, WPClient


# A minimal but realistic Avada page (Fusion Builder shortcodes) that the
# converter turns into Divi 5 blocks. Used as the default seeded original.
AVADA_FIXTURE = """[fusion_builder_container]
[fusion_builder_row]
[fusion_builder_column type="1_1"]
[fusion_text]Welcome to our clinic. We help with fertility and intimacy.[/fusion_text]
[fusion_button link="https://example.com/book"]Book a consultation[/fusion_button]
[fusion_imageframe image_id="42" image="https://example.com/img.jpg"]Photo[/fusion_imageframe]
[/fusion_builder_column]
[/fusion_builder_row]
[/fusion_builder_container]"""


def _wrap_wp_item(
    item_id: int, title: str, slug: str, content: str, author: int = 1
) -> dict[str, Any]:
    """Build a WP REST item shape (matching ``get_item`` responses)."""
    return {
        "id": item_id,
        "title": {"rendered": title},
        "slug": slug,
        "content": {"rendered": content, "raw": content},
        "author": author,
        "status": "publish",
        "date": "2024-01-01T00:00:00",
        "date_gmt": "2024-01-01T00:00:00",
        "modified": "2024-01-01T00:00:00",
        "modified_gmt": "2024-01-01T00:00:00",
        "categories": [5],
        "tags": [9],
        "featured_media": 42,
        "link": f"https://test.com/{slug}",
        "meta": {},
    }


class FakeWPStore:
    """In-memory store of pages/posts keyed by id, plus an id counter."""

    def __init__(self) -> None:
        self.items: dict[int, dict[str, Any]] = {}
        self._next_id = 1000

    def next_id(self) -> int:
        self._next_id += 1
        return self._next_id


_BLOCK_PATTERN = re.compile(r"<!--\s*wp:(divi/[a-z]+)")


class FakeWPClient(WPClient):
    """In-memory stand-in for :class:`WPClient` (WP REST surface only).

    Subclasses the real client so it is type-compatible with the orchestrator's
    ``wp: WPClient`` parameter, but overrides every network method with an
    in-memory implementation. ``__init__`` deliberately skips ``WPClient``
    construction (which would build a real ``requests.Session``).
    """

    def __init__(self, config: Config) -> None:
        # Skip WPClient.__init__ (builds a real session + rate limiter).
        self.config = config
        self.base_url = config.wp.url.rstrip("/")
        self.store = FakeWPStore()
        self.writes: list[dict[str, Any]] = []
        self.rate_calls = 0
        # Pagination cap to emulate the real shared-host ~100-row limit note.
        self.page_size_default = 50

    # --- rate limiting hooks (no-ops offline) ---
    def rate_limit(self) -> None:
        self.rate_calls += 1

    def _apply_rate_limit(self) -> None:
        self.rate_calls += 1

    # --- seeding helpers ---
    def seed(self, original_id: int, title: str, content: str, slug: str | None = None,
             author: int = 1) -> None:
        slug = slug or title.lower().replace(" ", "-")
        self.store.items[original_id] = _wrap_wp_item(original_id, title, slug, content, author)

    # --- read methods used by the orchestrator ---
    def get_items(self, post_type: str, page: int = 1, per_page: int = 50,
                  status: str = "any", context: str = "view", search: str | None = None,
                  author: int | None = None) -> list[dict[str, Any]]:
        items = list(self.store.items.values())
        if author is not None:
            items = [i for i in items if i.get("author") == author]
        if status != "any":
            items = [i for i in items if i.get("status") == status]
        if search:
            items = [
                i for i in items
                if search.lower() in (i.get("title", {}) or {}).get("rendered", "").lower()
                or search.lower() in (i.get("slug") or "").lower()
            ]
        return items

    def get_item(self, post_type: str, item_id: int) -> dict[str, Any]:
        item = self.store.items.get(item_id)
        if item is None:
            return {"ok": False, "error": "Not found", "status": 404}
        # Shallow copy so callers can't mutate the stored original in place.
        return dict(item)

    def get(self, endpoint: str, params: dict[str, Any] | None = None,
            skip_rate_limit: bool = False) -> Any:
        # audit post lookup / settings / design-system fallbacks
        if "wp/v2/settings" in endpoint:
            return {"page_on_front": None}
        if "users/me" in endpoint:
            return {"id": 7}
        return {"ok": True, "data": {}}

    # --- write methods (recorded) ---
    def _record(self, method: str, endpoint: str, payload: Any) -> None:
        self.writes.append({"method": method, "endpoint": endpoint, "payload": payload})

    def post(self, endpoint: str, json_data: dict[str, Any] | None = None,
             params: dict[str, Any] | None = None, skip_rate_limit: bool = False) -> dict[str, Any]:
        self._record("POST", endpoint, json_data)
        # category creation
        if endpoint == "categories":
            return {"id": 777, "slug": (json_data or {}).get("slug", "cat")}
        new_id = self.store.next_id()
        item = _wrap_wp_item(
            new_id,
            (json_data or {}).get("title", "Untitled"),
            (json_data or {}).get("slug", "untitled"),
            (json_data or {}).get("content", ""),
            author=7,
        )
        item["status"] = (json_data or {}).get("status", "draft")
        self.store.items[new_id] = item
        return {"ok": True, "id": new_id}

    def put(self, endpoint: str, json_data: dict[str, Any] | None = None) -> dict[str, Any]:
        self._record("PUT", endpoint, json_data)
        # endpoints look like "pages/123" or "posts/123"
        parts = endpoint.split("/")
        if len(parts) == 2 and parts[1].isdigit():
            item = self.store.items.get(int(parts[1]))
            if item is not None and json_data:
                for k, v in json_data.items():
                    if k in ("title", "slug", "status"):
                        if k == "title":
                            item["title"] = {"rendered": v}
                        else:
                            item[k] = v
                return {"ok": True, "id": int(parts[1])}
        # audit post content write -> treated as success
        if endpoint.startswith("pages/") and json_data and "content" in json_data:
            return {"ok": True, "id": int(parts[1])}
        return {"ok": True, "id": parts[1] if len(parts) > 1 else 0}

    def delete(self, endpoint: str, force: bool = False) -> dict[str, Any]:
        self._record("DELETE", endpoint, {"force": force})
        parts = endpoint.split("/")
        if len(parts) == 2 and parts[1].isdigit():
            self.store.items.pop(int(parts[1]), None)
        return {"ok": True}

    def update_meta(self, post_type: str, item_id: int, meta: dict[str, Any]) -> dict[str, Any]:
        self._record("META", f"{post_type}s/{item_id}", meta)
        item = self.store.items.get(item_id)
        if item is not None:
            item.setdefault("meta", {})
            item["meta"].update(meta)
        return {"ok": True}

    def bulk_delete_by_author(self, post_type: str, author_id: int, force: bool = False) -> int:
        deleted = 0
        for iid, item in list(self.store.items.items()):
            if item.get("author") == author_id:
                self.delete(f"{post_type}s/{iid}", force=force)
                deleted += 1
        return deleted


class FakeDiviOpsClient(DiviOpsClient):
    """In-memory stand-in for :class:`DiviOpsClient`.

    Subclasses the real client so ``isinstance(diviops, DiviOpsClient)`` checks
    in the verification engine pass, but overrides every network method with an
    in-memory implementation.
    """

    def __init__(self, wp_client: FakeWPClient | Any) -> None:
        # Deliberately skip DiviOpsClient.__init__ (which builds a real session).
        self.wp = wp_client
        self.base = "https://test.com"
        self.calls: list[dict[str, Any]] = []

    def _record(self, method: str, endpoint: str, payload: Any = None) -> None:
        self.calls.append({"method": method, "endpoint": endpoint, "payload": payload})

    def get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._record("GET", endpoint, params)
        # design-system endpoints return plausible empty/active payloads
        if "global-color" in endpoint:
            return {"ok": True, "data": {"customizer": {}}}
        if "global-font" in endpoint:
            return {"ok": True, "data": {"fonts": {}}}
        if "preset" in endpoint:
            return {"ok": True, "data": {"divi5_presets": {}}}
        if "variable" in endpoint:
            return {"ok": True, "data": {"variables": []}}
        if endpoint.endswith("page/get-layout") or "get-layout" in endpoint:
            return self._fake_layout()
        if "ping" in endpoint:
            return {"ok": True}
        return {"ok": True, "data": {}}

    def post(self, endpoint: str, json_data: dict[str, Any] | None = None,
             params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._record("POST", endpoint, json_data)
        if endpoint == "validate/blocks":
            content = (json_data or {}).get("content", "")
            return self._validate_blocks(content)
        if "page/update-content" in endpoint:
            return {"ok": True}
        if "page/update" in endpoint or "page/update-status" in endpoint:
            return {"ok": True}
        if "meta/flush-cache" in endpoint:
            return {"ok": True}
        return {"ok": True}

    def create_content(self, title: str, content: str = "", status: str = "draft",
                       post_type: str = "page") -> dict[str, Any]:
        # Delegate creation to the WP store (mirrors real client routing WP REST).
        created = self.wp.post(f"{post_type}s", json_data={
            "title": title, "content": content, "status": status})
        page_id = created.get("id")
        return {"ok": True, "id": page_id, "data": {"page_id": page_id}}

    def update_page_content(self, page_id: int, content: str) -> dict[str, Any]:
        self._record("POST", f"page/update-content/{page_id}", {"content": content})
        return {"ok": True}

    def get_page_layout(self, page_id: int) -> dict[str, Any]:
        self._record("GET", f"page/get-layout/{page_id}")
        return self._fake_layout()

    def validate_blocks(self, content: str) -> dict[str, Any]:
        """Mirror the real DiviOpsClient.validate_blocks endpoint."""
        return self._validate_blocks(content)

    # --- helpers ---
    def _validate_blocks(self, content: str) -> dict[str, Any]:
        # Reuse the real schema validator so generated markup is checked for real.
        from divi_migrator.core.schema_validator import validate_divi5_blocks
        ok, errors = validate_divi5_blocks(content)
        return {"ok": ok, "errors": errors}

    def _fake_layout(self) -> dict[str, Any]:
        # A layout response with one section/row/column + a text module so the
        # verification engine counts real blocks against migrated drafts.
        return {
            "ok": True,
            "data": {
                "blocks": [
                    {"block_name": "divi/section", "attributes": {},
                     "inner_blocks": [
                         {"block_name": "divi/row", "attributes": {},
                          "inner_blocks": [
                              {"block_name": "divi/text", "attributes": {}, "inner_blocks": []}
                          ]}
                     ]}
                ]
            },
        }


def make_config() -> Config:
    """Build a real Config object with dummy WP credentials (no network).

    The audit backup dir is isolated to a fresh temp dir per call so tests
    never leak audit state across runs (the real AuditManager persists a
    local JSON backup that it reloads on init).
    """
    import os
    import tempfile

    os.environ.setdefault("WP_URL", "https://test.com")
    os.environ.setdefault("WP_USER", "migration-bot")
    os.environ.setdefault("WP_APP_PASSWORD", "test-password")
    cfg = Config(
        wp=WPSettings(
            url="https://test.com",
            user="migration-bot",
            app_password=os.environ["WP_APP_PASSWORD"],
            ssl_verify=True,
            timeout=60,
        )
    )
    cfg.audit.backup_dir = Path(tempfile.mkdtemp(prefix="divi_audit_"))
    return cfg


def build_harness(
    originals: list[dict[str, Any]] | None = None,
) -> tuple[FakeWPClient, FakeDiviOpsClient, Config]:
    """Construct a fake WP + DiviOps harness seeded with originals.

    ``originals`` is a list of dicts: {id, title, content, slug?, author?}.
    Returns (wp, diviops, config) ready to hand to MigrationOrchestrator.
    """
    cfg = make_config()
    wp = FakeWPClient(cfg)
    if originals:
        for o in originals:
            wp.seed(
                original_id=o["id"],
                title=o["title"],
                content=o.get("content", AVADA_FIXTURE),
                slug=o.get("slug"),
                author=o.get("author", 1),
            )
    diviops = FakeDiviOpsClient(wp)
    return wp, diviops, cfg
