"""
Modrinth Collection Downloader
================================
Downloads mods, resource/texture packs, shaders, plugins and datapacks from
a public Modrinth collection, sorting everything into subfolders or
compressing it into a .zip named after the collection.

Run in development mode:
    python main.py

Build the Windows executable (.exe):
    build.bat
(see README.md for details)
"""

from app.gui import run_app

if __name__ == "__main__":
    run_app()
