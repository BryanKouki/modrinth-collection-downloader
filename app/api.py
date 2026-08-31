"""
HTTP client for the public Modrinth API.

This module only reads public data (collections, projects, versions) and
downloads the official files hosted by Modrinth itself (cdn.modrinth.com).
No user data is sent anywhere beyond the GET requests needed to query the
public API.
"""

from __future__ import annotations

import os
import re
from typing import Callable, List, Optional

import requests

from .version import APP_NAME, APP_VERSION, AUTHOR

API_BASE = "https://api.modrinth.com"

# Modrinth asks, as good practice, for a User-Agent that identifies the project.
USER_AGENT = f"{AUTHOR}/{APP_NAME.replace(' ', '')}/{APP_VERSION} (github.com/{AUTHOR})"

REQUEST_TIMEOUT = 20  # seconds
DOWNLOAD_CHUNK_SIZE = 1024 * 256  # 256 KB


class ModrinthAPIError(Exception):
    """Generic error while communicating with the Modrinth API."""


class ModrinthClient:
    """Thin wrapper around the public Modrinth API (v2 for projects/versions, v3 for collections)."""

    def __init__(self, timeout: int = REQUEST_TIMEOUT):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            }
        )

    # -- infrastructure -----------------------------------------------------

    def _get(self, path: str, params: Optional[dict] = None) -> Optional[dict]:
        url = f"{API_BASE}{path}"
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException:
            return None
        except ValueError:
            # Invalid JSON
            return None

    # -- endpoints ------------------------------------------------------

    def get_collection(self, collection_id: str) -> Optional[dict]:
        return self._get(f"/v3/collection/{collection_id}")

    def get_project(self, project_id: str) -> Optional[dict]:
        return self._get(f"/v2/project/{project_id}")

    def get_project_versions(self, project_id: str) -> Optional[List[dict]]:
        return self._get(f"/v2/project/{project_id}/version")

    def get_game_versions(self) -> Optional[List[dict]]:
        return self._get("/v2/tag/game_version")

    def get_loaders(self) -> Optional[List[dict]]:
        return self._get("/v2/tag/loader")

    # -- download ---------------------------------------------------------

    def download_file(
        self,
        url: str,
        destination_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> bool:
        """Download a file to destination_path. Returns True on success."""
        tmp_path = destination_path + ".part"
        try:
            os.makedirs(os.path.dirname(destination_path), exist_ok=True)
            with self.session.get(url, stream=True, timeout=self.timeout) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                with open(tmp_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                        if not chunk:
                            continue
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            progress_callback(downloaded, total)
            if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
                if os.path.exists(destination_path):
                    os.remove(destination_path)
                os.replace(tmp_path, destination_path)
                return True
            return False
        except requests.RequestException:
            return False
        except OSError:
            return False
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass


def extract_collection_id(collection_input: str) -> str:
    """Extract the collection ID from a Modrinth URL, or return it as-is.

    Examples:
        https://modrinth.com/collection/5OBQuutT -> 5OBQuutT
        5OBQuutT -> 5OBQuutT
    """
    url_pattern = r"(?:https?://)?(?:www\.)?modrinth\.com/collection/([^/?#]+)"
    match = re.search(url_pattern, collection_input)
    if match:
        return match.group(1)
    return collection_input.strip()


def sanitize_filename(name: str) -> str:
    """Strip characters that are invalid in file/folder names on Windows/Linux/macOS."""
    name = name.strip()
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = name.rstrip(" .")
    return name or "modrinth-collection"
