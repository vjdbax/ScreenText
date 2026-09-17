#!/usr/bin/env python3
"""
Smoke tests for ScreenText Helper — resource paths, imports, settings location.

Run:
    python -m unittest tests/test_smoke.py -v
    — or —
    python tests/test_smoke.py
"""

import os
import sys
import unittest

# Ensure src/ is importable
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)


# ── Test: utils.py ────────────────────────────────────────────────────────────

class TestGetResourcePath(unittest.TestCase):
    """get_resource_path resolves to real directories/files."""

    def setUp(self):
        from utils import get_resource_path
        self.get = get_resource_path

    def test_returns_string(self):
        result = self.get("assets")
        self.assertIsInstance(result, str)

    def test_assets_dir_exists(self):
        path = self.get("assets")
        self.assertTrue(os.path.isdir(path), f"assets dir missing: {path}")

    def test_icon_ico_exists(self):
        path = self.get(os.path.join("assets", "icon.ico"))
        self.assertTrue(os.path.isfile(path), f"icon.ico missing: {path}")

    def test_icon_png_exists(self):
        path = self.get(os.path.join("assets", "icon.png"))
        self.assertTrue(os.path.isfile(path), f"icon.png missing: {path}")

    def test_easyocr_models_dir_exists(self):
        path = self.get("easyocr_models")
        if os.path.isdir(path):
            self.assertTrue(os.path.isdir(path))
        else:
            # Models may not be downloaded yet — skip, don't fail
            self.skipTest("easyocr_models/ not present (run download_models.py first)")

    def test_model_files_exist(self):
        models_dir = self.get("easyocr_models")
        if not os.path.isdir(models_dir):
            self.skipTest("easyocr_models/ not present")
        # At least one .pth file should exist (may be in subdirs)
        pth_files = []
        for dirpath, _, filenames in os.walk(models_dir):
            for f in filenames:
                if f.endswith(".pth"):
                    pth_files.append(os.path.join(dirpath, f))
        self.assertGreater(len(pth_files), 0, "No .pth model files found")

    def test_src_dir_exists(self):
        path = self.get("src")
        self.assertTrue(os.path.isdir(path), f"src dir missing: {path}")

    def test_run_py_exists(self):
        path = self.get("run.py")
        self.assertTrue(os.path.isfile(path), f"run.py missing: {path}")


class TestGetDataDir(unittest.TestCase):
    """get_data_dir always resolves to %APPDATA%/ScreenTextHelper."""

    def setUp(self):
        from utils import get_data_dir
        self.data_dir = get_data_dir()

    def test_returns_string(self):
        self.assertIsInstance(self.data_dir, str)

    def test_ends_with_screentext_helper(self):
        self.assertTrue(self.data_dir.endswith("ScreenTextHelper"),
                        f"Expected path to end with 'ScreenTextHelper', got: {self.data_dir}")

    def test_inside_appdata(self):
        appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        self.assertTrue(self.data_dir.startswith(appdata),
                        f"Data dir not under APPDATA: {self.data_dir}")

    def test_directory_is_created(self):
        self.assertTrue(os.path.isdir(self.data_dir),
                        f"Data dir does not exist: {self.data_dir}")

    def test_not_inside_project(self):
        self.assertFalse(self.data_dir.startswith(PROJECT_ROOT),
                         f"Data dir should NOT be inside project root: {self.data_dir}")

    def test_writable(self):
        test_file = os.path.join(self.data_dir, "_smoke_test_write.tmp")
        try:
            with open(test_file, "w") as f:
                f.write("ok")
            self.assertTrue(os.path.isfile(test_file))
        finally:
            if os.path.exists(test_file):
                os.unlink(test_file)


class TestSettingsLocation(unittest.TestCase):
    """Settings object uses %APPDATA% and never writes inside the project."""

    def test_settings_importable(self):
        from settings import settings
        self.assertIsNotNone(settings)

    def test_config_file_in_appdata(self):
        from settings import settings
        appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        self.assertTrue(settings.config_file.startswith(appdata),
                        f"settings.json not in APPDATA: {settings.config_file}")

    def test_config_dir_in_appdata(self):
        from settings import settings
        appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        self.assertTrue(settings.config_dir.startswith(appdata),
                        f"config dir not in APPDATA: {settings.config_dir}")

    def test_not_inside_project(self):
        from settings import settings
        self.assertFalse(settings.config_file.startswith(PROJECT_ROOT),
                         f"settings.json inside project: {settings.config_file}")

    def test_defaults_are_complete(self):
        from settings import settings
        for key in ("hotkeys", "languages", "llm", "auto_start", "window_opacity"):
            self.assertIn(key, settings.DEFAULT_SETTINGS, f"Missing default key: {key}")


# ── Test: module imports ──────────────────────────────────────────────────────

class TestModuleImports(unittest.TestCase):
    """All src/ modules can be imported without errors.

    PyQt6 GUI modules are skipped — they require a running QApplication.
    """

    # Modules that need a running QApplication
    _GUI_MODULES = {
        "main_app", "main", "tray_icon", "settings_window",
        "overlay_window", "area_selector",
    }

    # Modules with heavy optional dependencies
    _OPTIONAL_MODULES = {
        "ocr_manager",    # needs easyocr, cv2, numpy
    }

    def _importable(self, module_name):
        try:
            __import__(module_name)
            return True
        except Exception:
            return False

    def test_utils_importable(self):
        self.assertTrue(self._importable("utils"))

    def test_settings_importable(self):
        self.assertTrue(self._importable("settings"))

    def test_constants_importable(self):
        self.assertTrue(self._importable("constants"))

    def test_text_formatter_importable(self):
        self.assertTrue(self._importable("text_formatter"))

    def test_translator_importable(self):
        self.assertTrue(self._importable("translator"))

    def test_hotkey_manager_importable(self):
        self.assertTrue(self._importable("hotkey_manager"))

    def test_translation_worker_importable(self):
        self.assertTrue(self._importable("translation_worker"))

    def test_ai_translator_importable(self):
        self.assertTrue(self._importable("ai_translator"))

    def test_screen_capture_importable(self):
        self.assertTrue(self._importable("screen_capture"))

    def test_ollama_installer_importable(self):
        self.assertTrue(self._importable("ollama_installer"))


# ── Test: constants ───────────────────────────────────────────────────────────

class TestConstants(unittest.TestCase):
    def test_version_format(self):
        from constants import APP_VERSION
        parts = APP_VERSION.split(".")
        self.assertEqual(len(parts), 3, f"Version should be X.Y.Z: {APP_VERSION}")

    def test_app_name_not_empty(self):
        from constants import APP_NAME
        self.assertTrue(len(APP_NAME) > 0)

    def test_api_urls_are_https(self):
        from constants import OPENROUTER_MODELS_URL
        self.assertTrue(OPENROUTER_MODELS_URL.startswith("https://"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
