"""WordPress and DiviOps REST API clients with retry logic, rate limiting, and audit guard."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any, cast

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from divi_migrator.config import Config

logger = logging.getLogger(__name__)

# HTTP status codes
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_TOO_MANY_REQUESTS = 429


class TokenBucketRateLimiter:
    """Token bucket rate limiter for API requests."""

    def __init__(self, rate: float, burst: int):
        """
        Args:
            rate: Requests per second (e.g., 0.5 for 2 seconds between requests)
            burst: Maximum burst capacity
        """
        self.rate = rate
        self.burst = burst
        self.tokens = float(burst)
        self.last_update = time.monotonic()
        self._lock = threading.Lock()

    def take(self) -> None:
        """Take a token, blocking until one is available."""
        with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self.last_update
                self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
                self.last_update = now

                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return

                # Wait for next token
                wait_time = (1.0 - self.tokens) / self.rate
                time.sleep(wait_time)


class WPClient:
    """WordPress REST API client with retry logic, rate limiting, and auth."""

    def __init__(self, config: Config, audit_guard: Any = None):
        self.config = config
        self.base_url = config.wp.url.rstrip("/")
        self.session = requests.Session()
        self.session.auth = (config.wp.user, config.wp.app_password)
        self.session.verify = config.wp.ssl_verify
        self.request_timeout = config.wp.timeout
        self.audit_guard = audit_guard

        # Rate limiting: default 0.5 req/sec (2s between requests)
        self.rate_limiter = TokenBucketRateLimiter(
            rate=config.migration.rate_limit if hasattr(config.migration, "rate_limit") else 0.5,
            burst=3
        )

        # Retry strategy
        retry_strategy = Retry(
            total=config.migration.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=[
                "HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST",
            ],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _url(self, endpoint: str) -> str:
        """Build full URL for WP REST endpoint."""
        endpoint = endpoint.lstrip("/")
        return f"{self.base_url}/wp-json/wp/v2/{endpoint}"

    def _diviops_url(self, endpoint: str) -> str:
        """Build full URL for DiviOps endpoint."""
        endpoint = endpoint.lstrip("/")
        return f"{self.base_url}/wp-json/diviops/v1/{endpoint}"

    def _apply_rate_limit(self) -> None:
        """Apply rate limiting before request."""
        self.rate_limiter.take()

    def _apply_rate_limit_skip(self) -> None:
        """Skip rate limiting for internal requests (audit loading)."""

    def get(self, endpoint: str, params: dict[str, Any] | None = None, skip_rate_limit: bool = False) -> dict[str, Any]:  # noqa: E501
        """GET request with retry and rate limiting."""
        if not skip_rate_limit:
            self._apply_rate_limit()
        if endpoint.startswith(("http://", "https://")):
            url = endpoint
        elif endpoint.startswith("diviops/"):
            url = f"{self.base_url}/wp-json/diviops/v1/{endpoint.replace('diviops/', '')}"
        else:
            url = self._url(endpoint)
        return self._request("GET", url, params=params)

    def post(
        self,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        skip_rate_limit: bool = False,
    ) -> dict[str, Any]:
        """POST request with retry and rate limiting."""
        if not skip_rate_limit:
            self._apply_rate_limit()
        if endpoint.startswith("diviops/"):
            url = f"{self.base_url}/wp-json/diviops/v1/{endpoint.replace('diviops/', '')}"
        else:
            url = self._url(endpoint)
        return self._request("POST", url, json=json_data, params=params)

    def put(self, endpoint: str, json_data: dict[str, Any] | None = None) -> dict[str, Any]:
        """PUT request with retry, rate limiting, and audit guard."""
        self._apply_rate_limit()
        # Audit guard for PUT
        if self.audit_guard:
            parts = endpoint.split("/")
            if len(parts) >= 2 and parts[0] in ("pages", "posts"):  # noqa: PLR2004
                post_type = parts[0].rstrip("s")
                try:
                    item_id = int(parts[1])
                    if self.audit_guard.audit.is_original(post_type, item_id):
                        logger.warning(f"Updating original {post_type} #{item_id} - ensure this is intentional rollback")  # noqa: E501
                except (ValueError, IndexError):
                    pass
        return self._request("PUT", self._url(endpoint), json=json_data)

    def delete(self, endpoint: str, force: bool = False) -> dict[str, Any]:
        """DELETE request with audit guard - NEVER allow force=True on originals."""
        self._apply_rate_limit()
        if self.audit_guard:
            parts = endpoint.split("/")
            if len(parts) >= 2 and parts[0] in ("pages", "posts"):  # noqa: PLR2004
                post_type = parts[0].rstrip("s")
                try:
                    item_id = int(parts[1])
                    if self.audit_guard.audit.is_original(post_type, item_id):
                        if force:
                            raise PermissionError(  # noqa: TRY003
                                f"BLOCKED: force=True delete on original {post_type} #{item_id}. "
                                f"Originals can only be trashed (force=False)."
                            )
                        logger.warning(f"Trashing original {post_type} #{item_id} - ensure this is intentional rollback")  # noqa: E501
                except (ValueError, IndexError):
                    pass

        # Force force=False for safety
        if force:
            logger.warning("force=True overridden to force=False for safety")
            force = False

        return self._request("DELETE", self._url(endpoint), params={"force": "false"})

    def _request(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        """Execute request with retry logic and rate limiting."""
        logger.debug("%s %s", method, url)
        kwargs.setdefault("timeout", self.request_timeout)

        # Handle rate limiting from server
        max_retries = 3
        for attempt in range(max_retries):
            resp = self.session.request(method, url, **kwargs)

            if resp.status_code == HTTP_TOO_MANY_REQUESTS:
                retry_after = int(resp.headers.get("Retry-After", "5"))
                logger.warning(f"Rate limited (429), waiting {retry_after}s before retry")
                time.sleep(retry_after)
                continue

            if resp.status_code == HTTP_UNAUTHORIZED:
                raise PermissionError("Authentication failed - check WP credentials")  # noqa: TRY003

            if resp.status_code == HTTP_FORBIDDEN:
                raise PermissionError("Forbidden - check permissions")  # noqa: TRY003

            if resp.status_code == HTTP_NOT_FOUND:
                return {"ok": False, "error": "Not found", "status": HTTP_NOT_FOUND}

            try:
                resp.raise_for_status()
            except requests.HTTPError:
                if attempt == max_retries - 1:
                    raise
                time.sleep(2 ** attempt)  # Exponential backoff
                continue

            try:
                return cast(dict[str, Any], resp.json())
            except Exception:
                return {"ok": True, "data": resp.text, "status": resp.status_code}

        raise RuntimeError(f"Max retries exceeded for {method} {url}")  # noqa: TRY003

    # Convenience methods
    def get_items(  # noqa: PLR0913
        self, post_type: str, page: int = 1, per_page: int = 50, status: str = "any", context: str = "view", search: str | None = None  # noqa: E501
    ) -> list[dict[str, Any]]:
        """Get items of a post type."""
        if post_type == "page":
            endpoint = "pages"
        elif post_type == "post":
            endpoint = "posts"
        else:
            endpoint = f"{post_type}s"
        params = {
            "page": page,
            "per_page": per_page,
            "status": status,
            "orderby": "id",
            "order": "asc",
            "context": context,
        }
        if search:
            params["search"] = search
        resp = self.get(endpoint, params=params)
        return resp if isinstance(resp, list) else []

    def get_item(self, post_type: str, item_id: int) -> dict[str, Any]:
        """Get a single item."""
        if post_type == "page":
            endpoint = "pages"
        elif post_type == "post":
            endpoint = "posts"
        elif post_type == "media":
            endpoint = "media"
        else:
            endpoint = f"{post_type}s"
        resp = self.get(f"{endpoint}/{item_id}")
        return resp if isinstance(resp, dict) else {}

    def create_draft(self, post_type: str, title: str, content: str = "") -> dict[str, Any]:
        """Create a draft page/post."""
        return self.post(f"{post_type}s", json_data={"title": title, "status": "draft", "content": content})  # noqa: E501

    def update_meta(self, post_type: str, item_id: int, meta: dict[str, Any]) -> dict[str, Any]:
        """Update post meta."""
        return self.put(f"{post_type}s/{item_id}", json_data={"meta": meta})

    def bulk_delete_by_author(self, post_type: str, author_id: int, force: bool = False) -> int:
        """Delete all content by specific author (for AI cleanup)."""
        if force:
            raise PermissionError("force=True not allowed for bulk delete")  # noqa: TRY003

        deleted = 0
        page = 1
        while True:
            items = self.get_items(post_type, page=page, per_page=100, status="any")
            if not items:
                break

            for item in items:
                if item.get("author") == author_id:
                    self.delete(f"{post_type}s/{item['id']}", force=False)
                    deleted += 1

            if len(items) < 100:  # noqa: PLR2004
                break
            page += 1

        return deleted


class DiviOpsClient:
    """DiviOps-specific operations via REST API."""

    def __init__(self, wp_client: WPClient):
        self.wp = wp_client
        self.base = wp_client.base_url

    def _request(self, method: str, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        """Make authenticated request to DiviOps endpoint."""
        url = f"{self.base}/wp-json/diviops/v1/{endpoint.lstrip('/')}"
        kwargs.setdefault("timeout", self.wp.request_timeout)
        resp = self.wp.session.request(method, url, **kwargs)

        if resp.status_code == 401:  # noqa: PLR2004
            raise PermissionError("DiviOps authentication failed - check DiviOps credentials")  # noqa: TRY003
        if resp.status_code == 403:  # noqa: PLR2004
            raise PermissionError("DiviOps forbidden - check permissions")  # noqa: TRY003
        if resp.status_code == 404:  # noqa: PLR2004
            return {"ok": False, "error": "Not found", "status": 404}

        resp.raise_for_status()
        try:
            return cast(dict[str, Any], resp.json())
        except Exception:
            return {"ok": True, "data": resp.text, "status": resp.status_code}

    def get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request("GET", endpoint, params=params)

    def post(
        self,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._request("POST", endpoint, json=json_data, params=params)

    # Page operations
    def create_content(
        self,
        title: str,
        content: str = "",
        status: str = "draft",
        post_type: str = "page",
    ) -> dict[str, Any]:
        """Create a new page or post with Divi 5 block content.

        Posts are created via the WP REST 'posts' endpoint (post-type correct)
        and then have their Divi block content pushed through DiviOps so they
        render in Divi 5. Pages use the DiviOps 'page/create' endpoint (which
        is page-only and ignores any 'type' field).

        Returns a normalized dict: {"ok": True, "id": <id>, "data": {"page_id": <id>}}.
        """
        if post_type == "post":
            created = self.wp.post(
                "posts",
                json_data={"title": title, "content": content, "status": status},
            )
            post_id = created.get("id") if isinstance(created, dict) else None
            if not post_id:
                return {"ok": False, "error": "Failed to create post", "data": created}
            # Ensure Divi 5 block content is applied (posts endpoint stores raw HTML).
            self.update_page_content(post_id, content)
            return {"ok": True, "id": post_id, "data": {"page_id": post_id}}

        return self.post(
            "page/create",
            json_data={"title": title, "content": content, "status": status, "type": post_type},
        )

    def update_page_content(self, page_id: int, content: str) -> dict[str, Any]:
        """Update page content via DiviOps."""
        return self.post(f"page/update-content/{page_id}", json_data={"content": content})

    def update_page(
        self, page_id: int, title: str, content: str = "", status: str = "publish", post_type: str = "page"  # noqa: E501
    ) -> dict[str, Any]:
        """Update an existing page via DiviOps."""
        return self.post(
            f"page/update/{page_id}",
            json_data={"title": title, "content": content, "status": status, "type": post_type},
        )

    def update_page_status(self, page_id: int, status: str) -> dict[str, Any]:
        """Update page status (publish, draft, etc.)."""
        return self.post(f"page/update-status/{page_id}", json_data={"status": status})

    def get_page(self, page_id: int) -> dict[str, Any]:
        """Get page data including raw Divi content."""
        return self.get(f"page/get/{page_id}")

    def get_page_layout(self, page_id: int) -> dict[str, Any]:
        """Get page layout for verification."""
        return self.get(f"page/get-layout/{page_id}")

    def flush_cache(self, post_id: int) -> dict[str, Any]:
        """Flush Divi cache for post."""
        return self.post("meta/flush-cache", json_data={"post_id": post_id})

    # Design system endpoints
    def get_global_colors(self) -> dict[str, Any]:
        return self.get("global-color/list")

    def get_global_fonts(self) -> dict[str, Any]:
        return self.get("global-font/list")

    def get_presets(self) -> dict[str, Any]:
        return self.get("preset/list")

    def get_variables(self) -> dict[str, Any]:
        return self.get("variable/list")

    def validate_blocks(self, content: str) -> dict[str, Any]:
        return self.post("validate/blocks", json_data={"content": content})

    def get_design_system(self) -> dict[str, Any]:
        return {
            "colors": self.get_global_colors(),
            "fonts": self.get_global_fonts(),
            "presets": self.get_presets(),
            "variables": self.get_variables(),
        }

    def ping(self) -> dict[str, Any]:
        """Health check - verify DiviOps plugin is active and reachable."""
        try:
            resp = self.get("meta/ping")
            return {"ok": True, "data": resp}  # noqa: TRY300
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # Media operations
    def upload_media(self, file_path: str) -> dict[str, Any]:
        """Upload media file to WordPress."""
        with Path(file_path).open("rb") as f:
            files = {"file": f}
            return self._request("POST", "media", files=files)

    # Theme Builder endpoints
    def get_tb_templates(self) -> dict[str, Any]:
        return self.get("tb-template/list")

    def get_tb_layout(self, layout_id: int) -> dict[str, Any]:
        return self.get(f"tb-layout/get/{layout_id}")

    # Library endpoints
    def get_library_items(self, layout_type: str | None = None) -> dict[str, Any]:
        params = {"type": layout_type} if layout_type else None
        return self.get("library/list", params=params)

    def save_library_item(self, title: str, content: str, layout_type: str, scope: str = "non_global") -> dict[str, Any]:  # noqa: E501
        return self.post("library/save", json_data={
            "title": title, "content": content, "layout_type": layout_type, "scope": scope
        })


def create_clients(config: Config, audit_guard: Any = None) -> tuple[WPClient, DiviOpsClient]:
    """Create WP and DiviOps clients."""
    wp = WPClient(config, audit_guard)
    diviops = DiviOpsClient(wp)
    return wp, diviops
