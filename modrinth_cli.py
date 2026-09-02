#!/usr/bin/env python3
"""
Modrinth Collection Downloader - CLI edition
==============================================

A single, dependency-free Python file that downloads every mod, resource
pack, shader, plugin and datapack from a public Modrinth collection,
straight from the terminal. No pip install required: everything here uses
only the Python standard library.

This is a self-contained sibling of the full desktop GUI app in this
repository (see app/), reimplementing the same core logic (categorization,
dependency resolution, stable-release preference, per-item selection,
never-overwrite saving) for people who prefer scripting or automation over
a graphical interface.

USAGE
-----
Fully interactive (it will ask for anything missing):

    python modrinth_cli.py

Fully scripted, for automation:

    python modrinth_cli.py \
        --collection https://modrinth.com/collection/N6yU1DBr \
        --version 1.21.1 --loader fabric \
        --dest ./output --zip -y

Just look at what's inside a collection without downloading anything:

    python modrinth_cli.py --collection N6yU1DBr --list-items

Review and exclude specific items interactively before downloading:

    python modrinth_cli.py --collection N6yU1DBr --version 1.21.1 \
        --loader fabric --dest ./output --select

Run with -h / --help to see every available option.

SAFETY
------
This script only queries Modrinth's public API (api.modrinth.com) and
downloads official files hosted by Modrinth itself (cdn.modrinth.com). It
does not collect, send, or execute anything beyond that.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_BASE = "https://api.modrinth.com"
APP_NAME = "ModrinthCollectionDownloaderCLI"
APP_VERSION = "1.0.0"
AUTHOR = "BryanKouki"
USER_AGENT = f"{AUTHOR}/{APP_NAME}/{APP_VERSION} (github.com/{AUTHOR})"

REQUEST_TIMEOUT = 20
DOWNLOAD_TIMEOUT = 30
DOWNLOAD_CHUNK_SIZE = 1024 * 256

PLUGIN_LOADERS = {
    "bukkit", "spigot", "paper", "purpur", "folia",
    "sponge", "velocity", "waterfall", "bungeecord",
}
DATAPACK_LOADERS = {"datapack"}

FOLDER_MODS = "mods"
FOLDER_RESOURCEPACKS = "resourcepacks"
FOLDER_SHADERPACKS = "shaderpacks"
FOLDER_PLUGINS = "plugins"
FOLDER_DATAPACKS = "datapacks"

# Loaders in real-world popularity order, used only to sort --list-items output.
LOADER_POPULARITY = [
    "neoforge", "fabric", "forge", "quilt",
    "paper", "spigot", "purpur", "bukkit", "folia", "sponge",
    "velocity", "waterfall", "bungeecord",
    "datapack",
]

DEFAULT_LANG = "en"


# ---------------------------------------------------------------------------
# Messages (English / Portuguese) - a small, CLI-focused subset
# ---------------------------------------------------------------------------

MESSAGES: Dict[str, Dict[str, str]] = {
    "en": {
        "prompt_collection": "Collection ID or URL: ",
        "prompt_version": "Minecraft version (e.g. 1.21.1): ",
        "prompt_loader": "Mod loader (e.g. fabric, forge, neoforge, paper): ",
        "prompt_dest": "Destination folder [.]: ",
        "prompt_confirm": "Proceed with the download? [Y/n]: ",
        "prompt_exclude_numbers": (
            "Enter item numbers to EXCLUDE, comma-separated (e.g. 1,3,7), "
            "or press Enter to include everything: "
        ),
        "error_no_collection": "No collection ID or URL was given.",
        "error_collection_not_found": "Collection '{id}' was not found or is inaccessible.",
        "error_empty_collection": "Collection '{id}' has no items.",
        "error_no_version": "No Minecraft version was given.",
        "error_no_loader": "No mod loader was given.",
        "error_no_destination": "No destination folder was given.",
        "error_no_category": "At least one of --no-mods / --no-resourcepacks / --no-shaders must be left enabled.",
        "info_fetching_collection": "Fetching collection information...",
        "info_collection_found": "Collection found: '{name}' with {count} item(s).",
        "info_fetching_items": "Fetching item details ({count} item(s))...",
        "info_aborted": "Aborted.",
        "items_header": "Items in this collection:",
        "items_row": "  [{num}] {name}  ({type})",
        "items_excluded_none": "Everything will be included.",
        "items_excluded_some": "Excluded: {names}",
        "confirm_summary": (
            "\nAbout to download collection '{name}':\n"
            "  Minecraft version : {version}\n"
            "  Mod loader        : {loader}\n"
            "  Include           : {categories}\n"
            "  Dependencies      : {deps}\n"
            "  Prefer stable     : {stable}\n"
            "  Save as           : {save_mode}\n"
            "  Destination       : {dest}\n"
            "  Items excluded    : {excluded_count}\n"
        ),
        "log_start": "Starting download of collection '{id}'...",
        "log_downloading": "DOWNLOADING: {name} -> {filename}",
        "log_download_success": "OK: {name} saved to {folder}/",
        "log_download_failed": "FAILED: could not download {name}.",
        "log_no_version_found": "INCOMPATIBLE: {name} - no version for Minecraft {version} / loader {loader}.",
        "log_project_not_found": "FAILED: could not fetch project {id} (removed or network error).",
        "log_project_skipped_category": "SKIPPED: {name} - type '{type}' is not included.",
        "log_project_skipped_selection": "SKIPPED: {name} - deselected by the user.",
        "log_processing_dependencies": "Processing {count} required dependency(ies) of {name}...",
        "log_dependency_of": "  [DEPENDENCY of {parent}] {message}",
        "log_zipping": "Zipping files into {name}.zip...",
        "log_moving": "Moving files to {path}...",
        "log_done": "Download finished.",
        "reason_project_not_found": "Could not fetch the project's details (removed, or a network error occurred).",
        "reason_no_file": "No downloadable file was found for this version.",
        "reason_download_error": "The download failed (network error, or the file could not be saved).",
        "reason_no_version": "No version published for Minecraft {version} with the {loader} loader.",
        "summary_header": "\n===== SUMMARY =====",
        "summary_line": "  Success: {success}   Failed: {failed}   Incompatible: {incompatible}   Skipped: {skipped}",
        "summary_output": "  Saved to: {path}",
        "summary_failed_header": "\nFailed items:",
        "summary_incompatible_header": "\nIncompatible items:",
        "summary_item_line": "  - {name}: {reason}",
        "summary_more": "  ... and {count} more",
        "yes_chars": "y",
    },
    "pt": {
        "prompt_collection": "ID ou URL da coleção: ",
        "prompt_version": "Versão do Minecraft (ex: 1.21.1): ",
        "prompt_loader": "Mod loader (ex: fabric, forge, neoforge, paper): ",
        "prompt_dest": "Pasta de destino [.]: ",
        "prompt_confirm": "Continuar com o download? [S/n]: ",
        "prompt_exclude_numbers": (
            "Digite os números dos itens para EXCLUIR, separados por vírgula (ex: 1,3,7), "
            "ou pressione Enter para incluir tudo: "
        ),
        "error_no_collection": "Nenhum ID ou URL de coleção foi informado.",
        "error_collection_not_found": "A coleção '{id}' não foi encontrada ou está inacessível.",
        "error_empty_collection": "A coleção '{id}' não tem itens.",
        "error_no_version": "Nenhuma versão do Minecraft foi informada.",
        "error_no_loader": "Nenhum mod loader foi informado.",
        "error_no_destination": "Nenhuma pasta de destino foi informada.",
        "error_no_category": "Pelo menos uma entre --no-mods / --no-resourcepacks / --no-shaders precisa ficar habilitada.",
        "info_fetching_collection": "Buscando informações da coleção...",
        "info_collection_found": "Coleção encontrada: '{name}' com {count} item(ns).",
        "info_fetching_items": "Buscando detalhes dos itens ({count} item(ns))...",
        "info_aborted": "Cancelado.",
        "items_header": "Itens desta coleção:",
        "items_row": "  [{num}] {name}  ({type})",
        "items_excluded_none": "Tudo será incluído.",
        "items_excluded_some": "Excluídos: {names}",
        "confirm_summary": (
            "\nPrestes a baixar a coleção '{name}':\n"
            "  Versão do Minecraft : {version}\n"
            "  Mod loader          : {loader}\n"
            "  Incluir             : {categories}\n"
            "  Dependências        : {deps}\n"
            "  Preferir estável    : {stable}\n"
            "  Salvar como         : {save_mode}\n"
            "  Destino             : {dest}\n"
            "  Itens excluídos     : {excluded_count}\n"
        ),
        "log_start": "Iniciando download da coleção '{id}'...",
        "log_downloading": "BAIXANDO: {name} -> {filename}",
        "log_download_success": "OK: {name} salvo em {folder}/",
        "log_download_failed": "FALHA: não foi possível baixar {name}.",
        "log_no_version_found": "INCOMPATÍVEL: {name} - nenhuma versão para Minecraft {version} / loader {loader}.",
        "log_project_not_found": "FALHA: não foi possível buscar o projeto {id} (removido ou erro de rede).",
        "log_project_skipped_category": "IGNORADO: {name} - tipo '{type}' não está incluído.",
        "log_project_skipped_selection": "IGNORADO: {name} - desmarcado pelo usuário.",
        "log_processing_dependencies": "Processando {count} dependência(s) obrigatória(s) de {name}...",
        "log_dependency_of": "  [DEPENDÊNCIA de {parent}] {message}",
        "log_zipping": "Compactando arquivos em {name}.zip...",
        "log_moving": "Movendo arquivos para {path}...",
        "log_done": "Download finalizado.",
        "reason_project_not_found": "Não foi possível obter os dados do projeto (removido, ou erro de rede).",
        "reason_no_file": "Nenhum arquivo para download foi encontrado nessa versão.",
        "reason_download_error": "O download falhou (erro de rede ou não foi possível salvar o arquivo).",
        "reason_no_version": "Nenhuma versão publicada para Minecraft {version} com o loader {loader}.",
        "summary_header": "\n===== RESUMO =====",
        "summary_line": "  Sucesso: {success}   Falharam: {failed}   Incompatíveis: {incompatible}   Ignorados: {skipped}",
        "summary_output": "  Salvo em: {path}",
        "summary_failed_header": "\nItens que falharam:",
        "summary_incompatible_header": "\nItens incompatíveis:",
        "summary_item_line": "  - {name}: {reason}",
        "summary_more": "  ... e mais {count}",
        "yes_chars": "s",
    },
}

LANG = DEFAULT_LANG


def t(key: str, **kwargs) -> str:
    table = MESSAGES.get(LANG, MESSAGES[DEFAULT_LANG])
    text = table.get(key) or MESSAGES[DEFAULT_LANG].get(key) or key
    return text.format(**kwargs) if kwargs else text


# ---------------------------------------------------------------------------
# Minimal Modrinth API client (stdlib-only, via urllib)
# ---------------------------------------------------------------------------

def api_get(path: str) -> Optional[dict]:
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            raw = resp.read()
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        return None
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None


def download_file(url: str, destination_path: str) -> bool:
    tmp_path = destination_path + ".part"
    try:
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT) as resp, open(tmp_path, "wb") as out_file:
            while True:
                chunk = resp.read(DOWNLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                out_file.write(chunk)
        if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
            if os.path.exists(destination_path):
                os.remove(destination_path)
            os.replace(tmp_path, destination_path)
            return True
        return False
    except (urllib.error.URLError, OSError, TimeoutError):
        return False
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def extract_collection_id(collection_input: str) -> str:
    match = re.search(r"(?:https?://)?(?:www\.)?modrinth\.com/collection/([^/?#]+)", collection_input)
    return match.group(1) if match else collection_input.strip()


def sanitize_filename(name: str) -> str:
    name = name.strip()
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = name.rstrip(" .")
    return name or "modrinth-collection"


def unique_path(base_path: str, suffix: str) -> str:
    candidate = base_path
    i = 2
    while os.path.exists(candidate + suffix):
        candidate = f"{base_path} ({i})"
        i += 1
    return candidate


# ---------------------------------------------------------------------------
# Categorization / version selection (same rules as the desktop app)
# ---------------------------------------------------------------------------

def categorize(project_type: str, loaders: List[str]) -> str:
    loaders_lower = {l.lower() for l in loaders}
    if project_type == "shader":
        return FOLDER_SHADERPACKS
    if project_type == "resourcepack":
        return FOLDER_RESOURCEPACKS
    if loaders_lower & DATAPACK_LOADERS:
        return FOLDER_DATAPACKS
    if loaders_lower & PLUGIN_LOADERS:
        return FOLDER_PLUGINS
    return FOLDER_MODS


def item_category(project_type: str) -> str:
    if project_type == "shader":
        return "shader"
    if project_type == "resourcepack":
        return "resourcepack"
    return "mod"


def category_allowed(project_type: str, include_mods: bool, include_resourcepacks: bool, include_shaders: bool) -> bool:
    if project_type == "shader":
        return include_shaders
    if project_type == "resourcepack":
        return include_resourcepacks
    return include_mods


def pick_version(
    versions: List[dict], mc_version: str, loader: str, project_type: str, prefer_stable: bool,
) -> Optional[dict]:
    requested_loader = loader.lower()
    same_mc_version = [v for v in versions if mc_version in v.get("game_versions", [])]

    if project_type == "resourcepack":
        candidates = [
            v for v in same_mc_version
            if not v.get("loaders") or "minecraft" in [l.lower() for l in v.get("loaders", [])]
        ]
    elif project_type == "shader":
        candidates = same_mc_version
    else:
        exact_loader_matches = [
            v for v in same_mc_version
            if requested_loader in [l.lower() for l in v.get("loaders", [])]
        ]
        if exact_loader_matches:
            candidates = exact_loader_matches
        else:
            candidates = [
                v for v in same_mc_version
                if set(l.lower() for l in v.get("loaders", [])) & (PLUGIN_LOADERS | DATAPACK_LOADERS)
            ]

    if not candidates:
        return None

    candidates.sort(key=lambda v: v.get("date_published", ""), reverse=True)

    if prefer_stable:
        releases = [v for v in candidates if v.get("version_type") == "release"]
        if releases:
            return releases[0]
    return candidates[0]


def sort_loaders_by_popularity(names: List[str]) -> List[str]:
    seen: List[str] = []
    for name in names:
        if name not in seen:
            seen.append(name)

    def sort_key(name: str):
        low = name.lower()
        return (0, LOADER_POPULARITY.index(low)) if low in LOADER_POPULARITY else (1, low)

    return sorted(seen, key=sort_key)


# ---------------------------------------------------------------------------
# Options / result data structures
# ---------------------------------------------------------------------------

@dataclass
class Options:
    collection_input: str
    mc_version: str
    loader: str
    include_mods: bool = True
    include_resourcepacks: bool = True
    include_shaders: bool = True
    download_dependencies: bool = True
    prefer_stable: bool = True
    save_as_zip: bool = False
    destination_dir: str = "."
    max_workers: int = 5
    excluded_project_ids: Set[str] = field(default_factory=set)
    known_names: Dict[str, str] = field(default_factory=dict)


@dataclass
class ResultItem:
    name: str
    reason: str


@dataclass
class Result:
    collection_name: str = ""
    output_path: str = ""
    success: List[str] = field(default_factory=list)
    failed: List[ResultItem] = field(default_factory=list)
    incompatible: List[ResultItem] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Core download orchestration
# ---------------------------------------------------------------------------

def run_download(options: Options) -> Result:
    result = Result()
    print_lock = threading.Lock()

    def log(message: str) -> None:
        with print_lock:
            print(message)

    collection_id = extract_collection_id(options.collection_input)
    log(t("log_start", id=collection_id))
    log(t("info_fetching_collection"))

    collection = api_get(f"/v3/collection/{collection_id}")
    if not collection:
        result.error = t("error_collection_not_found", id=collection_id)
        log(result.error)
        return result

    project_ids: List[str] = collection.get("projects", []) or []
    if not project_ids:
        result.error = t("error_empty_collection", id=collection_id)
        log(result.error)
        return result

    collection_name = sanitize_filename(collection.get("name") or collection_id)
    result.collection_name = collection_name
    log(t("info_collection_found", name=collection.get("name") or collection_id, count=len(project_ids)))

    work_root = tempfile.mkdtemp(prefix="modrinth_cli_")
    work_dir = os.path.join(work_root, collection_name)
    os.makedirs(work_dir, exist_ok=True)

    processed: Set[str] = set()
    processed_lock = threading.Lock()
    result_lock = threading.Lock()

    def process_project(project_id: str, is_dependency: bool = False, parent_name: Optional[str] = None) -> None:
        with processed_lock:
            if project_id in processed:
                return
            processed.add(project_id)

        def log_line(key: str, **kwargs) -> None:
            msg = t(key, **kwargs)
            if is_dependency and parent_name:
                msg = t("log_dependency_of", parent=parent_name, message=msg)
            log(msg)

        if not is_dependency and project_id in options.excluded_project_ids:
            name = options.known_names.get(project_id, project_id)
            log_line("log_project_skipped_selection", name=name)
            with result_lock:
                result.skipped.append(name)
            return

        try:
            project = api_get(f"/v2/project/{project_id}")
            if not project:
                log_line("log_project_not_found", id=project_id)
                with result_lock:
                    result.failed.append(ResultItem(name=project_id, reason=t("reason_project_not_found")))
                return

            display_name = project.get("title") or project.get("slug") or project_id
            project_type = project.get("project_type", "mod")

            if not is_dependency and not category_allowed(
                project_type, options.include_mods, options.include_resourcepacks, options.include_shaders
            ):
                log_line("log_project_skipped_category", name=display_name, type=project_type)
                with result_lock:
                    result.skipped.append(display_name)
                return

            versions = api_get(f"/v2/project/{project_id}/version") or []
            chosen = pick_version(versions, options.mc_version, options.loader, project_type, options.prefer_stable)
            if not chosen:
                log_line("log_no_version_found", name=display_name, version=options.mc_version, loader=options.loader)
                with result_lock:
                    result.incompatible.append(ResultItem(
                        name=display_name,
                        reason=t("reason_no_version", version=options.mc_version, loader=options.loader),
                    ))
                return

            if options.download_dependencies:
                required_deps = [
                    d for d in chosen.get("dependencies", [])
                    if d.get("dependency_type") == "required" and d.get("project_id")
                ]
                if required_deps:
                    log_line("log_processing_dependencies", count=len(required_deps), name=display_name)
                    for dep in required_deps:
                        process_project(dep["project_id"], is_dependency=True, parent_name=display_name)

            file_info = next((f for f in chosen.get("files", []) if f.get("primary")), None)
            if not file_info and chosen.get("files"):
                file_info = chosen["files"][0]
            if not file_info:
                log_line("log_download_failed", name=display_name)
                with result_lock:
                    result.failed.append(ResultItem(name=display_name, reason=t("reason_no_file")))
                return

            folder = categorize(project_type, chosen.get("loaders", []))
            filename = file_info["filename"]
            dest_path = os.path.join(work_dir, folder, filename)

            log_line("log_downloading", name=display_name, filename=filename)
            ok = download_file(file_info["url"], dest_path)
            if ok:
                log_line("log_download_success", name=display_name, folder=folder)
                with result_lock:
                    result.success.append(display_name)
            else:
                log_line("log_download_failed", name=display_name)
                with result_lock:
                    result.failed.append(ResultItem(name=display_name, reason=t("reason_download_error")))
        except Exception as exc:  # never let one bad project silently kill the batch
            name = options.known_names.get(project_id, project_id)
            log(f"ERROR ({name}): {exc}")
            with result_lock:
                result.failed.append(ResultItem(name=name, reason=str(exc)))

    with ThreadPoolExecutor(max_workers=max(1, options.max_workers)) as executor:
        futures = [executor.submit(process_project, pid) for pid in project_ids]
        for future in futures:
            future.result()

    try:
        if options.save_as_zip:
            log(t("log_zipping", name=collection_name))
            zip_base = unique_path(os.path.join(options.destination_dir, collection_name), ".zip")
            shutil.make_archive(zip_base, "zip", root_dir=work_root, base_dir=collection_name)
            result.output_path = zip_base + ".zip"
        else:
            log(t("log_moving", path=options.destination_dir))
            final_dir = unique_path(os.path.join(options.destination_dir, collection_name), "")
            os.makedirs(options.destination_dir, exist_ok=True)
            shutil.move(work_dir, final_dir)
            result.output_path = final_dir
    except OSError as exc:
        result.error = str(exc)
        log(f"ERROR: {exc}")
    finally:
        shutil.rmtree(work_root, ignore_errors=True)

    log(t("log_done"))
    return result


# ---------------------------------------------------------------------------
# Item preview (used by --list-items and --select)
# ---------------------------------------------------------------------------

def fetch_items_preview(project_ids: List[str], max_workers: int = 8) -> List[dict]:
    fetched: Dict[str, Optional[dict]] = {}
    lock = threading.Lock()

    def fetch_one(pid: str) -> None:
        proj = api_get(f"/v2/project/{pid}")
        with lock:
            fetched[pid] = proj

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        list(executor.map(fetch_one, project_ids))

    items = []
    for pid in project_ids:
        proj = fetched.get(pid)
        if proj:
            items.append({
                "id": pid,
                "name": proj.get("title") or proj.get("slug") or pid,
                "type": proj.get("project_type", "mod"),
            })
        else:
            items.append({"id": pid, "name": pid, "type": "mod"})
    return items


def print_items(items: List[dict]) -> None:
    print(t("items_header"))
    for i, item in enumerate(items, start=1):
        print(t("items_row", num=i, name=item["name"], type=item["type"]))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="modrinth_cli.py",
        description=(
            "Download every mod, resource/texture pack, shader, plugin and datapack "
            "from a public Modrinth collection, from the terminal, with zero pip "
            "dependencies."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python modrinth_cli.py\n"
            "  python modrinth_cli.py -c N6yU1DBr -v 1.21.1 -l fabric -d ./out -y\n"
            "  python modrinth_cli.py -c N6yU1DBr --list-items\n"
            "  python modrinth_cli.py -c N6yU1DBr -v 1.21.1 -l fabric -d ./out --select\n"
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {APP_VERSION}",
        help="Show the program's version and exit.",
    )
    parser.add_argument("--collection", "-c", help="Collection ID or URL.")
    parser.add_argument("--mc-version", "-v", dest="mc_version", help="Minecraft version (e.g. 1.21.1).")
    parser.add_argument("--loader", "-l", help="Mod loader (e.g. fabric, forge, neoforge, paper).")
    parser.add_argument("--dest", "-d", help="Destination folder (default: current directory).")
    parser.add_argument("--zip", action="store_true", help="Save as a single .zip instead of a folder.")
    parser.add_argument("--no-mods", action="store_true", help="Exclude mods, plugins and datapacks.")
    parser.add_argument("--no-resourcepacks", action="store_true", help="Exclude resource/texture packs.")
    parser.add_argument("--no-shaders", action="store_true", help="Exclude shaders.")
    parser.add_argument("--no-deps", action="store_true", help="Do not download required dependencies.")
    parser.add_argument(
        "--allow-beta", action="store_true",
        help="Do not prefer stable releases; use the newest version available even if alpha/beta.",
    )
    parser.add_argument("--exclude", help="Comma-separated project IDs/slugs to exclude from the download.")
    parser.add_argument(
        "--select", action="store_true",
        help="Interactively review the collection's items and choose which ones to exclude before downloading.",
    )
    parser.add_argument(
        "--list-items", action="store_true",
        help="Just print every item in the collection (with its ID) and exit, without downloading anything.",
    )
    parser.add_argument("--workers", type=int, default=5, help="Number of parallel download threads (default: 5).")
    parser.add_argument("--lang", choices=["en", "pt"], default="en", help="Output language (default: en).")
    parser.add_argument("-y", "--yes", action="store_true", help="Skip the confirmation prompt.")
    return parser


def prompt(message: str, default: Optional[str] = None) -> str:
    try:
        value = input(message).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(1)
    return value or (default or "")


def confirm(message: str) -> bool:
    answer = prompt(message).strip().lower()
    if not answer:
        return True
    return answer[0] == t("yes_chars")


def main() -> None:
    global LANG

    parser = build_arg_parser()
    args = parser.parse_args()
    LANG = args.lang if args.lang in MESSAGES else DEFAULT_LANG

    collection_input = args.collection or prompt(t("prompt_collection"))
    if not collection_input:
        print(t("error_no_collection"))
        sys.exit(1)

    excluded_ids: Set[str] = set()
    known_names: Dict[str, str] = {}

    if args.list_items or args.select:
        collection_id = extract_collection_id(collection_input)
        print(t("info_fetching_collection"))
        collection = api_get(f"/v3/collection/{collection_id}")
        if not collection:
            print(t("error_collection_not_found", id=collection_id))
            sys.exit(1)
        project_ids = collection.get("projects", []) or []
        if not project_ids:
            print(t("error_empty_collection", id=collection_id))
            sys.exit(1)

        print(t("info_fetching_items", count=len(project_ids)))
        items = fetch_items_preview(project_ids)
        print_items(items)
        known_names = {item["id"]: item["name"] for item in items}

        if args.list_items and not args.select:
            return

        if args.select:
            raw = prompt(t("prompt_exclude_numbers"))
            if raw.strip():
                try:
                    numbers = {int(n.strip()) for n in raw.split(",") if n.strip()}
                except ValueError:
                    numbers = set()
                for i, item in enumerate(items, start=1):
                    if i in numbers:
                        excluded_ids.add(item["id"])
            if excluded_ids:
                names = ", ".join(known_names[pid] for pid in excluded_ids)
                print(t("items_excluded_some", names=names))
            else:
                print(t("items_excluded_none"))

    if args.exclude:
        excluded_ids |= {x.strip() for x in args.exclude.split(",") if x.strip()}

    version = args.mc_version or prompt(t("prompt_version"))
    if not version:
        print(t("error_no_version"))
        sys.exit(1)

    loader = args.loader or prompt(t("prompt_loader"))
    if not loader:
        print(t("error_no_loader"))
        sys.exit(1)

    dest = args.dest or prompt(t("prompt_dest"), default=".")
    if not dest:
        print(t("error_no_destination"))
        sys.exit(1)

    include_mods = not args.no_mods
    include_resourcepacks = not args.no_resourcepacks
    include_shaders = not args.no_shaders
    if not (include_mods or include_resourcepacks or include_shaders):
        print(t("error_no_category"))
        sys.exit(1)

    options = Options(
        collection_input=collection_input,
        mc_version=version,
        loader=loader,
        include_mods=include_mods,
        include_resourcepacks=include_resourcepacks,
        include_shaders=include_shaders,
        download_dependencies=not args.no_deps,
        prefer_stable=not args.allow_beta,
        save_as_zip=args.zip,
        destination_dir=dest,
        max_workers=max(1, args.workers),
        excluded_project_ids=excluded_ids,
        known_names=known_names,
    )

    if not args.yes:
        categories = ", ".join(
            name for name, on in (
                ("mods/plugins/datapacks", include_mods),
                ("resource/texture packs", include_resourcepacks),
                ("shaders", include_shaders),
            ) if on
        )
        print(t(
            "confirm_summary",
            name=collection_input,
            version=version,
            loader=loader,
            categories=categories,
            deps="yes" if options.download_dependencies else "no",
            stable="yes" if options.prefer_stable else "no",
            save_mode="zip" if options.save_as_zip else "folder",
            dest=dest,
            excluded_count=len(excluded_ids),
        ))
        if not confirm(t("prompt_confirm")):
            print(t("info_aborted"))
            sys.exit(0)

    result = run_download(options)

    print(t("summary_header"))
    print(t(
        "summary_line",
        success=len(result.success), failed=len(result.failed),
        incompatible=len(result.incompatible), skipped=len(result.skipped),
    ))
    if result.output_path:
        print(t("summary_output", path=result.output_path))

    def print_result_items(items: List[ResultItem], header_key: str, cap: int = 15) -> None:
        if not items:
            return
        print(t(header_key))
        for item in items[:cap]:
            print(t("summary_item_line", name=item.name, reason=item.reason))
        if len(items) > cap:
            print(t("summary_more", count=len(items) - cap))

    print_result_items(result.failed, "summary_failed_header")
    print_result_items(result.incompatible, "summary_incompatible_header")

    if result.error and not result.output_path:
        sys.exit(1)


if __name__ == "__main__":
    main()
