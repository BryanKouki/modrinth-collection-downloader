"""
Graphical interface for the Modrinth Collection Downloader.

Compact, single-card layout: the download settings are the main focus, the
activity log is tucked away (collapsed) behind a small toggle so it doesn't
compete for attention, and a small details panel automatically lists which
items failed or were incompatible — and why — right after a download
finishes. A dedicated Cancel button sits centered below the main action
while a download is running.

Version/loader pickers are a search box on top of a real scrollable list
(tk.Listbox + ttk.Scrollbar) instead of a dropdown, so the user can either
scroll through the options or just type a value that isn't in the list yet.
"""

from __future__ import annotations

import os
import queue
import sys
import threading
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk
from typing import Any, List, Optional, Tuple

import customtkinter as ctk

from .downloader import DownloadManager, DownloadOptions, DownloadResult, ResultItem
from .i18n import t
from .version import APP_VERSION, AUTHOR, GITHUB_URL

# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Color palette — the exact dark-theme tokens Modrinth's own site uses
# (extracted from their published CSS custom properties: --surface-*,
# --color-text-*, --color-brand, --color-red/orange/gray, --radius-*).
# This keeps the app's colors authentically "Modrinth", while the layout
# below stays our own compact single-card form rather than a copy of
# their page structure.
# ---------------------------------------------------------------------------
BG = "#16181c"              # --surface-1 (page background)
CARD = "#27292e"            # --surface-3 (--color-raised-bg)
CARD_BORDER = "#34363c"     # --surface-4 (--color-button-bg / divider)
INPUT_BG = "#1d1f23"        # --surface-2
INPUT_BORDER = "#34363c"    # --surface-4
GREEN = "#1bd96a"           # --color-green-500 (--color-brand)
GREEN_HOVER = "#0faa4f"     # --color-green-600
RED = "#ff496e"             # --color-red-500
RED_HOVER = "#c8083d"       # --color-red-700
ORANGE = "#ffa347"          # --color-orange-400
GRAY = "#9fa4b3"            # --color-gray-500 (--color-secondary base)
TEXT = "#ffffff"            # --color-text-primary
LABEL = "#96a2b0"           # --color-text-tertiary (--color-secondary)
BASE_TEXT = "#b0bac5"       # --color-text-default (--color-base)
ACCENT_CONTRAST = "#000000"  # --color-accent-contrast (text on brand-green buttons)
DISABLED_BG = "#1a1c20"     # --surface-1-5

# Radius scale (--radius-sm/md/lg), used consistently instead of ad hoc values.
RADIUS_SM = 8
RADIUS_MD = 12
RADIUS_LG = 16

# Official per-loader accent colors, straight from Modrinth's own
# --color-platform-* tokens — used to color the mod loader list so each
# entry reads the same way it does on the real site.
LOADER_COLORS = {
    "fabric": "#dbb69b",
    "quilt": "#c796f9",
    "forge": "#959eef",
    "neoforge": "#f99e6b",
    "liteloader": "#7ab0ee",
    "bukkit": "#f6af7b",
    "bungeecord": "#d2c080",
    "folia": "#a5e388",
    "paper": "#ee8888",
    "purpur": "#c3abf7",
    "spigot": "#f1cc84",
    "velocity": "#83d5ef",
    "waterfall": "#78a4fb",
    "sponge": "#f9e580",
    "datapack": "#b4bac5",
}

# Loaders ordered by real-world popularity — unknown loaders returned by the
# API (e.g. a brand-new one) are appended alphabetically after these.
LOADER_POPULARITY = [
    "neoforge", "fabric", "forge", "quilt",
    "paper", "spigot", "purpur", "bukkit", "folia", "sponge",
    "velocity", "waterfall", "bungeecord",
    "datapack",
]

DEFAULT_MC_VERSIONS = [
    "1.21.4", "1.21.3", "1.21.1", "1.21", "1.20.6", "1.20.4", "1.20.2",
    "1.20.1", "1.19.4", "1.19.2", "1.18.2", "1.17.1", "1.16.5", "1.12.2",
]
DEFAULT_LOADERS = list(LOADER_POPULARITY)


def resource_path(relative_path: str) -> str:
    """Resolve the path to a bundled resource (e.g. the app icon).

    Works both when running from source (project root is one level above
    this app/ package) and when running inside a PyInstaller --onefile
    build, where bundled data files are extracted to a temp folder exposed
    as sys._MEIPASS.
    """
    base_path = getattr(sys, "_MEIPASS", None)
    if base_path is None:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def sort_by_popularity(names: List[str]) -> List[str]:
    """Sort loader names by LOADER_POPULARITY, unknown ones last (alphabetically)."""
    seen: List[str] = []
    for name in names:
        if name not in seen:
            seen.append(name)

    def sort_key(name: str) -> Tuple[int, Any]:
        low = name.lower()
        if low in LOADER_POPULARITY:
            return (0, LOADER_POPULARITY.index(low))
        return (1, low)

    return sorted(seen, key=sort_key)


