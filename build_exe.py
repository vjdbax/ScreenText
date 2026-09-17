#!/usr/bin/env python3
"""
Скрипт сборки ScreenText Helper v5.5.0 в .exe через PyInstaller.

Запуск:
    python build_exe.py

Требования:
    - Python 3.10+ с pip
    - Все зависимости из requirements.txt
    - (Опционально) Inno Setup 6+ для создания инсталлятора
"""

import os
import sys
import subprocess
import shutil
import winreg
from pathlib import Path

# ── Конфигурация ──────────────────────────────────────────────────────────────

APP_NAME = "ScreenTextHelper"
ENTRY_POINT = "run.py"
ICON_PATH = "assets/icon.ico"
ASSETS_DIR = "assets"
MODELS_DIR = "easyocr_models"

# ── Утилиты ───────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent


def banner(text: str) -> None:
    width = 60
    print("\n" + "=" * width)
    print(f"  {text}")
    print("=" * width)


def run(cmd: list[str], check: bool = True, **kwargs) -> subprocess.CompletedProcess:
    print(f"  >> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(ROOT), **kwargs)
    if check and result.returncode != 0:
        print(f"[ОШИБКА] Команда завершилась с кодом {result.returncode}")
        sys.exit(1)
    return result


def pip_install(*packages: str) -> None:
    run([sys.executable, "-m", "pip", "install", *packages])


def is_package_installed(name: str) -> bool:
    result = run(
        [sys.executable, "-m", "pip", "show", name],
        check=False,
        capture_output=True,
    )
    return result.returncode == 0


# ── Этапы сборки ──────────────────────────────────────────────────────────────

def step_ensure_pip() -> None:
    banner("Проверка pip")
    try:
        import pip  # noqa: F401
        print("  pip доступен.")
    except ImportError:
        print("  pip не найден, устанавливаю...")
        run([sys.executable, "-m", "ensurepip", "--upgrade"])


def step_install_dependencies() -> None:
    banner("Установка зависимостей проекта")
    req_file = ROOT / "requirements.txt"
    if req_file.exists():
        pip_install("-r", str(req_file))
    else:
        print("  [ПРЕДУПРЕЖДЕНИЕ] requirements.txt не найден, пропускаю.")


def step_install_pyinstaller() -> None:
    banner("Проверка PyInstaller")
    if is_package_installed("pyinstaller"):
        print("  PyInstaller уже установлен.")
    else:
        print("  Устанавливаю PyInstaller...")
        pip_install("pyinstaller")


def step_download_models() -> None:
    banner("Предзагрузка моделей EasyOCR")
    models_path = ROOT / MODELS_DIR
    if models_path.exists() and any(models_path.iterdir()):
        print(f"  Модели уже загружены в {models_path}.")
        return

    download_script = ROOT / "download_models.py"
    if download_script.exists():
        run([sys.executable, str(download_script)])
    else:
        print("  [ПРЕДУПРЕЖДЕНИЕ] download_models.py не найден, пропускаю.")


def step_compile() -> None:
    banner("Компиляция через PyInstaller")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconsole",
        "--onedir",
        "--noconfirm",
        "--clean",
        f"--name={APP_NAME}",
        f"--icon={ICON_PATH}",
        f"--add-data={ASSETS_DIR};assets",
        "--paths=src",
        # ── Сбор модулей ──
        "--collect-all", "easyocr",
        "--collect-all", "torch",
        "--collect-all", "torchvision",
        # ── Скрытые импорты (PyInstaller не всегда находит автоматически) ──
        "--hidden-import=PyQt6",
        "--hidden-import=PyQt6.QtWidgets",
        "--hidden-import=PyQt6.QtCore",
        "--hidden-import=PyQt6.QtGui",
        "--hidden-import=PyQt6.sip",
        "--hidden-import=PyQt6.Qwt",
        "--hidden-import=easyocr",
        "--hidden-import=torch",
        "--hidden-import=torch.nn",
        "--hidden-import=torch.nn.functional",
        "--hidden-import=torchvision",
        "--hidden-import=torchvision.transforms",
        "--hidden-import=numpy",
        "--hidden-import=cv2",
        "--hidden-import=cv2.cv2",
        "--hidden-import=PIL",
        "--hidden-import=PIL.Image",
        "--hidden-import=PIL.ImageGrab",
        "--hidden-import=requests",
        "--hidden-import=keyboard",
        "--hidden-import=pyautogui",
        "--hidden-import=pyperclip",
        "--hidden-import=qtawesome",
        "--hidden-import=deep_translator",
        "--hidden-import=deep_translator.google_trans",
        "--hidden-import=urllib3",
        "--hidden-import=certifi",
        "--hidden-import=charset_normalizer",
        "--hidden-import=idna",
        # ── Исключения для уменьшения размера ──
        "--exclude-module=matplotlib",
        "--exclude-module=scipy",
        "--exclude-module=pandas",
        "--exclude-module=IPython",
        "--exclude-module=notebook",
        ENTRY_POINT,
    ]

    # Добавляем easyocr_models, если существуют
    models_path = ROOT / MODELS_DIR
    if models_path.exists():
        cmd.insert(-1, f"--add-data={MODELS_DIR};easyocr_models")

    run(cmd)


