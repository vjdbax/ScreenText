"""
Centralized resource path resolution for ScreenText Helper.

Handles three execution contexts:
  1. Development  — running from source via `python run.py`
  2. --onedir     — PyInstaller folder distribution (exe + data side-by-side)
  3. --onefile    — PyInstaller single-file (extracted to sys._MEIPASS)
"""

import os
import sys
from typing import Optional


def _frozen_bundle_dir() -> Optional[str]:
    """Return the bundle root when running as a PyInstaller build.

    --onefile  → sys._MEIPASS  (temp extraction dir)
    --onedir   → directory containing sys.executable
    """
    if getattr(sys, "frozen", False):
        # --onefile: _MEIPASS exists and points to the temp folder
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass and os.path.isdir(meipass):
            return meipass
        # --onedir: data sits next to the .exe
        return os.path.dirname(sys.executable)
    return None


def _dev_project_root() -> str:
    """Return the project root when running from source.

    src/utils.py  →  project root is two levels up.
    """
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── Public API ────────────────────────────────────────────────────────────────

def get_resource_path(relative_path: str) -> str:
    """Resolve *relative_path* to an absolute path for both dev and frozen modes.

    Examples::

        get_resource_path("assets/icon.png")
        get_resource_path("easyocr_models")
    """
    bundle = _frozen_bundle_dir()
    base = bundle if bundle else _dev_project_root()
    return os.path.join(base, relative_path)


def get_data_dir() -> str:
    """Return the writable user-data directory (%APPDATA%/ScreenTextHelper).

    This directory is **always** outside the install/dist folder so that
    settings and logs are never written into a read-only location.
    """
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    data_dir = os.path.join(appdata, "ScreenTextHelper")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir
