"""
Support for exporting a resolved collection as a Modrinth Modpack (.mrpack)
file, instead of downloading the actual mod/resourcepack/shader files.

A .mrpack only needs to reference each file's official download URL and
hash — both already included in the version data the Modrinth API returns
for every file — so building one requires no extra file downloads at all,
just assembling that metadata and zipping it up.

Unlike the rest of this app, generating a .mrpack also talks to each mod
loader's own official metadata service, since the Modrinth API only knows
a loader's *name* (e.g. "fabric"), not a concrete version number, which the
.mrpack format's dependencies block requires:

    Fabric   -> meta.fabricmc.net
    Quilt    -> meta.quiltmc.org
    Forge    -> files.minecraftforge.net
    NeoForge -> maven.neoforged.net

These are each project's own official, public metadata API — nothing
unofficial or third-party beyond that — and only ever contacted when the
user picks ".mrpack" as the save format. Nothing is sent to them besides
the plain GET request itself.
"""

from __future__ import annotations

import json
import zipfile
from typing import Dict, List, Optional

import requests

from .version import APP_NAME, APP_VERSION, AUTHOR

USER_AGENT = f"{AUTHOR}/{APP_NAME.replace(' ', '')}/{APP_VERSION} (github.com/{AUTHOR})"
REQUEST_TIMEOUT = 15

# .mrpack only has a concept of client mod loaders — there's no equivalent
# for server plugin loaders (Paper/Spigot/...) or datapacks.
MRPACK_DEPENDENCY_KEY: Dict[str, str] = {
    "fabric": "fabric-loader",
    "quilt": "quilt-loader",
    "forge": "forge",
    "neoforge": "neoforge",
}
MRPACK_SUPPORTED_LOADERS = set(MRPACK_DEPENDENCY_KEY)

# Categories that make sense inside a .mrpack; plugins and datapacks are
# deliberately left out (see module docstring) and get skipped instead.
MRPACK_SUPPORTED_FOLDERS = {"mods", "resourcepacks", "shaderpacks"}

FORMAT_VERSION = 1
PACK_VERSION_ID = "1.0.0"


def is_loader_supported(loader: str) -> bool:
    return loader.lower() in MRPACK_SUPPORTED_LOADERS


def get_latest_loader_version(loader: str, mc_version: str) -> Optional[str]:
    """Best-effort fetch of the latest/recommended version of `loader`
    compatible with `mc_version`, from that loader's own official metadata
    API.

    Returns None if the loader isn't one of the four .mrpack supports, or
    the lookup fails for any reason (network error, unexpected response
    shape, ...) — callers should treat that as "let the person set it
    manually after importing", not as a fatal error; the rest of the pack
    is still perfectly valid without it.
    """
    loader = loader.lower()
    headers = {"User-Agent": USER_AGENT}
    try:
        if loader == "fabric":
            resp = requests.get(
                "https://meta.fabricmc.net/v2/versions/loader", headers=headers, timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            versions = resp.json() or []
            stable = [v for v in versions if v.get("loader", {}).get("stable")]
            pick = stable[0] if stable else (versions[0] if versions else None)
            return pick["loader"]["version"] if pick else None

        if loader == "quilt":
            resp = requests.get(
                "https://meta.quiltmc.org/v3/versions/loader", headers=headers, timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            versions = resp.json() or []
            return versions[0]["version"] if versions else None

        if loader == "forge":
            resp = requests.get(
                "https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json",
                headers=headers, timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            promos = (resp.json() or {}).get("promos", {})
            return promos.get(f"{mc_version}-recommended") or promos.get(f"{mc_version}-latest")

        if loader == "neoforge":
            resp = requests.get(
                "https://maven.neoforged.net/api/maven/versions/releases/net/neoforged/neoforge",
                headers=headers, timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            versions = (resp.json() or {}).get("versions", [])
            # NeoForge's own version scheme mirrors the Minecraft version:
            # for MC 1.21.1 it's "21.1.<build>". Derive that prefix and take
            # the newest matching build; versions are listed oldest-first.
            parts = mc_version.split(".")
            if len(parts) >= 2:
                minor = parts[1]
                patch = parts[2] if len(parts) > 2 else "0"
                prefix = f"{minor}.{patch}."
                matching = [v for v in versions if v.startswith(prefix)]
                if matching:
                    return matching[-1]
            return versions[-1] if versions else None
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
        return None
    return None


def build_file_entry(
    folder: str,
    filename: str,
    url: str,
    size: int,
    hashes: Optional[Dict[str, str]],
    client_side: str,
    server_side: str,
) -> dict:
    """Build one entry of the .mrpack index's "files" array."""
    entry_hashes = {k: v for k, v in (hashes or {}).items() if k in ("sha1", "sha512")}
    return {
        "path": f"{folder}/{filename}",
        "hashes": entry_hashes,
        "env": {
            "client": client_side or "required",
            "server": server_side or "required",
        },
        "downloads": [url],
        "fileSize": size or 0,
    }


def build_index(
    name: str,
    mc_version: str,
    loader: str,
    loader_version: Optional[str],
    files: List[dict],
) -> dict:
    """Build the full modrinth.index.json contents."""
    dependencies: Dict[str, str] = {"minecraft": mc_version}
    dep_key = MRPACK_DEPENDENCY_KEY.get(loader.lower())
    if dep_key and loader_version:
        dependencies[dep_key] = loader_version
    return {
        "formatVersion": FORMAT_VERSION,
        "game": "minecraft",
        "versionId": PACK_VERSION_ID,
        "name": name,
        "files": files,
        "dependencies": dependencies,
    }


def write_mrpack(index_data: dict, output_path: str) -> None:
    """Zip up modrinth.index.json into a .mrpack file at output_path."""
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("modrinth.index.json", json.dumps(index_data, indent=2, ensure_ascii=False))
