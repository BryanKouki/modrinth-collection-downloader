"""
Orchestrates downloading an entire Modrinth collection.

Fetches every project in the collection, resolves the right version for the
requested Minecraft version + loader (preferring stable releases if asked),
optionally follows required dependencies, sorts files into category
subfolders (mods/resourcepacks/shaderpacks/plugins/datapacks), and finally
saves the result as a plain folder or a .zip file, named after the
collection.

This module only downloads official files from Modrinth (cdn.modrinth.com)
based on public data from the API (api.modrinth.com). It does not execute
anything, and does not collect or send any user data.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Set

from .api import ModrinthClient, extract_collection_id, sanitize_filename
from .i18n import t

# Known loaders, used only to decide the destination subfolder.
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


@dataclass
class DownloadOptions:
    collection_input: str
    mc_version: str
    loader: str
    include_mods: bool = True
    include_resourcepacks: bool = True
    include_shaders: bool = True
    download_dependencies: bool = True
    prefer_stable: bool = True
    save_as_zip: bool = False
    destination_dir: str = ""
    max_workers: int = 5
    # Individual items the user unchecked in the items checklist (empty by
    # default — everything is included unless explicitly deselected).
    excluded_project_ids: Set[str] = field(default_factory=set)
    # Friendly names for excluded_project_ids, so the log/skip list can show
    # "Sodium" instead of a raw project id — populated from the preview
    # fetch in the GUI; falls back to the raw id when not available.
    known_names: dict = field(default_factory=dict)


@dataclass
class ResultItem:
    """A single failed/incompatible entry, with a human-readable reason."""
    name: str
    reason: str


@dataclass
class DownloadResult:
    collection_name: str = ""
    output_path: str = ""
    success: List[str] = field(default_factory=list)
    failed: List[ResultItem] = field(default_factory=list)
    incompatible: List[ResultItem] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    cancelled: bool = False
    error: Optional[str] = None


LogFn = Callable[[str], None]
ProgressFn = Callable[[int, int], None]  # (completed, total)


class DownloadManager:
    """Orchestrates downloading an entire Modrinth collection."""

    def __init__(self, lang: str = "en"):
        self.lang = lang
        self.client = ModrinthClient()
        self._cancel_event = threading.Event()
        self._lock = threading.Lock()

    def cancel(self) -> None:
        self._cancel_event.set()

    def _tr(self, key: str, **kwargs) -> str:
        return t(self.lang, key, **kwargs)

    def _log(self, log_fn: LogFn, key: str, **kwargs) -> None:
        log_fn(self._tr(key, **kwargs))

    # -- categorization ------------------------------------------------------

    def categorize(self, project_type: str, loaders: List[str]) -> str:
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

    def _category_allowed(self, project_type: str, options: DownloadOptions) -> bool:
        if project_type == "shader":
            return options.include_shaders
        if project_type == "resourcepack":
            return options.include_resourcepacks
        return options.include_mods  # mod, modpack, plugin, datapack

    def _pick_version(
        self,
        versions: List[dict],
        mc_version: str,
        loader: str,
        project_type: str,
        prefer_stable: bool,
    ) -> Optional[dict]:
        requested_loader = loader.lower()

        same_mc_version = [v for v in versions if mc_version in v.get("game_versions", [])]

        if project_type == "resourcepack":
            # Modrinth tags resource/texture pack versions with the "minecraft"
            # loader (sometimes no loader at all) — they don't depend on the
            # mod loader the user picked.
            candidates = [
                v for v in same_mc_version
                if not v.get("loaders") or "minecraft" in [l.lower() for l in v.get("loaders", [])]
            ]
        elif project_type == "shader":
            # Shaders depend on a "shader loader" (Iris/OptiFine/Canvas), not on
            # the mod loader the user picked — we only filter by game version.
            candidates = same_mc_version
        else:
            # "mod" (this also covers plugins and datapacks, which on the
            # Modrinth API are just "mod" projects with a different loader).
            exact_loader_matches = [
                v for v in same_mc_version
                if requested_loader in [l.lower() for l in v.get("loaders", [])]
            ]
            if exact_loader_matches:
                # A version exists for the requested mod loader (e.g. Fabric) — use it.
                candidates = exact_loader_matches
            else:
                # No version for the requested mod loader: this could be a
                # server plugin (Paper/Spigot/...) or a datapack — those don't
                # use the same loader field as client mods, so they're
                # accepted regardless of the loader the user chose.
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

    # -- execution -------------------------------------------------------

    def run(
        self,
        options: DownloadOptions,
        log_fn: LogFn,
        progress_fn: Optional[ProgressFn] = None,
    ) -> DownloadResult:
        result = DownloadResult()
        self._cancel_event.clear()

        collection_id = extract_collection_id(options.collection_input)
        self._log(log_fn, "log_start", id=collection_id)
        self._log(log_fn, "log_fetching_collection")

        collection = self.client.get_collection(collection_id)
        if not collection:
            result.error = self._tr("msg_error_collection_not_found", id=collection_id)
            log_fn(result.error)
            return result

        project_ids: List[str] = collection.get("projects", []) or []
        if not project_ids:
            result.error = self._tr("msg_error_empty_collection", id=collection_id)
            log_fn(result.error)
            return result

        collection_name = sanitize_filename(collection.get("name") or collection_id)
        result.collection_name = collection_name
        self._log(
            log_fn,
            "log_collection_found",
            name=collection.get("name") or collection_id,
            count=len(project_ids),
        )

        # Download everything into a temp folder first; only move/zip to the
        # final destination once everything is done.
        work_root = tempfile.mkdtemp(prefix="modrinth_dl_")
        work_dir = os.path.join(work_root, collection_name)
        os.makedirs(work_dir, exist_ok=True)

        processed: Set[str] = set()
        processed_lock = threading.Lock()
        total_main = max(len(project_ids), 1)
        completed = {"count": 0}

        def report_progress() -> None:
            if progress_fn:
                progress_fn(completed["count"], total_main)

        def process_project(
            project_id: str,
            is_dependency: bool = False,
            parent_name: Optional[str] = None,
        ) -> None:
            if self._cancel_event.is_set():
                return

            with processed_lock:
                if project_id in processed:
                    return
                processed.add(project_id)

            def log_line(key: str, **kwargs) -> None:
                msg = self._tr(key, **kwargs)
                if is_dependency and parent_name:
                    msg = self._tr("log_dependency_of", parent=parent_name, message=msg)
                log_fn(msg)

            def finish_main_unit() -> None:
                if not is_dependency:
                    with self._lock:
                        completed["count"] += 1
                    report_progress()

            if not is_dependency and project_id in options.excluded_project_ids:
                # Deselected by the user in the items checklist — skip it
                # without even spending an API call on it.
                name = options.known_names.get(project_id, project_id)
                log_line("log_project_skipped_selection", name=name)
                with self._lock:
                    result.skipped.append(name)
                finish_main_unit()
                return

            try:
                project = self.client.get_project(project_id)
                if not project:
                    log_line("log_project_not_found", id=project_id)
                    with self._lock:
                        result.failed.append(ResultItem(name=project_id, reason=self._tr("reason_project_not_found")))
                    finish_main_unit()
                    return

                display_name = project.get("title") or project.get("slug") or project_id
                project_type = project.get("project_type", "mod")

                if not is_dependency and not self._category_allowed(project_type, options):
                    log_line("log_project_skipped_category", name=display_name, type=project_type)
                    with self._lock:
                        result.skipped.append(display_name)
                    finish_main_unit()
                    return

                versions = self.client.get_project_versions(project_id) or []
                chosen = self._pick_version(
                    versions, options.mc_version, options.loader, project_type, options.prefer_stable
                )
                if not chosen:
                    log_line(
                        "log_no_version_found",
                        name=display_name,
                        version=options.mc_version,
                        loader=options.loader,
                    )
                    with self._lock:
                        result.incompatible.append(ResultItem(
                            name=display_name,
                            reason=self._tr("reason_no_version", version=options.mc_version, loader=options.loader),
                        ))
                    finish_main_unit()
                    return

                # Required dependencies first (if enabled).
                if options.download_dependencies and not self._cancel_event.is_set():
                    required_deps = [
                        d
                        for d in chosen.get("dependencies", [])
                        if d.get("dependency_type") == "required" and d.get("project_id")
                    ]
                    if required_deps:
                        log_line("log_processing_dependencies", count=len(required_deps), name=display_name)
                        for dep in required_deps:
                            process_project(dep["project_id"], is_dependency=True, parent_name=display_name)

                if self._cancel_event.is_set():
                    return

                file_info = next((f for f in chosen.get("files", []) if f.get("primary")), None)
                if not file_info and chosen.get("files"):
                    file_info = chosen["files"][0]
                if not file_info:
                    log_line("log_download_failed", name=display_name)
                    with self._lock:
                        result.failed.append(ResultItem(name=display_name, reason=self._tr("reason_no_file")))
                    finish_main_unit()
                    return

                folder = self.categorize(project_type, chosen.get("loaders", []))
                target_dir = os.path.join(work_dir, folder)
                filename = file_info["filename"]
                dest_path = os.path.join(target_dir, filename)

                log_line("log_downloading", name=display_name, filename=filename)

                ok = self.client.download_file(file_info["url"], dest_path)
                if ok:
                    log_line("log_download_success", name=display_name, folder=folder)
                    with self._lock:
                        result.success.append(display_name)
                else:
                    log_line("log_download_failed", name=display_name)
                    with self._lock:
                        result.failed.append(ResultItem(name=display_name, reason=self._tr("reason_download_error")))

                finish_main_unit()
            except Exception as exc:
                # Defensive fallback: never let one bad project silently derail
                # the whole batch — attribute the error to it and move on.
                safe_name = project_id
                try:
                    safe_name = display_name  # may not be defined yet, that's fine
                except NameError:
                    pass
                log_line("log_error_unexpected", name=safe_name, error=str(exc))
                with self._lock:
                    result.failed.append(ResultItem(name=safe_name, reason=str(exc)))
                finish_main_unit()

        try:
            with ThreadPoolExecutor(max_workers=max(1, options.max_workers)) as executor:
                futures = [executor.submit(process_project, pid) for pid in project_ids]
                for future in futures:
                    future.result()
        except Exception as exc:  # never let the download thread die silently
            result.error = self._tr("msg_error_unexpected", error=str(exc))
            log_fn(result.error)

        if self._cancel_event.is_set():
            result.cancelled = True
            self._log(log_fn, "log_cancelled")
            self._cleanup(work_root)
            return result

        try:
            if options.save_as_zip:
                self._log(log_fn, "log_zipping", name=collection_name)
                zip_base = self._unique_path(
                    os.path.join(options.destination_dir, collection_name), ".zip"
                )
                shutil.make_archive(
                    zip_base, "zip", root_dir=work_root, base_dir=collection_name
                )
                result.output_path = zip_base + ".zip"
            else:
                self._log(log_fn, "log_moving", path=options.destination_dir)
                final_dir = self._unique_path(
                    os.path.join(options.destination_dir, collection_name), ""
                )
                shutil.move(work_dir, final_dir)
                result.output_path = final_dir
        except OSError as exc:
            result.error = self._tr("msg_error_unexpected", error=str(exc))
            log_fn(result.error)
        finally:
            self._cleanup(work_root)

        self._log(log_fn, "log_done")
        return result

    @staticmethod
    def _unique_path(base_path: str, suffix: str) -> str:
        """Avoid overwriting something that already exists by appending ' (2)', ' (3)', ..."""
        candidate = base_path
        i = 2
        while os.path.exists(candidate + suffix):
            candidate = f"{base_path} ({i})"
            i += 1
        return candidate

    @staticmethod
    def _cleanup(work_root: str) -> None:
        try:
            if os.path.exists(work_root):
                shutil.rmtree(work_root, ignore_errors=True)
        except OSError:
            pass