class SearchableSelectList(ctk.CTkFrame):
    """A compact search box on top of a real scrollable list — used for the
    Minecraft version and mod loader pickers, instead of a dropdown you have
    to keep clicking to scroll through.

    The search entry both filters the list below it AND holds the current
    value (so the user can type something that isn't in the list at all,
    e.g. a version that was just released).
    """

    def __init__(self, master, items: Optional[List[str]] = None, placeholder: str = "",
                 list_height: int = 4, item_colors: Optional[dict] = None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._all_items: List[str] = list(items or [])
        self._item_colors = item_colors or {}

        self.entry = ctk.CTkEntry(
            self, height=32, placeholder_text=placeholder,
            fg_color=INPUT_BG, border_color=INPUT_BORDER, text_color=TEXT,
            placeholder_text_color=GRAY,
        )
        self.entry.pack(fill="x")
        self.entry.bind("<KeyRelease>", self._on_search_changed)

        list_container = tk.Frame(self, bg=INPUT_BG, highlightthickness=1, highlightbackground=INPUT_BORDER)
        list_container.pack(fill="x", pady=(4, 0))

        scrollbar = ttk.Scrollbar(list_container, orient="vertical", style="Dark.Vertical.TScrollbar")
        scrollbar.pack(side="right", fill="y")

        self.listbox = tk.Listbox(
            list_container, height=list_height, bg=INPUT_BG, fg=TEXT, bd=0, highlightthickness=0,
            selectbackground=GREEN, selectforeground=ACCENT_CONTRAST,
            activestyle="none", font=("Segoe UI", 10),
            yscrollcommand=scrollbar.set,
        )
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.listbox.yview)
        self.listbox.bind("<<ListboxSelect>>", self._on_select)

        self._refresh_list(self._all_items)

    def _refresh_list(self, items: List[str]) -> None:
        self.listbox.delete(0, "end")
        for item in items:
            self.listbox.insert("end", item)
            color = self._item_colors.get(item.lower())
            if color:
                self.listbox.itemconfig(self.listbox.size() - 1, foreground=color)

    def _on_search_changed(self, _event=None) -> None:
        query = self.entry.get().strip().lower()
        if not query:
            self._refresh_list(self._all_items)
            return
        filtered = [i for i in self._all_items if query in i.lower()]
        self._refresh_list(filtered)

    def _on_select(self, _event=None) -> None:
        selection = self.listbox.curselection()
        if not selection:
            return
        value = self.listbox.get(selection[0])
        self.entry.delete(0, "end")
        self.entry.insert(0, value)

    def get(self) -> str:
        return self.entry.get().strip()

    def set(self, value: str) -> None:
        self.entry.delete(0, "end")
        self.entry.insert(0, value)

    def set_items(self, items: List[str]) -> None:
        """Replace the underlying data set and show it in full.

        Deliberately does NOT re-apply the search box's current text as a
        filter: this runs once, when fresh data arrives from the API, and
        a previously typed/preset value (e.g. a default loader) should stay
        in the entry untouched while the list below shows every option.
        """
        self._all_items = list(items)
        self._refresh_list(self._all_items)

    def configure_state(self, state: str) -> None:
        self.entry.configure(state=state)
        self.listbox.configure(state=state)


class ModrinthDownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.lang = "en"
        self.manager: Optional[DownloadManager] = None
        self.is_running = False
        self.log_visible = False
        self.event_queue: "queue.Queue" = queue.Queue()

        # Registry of (widget, i18n_key) pairs whose .configure(text=...) is
        # refreshed automatically on every language switch.
        self._i18n_targets: List[Tuple[Any, str]] = []
        self._i18n_placeholders: List[Tuple[Any, str]] = []

        self._setup_ttk_style()

        self.title(t(self.lang, "app_title"))
        self.geometry("740x880")
        self.minsize(620, 620)
        self.configure(fg_color=BG)
        ctk.set_appearance_mode("dark")
        self._apply_app_icon()

        self._build_widgets()
        self.refresh_texts()
        self._start_remote_options_fetch()
        self.after(100, self._process_events)

    # ------------------------------------------------------------------
    # ttk styling (for the scrollbars used inside SearchableSelectList)
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # App icon (window title bar + taskbar)
    # ------------------------------------------------------------------
    def _apply_app_icon(self) -> None:
        # .ico: sets the title bar and taskbar icon on Windows.
        ico_path = resource_path("icon.ico")
        if os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
            except Exception:
                pass

        # .png fallback via iconphoto: covers Linux/macOS (and reinforces
        # Windows), where iconbitmap alone may not apply everywhere.
        png_path = resource_path("icon.png")
        if os.path.exists(png_path):
            try:
                icon_image = tk.PhotoImage(file=png_path)
                self.iconphoto(True, icon_image)
                self._icon_photo_ref = icon_image  # keep a reference alive
            except Exception:
                pass

    def _setup_ttk_style(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(
            "Dark.Vertical.TScrollbar",
            background=CARD_BORDER, troughcolor=INPUT_BG, bordercolor=INPUT_BG,
            arrowcolor=TEXT, relief="flat",
        )
        style.map("Dark.Vertical.TScrollbar", background=[("active", GREEN)])

    # ------------------------------------------------------------------
    # Small helpers that register widgets for automatic translation
    # ------------------------------------------------------------------
    def _label(self, parent, key: str, **kw) -> ctk.CTkLabel:
        lbl = ctk.CTkLabel(parent, text="", **kw)
        self._i18n_targets.append((lbl, key))
        return lbl

    def _button(self, parent, key: str, **kw) -> ctk.CTkButton:
        btn = ctk.CTkButton(parent, text="", **kw)
        self._i18n_targets.append((btn, key))
        return btn

    def _checkbox(self, parent, key: str, variable, **kw) -> ctk.CTkCheckBox:
        chk = ctk.CTkCheckBox(
            parent, text="", variable=variable, fg_color=GREEN, hover_color=GREEN_HOVER,
            text_color=TEXT, checkmark_color=ACCENT_CONTRAST, **kw,
        )
        self._i18n_targets.append((chk, key))
        return chk

    def _radio(self, parent, key: str, variable, value: str, **kw) -> ctk.CTkRadioButton:
        rb = ctk.CTkRadioButton(
            parent, text="", variable=variable, value=value,
            fg_color=GREEN, hover_color=GREEN_HOVER, text_color=TEXT, **kw,
        )
        self._i18n_targets.append((rb, key))
        return rb

    def _section_label(self, parent, key: str) -> ctk.CTkLabel:
        return self._label(
            parent, key, font=ctk.CTkFont(size=11, weight="bold"), text_color=LABEL, anchor="w",
        )

    # ------------------------------------------------------------------
    # Widget construction
    # ------------------------------------------------------------------
    def _build_widgets(self) -> None:
        self.scroll = ctk.CTkScrollableFrame(self, fg_color=BG)
        self.scroll.pack(fill="both", expand=True)
        self.scroll.grid_columnconfigure(0, weight=1)

        content = ctk.CTkFrame(self.scroll, fg_color=BG)
        content.pack(fill="both", expand=True, padx=24, pady=(14, 22))
        content.grid_columnconfigure(0, weight=1)

        self._build_topbar(content)
        self._build_header(content)
        self._build_collection_card(content)
        self._build_main_card(content)
        self._build_results(content)
        self._build_log(content)
        self._build_footer(content)

        self._all_inputs = [
            self.entry_collection, self.btn_fetch_items, self.btn_select_all, self.btn_select_none,
            self.chk_mods, self.chk_resourcepacks, self.chk_shaders,
            self.chk_dependencies, self.chk_prefer_stable,
            self.radio_folder, self.radio_zip, self.btn_choose_folder,
        ]

    def _build_topbar(self, parent) -> None:
        bar = ctk.CTkFrame(parent, fg_color="transparent")
        bar.pack(fill="x", pady=(0, 4))

        self.btn_guide = self._button(
            bar, "btn_guide", width=88, height=28,
            fg_color="transparent", border_width=1, border_color=CARD_BORDER,
            text_color=LABEL, hover_color=CARD, command=self._open_guide,
        )
        self.btn_guide.pack(side="right", padx=(6, 0))

        self.btn_lang = self._button(
            bar, "btn_lang", width=54, height=28,
            fg_color="transparent", border_width=1, border_color=CARD_BORDER,
            text_color=LABEL, hover_color=CARD, command=self._toggle_language,
        )
        self.btn_lang.pack(side="right")

    def _build_header(self, parent) -> None:
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", pady=(2, 14))

        self.lbl_title = self._label(
            header, "app_title", font=ctk.CTkFont(size=25, weight="bold"), text_color=GREEN, anchor="w",
        )
        self.lbl_title.pack(fill="x")

        self.lbl_subtitle = self._label(
            header, "app_subtitle", font=ctk.CTkFont(size=13), text_color=LABEL, anchor="w",
        )
        self.lbl_subtitle.pack(fill="x", pady=(3, 0))

    def _build_collection_card(self, parent) -> None:
        card = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=RADIUS_LG, border_width=1, border_color=CARD_BORDER)
        card.pack(fill="x", pady=(0, 14))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=20, pady=18)

        self.lbl_collection = self._section_label(inner, "label_collection")
        self.lbl_collection.pack(fill="x")

        entry_row = ctk.CTkFrame(inner, fg_color="transparent")
        entry_row.pack(fill="x", pady=(6, 0))
        entry_row.grid_columnconfigure(0, weight=1)

        self.entry_collection = ctk.CTkEntry(
            entry_row, height=36, fg_color=INPUT_BG, border_color=INPUT_BORDER,
            text_color=TEXT, placeholder_text_color=GRAY,
        )
        self.entry_collection.grid(row=0, column=0, sticky="ew")
        self.entry_collection.bind("<KeyRelease>", self._on_collection_text_changed)
        self._i18n_placeholders.append((self.entry_collection, "placeholder_collection"))

        self.btn_fetch_items = self._button(
            entry_row, "btn_fetch_items", height=36, width=120, fg_color=CARD_BORDER,
            hover_color=INPUT_BORDER, text_color=TEXT, command=self._on_fetch_items_clicked,
        )
        self.btn_fetch_items.grid(row=0, column=1, padx=(8, 0))

        # Individual, checkable items — populated once the collection above
        # is loaded. Everything defaults to checked (included).
        items_header = ctk.CTkFrame(inner, fg_color="transparent")
        items_header.pack(fill="x", pady=(16, 6))
        self.lbl_items = self._section_label(items_header, "label_items")
        self.lbl_items.pack(side="left")

        self.btn_select_none = self._button(
            items_header, "btn_select_none", width=84, height=22, fg_color="transparent",
            border_width=1, border_color=CARD_BORDER, text_color=LABEL, hover_color=INPUT_BG,
            font=ctk.CTkFont(size=11), command=self._select_no_items,
        )
        self.btn_select_none.pack(side="right", padx=(6, 0))
        self.btn_select_all = self._button(
            items_header, "btn_select_all", width=84, height=22, fg_color="transparent",
            border_width=1, border_color=CARD_BORDER, text_color=LABEL, hover_color=INPUT_BG,
            font=ctk.CTkFont(size=11), command=self._select_all_items,
        )
        self.btn_select_all.pack(side="right")

        items_outer = tk.Frame(inner, bg=INPUT_BG, highlightthickness=1, highlightbackground=INPUT_BORDER)
        items_outer.pack(fill="x")

        items_scrollbar = ttk.Scrollbar(items_outer, orient="vertical", style="Dark.Vertical.TScrollbar")
        items_scrollbar.pack(side="right", fill="y")

        self.items_canvas = tk.Canvas(
            items_outer, bg=INPUT_BG, highlightthickness=0, height=210,
            yscrollcommand=items_scrollbar.set,
        )
        self.items_canvas.pack(side="left", fill="both", expand=True)
        items_scrollbar.config(command=self.items_canvas.yview)

        self.items_inner = tk.Frame(self.items_canvas, bg=INPUT_BG)
        self._items_window = self.items_canvas.create_window((0, 0), window=self.items_inner, anchor="nw")

        def _on_inner_configure(_event=None):
            self.items_canvas.configure(scrollregion=self.items_canvas.bbox("all"))

        def _on_canvas_configure(event):
            self.items_canvas.itemconfig(self._items_window, width=event.width)

        self.items_inner.bind("<Configure>", _on_inner_configure)
        self.items_canvas.bind("<Configure>", _on_canvas_configure)

        self.preview_items: List[dict] = []
        self.item_vars: dict = {}
        self._fetched_collection_text: Optional[str] = None
        self._dynamic_item_widgets: List[Any] = []
        self._render_items_checklist()

    def _build_main_card(self, parent) -> None:
        card = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=RADIUS_LG, border_width=1, border_color=CARD_BORDER)
        card.pack(fill="x", pady=(0, 14))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=20, pady=18)
        inner.grid_columnconfigure(0, weight=1)
        inner.grid_columnconfigure(1, weight=1)

        row = 0

        # Version / Loader
        self.lbl_mc_version = self._section_label(inner, "label_mc_version")
        self.lbl_mc_version.grid(row=row, column=0, sticky="w")
        self.lbl_loader = self._section_label(inner, "label_loader")
        self.lbl_loader.grid(row=row, column=1, sticky="w", padx=(14, 0))
        row += 1

        self.list_version = SearchableSelectList(inner, items=DEFAULT_MC_VERSIONS, list_height=4)
        self.list_version.grid(row=row, column=0, sticky="ew", pady=(6, 2))
        self._i18n_placeholders.append((self.list_version.entry, "placeholder_mc_version"))

        self.list_loader = SearchableSelectList(inner, items=DEFAULT_LOADERS, list_height=4, item_colors=LOADER_COLORS)
        self.list_loader.grid(row=row, column=1, sticky="ew", padx=(14, 0), pady=(6, 2))
        self.list_loader.set("fabric")
        self._i18n_placeholders.append((self.list_loader.entry, "placeholder_loader"))
        row += 1

        self.lbl_hint_editable = self._label(
            inner, "hint_editable", font=ctk.CTkFont(size=11), text_color=GRAY, anchor="w",
        )
        self.lbl_hint_editable.grid(row=row, column=0, columnspan=2, sticky="w", pady=(4, 14))
        row += 1

        # Content to download
        self.lbl_include = self._section_label(inner, "label_include")
        self.lbl_include.grid(row=row, column=0, columnspan=2, sticky="w")
        row += 1

        include_row = ctk.CTkFrame(inner, fg_color="transparent")
        include_row.grid(row=row, column=0, columnspan=2, sticky="w", pady=(8, 14))
        row += 1

        self.var_include_mods = ctk.BooleanVar(value=True)
        self.var_include_resourcepacks = ctk.BooleanVar(value=True)
        self.var_include_shaders = ctk.BooleanVar(value=True)

        self.chk_mods = self._checkbox(
            include_row, "chk_mods", self.var_include_mods,
            command=lambda: self._on_category_toggle("mod"),
        )
        self.chk_mods.pack(side="left", padx=(0, 14))
        self.chk_resourcepacks = self._checkbox(
            include_row, "chk_resourcepacks", self.var_include_resourcepacks,
            command=lambda: self._on_category_toggle("resourcepack"),
        )
        self.chk_resourcepacks.pack(side="left", padx=(0, 14))
        self.chk_shaders = self._checkbox(
            include_row, "chk_shaders", self.var_include_shaders,
            command=lambda: self._on_category_toggle("shader"),
        )
        self.chk_shaders.pack(side="left")

        # Dependencies
        self.lbl_dependencies = self._section_label(inner, "label_dependencies")
        self.lbl_dependencies.grid(row=row, column=0, columnspan=2, sticky="w")
        row += 1
        self.var_dependencies = ctk.BooleanVar(value=True)
        self.chk_dependencies = self._checkbox(inner, "chk_dependencies", self.var_dependencies)
        self.chk_dependencies.grid(row=row, column=0, columnspan=2, sticky="w", pady=(8, 14))
        row += 1

        # Release preference
        self.lbl_release_pref = self._section_label(inner, "label_release_pref")
        self.lbl_release_pref.grid(row=row, column=0, columnspan=2, sticky="w")
        row += 1
        self.var_prefer_stable = ctk.BooleanVar(value=True)
        self.chk_prefer_stable = self._checkbox(inner, "chk_prefer_stable", self.var_prefer_stable)
        self.chk_prefer_stable.grid(row=row, column=0, columnspan=2, sticky="w", pady=(8, 14))
        row += 1

        # Where to save
        self.lbl_save_options = self._section_label(inner, "label_save_options")
        self.lbl_save_options.grid(row=row, column=0, columnspan=2, sticky="w")
        row += 1

        save_row = ctk.CTkFrame(inner, fg_color="transparent")
        save_row.grid(row=row, column=0, columnspan=2, sticky="w", pady=(8, 10))
        row += 1
        self.var_save_mode = ctk.StringVar(value="folder")
        self.radio_folder = self._radio(save_row, "radio_save_folder", self.var_save_mode, "folder")
        self.radio_folder.pack(side="left", padx=(0, 20))
        self.radio_zip = self._radio(save_row, "radio_save_zip", self.var_save_mode, "zip")
        self.radio_zip.pack(side="left")

        dest_row = ctk.CTkFrame(inner, fg_color="transparent")
        dest_row.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        dest_row.grid_columnconfigure(1, weight=1)
        row += 1
        self.btn_choose_folder = self._button(
            dest_row, "btn_choose_folder", height=32, fg_color=CARD_BORDER, hover_color=INPUT_BORDER,
            text_color=TEXT, command=self._choose_destination,
        )
        self.btn_choose_folder.grid(row=0, column=0, sticky="w")
        self.lbl_destination_value = ctk.CTkLabel(
            dest_row, text="", font=ctk.CTkFont(size=12), text_color=GRAY, anchor="w",
        )
        self.lbl_destination_value.grid(row=0, column=1, sticky="ew", padx=(12, 0))
        self.destination_dir = ""

        self.lbl_hint_output = self._label(
            inner, "hint_output_name", font=ctk.CTkFont(size=11), text_color=GRAY, anchor="w",
        )
        self.lbl_hint_output.grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 16))
        row += 1

        # Download CTA
        self.btn_download = self._button(
            inner, "btn_download", height=42, corner_radius=RADIUS_MD,
            fg_color=GREEN, hover_color=GREEN_HOVER, text_color=ACCENT_CONTRAST,
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._on_download_clicked,
        )
        self.btn_download.grid(row=row, column=0, columnspan=2, sticky="ew")
        row += 1

        # Cancel button — centered, only usable while a download is running.
        self.btn_cancel = self._button(
            inner, "btn_cancel", width=140, height=30, corner_radius=RADIUS_SM,
            fg_color=DISABLED_BG, hover_color=DISABLED_BG, text_color=LABEL,
            state="disabled", command=self._on_cancel_clicked,
        )
        self.btn_cancel.grid(row=row, column=0, columnspan=2, pady=(10, 0))
        row += 1

        self.progress = ctk.CTkProgressBar(inner, progress_color=GREEN, fg_color=INPUT_BG)
        self.progress.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        self.progress.set(0)
        row += 1

        self.lbl_status = self._label(
            inner, "status_idle", font=ctk.CTkFont(size=12), text_color=BASE_TEXT, anchor="w",
        )
        self.lbl_status.grid(row=row, column=0, columnspan=2, sticky="w", pady=(6, 0))

    def _build_results(self, parent) -> None:
        card = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=RADIUS_LG, border_width=1, border_color=CARD_BORDER)
        card.pack(fill="x", pady=(0, 14))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=18, pady=16)

        self.lbl_results = self._label(
            inner, "label_results", font=ctk.CTkFont(size=12, weight="bold"), text_color=LABEL, anchor="w",
        )
        self.lbl_results.pack(fill="x", pady=(0, 10))

        stats_row = ctk.CTkFrame(inner, fg_color="transparent")
        stats_row.pack(fill="x")
        stats_row.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.stat_success = self._stat_box(stats_row, GREEN, 0)
        self.stat_failed = self._stat_box(stats_row, RED, 1)
        self.stat_incompatible = self._stat_box(stats_row, ORANGE, 2)
        self.stat_skipped = self._stat_box(stats_row, GRAY, 3)

        # Compact details panel: which items failed/were incompatible, and why.
        # Populated automatically at the end of each download.
        self.details_text = tk.Text(
            inner, height=5, bg=INPUT_BG, fg=TEXT, insertbackground=TEXT,
            relief="flat", wrap="word", font=("Consolas", 10), padx=8, pady=6,
        )
        self.details_text.pack(fill="x", pady=(10, 0))
        self.details_text.tag_configure("fail", foreground=RED)
        self.details_text.tag_configure("warn", foreground=ORANGE)
        self.details_text.tag_configure("muted", foreground=GRAY)
        self._set_details_placeholder()

    def _stat_box(self, parent, color: str, col: int) -> dict:
        box = ctk.CTkFrame(parent, fg_color=INPUT_BG, corner_radius=RADIUS_MD)
        box.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 8, 0))
        value = ctk.CTkLabel(box, text="0", font=ctk.CTkFont(size=18, weight="bold"), text_color=color)
        value.pack(pady=(8, 0))
        label = self._label(box, {0: "results_success", 1: "results_failed",
                                   2: "results_incompatible", 3: "results_skipped"}[col],
                             font=ctk.CTkFont(size=10), text_color=GRAY)
        label.pack(pady=(0, 8))
        return {"box": box, "value": value, "label": label}

    def _build_log(self, parent) -> None:
        card = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=RADIUS_LG, border_width=1, border_color=CARD_BORDER)
        card.pack(fill="x", pady=(0, 14))
        self.log_inner = ctk.CTkFrame(card, fg_color="transparent")
        self.log_inner.pack(fill="both", expand=True, padx=18, pady=14)

        top = ctk.CTkFrame(self.log_inner, fg_color="transparent")
        top.pack(fill="x")
        self.lbl_log = self._label(
            top, "label_log", font=ctk.CTkFont(size=12, weight="bold"), text_color=LABEL, anchor="w",
        )
        self.lbl_log.pack(side="left")

        self.btn_clear_log = self._button(
            top, "btn_clear_log", width=64, height=24, fg_color="transparent",
            border_width=1, border_color=CARD_BORDER, text_color=LABEL, hover_color=INPUT_BG,
            command=self._clear_log,
        )
        self.btn_clear_log.pack(side="right", padx=(6, 0))
        self.btn_toggle_log = self._button(
            top, "btn_show_log", width=64, height=24, fg_color="transparent",
            border_width=1, border_color=CARD_BORDER, text_color=LABEL, hover_color=INPUT_BG,
            command=self._toggle_log,
        )
        self.btn_toggle_log.pack(side="right")

        self.log_content = ctk.CTkFrame(self.log_inner, fg_color="transparent")
        # Not packed yet — the log starts collapsed (see _toggle_log/log_visible).

        self.log_text = tk.Text(
            self.log_content, height=8, bg=INPUT_BG, fg=TEXT, insertbackground=TEXT,
            relief="flat", wrap="word", font=("Consolas", 10), padx=10, pady=8,
        )
        self.log_text.pack(fill="both", expand=True, pady=(10, 0))
        self.log_text.configure(state="disabled")
        self.log_text.tag_configure("ok", foreground=GREEN)
        self.log_text.tag_configure("fail", foreground=RED)
        self.log_text.tag_configure("warn", foreground=ORANGE)
        self.log_text.tag_configure("muted", foreground=GRAY)
        self.log_text.tag_configure("normal", foreground=TEXT)

    def _build_footer(self, parent) -> None:
        footer = ctk.CTkFrame(parent, fg_color="transparent")
        footer.pack(fill="x", pady=(2, 0))

        row1 = ctk.CTkFrame(footer, fg_color="transparent")
        row1.pack()
        self.lbl_made_by = ctk.CTkLabel(row1, text="", font=ctk.CTkFont(size=12), text_color=GRAY)
        self.lbl_made_by.pack(side="left")
        self.lbl_sep1 = ctk.CTkLabel(row1, text="  \u2022  ", font=ctk.CTkFont(size=12), text_color=GRAY)
        self.lbl_sep1.pack(side="left")
        self.btn_star = ctk.CTkButton(
            row1, text="", fg_color="transparent", hover=False, text_color=GREEN,
            font=ctk.CTkFont(size=12, underline=True), command=lambda: webbrowser.open(GITHUB_URL),
        )
        self.btn_star.pack(side="left")

        self.lbl_powered = ctk.CTkLabel(footer, text="", font=ctk.CTkFont(size=11), text_color=GRAY)
        self.lbl_powered.pack(pady=(4, 0))

    # ------------------------------------------------------------------
    # Language
    # ------------------------------------------------------------------
    def _toggle_language(self) -> None:
        self.lang = "pt" if self.lang == "en" else "en"
        self.refresh_texts()

    def refresh_texts(self) -> None:
        L = self.lang
        self.title(t(L, "app_title"))

        for widget, key in self._i18n_targets:
            widget.configure(text=t(L, key))
        for widget, key in self._i18n_placeholders:
            widget.configure(placeholder_text=t(L, key))

        if self.destination_dir:
            self.lbl_destination_value.configure(text=self.destination_dir)
        else:
            self.lbl_destination_value.configure(text=t(L, "placeholder_destination"))

        self.btn_download.configure(text=t(L, "btn_downloading" if self.is_running else "btn_download"))
        self.lbl_status.configure(text=t(L, "status_running" if self.is_running else "status_idle"))
        self.btn_toggle_log.configure(text=t(L, "btn_hide_log" if self.log_visible else "btn_show_log"))

        self._render_items_checklist()

        self.lbl_made_by.configure(text=t(L, "footer_made_by", author=AUTHOR))
        self.btn_star.configure(text=t(L, "footer_star"))
        self.lbl_powered.configure(
            text=f'{t(L, "footer_powered")}   {t(L, "footer_version", version=APP_VERSION)}'
        )

        self._refresh_details_panel_texts()

    # ------------------------------------------------------------------
    # Guide
    # ------------------------------------------------------------------
    def _open_guide(self) -> None:
        L = self.lang
        win = ctk.CTkToplevel(self)
        win.title(t(L, "guide_title"))
        win.geometry("560x620")
        win.configure(fg_color=BG)
        win.transient(self)
        ico_path = resource_path("icon.ico")
        if os.path.exists(ico_path):
            try:
                win.after(200, lambda: win.iconbitmap(ico_path))
            except Exception:
                pass

        ctk.CTkLabel(
            win, text=t(L, "guide_title"), font=ctk.CTkFont(size=18, weight="bold"),
            text_color=GREEN,
        ).pack(padx=20, pady=(18, 10), anchor="w")

        box = ctk.CTkTextbox(
            win, fg_color=INPUT_BG, text_color=TEXT, wrap="word",
            font=ctk.CTkFont(size=12),
        )
        box.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        box.insert("1.0", t(L, "guide_text"))
        box.configure(state="disabled")

        ctk.CTkButton(
            win, text=t(L, "btn_close"), fg_color=GREEN, hover_color=GREEN_HOVER,
            text_color=ACCENT_CONTRAST, command=win.destroy,
        ).pack(pady=(0, 18))

    # ------------------------------------------------------------------
    # Destination
    # ------------------------------------------------------------------
    def _choose_destination(self) -> None:
        path = filedialog.askdirectory(title=t(self.lang, "btn_choose_folder"))
        if path:
            self.destination_dir = path
            self.lbl_destination_value.configure(text=path)

    # ------------------------------------------------------------------
    # Items checklist (individual mods/resourcepacks/shaders in the
    # collection — fetched on demand, all checked by default)
    # ------------------------------------------------------------------
    def _item_category(self, project_type: str) -> str:
        if project_type == "shader":
            return "shader"
        if project_type == "resourcepack":
            return "resourcepack"
        return "mod"  # mod, modpack, plugin, datapack, or unknown

    def _on_collection_text_changed(self, _event=None) -> None:
        # If the collection field changes after a fetch, the loaded items no
        # longer match it — clear them so the list can't look stale.
        if self.entry_collection.get().strip() != self._fetched_collection_text and self.preview_items:
            self.preview_items = []
            self.item_vars = {}
            self._render_items_checklist()

    def _on_fetch_items_clicked(self) -> None:
        raw = self.entry_collection.get().strip()
        L = self.lang
        if not raw:
            messagebox.showerror(t(L, "msg_error_title"), t(L, "msg_error_no_collection"))
            return

        self.btn_fetch_items.configure(state="disabled", text=t(L, "btn_fetch_items_loading"))

        def worker():
            from concurrent.futures import ThreadPoolExecutor

            from .api import ModrinthClient, extract_collection_id

            client = ModrinthClient()
            collection_id = extract_collection_id(raw)
            collection = client.get_collection(collection_id)
            if not collection:
                self.event_queue.put({"type": "preview_error", "id": collection_id})
                return

            project_ids = collection.get("projects", []) or []
            fetched: dict = {}
            lock = threading.Lock()

            def fetch_one(pid: str) -> None:
                proj = client.get_project(pid)
                with lock:
                    fetched[pid] = proj

            if project_ids:
                with ThreadPoolExecutor(max_workers=8) as executor:
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

            self.event_queue.put({"type": "preview_loaded", "items": items, "raw_text": raw})

        threading.Thread(target=worker, daemon=True).start()

    def _render_items_checklist(self) -> None:
        for widget in self._dynamic_item_widgets:
            widget.destroy()
        self._dynamic_item_widgets = []

        if not self.preview_items:
            placeholder = tk.Label(
                self.items_inner, text=t(self.lang, "items_placeholder"),
                bg=INPUT_BG, fg=GRAY, font=("Segoe UI", 11), wraplength=560,
                justify="left", anchor="w", padx=10, pady=10,
            )
            placeholder.pack(fill="x")
            self._dynamic_item_widgets.append(placeholder)
            self.items_canvas.configure(height=60)
            return

        groups: dict = {"mod": [], "resourcepack": [], "shader": []}
        for item in self.preview_items:
            groups.setdefault(self._item_category(item["type"]), []).append(item)

        self.items_canvas.configure(height=210)

        for cat_key, header_key in (
            ("mod", "group_mods"), ("resourcepack", "group_resourcepacks"), ("shader", "group_shaders"),
        ):
            cat_items = groups.get(cat_key, [])
            if not cat_items:
                continue

            header = tk.Label(
                self.items_inner, text=t(self.lang, header_key),
                bg=INPUT_BG, fg=LABEL, font=("Segoe UI", 10, "bold"),
                anchor="w", padx=10, pady=(6),
            )
            header.pack(fill="x", pady=(6, 0))
            self._dynamic_item_widgets.append(header)

            for item in cat_items:
                var = self.item_vars.get(item["id"])
                if var is None:
                    var = ctk.BooleanVar(value=True)
                    self.item_vars[item["id"]] = var
                cb = ctk.CTkCheckBox(
                    self.items_inner, text=item["name"], variable=var,
                    fg_color=GREEN, hover_color=GREEN_HOVER, text_color=TEXT,
                    checkmark_color=ACCENT_CONTRAST, font=ctk.CTkFont(size=12),
                    bg_color=INPUT_BG,
                )
                cb.pack(fill="x", anchor="w", padx=10, pady=1)
                self._dynamic_item_widgets.append(cb)

    def _select_all_items(self) -> None:
        for var in self.item_vars.values():
            var.set(True)

    def _select_no_items(self) -> None:
        for var in self.item_vars.values():
            var.set(False)

    def _on_category_toggle(self, category: str) -> None:
        value = {
            "mod": self.var_include_mods,
            "resourcepack": self.var_include_resourcepacks,
            "shader": self.var_include_shaders,
        }[category].get()
        for item in self.preview_items:
            if self._item_category(item["type"]) == category:
                var = self.item_vars.get(item["id"])
                if var is not None:
                    var.set(value)

    # ------------------------------------------------------------------
    # Fetch remote versions/loaders (does not block the UI)
    # ------------------------------------------------------------------
    def _start_remote_options_fetch(self) -> None:
        def worker():
            try:
                client = DownloadManager(self.lang).client
                versions_data = client.get_game_versions() or []
                loaders_data = client.get_loaders() or []
                versions = [
                    v["version"] for v in versions_data
                    if v.get("version_type") == "release" and v.get("version")
                ]
                loaders = [l["name"] for l in loaders_data if l.get("name")]
                if versions or loaders:
                    self.event_queue.put({"type": "options_loaded", "versions": versions, "loaders": loaders})
            except Exception:
                pass  # keep the default lists on network failure

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------
    # Log helpers
    # ------------------------------------------------------------------
    def _toggle_log(self) -> None:
        self.log_visible = not self.log_visible
        if self.log_visible:
            self.log_content.pack(fill="both", expand=True)
        else:
            self.log_content.pack_forget()
        self.btn_toggle_log.configure(text=t(self.lang, "btn_hide_log" if self.log_visible else "btn_show_log"))

    def _append_log(self, line: str) -> None:
        tag = "normal"
        head = line.upper()[:16]
        if head.startswith("OK:"):
            tag = "ok"
        elif any(k in head for k in ("FAIL", "FALHA", "ERROR", "ERRO")):
            tag = "fail"
        elif "INCOMPAT" in head:
            tag = "warn"
        elif any(k in head for k in ("SKIP", "IGNOR")):
            tag = "muted"

        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n", tag)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    # ------------------------------------------------------------------
    # Details panel (which items failed/were incompatible, and why)
    # ------------------------------------------------------------------
    def _set_details_placeholder(self) -> None:
        self.details_text.configure(state="normal")
        self.details_text.delete("1.0", "end")
        self.details_text.insert("1.0", t(self.lang, "details_empty"), "muted")
        self.details_text.configure(state="disabled")
        self._details_is_placeholder = True

    def _refresh_details_panel_texts(self) -> None:
        # Only re-render the placeholder on language switch; a populated
        # panel (after a real download) keeps its already-built content,
        # since re-translating stored reasons would require re-running.
        if getattr(self, "_details_is_placeholder", True):
            self._set_details_placeholder()

    def _update_details_panel(self, result: DownloadResult) -> None:
        cap = 6
        lines: List[Tuple[str, str]] = []

        for item in result.failed[:cap]:
            lines.append((f"\u2715 {item.name} \u2014 {item.reason}", "fail"))
        extra_failed = len(result.failed) - cap
        if extra_failed > 0:
            lines.append((t(self.lang, "details_more", count=extra_failed), "muted"))

        for item in result.incompatible[:cap]:
            lines.append((f"\u26a0 {item.name} \u2014 {item.reason}", "warn"))
        extra_incompatible = len(result.incompatible) - cap
        if extra_incompatible > 0:
            lines.append((t(self.lang, "details_more", count=extra_incompatible), "muted"))

        self.details_text.configure(state="normal")
        self.details_text.delete("1.0", "end")
        if not lines:
            self.details_text.insert("1.0", t(self.lang, "details_empty"), "muted")
            self._details_is_placeholder = True
        else:
            for text, tag in lines:
                self.details_text.insert("end", text + "\n", tag)
            self._details_is_placeholder = False
        self.details_text.configure(state="disabled")

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------
    def _on_download_clicked(self) -> None:
        L = self.lang
        collection = self.entry_collection.get().strip()
        version = self.list_version.get()
        loader = self.list_loader.get()

        if not collection:
            messagebox.showerror(t(L, "msg_error_title"), t(L, "msg_error_no_collection"))
            return
        if not version:
            messagebox.showerror(t(L, "msg_error_title"), t(L, "msg_error_no_version"))
            return
        if not loader:
            messagebox.showerror(t(L, "msg_error_title"), t(L, "msg_error_no_loader"))
            return
        if not (self.var_include_mods.get() or self.var_include_resourcepacks.get() or self.var_include_shaders.get()):
            messagebox.showerror(t(L, "msg_error_title"), t(L, "msg_error_no_category"))
            return
        if not self.destination_dir:
            messagebox.showerror(t(L, "msg_error_title"), t(L, "msg_error_no_destination"))
            return

        excluded_ids = {pid for pid, var in self.item_vars.items() if not var.get()}
        if self.item_vars and len(excluded_ids) == len(self.item_vars):
            messagebox.showerror(t(L, "msg_error_title"), t(L, "msg_error_no_items_selected"))
            return
        known_names = {item["id"]: item["name"] for item in self.preview_items}

        options = DownloadOptions(
            collection_input=collection,
            mc_version=version,
            loader=loader,
            include_mods=self.var_include_mods.get(),
            include_resourcepacks=self.var_include_resourcepacks.get(),
            include_shaders=self.var_include_shaders.get(),
            download_dependencies=self.var_dependencies.get(),
            prefer_stable=self.var_prefer_stable.get(),
            save_as_zip=(self.var_save_mode.get() == "zip"),
            destination_dir=self.destination_dir,
            excluded_project_ids=excluded_ids,
            known_names=known_names,
        )

        self._clear_log()
        self._reset_stats()
        self._set_details_placeholder()
        self._set_running_state(True)

        self.manager = DownloadManager(lang=self.lang)

        def log_fn(msg: str):
            self.event_queue.put({"type": "log", "message": msg})

        def progress_fn(done: int, total: int):
            self.event_queue.put({"type": "progress", "done": done, "total": total})

        def worker():
            result = self.manager.run(options, log_fn, progress_fn)
            self.event_queue.put({"type": "done", "result": result})

        threading.Thread(target=worker, daemon=True).start()

    def _on_cancel_clicked(self) -> None:
        if self.is_running and self.manager:
            self.manager.cancel()
            self.btn_cancel.configure(state="disabled")

    def _set_running_state(self, running: bool) -> None:
        self.is_running = running
        for widget in self._all_inputs:
            try:
                widget.configure(state="disabled" if running else "normal")
            except Exception:
                pass
        self.list_version.configure_state("disabled" if running else "normal")
        self.list_loader.configure_state("disabled" if running else "normal")

        self.btn_download.configure(
            text=t(self.lang, "btn_downloading" if running else "btn_download"),
            state="disabled" if running else "normal",
        )
        self.btn_cancel.configure(
            state="normal" if running else "disabled",
            fg_color=RED if running else DISABLED_BG,
            hover_color=RED_HOVER if running else DISABLED_BG,
            text_color=TEXT if running else LABEL,
        )
        self.lbl_status.configure(text=t(self.lang, "status_running" if running else "status_idle"))
        if not running:
            self.progress.set(0)

    def _reset_stats(self) -> None:
        for stat in (self.stat_success, self.stat_failed, self.stat_incompatible, self.stat_skipped):
            stat["value"].configure(text="0")

    # ------------------------------------------------------------------
    # Event queue coming from worker threads
    # ------------------------------------------------------------------
    def _process_events(self) -> None:
        try:
            while True:
                event = self.event_queue.get_nowait()
                etype = event["type"]
                if etype == "log":
                    self._append_log(event["message"])
                elif etype == "progress":
                    total = max(event["total"], 1)
                    self.progress.set(min(event["done"] / total, 1.0))
                elif etype == "options_loaded":
                    if event.get("versions"):
                        current = self.list_version.get()
                        self.list_version.set_items(event["versions"])
                        if not current:
                            self.list_version.set(event["versions"][0])
                    if event.get("loaders"):
                        ordered = sort_by_popularity(event["loaders"])
                        self.list_loader.set_items(ordered)
                elif etype == "done":
                    self._on_download_done(event["result"])
                elif etype == "preview_loaded":
                    self.preview_items = event["items"]
                    self.item_vars = {}
                    self._fetched_collection_text = event["raw_text"]
                    self._render_items_checklist()
                    self.btn_fetch_items.configure(state="normal", text=t(self.lang, "btn_fetch_items"))
                elif etype == "preview_error":
                    self.btn_fetch_items.configure(state="normal", text=t(self.lang, "btn_fetch_items"))
                    messagebox.showerror(
                        t(self.lang, "msg_error_title"),
                        t(self.lang, "msg_error_collection_not_found", id=event["id"]),
                    )
        except queue.Empty:
            pass
        self.after(100, self._process_events)

    def _on_download_done(self, result: DownloadResult) -> None:
        L = self.lang
        self._set_running_state(False)

        self.stat_success["value"].configure(text=str(len(result.success)))
        self.stat_failed["value"].configure(text=str(len(result.failed)))
        self.stat_incompatible["value"].configure(text=str(len(result.incompatible)))
        self.stat_skipped["value"].configure(text=str(len(result.skipped)))
        self._update_details_panel(result)

        if result.cancelled:
            self.lbl_status.configure(text=t(L, "status_cancelled"))
            return

        if result.error and not result.output_path:
            self.lbl_status.configure(text=t(L, "status_error"))
            messagebox.showerror(t(L, "msg_error_title"), result.error)
            return

        self.lbl_status.configure(text=t(L, "status_done"))

        summary = t(
            L, "msg_done_text",
            success=len(result.success),
            failed=len(result.failed),
            incompatible=len(result.incompatible),
            skipped=len(result.skipped),
            path=result.output_path,
        )
        summary += self._format_result_items(result.failed, "msg_done_failed_header")
        summary += self._format_result_items(result.incompatible, "msg_done_incompatible_header")

        # A failed/incompatible download is still informative, not a hard
        # error — show it as info so the person can read the reasons calmly.
        messagebox.showinfo(t(L, "msg_done_title"), summary)

    def _format_result_items(self, items: List[ResultItem], header_key: str, cap: int = 10) -> str:
        if not items:
            return ""
        lines = [f"  \u2022 {item.name} \u2014 {item.reason}" for item in items[:cap]]
        extra = len(items) - cap
        if extra > 0:
            lines.append(t(self.lang, "details_more", count=extra))
        return f"\n\n{t(self.lang, header_key)}\n" + "\n".join(lines)


def run_app() -> None:
    app = ModrinthDownloaderApp()
    app.mainloop()