def step_verify() -> None:
    banner("Проверка результата")
    dist_dir = ROOT / "dist" / APP_NAME
    exe_path = dist_dir / f"{APP_NAME}.exe"

    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"  [OK] {exe_path}  ({size_mb:.1f} MB)")
        print(f"  Папка дистрибутива: {dist_dir}")
    else:
        print(f"  [ОШИБКА] {exe_path} не найден!")
        sys.exit(1)


# ── Этап 6: Сборка инсталлятора через Inno Setup ─────────────────────────────

def _find_iscc() -> str | None:
    """Поиск компилятора Inno Setup (ISCC.exe) в системе."""
    # 1. Проверяем PATH
    iscc_shutil = shutil.which("ISCC.exe")
    if iscc_shutil:
        return iscc_shutil

    # 2. Ищем в реестре (Inno Setup пишет ключ при установке)
    registry_paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1"),
    ]
    for root_key, subkey in registry_paths:
        try:
            with winreg.OpenKey(root_key, subkey) as key:
                install_dir, _ = winreg.QueryValueEx(key, "InstallLocation")
                candidate = os.path.join(install_dir, "ISCC.exe")
                if os.path.isfile(candidate):
                    return candidate
        except (FileNotFoundError, OSError):
            continue

    # 3. Проверяем стандартные пути
    default_paths = [
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    ]
    for p in default_paths:
        if os.path.isfile(p):
            return p

    return None


def step_build_installer() -> None:
    """Компиляция инсталлятора через Inno Setup (опционально)."""
    banner("Сборка инсталлятора (Inno Setup)")

    iscc = _find_iscc()
    if iscc is None:
        print("  Inno Setup не найден в системе.")
        print("  Пропускаю создание инсталлятора.")
        print("  Для ручной сборки установите Inno Setup 6+ и запустите:")
        print(f"    iscc.exe {ROOT / 'installer.iss'}")
        return

    print(f"  ISCC.exe: {iscc}")

    iss_path = ROOT / "installer.iss"
    if not iss_path.exists():
        print(f"  [ОШИБКА] {iss_path} не найден!")
        return

    cmd = [iscc, str(iss_path)]
    print(f"  >> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)

    if result.returncode == 0:
        installer_dir = ROOT / "dist_installer"
        setup_files = list(installer_dir.glob("*.exe")) if installer_dir.exists() else []
        if setup_files:
            for f in setup_files:
                size_mb = f.stat().st_size / (1024 * 1024)
                print(f"  [OK] {f.name}  ({size_mb:.1f} MB)")
        else:
            print("  [OK] Инсталлятор собран, но .exe не найден в dist_installer/")
        print(f"  Папка: {installer_dir}")
    else:
        print(f"  [ОШИБКА] Inno Setup завершился с кодом {result.returncode}")
        if result.stdout:
            print(f"  stdout:\n{result.stdout}")
        if result.stderr:
            print(f"  stderr:\n{result.stderr}")


# ── Точка входа ───────────────────────────────────────────────────────────────

def main() -> None:
    banner("ScreenText Helper v5.5.0 — Сборка .exe")
    print(f"  Python: {sys.version}")
    print(f"  Каталог: {ROOT}")

    step_ensure_pip()
    step_install_dependencies()
    step_install_pyinstaller()
    step_download_models()
    step_compile()
    step_verify()
    step_build_installer()

    banner("Сборка завершена!")
    print(f"  Запуск:  dist\\{APP_NAME}\\{APP_NAME}.exe")
    installer_dir = ROOT / "dist_installer"
    if installer_dir.exists() and list(installer_dir.glob("*.exe")):
        print(f"  Инсталлятор:  dist_installer\\")
    print()


if __name__ == "__main__":
    main()
