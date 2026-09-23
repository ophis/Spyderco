"""Filesystem paths shared across tools/, derived from this file's location."""

from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
ROOT = TOOLS.parent

CATALOGS = ROOT / "Catalogs"
IMAGES = CATALOGS / "images"
FAMILIES = TOOLS / "families"
DATA = TOOLS / "data"
CACHE = TOOLS / "cache"
PROFILES = TOOLS / ".profiles"
README = ROOT / "README.md"
