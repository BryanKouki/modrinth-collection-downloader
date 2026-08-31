# Modrinth Collection Downloader

Download every mod, resource/texture pack, shader, plugin and datapack from a
public [Modrinth](https://modrinth.com) collection in one go — sorted
automatically into the right subfolders, or packed into a single `.zip`
named after the collection itself.

Made by **[BryanKouki](https://github.com/BryanKouki)** — v1.0.0

> This app only talks to `api.modrinth.com` (public read-only queries) and
> downloads files from `cdn.modrinth.com` (Modrinth's own CDN, hosting the
> official files). There is no telemetry, no data collection, and no
> execution of third-party code — it just downloads files, and the full
> source is right here in this repository.

---

## Table of contents

- [Overview](#overview)
- [Features](#features)
- [How folders are organized](#how-folders-are-organized)
- [Requirements](#requirements)
- [Running in development mode](#running-in-development-mode)
- [Building the Windows executable (.exe)](#building-the-windows-executable-exe)
- [Manual PyInstaller build](#manual-pyinstaller-build)
- [Build troubleshooting](#build-troubleshooting)
- [Project structure](#project-structure)
- [Frequently asked questions](#frequently-asked-questions)
- [Security and privacy](#security-and-privacy)
- [Contributing](#contributing)
- [Credits](#credits)
- [License](#license)

---

## Overview

Paste a collection's ID or URL, pick a Minecraft version and a mod loader,
check what you want included, and the app will:

1. Query the official public Modrinth API for the collection's contents;
2. For every project in it, resolve the right version for your chosen
   Minecraft version + loader (optionally always preferring a stable
   release over alpha/beta builds);
3. Optionally follow and download each mod's required dependencies;
4. Automatically sort every downloaded file into `mods/`, `resourcepacks/`,
   `shaderpacks/`, `plugins/` or `datapacks/`;
5. Save the result either as a plain organized folder or as a single
   `.zip` file, named after the collection, without ever overwriting
   something that already exists at the destination.

The interface is fully bilingual (English and Portuguese, toggled instantly
from the top bar) and defaults to English. It's a desktop GUI app — no
command line arguments, no config files to edit by hand.

---

## Features

- Compact, form-first layout: the download settings are front and center,
  the activity log stays tucked away (collapsed) until you actually want to
  read it.
- Bilingual interface (English / Portuguese) with an instant top-bar toggle,
  defaulting to English.
- Built-in guide window explaining every field and every result category,
  without leaving the app.
- Collection input accepts both a bare ID (`YV97U1kk`) and a full URL
  (`https://modrinth.com/collection/YV97U1kk`).
- Optional per-item checklist: load the collection's contents and every
  mod, resource pack and shader shows up individually, grouped by category,
  **checked by default** — uncheck anything you don't want before
  downloading. "Select all" / "Select none" shortcuts, and toggling a
  category filter (Mods, Resource Packs, Shaders) checks/unchecks every
  item of that category in one click. This step is entirely optional — skip
  it and the download still works using just the category filters below.
- Minecraft version and mod loader pickers are a search box on top of a real
  scrollable list (not a dropdown you have to keep clicking) — you can
  either scroll/click through the options or just type a value that isn't
  in the list yet (handy right after a new Minecraft version drops).
- Mod loaders are listed in real-world popularity order: NeoForge, Fabric,
  Forge, Quilt, then the server plugin loaders (Paper, Spigot, Purpur,
  Bukkit, Folia, Sponge, Velocity, Waterfall, BungeeCord), then Datapack.
- Independent category checkboxes for what to include: Mods/Plugins/Datapacks,
  Resource/Texture Packs, Shaders.
- Optional recursive download of each mod's required dependencies.
- Optional preference for the latest stable release over newer alpha/beta
  builds.
- Automatic sorting into category subfolders (see below).
- Save as an organized folder or as a single `.zip`, always named after the
  real collection name, and never overwriting an existing folder/zip (it
  appends " (2)", " (3)", etc. instead).
- Collapsible, color-coded activity log: green for success, red for
  failures, orange for incompatible items, gray for skipped ones — hidden
  by default to keep the window compact, one click away when you need it.
- Summary panel with running counts of items that succeeded, failed, were
  incompatible, or were skipped, plus a compact details list that
  automatically shows **which items failed or were incompatible, and why**,
  right after each download — the same reasons are echoed in the
  completion popup.
- Parallel downloads (several worker threads at once) so large collections
  don't take forever.
- Dedicated Cancel button, centered under the main action, enabled only
  while a download is actually running.

---

## How folders are organized

The Modrinth API only has 4 official project types: `mod`, `modpack`,
`resourcepack` and `shader` — there is no separate type for "plugin",
"datapack" or "texture pack". This app refines that classification by also
looking at the **loader** of the downloaded version:

| Folder            | Criteria                                                                                                   |
|--------------------|---------------------------------------------------------------------------------------------------------------|
| `mods/`            | `mod` type, with a client mod loader (Fabric, Forge, NeoForge, Quilt, etc.)                                    |
| `plugins/`         | `mod` type, with a server plugin loader (Bukkit, Spigot, Paper, Purpur, Folia, Sponge, Velocity, Waterfall, BungeeCord) |
| `datapacks/`       | `mod` type, with the `datapack` loader                                                                         |
| `resourcepacks/`   | `resourcepack` type (this also covers texture packs — Modrinth does not separate the two officially)          |
| `shaderpacks/`     | `shader` type                                                                                                  |

Plugins and datapacks use a completely different "loader" field than the mod
loader you pick on the main screen (you might pick "fabric", but a plugin in
the collection may only have a "paper" build). The app already accounts for
this: if there's no version for the mod loader you picked, it automatically
falls back to accepting plugin/datapack versions, since those don't depend
on the client-side mod loader at all.

---

## Requirements

**To run in development mode (the `.py` files directly):**
- [Python 3.10 or newer](https://www.python.org/downloads/)
- An internet connection (only to query the Modrinth API)

**To just use an already-built `.exe`:**
- Windows 10/11 (64-bit)
- Nothing else — the executable ships with everything bundled in

---

## Running in development mode

```bash
# 1. Clone the repository
git clone https://github.com/BryanKouki/modrinth-collection-downloader.git
cd modrinth-collection-downloader

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
python main.py
```

This opens the GUI directly — no terminal interaction, command-line flags,
or config files needed.

---

## Building the Windows executable (.exe)

> **Important:** the `.exe` has to be built **on a Windows machine**.
> PyInstaller packages the app for whichever operating system it's running
> on — it is not possible to produce a Windows `.exe` by running the build
> on Linux or macOS.

### Easy way (using the included script)

1. **Install Python on Windows** — get it from
   [python.org/downloads](https://www.python.org/downloads/) and, during
   installation, **check "Add python.exe to PATH"**.
2. **Download/clone this repository** into a folder on Windows.
3. *(Optional)* Drop an `icon.ico` file in the project root if you want a
   custom icon for the `.exe`.
4. **Double-click `build.bat`** (or open Command Prompt in the project
   folder and run it from there).

   The script does everything on its own:
   - Checks that Python is installed;
   - Installs the dependencies (`customtkinter`, `requests`, `pyinstaller`);
   - Cleans up any previous build (`build/`, `dist/`, `*.spec`);
   - Runs PyInstaller with the correct flags;
   - Reports whether it succeeded and where the file ended up.

5. When it's done, the executable will be at:
   ```
   dist\ModrinthCollectionDownloader.exe
   ```
   That single file can be copied and shared as-is — nothing else needs to
   go with it (it's a `--onefile` build).

---

## Manual PyInstaller build

If you'd rather run the commands yourself instead of using `build.bat`:

```bat
:: 1. Install dependencies
pip install -r requirements.txt

:: 2. Run PyInstaller
python -m PyInstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name "ModrinthCollectionDownloader" ^
    --collect-all customtkinter ^
    main.py
```

What each flag does:

| Flag | Purpose |
|------|----------|
| `--onefile` | Produces a single `.exe` file instead of a folder full of DLLs |
| `--windowed` | Runs without opening a console/terminal window alongside it |
| `--name` | Sets the final executable's name |
| `--collect-all customtkinter` | Bundles CustomTkinter's internal theme/asset files (**required** — without it the `.exe` opens with a broken interface, or doesn't open at all) |
| `--icon=icon.ico` | *(optional)* uses a custom icon — only works if `icon.ico` exists in the folder |

---

## Build troubleshooting

**Windows Defender / my antivirus flagged the .exe as a virus**
This is an extremely common false positive for PyInstaller-built
executables in general (not specific to this project) — it happens because
the `.exe` isn't digitally signed and the antivirus has never seen the
binary before. Since the full source code is right here in the repository,
you can review exactly what it does, or just run `python main.py` directly
instead of building an `.exe` if you'd rather avoid dealing with it.

**"customtkinter" errors / broken interface in the built .exe**
You're missing the `--collect-all customtkinter` flag in the PyInstaller
command. Use `build.bat`, which already includes it, or add it manually to
your own command.

**"python is not recognized as an internal or external command"**
Python wasn't added to the Windows PATH during installation. Reinstall
Python and check **"Add python.exe to PATH"**, or add it manually through
the Windows environment variable settings.

**The build takes a long time or seems stuck**
`--onefile` PyInstaller builds usually take anywhere from 30 seconds to a
couple of minutes depending on the machine — that's normal. If it's
genuinely stuck, run `build.bat` from Command Prompt (not by double-click)
so you can see the full error output.

---

## Project structure

```
modrinth-collection-downloader/
├── main.py               # Entry point
├── build.bat               # Builds the .exe automatically on Windows
├── requirements.txt
├── README.md
└── app/
    ├── __init__.py
    ├── api.py               # Public Modrinth API client
    ├── downloader.py          # Orchestrates downloading/organizing the collection
    ├── gui.py                   # Graphical interface (CustomTkinter)
    ├── i18n.py                    # English / Portuguese UI strings
    └── version.py                  # App name, version and author
```

---

## Frequently asked questions

**Does it work with private collections?**
No — the app uses Modrinth's public API, so it only works with **public**
collections.

**Why did a mod end up marked "Incompatible"?**
It means the project exists on Modrinth, but has **no published version**
for the Minecraft version + mod loader combination you picked. This is
common for old/abandoned mods, or when the Minecraft version is very new.

**Why did an item end up marked "Skipped"?**
Either its type (mod, resource pack, or shader) wasn't checked in the
category filters, or it was individually unchecked in the items checklist
(if you used it).

**Does the app modify or delete existing files?**
No. Everything downloads into a temporary folder first, and only at the
very end does it move (or zip) that into the destination you picked — and
if a folder/zip with the same name already exists there, it creates a copy
named " (2)", " (3)", etc. instead of overwriting anything.

**Do I need to keep the app open while playing Minecraft?**
No, it's only used to download the files. You can close it right after.

**Does it work on Linux/macOS?**
Yes, in development mode (`python main.py`) it runs on any system with
Python 3.10+. Only the `.exe` build is Windows-specific — running
PyInstaller on Linux/macOS would produce a native binary for that system,
not a `.exe`.

---

## Security and privacy

- The source code is **fully open** — read it line by line before building
  or running it.
- Network requests only ever go to two domains: `api.modrinth.com` (public
  data queries) and `cdn.modrinth.com` (downloading the official files
  hosted by Modrinth itself).
- **No user data is collected, sent, or stored** anywhere other than your
  own computer.
- No telemetry, no ads, no silent auto-updates, no execution of third-party
  scripts or code.

---

## Contributing

Contributions are welcome:

1. Open an [issue](../../issues) to report a bug or suggest an improvement;
2. Fork the project;
3. Create a branch for your feature/fix (`git checkout -b my-feature`);
4. Commit your changes (`git commit -m 'Add my feature'`);
5. Open a Pull Request.

---

## Credits

Built by **[BryanKouki](https://github.com/BryanKouki)**.

If this project helped you, consider leaving a star on the repository.

Powered by the [Modrinth API](https://docs.modrinth.com/) — every download
happens directly on your own computer.

---

## License

Personal/utility open-source project. Use, modify and redistribute freely.
