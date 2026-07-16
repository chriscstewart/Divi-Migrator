"""WordPress and DiviOps REST API clients with retry logic."""

from __future__ import annotations

import logging
from typing import Any, Optional, cast

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from divi_migrator.config import Config

logger = logging.getLogger(__name__)

# HTTP status codes
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404


class WPClient:
    """WordPress REST API client with retry logic and auth."""

    def __init__(self, config: Config):
        self.config = config
        self.base_url = config.wp.url.rstrip("/")
        self.session = requests.Session()
        self.session.auth = (config.wp.user, config.wp.app_password)
        self.session.verify = config.wp.ssl_verify

        # Store timeout separately since Session doesn't have a timeout attribute
        self.request_timeout = config.wp.timeout

        # Retry strategy
        retry_strategy = Retry(
            total=config.migration.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=[
                "HEAD",
                "GET",
                "PUT",
                "DELETE",
                "OPTIONS",
                "TRACE",
                "POST",
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

    def get(self, endpoint: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """GET request with retry."""
        url = (
            self._url(endpoint)
            if not endpoint.startswith("diviops/")
            else f"{self.base_url}/wp-json/diviops/v1/{endpoint.replace('diviops/', '')}"
        )
        return self._request("GET", url, params=params)

    def post(
        self,
        endpoint: str,
        json_data: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """POST request with retry."""
        url = (
            self._url(endpoint)
            if not endpoint.startswith("diviops/")
            else f"{self.base_url}/wp-json/diviops/v1/{endpoint.replace('diviops/', '')}"
        )
        return self._request("POST", url, json=json_data, params=params)

    def put(self, endpoint: str, json_data: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """PUT request with retry."""
        url = (
            self._url(endpoint)
            if not endpoint.startswith("diviops/")
            else f"{self.base_url}/wp-json/diviops/v1/{endpoint.replace('diviops/', '')}"
        )
        return self._request("PUT", url, json=json_data)

    def delete(self, endpoint: str, force: bool = True) -> dict[str, Any]:
        """DELETE request with retry."""
        url = self._url(endpoint)
        params = {"force": "true"} if force else {}
        return self._request("DELETE", url, params=params)

    def _request(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        """Execute request with retry logic."""
        logger.debug("%s %s", method, url)
        # Set timeout from config
        kwargs.setdefault("timeout", self.request_timeout)
        resp = self.session.request(method, url, **kwargs)

        if resp.status_code == HTTP_UNAUTHORIZED:
            raise PermissionError("Authentication failed - check WP credentials")

        if resp.status_code == HTTP_FORBIDDEN:
            raise PermissionError("Forbidden - check permissions")

        if resp.status_code == HTTP_NOT_FOUND:
            return {"ok": False, "error": "Not found", "status": HTTP_NOT_FOUND}

        resp.raise_for_status()

        try:
            return cast(dict[str, Any], resp.json())
        except Exception:
            return {"ok": True, "data": resp.text, "status": resp.status_code}

    # Convenience methods
    def get_items(
        self, post_type: str, page: int = 1, per_page: int = 50, status: str = "any"
    ) -> list[dict[str, Any]]:
        """Get items of a post type."""
        url = f"{self.base_url}/wp-json/wp/v2/{post_type}s"
        params = {
            "page": page,
            "per_page": per_page,
            "status": status,
            "orderby": "id",
            "order": "asc",
        }
        resp = self.get(url, params=params)
        return resp if isinstance(resp, list) else []

    def get_item(self, post_type: str, item_id: int) -> dict[str, Any]:
        """Get a single item."""
        url = f"{self.base_url}/wp-json/wp/v2/{post_type}s/{item_id}"
        resp = self.get(url)
        return resp if isinstance(resp, dict) else {}

    def create_draft(self, post_type: str, title: str, content: str = "") -> dict[str, Any]:
        """Create a draft page/post."""
        url = f"{self.base_url}/wp-json/wp/v2/{post_type}s"
        data = {"title": title, "status": "draft", "content": content}
        return self.post(url, json_data=data)

    def update_meta(self, post_type: str, item_id: int, meta: dict[str, Any]) -> dict[str, Any]:
        """Update post meta."""
        url = f"{self.base_url}/wp-json/wp/v2/{post_type}s/{item_id}"
        return self.put(url, json_data={"meta": meta})


class DiviOpsClient:
    """DiviOps-specific operations via REST API."""

    def __init__(self, wp_client: WPClient):
        self.wp = wp_client
        self.base = wp_client.base_url

    def _url(self, endpoint: str) -> str:
        return f"{self.wp.base_url}/wp-json/diviops/v1/{endpoint.lstrip('/')}"

    def _handle(self, resp: requests.Response) -> dict[str, Any]:
        if not resp.ok:
            raise RuntimeError(f"DiviOps error {resp.status_code}: {resp.text}")
        return cast(dict[str, Any], resp.json())

    # Page operations
    def create_page(
        self, title: str, content: str = "", status: str = "draft", post_type: str = "page"
    ) -> dict[str, Any]:
        """Create a new page via DiviOps."""
        resp = self.wp.session.post(
            f"{self.wp.base_url}/wp-json/diviops/v1/page/create",
            json={"title": title, "content": content, "status": status, "type": post_type},
            timeout=30,
        )
        self._handle(resp)
        return cast(dict[str, Any], resp.json())

    def update_page_content(self, page_id: int, content: str) -> dict[str, Any]:
        """Update page content via DiviOps."""
        resp = self.wp.session.post(
            f"{self.wp.base_url}/wp-json/diviops/v1/page/update-content/{page_id}",
            json={"content": content},
            timeout=60,
        )
        self._handle(resp)
        return cast(dict[str, Any], resp.json())

    def get_page(self, page_id: int) -> dict[str, Any]:
        """Get page data including raw Divi content."""
        resp = requests.get(f"{self.wp.base_url}/wp-json/diviops/v1/page/get/{page_id}", timeout=30)
        self._handle(resp)
        return cast(dict[str, Any], resp.json())

    def get_page_layout(self, page_id: int) -> dict[str, Any]:
        """Get page layout for verification."""
        resp = requests.get(
            f"{self.wp.base_url}/wp-json/diviops/v1/page/get-layout/{page_id}", timeout=30
        )
        self._handle(resp)
        return cast(dict[str, Any], resp.json())

    def update_page_status(self, page_id: int, status: str) -> dict[str, Any]:
        """Update page status (publish, draft, etc.)."""
        resp = requests.post(
            f"{self.wp.base_url}/wp-json/diviops/v1/page/update-status/{page_id}",
            json={"status": status},
            timeout=30,
        )
        self._handle(resp)
        return cast(dict[str, Any], resp.json())

    def flush_cache(self, post_id: int) -> dict[str, Any]:
        """Flush Divi cache for post."""
        resp = requests.post(
            f"{self.wp.base_url}/wp-json/diviops/v1/meta/flush-cache",
            json={"post_id": post_id},
            timeout=30,
        )
        self._handle(resp)
        return cast(dict[str, Any], resp.json())

    # Design system endpoints
    def get_global_colors(self) -> dict[str, Any]:
        """Get global color palette."""
        resp = requests.get(f"{self.wp.base_url}/wp-json/diviops/v1/global-color/list", timeout=30)
        self._handle(resp)
        return cast(dict[str, Any], resp.json())

    def get_global_fonts(self) -> dict[str, Any]:
        """Get global fonts."""
        resp = requests.get(f"{self.wp.base_url}/wp-json/diviops/v1/global-font/list", timeout=30)
        self._handle(resp)
        return cast(dict[str, Any], resp.json())

    def get_presets(self) -> dict[str, Any]:
        """Get module presets."""
        resp = requests.get(f"{self.wp.base_url}/wp-json/diviops/v1/preset/list", timeout=30)
        self._handle(resp)
        return cast(dict[str, Any], resp.json())

    def get_variables(self) -> dict[str, Any]:
        """Get CSS variables."""
        resp = requests.get(f"{self.wp.base_url}/wp-json/diviops/v1/variable/list", timeout=30)
        self._handle(resp)
        return cast(dict[str, Any], resp.json())

    def validate_blocks(self, content: str) -> dict[str, Any]:
        """Validate Divi 5 block structure."""
        resp = requests.post(
            f"{self.wp.base_url}/wp-json/diviops/v1/validate/blocks",
            json={"content": content},
            timeout=30,
        )
        self._handle(resp)
        return cast(dict[str, Any], resp.json())

    def get_design_system(self) -> dict[str, Any]:
        """Get all design system data in one call."""
        return {
            "colors": self.get_global_colors(),
            "fonts": self.get_global_fonts(),
            "presets": self.get_presets(),
            "variables": self.get_variables(),
        }