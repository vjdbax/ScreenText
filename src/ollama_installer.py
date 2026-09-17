#!/usr/bin/env python3
import os
import re
import json
import time
import subprocess
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    requests = None
    HAS_REQUESTS = False
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QComboBox, QFrame, QLineEdit, QFileDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread


# ---------------------------------------------------------------------------
# Hardware detection
# ---------------------------------------------------------------------------

def detect_hardware_profile() -> dict:
    """Detect GPU VRAM, system RAM, and recommend the best Ollama model."""
    vram_gb = 0.0
    gpu_name = "Неизвестная видеокарта"

    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        vram_gb = round(info.total / (1024 ** 3), 1)
        gpu_name = pynvml.nvmlDeviceName(handle).decode("utf-8", errors="replace")
        pynvml.nvmlShutdown()
    except Exception:
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0 and r.stdout.strip():
                parts = r.stdout.strip().split(",")
                gpu_name = parts[0].strip()
                vram_gb = round(float(parts[1].strip()) / 1024, 1)
        except Exception:
            pass

    if vram_gb == 0.0:
        try:
            import ctypes, ctypes.wintypes
            class VIDEO_MEMORY(ctypes.Structure):
                _fields_ = [
                    ("cb", ctypes.wintypes.DWORD), ("dwMemoryLoad", ctypes.wintypes.DWORD),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            mem = VIDEO_MEMORY(); mem.cb = ctypes.sizeof(mem)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
            vram_gb = round(mem.ullTotalPhys / (1024 ** 3), 1) if mem.ullTotalPhys > 0 else 0.0
            gpu_name = "Встроенная графика (shared memory)"
        except Exception:
            pass

    ram_gb = 0.0
    try:
        import psutil
        ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 1)
    except Exception:
        try:
            import ctypes, ctypes.wintypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.wintypes.DWORD), ("dwMemoryLoad", ctypes.wintypes.DWORD),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            mem = MEMORYSTATUSEX(); mem.dwLength = ctypes.sizeof(mem)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
            ram_gb = round(mem.ullTotalPhys / (1024 ** 3), 1)
        except Exception:
            pass

    if vram_gb >= 8:
        rec_id = "qwen2.5vl:7b"
        rec_text = f"🟢 {gpu_name} ({vram_gb} ГБ VRAM) — Рекомендуется Qwen 2.5 VL (7B): книги, манга, сложная верстка."
    elif vram_gb >= 3:
        rec_id = "qwen2.5vl:3b"
        rec_text = f"🟡 {gpu_name} ({vram_gb} ГБ VRAM) — Рекомендуется Qwen 2.5 VL (3B): быстрый перевод игр и UI."
    elif vram_gb > 0:
        rec_id = "minicpm-v:latest"
        rec_text = f"🟡 {gpu_name} ({vram_gb} ГБ VRAM) — Только MiniCPM-V (~2 ГБ). Возможны сбои на русском."
    else:
        rec_id = "qwen2.5vl:3b"
        rec_text = f"⚠️ GPU не обнаружена (RAM {ram_gb} ГБ). Ollama будет работать на CPU — медленно."

    return {"vram_gb": vram_gb, "ram_gb": ram_gb, "gpu_name": gpu_name,
            "recommended_model_id": rec_id, "recommendation_text": rec_text}


# ---------------------------------------------------------------------------
# OLLAMA_MODELS path helpers
# ---------------------------------------------------------------------------

def get_ollama_models_path() -> str:
    val = os.environ.get("OLLAMA_MODELS", "")
    if val:
        return val
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_READ)
        val, _ = winreg.QueryValueEx(key, "OLLAMA_MODELS"); winreg.CloseKey(key)
        return val
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), ".ollama", "models")


def set_ollama_models_path(path: str) -> bool:
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_WRITE)
        winreg.SetValueEx(key, "OLLAMA_MODELS", 0, winreg.REG_SZ, path); winreg.CloseKey(key)
        os.environ["OLLAMA_MODELS"] = path
        return True
    except Exception:
        return False


def restart_ollama_service():
    try:
        subprocess.run(["taskkill", "/IM", "ollama.exe", "/F"], capture_output=True, timeout=5)
    except Exception:
        pass
    time.sleep(1)
    try:
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        ollama_path = os.path.join(local_app_data, "Programs", "Ollama", "ollama.exe")
        if os.path.exists(ollama_path):
            subprocess.Popen([ollama_path], creationflags=subprocess.DETACHED_PROCESS)
        else:
            subprocess.Popen(["ollama", "serve"], creationflags=subprocess.DETACHED_PROCESS)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Built-in Vision catalog (offline fallback)
# ---------------------------------------------------------------------------

_BUILTIN_VISION_CATALOG = [
    {"tag": "qwen2.5vl:7b",   "display": "Qwen 2.5 VL (7B)",   "vram": 8,  "score": 100, "purpose": "Книги, манга, сложная верстка, мелкий шрифт"},
    {"tag": "qwen2.5vl:3b",   "display": "Qwen 2.5 VL (3B)",   "vram": 3,  "score": 100, "purpose": "Быстрый перевод игр, субтитров, UI"},
    {"tag": "qwen2.5vl:72b",  "display": "Qwen 2.5 VL (72B)",  "vram": 48, "score": 100, "purpose": "Максимальное качество, требует сервер"},
    {"tag": "llama3.2-vision:11b", "display": "Llama 3.2 Vision (11B)", "vram": 8, "score": 80, "purpose": "Документы на английском, печатный текст"},
    {"tag": "llama3.2-vision:90b", "display": "Llama 3.2 Vision (90B)", "vram": 64, "score": 80, "purpose": "Высокое качество, требует сервер"},
    {"tag": "minicpm-v:latest",    "display": "MiniCPM-V 4.6",         "vram": 2,  "score": 50, "purpose": "Компактная для слабых ПК, возможны сбои RU"},
    {"tag": "moondream:latest",    "display": "Moondream",             "vram": 2,  "score": 40, "purpose": "Экспериментальная, базовое распознавание"},
]


# ---------------------------------------------------------------------------
# Online catalog scanner
# ---------------------------------------------------------------------------

def is_local_vision_model(model_tag: str) -> bool:
    """Фильтр: пропускает только локальные Vision-модели, исключает облако и чисто текстовые."""
    tag_lower = model_tag.lower()
    if ":cloud" in tag_lower or "cloud" in tag_lower or "[облако]" in tag_lower:
        return False
    text_only = ["deepseek-r1", "llama3.1", "qwen2.5-coder", "mistral", "gemma2"]
    if any(t in tag_lower for t in text_only) and not any(v in tag_lower for v in ["vl", "vision"]):
        return False
    return True


class OllamaCatalogScannerWorker(QThread):
    """Scans Ollama catalog for Vision models (online + offline fallback)."""
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def run(self):
        models = self._try_online_scan()
        if not models:
            models = list(_BUILTIN_VISION_CATALOG)
        self.finished.emit(models)

    def _try_online_scan(self):
        if not HAS_REQUESTS:
            return None
        try:
            r = requests.get("https://ollama.com/search?c=vision", timeout=6,
                             headers={"User-Agent": "ScreenTextHelper/5.5"})
            if r.status_code != 200:
                return None
            html = r.text
            found_tags = re.findall(r'href="/library/([^"]+)"', html)
            if not found_tags:
                found_tags = re.findall(r'/library/([a-zA-Z0-9._-]+)', html)
            if not found_tags:
                return None
            seen = set()
            models = []
            for tag in found_tags:
                tag = tag.strip().rstrip('/')
                if tag in seen or not tag or not is_local_vision_model(tag):
                    continue
                seen.add(tag)
                info = self._build_model_info(tag)
                if info:
                    models.append(info)
            return models if models else None
        except Exception:
            return None

    def _build_model_info(self, tag: str):
        t = tag.lower()
        known = {item["tag"]: item for item in _BUILTIN_VISION_CATALOG}
        if tag in known:
            k = known[tag]
            return {"tag": tag, "display": k["display"], "vram": k["vram"],
                    "score": k["score"], "purpose": k["purpose"]}
        if "qwen" in t and ("vl" in t or "vision" in t):
            score, purpose = 100, "Книги, манга, сложная верстка"
            vram = 8 if any(x in t for x in ["7b", "72b"]) else 3
        elif "gpt-4o" in t:
            score, purpose, vram = 100, "Универсальный эталон OpenAI", 0
        elif "gemini" in t and ("vision" in t or "flash" in t):
            score, purpose, vram = 100, "Высокоскоростной облачный Vision", 0
        elif "llama" in t and "vision" in t:
            score, purpose = 80, "Документы на английском"
            vram = 90 if "90b" in t else 8
        elif "minicpm" in t:
            score, purpose, vram = 50, "Компактная для слабых ПК", 2
        elif "moondream" in t:
            score, purpose, vram = 40, "Экспериментальная", 2
        elif "pixtral" in t:
            score, purpose, vram = 80, "Открытая Vision-модель", 8
        else:
            score, purpose, vram = 30, "Неизвестная Vision-модель", 0
        short = tag.split(":")[0] if ":" in tag else tag
        display = short.replace("-", " ").replace("_", " ").title()
        return {"tag": tag, "display": display, "vram": vram, "score": score, "purpose": purpose}


# ---------------------------------------------------------------------------
# Pull / delete worker (preserved)
# ---------------------------------------------------------------------------

class InstallerThread(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, model_name, action="pull"):
        super().__init__()
        self.model_name = model_name
        self.action = action

    def run(self):
        try:
            if self.action == "pull":
                self.status.emit("Проверка системы...")
                if not self.check_ollama_installed():
                    if not self.install_ollama():
                        return
            if self.action == "pull":
                self.pull_model()
            elif self.action == "delete":
                self.delete_model()
        except Exception as e:
            self.finished.emit(False, f"Ошибка: {str(e)}")

    def check_ollama_installed(self):
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        ollama_path = os.path.join(local_app_data, "Programs", "Ollama", "ollama.exe")
        if os.path.exists(ollama_path):
            return True
        try:
            subprocess.run(["ollama", "--version"], capture_output=True, check=True)
            return True
        except Exception:
            return False

    def install_ollama(self):
        if not HAS_REQUESTS:
            self.finished.emit(False, "Библиотека requests не установлена")
            return False
        try:
            self.status.emit("Скачивание Ollama (~50 МБ)...")
            setup_path = os.path.join(os.environ.get("TEMP", ""), "OllamaSetup.exe")
            response = requests.get("https://ollama.com/download/OllamaSetup.exe", stream=True, timeout=20)
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            with open(setup_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk); downloaded += len(chunk)
                        self.progress.emit(int((downloaded / total_size) * 100))
            self.status.emit("Установка Ollama (подтвердите в окне Windows)...")
            self.progress.emit(0)
            subprocess.Popen([setup_path]).wait()
            self.status.emit("Ожидание запуска службы...")
            time.sleep(5)
            return True
        except Exception as e:
            self.finished.emit(False, f"Ошибка установки Ollama: {str(e)}")
            return False

    def pull_model(self):
        if not HAS_REQUESTS:
            self.finished.emit(False, "Библиотека requests не установлена")
            return
        self.status.emit(f"Запрос на загрузку {self.model_name}...")
        self.progress.emit(0)
        response = requests.post("http://localhost:11434/api/pull",
                                 json={"name": self.model_name, "stream": True}, stream=True, timeout=None)
        for line in response.iter_lines():
            if line:
                data = json.loads(line.decode('utf-8'))
                msg = data.get('status', '')
                if 'total' in data and data['total'] > 0:
                    percent = int((data.get('completed', 0) / data['total']) * 100)
                    self.progress.emit(percent)
                    self.status.emit(f"Загрузка слоев: {percent}%")
                else:
                    self.status.emit(msg)
                if msg == "success":
                    self.progress.emit(100)
                    self.finished.emit(True, "Модель установлена!")
                    break

    def delete_model(self):
        if not HAS_REQUESTS:
            self.finished.emit(False, "Библиотека requests не установлена")
            return
        self.status.emit(f"Удаление модели {self.model_name}...")
        try:
            response = requests.delete("http://localhost:11434/api/delete",
                                       json={"name": self.model_name}, timeout=10)
            if response.status_code == 200:
                self.progress.emit(100)
                self.finished.emit(True, "Модель успешно удалена с ПК.")
            else:
                self.finished.emit(False, f"Ошибка сервера: {response.status_code}")
        except Exception as e:
            self.finished.emit(False, f"Ошибка при удалении: {str(e)}")


def _parse_semver(version_str):
    v = version_str.lstrip('v')
    parts = []
    for p in v.split('.'):
        try: parts.append(int(p))
        except ValueError: parts.append(0)
    while len(parts) < 3: parts.append(0)
    return tuple(parts[:3])


class OllamaUpdateCheckerWorker(QThread):
    update_available = pyqtSignal(str, str)
    up_to_date = pyqtSignal(str)
    check_failed = pyqtSignal()

    def run(self):
        try:
            local = self._get_local_version()
            if not local: self.check_failed.emit(); return
            remote = self._get_remote_version()
            if not remote: self.check_failed.emit(); return
            if _parse_semver(remote) > _parse_semver(local):
                self.update_available.emit(local, remote)
            else:
                self.up_to_date.emit(local)
        except Exception:
            self.check_failed.emit()

    def _get_local_version(self):
        try:
            result = subprocess.run(["ollama", "--version"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                out = result.stdout.strip()
                if 'version' in out.lower(): return out.split()[-1].lstrip('v')
        except Exception: pass
        return None

    def _get_remote_version(self):
        if not HAS_REQUESTS: return None
        try:
            r = requests.get("https://api.github.com/repos/ollama/ollama/releases/latest",
                             timeout=10, headers={"Accept": "application/vnd.github.v3+json"})
            if r.status_code == 200: return r.json().get("tag_name", "").lstrip('v')
        except Exception: pass
        return None


# ---------------------------------------------------------------------------
# Main dialog
# ---------------------------------------------------------------------------

class OllamaInstallerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Мастер управления локальным ИИ")
        self.setMinimumSize(580, 620)

        self.hw = detect_hardware_profile()
        self._catalog = []
        self._workers = []
        self.success_state = False

        self._apply_style()
        self.setup_ui()
        self._start_catalog_scan()

    def _apply_style(self):
        self.setStyleSheet("""
            QDialog { background-color: #1E1E1E; border: 2px solid #3C3C3C; border-radius: 8px; }
            QLabel { color: #CCCCCC; font-family: "Segoe UI"; font-size: 12px; border: none;}
            QProgressBar { border: 1px solid #3C3C3C; border-radius: 5px; text-align: center; color: white; background-color: #2D2D2D; height: 18px; }
            QProgressBar::chunk { background-color: #0E639C; border-radius: 4px; }
            QPushButton { background-color: #2D2D2D; color: #CCCCCC; border: 1px solid #3C3C3C; border-radius: 4px; padding: 8px; font-weight: bold; }
            QPushButton:hover { background-color: #3C3C3C; color: #FFFFFF; }
            QComboBox { background-color: #2D2D2D; color: white; border: 1px solid #3C3C3C; padding: 6px; border-radius: 4px; }
            QComboBox QAbstractItemView { background-color: #2D2D2D; color: white; selection-background-color: #0E639C; }
            QLineEdit { background-color: #2D2D2D; color: #EEEEEE; border: 1px solid #3C3C3C; padding: 4px 6px; border-radius: 3px; font-size: 11px; }
            QFrame#desc_box { background-color: #252526; border: 1px solid #3C3C3C; border-radius: 6px; }
            QFrame#hw_banner { background-color: #0d2137; border: 1px solid #1565C0; border-radius: 6px; padding: 8px; }
            QFrame#folder_box { background-color: #252526; border: 1px solid #3C3C3C; border-radius: 6px; padding: 6px; }
        """)

    # ------------------------------------------------------------------ UI
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # --- Hardware banner ---
        hw_frame = QFrame(); hw_frame.setObjectName("hw_banner")
        hw_l = QVBoxLayout(hw_frame); hw_l.setContentsMargins(10, 8, 10, 8); hw_l.setSpacing(2)
        hw_title = QLabel(f"<b>💻 {self.hw['gpu_name']}</b>")
        hw_title.setStyleSheet("color: #4FC3F7; font-size: 13px;")
        hw_l.addWidget(hw_title)
        hw_detail = QLabel(
            f"VRAM: {self.hw['vram_gb']} ГБ  |  RAM: {self.hw['ram_gb']} ГБ  |  "
            f"Рекомендация: <b>{self.hw['recommended_model_id']}</b>")
        hw_detail.setStyleSheet("color: #B0BEC5; font-size: 11px;")
        hw_l.addWidget(hw_detail)
        layout.addWidget(hw_frame)

        # --- Model selector + refresh ---
        sel_row = QHBoxLayout()
        self.model_selector = QComboBox()
        self.model_selector.setEditable(True)
        self.model_selector.setMinimumWidth(340)
        self.model_selector.currentIndexChanged.connect(self._on_model_selected)
        sel_row.addWidget(self.model_selector, 1)
        self.refresh_catalog_btn = QPushButton("🔄 Сканировать каталог")
        self.refresh_catalog_btn.setFixedWidth(170)
        self.refresh_catalog_btn.clicked.connect(self._start_catalog_scan)
        sel_row.addWidget(self.refresh_catalog_btn)
        layout.addLayout(sel_row)

        # --- Description card ---
        self.desc_frame = QFrame(); self.desc_frame.setObjectName("desc_box")
        desc_layout = QVBoxLayout(self.desc_frame); desc_layout.setContentsMargins(10, 8, 10, 8)
        self.desc_label = QLabel("")
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet("color: #BBBBBB; font-size: 11px; line-height: 140%;")
        desc_layout.addWidget(self.desc_label)
        layout.addWidget(self.desc_frame)

        # --- OLLAMA_MODELS folder ---
        folder_frame = QFrame(); folder_frame.setObjectName("folder_box")
        folder_l = QHBoxLayout(folder_frame); folder_l.setContentsMargins(8, 6, 8, 6)
        folder_l.addWidget(QLabel("Папка моделей:"))
        self.folder_input = QLineEdit()
        self.folder_input.setReadOnly(True)
        self.folder_input.setText(get_ollama_models_path())
        folder_l.addWidget(self.folder_input, 1)
        self.folder_browse_btn = QPushButton("Обзор...")
        self.folder_browse_btn.setFixedWidth(80)
        self.folder_browse_btn.clicked.connect(self._browse_models_folder)
        folder_l.addWidget(self.folder_browse_btn)
        layout.addWidget(folder_frame)
        self.folder_hint = QLabel("")
        self.folder_hint.setWordWrap(True)
        self.folder_hint.setStyleSheet("color: #FFA726; font-size: 10px;")
        layout.addWidget(self.folder_hint)

        # --- Status / progress ---
        self.status_label = QLabel("Готов к работе.")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        self.progress_bar = QProgressBar(); self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # --- Buttons ---
        btns_row = QHBoxLayout()
        self.start_btn = QPushButton("Установить / Обновить")
        self.start_btn.setStyleSheet("background-color: #0E639C; color: white;")
        self.start_btn.clicked.connect(self.start_installation)
        self.delete_btn = QPushButton("Удалить модель")
        self.delete_btn.setStyleSheet("QPushButton { color: #FF4D4D; } QPushButton:hover { background-color: #551A1A; }")
        self.delete_btn.clicked.connect(self.start_deletion)
        self.restart_btn = QPushButton("Перезапустить Ollama")
        self.restart_btn.setStyleSheet("QPushButton { color: #FFA726; } QPushButton:hover { background-color: #4A3600; }")
        self.restart_btn.clicked.connect(self._restart_ollama)
        btns_row.addWidget(self.start_btn); btns_row.addWidget(self.delete_btn); btns_row.addWidget(self.restart_btn)
        layout.addLayout(btns_row)

        self.close_btn = QPushButton("Закрыть")
        self.close_btn.clicked.connect(self.close_dialog)
        layout.addWidget(self.close_btn)

    # ----------------------------------------------------- catalog scan
    def _start_catalog_scan(self):
        self.refresh_catalog_btn.setEnabled(False)
        self.status_label.setText("⏳ Поиск Vision-моделей в каталоге Ollama...")
        self.status_label.setStyleSheet("color: #FFA726;")
        worker = OllamaCatalogScannerWorker()
        worker.finished.connect(self._on_catalog_ready)
        worker.error.connect(self._on_catalog_error)
        self._workers.append(worker)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        worker.error.connect(lambda: self._cleanup_worker(worker))
        worker.start()

    def _on_catalog_ready(self, models):
        self.refresh_catalog_btn.setEnabled(True)
        self._catalog = sorted(
            [m for m in models if is_local_vision_model(m["tag"])],
            key=lambda m: -m.get("score", 0),
        )
        self.model_selector.blockSignals(True)
        self.model_selector.clear()
        for m in self._catalog:
            badge = "🟢" if m["score"] >= 90 else ("🟡" if m["score"] >= 50 else "🔴")
            size_str = f"~{m['vram']} ГБ" if m["vram"] else "облако"
            display = f"{badge} {m['score']}% | {m['display']} [{size_str}]"
            self.model_selector.addItem(display, m["tag"])
        self._auto_select_model()
        self.model_selector.blockSignals(False)
        self._on_model_selected(self.model_selector.currentIndex())
        self.status_label.setText(f"✅ Найдено моделей: {len(self._catalog)}")
        self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")

    def _on_catalog_error(self, err):
        self.refresh_catalog_btn.setEnabled(True)
        self.status_label.setText("❌ Ошибка каталога. Используется встроенный список.")
        self.status_label.setStyleSheet("color: #FF6B6B;")
        self._catalog = sorted(
            [m for m in _BUILTIN_VISION_CATALOG if is_local_vision_model(m["tag"])],
            key=lambda m: -m.get("score", 0),
        )
        self.model_selector.blockSignals(True)
        self.model_selector.clear()
        for m in self._catalog:
            badge = "🟢" if m["score"] >= 90 else ("🟡" if m["score"] >= 50 else "🔴")
            size_str = f"~{m['vram']} ГБ" if m["vram"] else "облако"
            display = f"{badge} {m['score']}% | {m['display']} [{size_str}]"
            self.model_selector.addItem(display, m["tag"])
        self._auto_select_model()
        self.model_selector.blockSignals(False)
        self._on_model_selected(self.model_selector.currentIndex())

    def _cleanup_worker(self, w):
        if w in self._workers: self._workers.remove(w)

    # ----------------------------------------------------- auto-select
    def _auto_select_model(self):
        rec = self.hw["recommended_model_id"]
        for i, m in enumerate(self._catalog):
            if m["tag"] == rec:
                self.model_selector.setCurrentIndex(i); return
        if self._catalog:
            self.model_selector.setCurrentIndex(0)

    # ----------------------------------------------------- description
    def _on_model_selected(self, index):
        tag = self.model_selector.currentData()
        if not tag:
            text = self.model_selector.currentText().strip()
            if text:
                tag = text.split("|")[-1].strip() if "|" in text else text
        if not tag:
            self.desc_label.setText("<i>Выберите модель для просмотра описания.</i>")
            return
        info = None
        for m in self._catalog:
            if m["tag"] == tag:
                info = m; break
        vram = info["vram"] if info else 0
        score = info["score"] if info else 0
        purpose = info["purpose"] if info else "Базовое распознавание и перевод"
        display = info["display"] if info else tag
        vram_hw = self.hw["vram_gb"]
        if vram == 0:
            compat = "<span style='color:#4FC3F7;'>☁️ Облачная модель — VRAM не требуется.</span>"
        elif vram_hw >= vram:
            compat = f"<span style='color:#4CAF50;'>✅ Совместимо с вашей видеокартой ({vram_hw} ГБ >= {vram} ГБ).</span>"
        else:
            compat = (f"<span style='color:#FF6B6B;'>⚠️ Недостаточно памяти: нужно {vram} ГБ, есть {vram_hw} ГБ. "
                      f"Модель будет работать медленно на CPU.</span>")
        badge = "🟢" if score >= 90 else ("🟡" if score >= 50 else "🔴")
        self.desc_label.setText(
            f"<b>{badge} {display}</b><br>"
            f"<b>Назначение:</b> {purpose}<br>"
            f"<b>VRAM:</b> {'облако' if vram == 0 else f'~{vram} ГБ'}<br>"
            f"<b>Совместимость:</b> {compat}"
        )

    # ----------------------------------------------------- folder
    def _browse_models_folder(self):
        current = self.folder_input.text()
        path = QFileDialog.getExistingDirectory(self, "Выберите папку для моделей Ollama", current)
        if not path: return
        if set_ollama_models_path(path):
            self.folder_input.setText(path)
            self.folder_hint.setText("✅ Путь сохранён. Нажмите «Перезапустить Ollama» или перезагрузите ПК.")
        else:
            self.folder_hint.setText("❌ Не удалось записать путь. Запустите от имени администратора.")

    # ----------------------------------------------------- restart
    def _restart_ollama(self):
        self.status_label.setText("Перезапуск Ollama..."); self.status_label.setStyleSheet("color: #FFA726;")
        restart_ollama_service(); time.sleep(3)
        self.status_label.setText("✅ Ollama перезапущена."); self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")

    # ----------------------------------------------------- busy
    def set_ui_busy(self, busy):
        self.start_btn.setEnabled(not busy); self.delete_btn.setEnabled(not busy)
        self.model_selector.setEnabled(not busy); self.close_btn.setEnabled(not busy)
        self.refresh_catalog_btn.setEnabled(not busy); self.folder_browse_btn.setEnabled(not busy)

    # ----------------------------------------------------- get model
    def _get_selected_tag(self) -> str:
        tag = self.model_selector.currentData()
        if tag:
            return tag
        text = self.model_selector.currentText().strip()
        if "|" in text:
            return text.split("|")[-1].strip()
        return text

    # ----------------------------------------------------- install
    def start_installation(self):
        self.set_ui_busy(True); self.progress_bar.setValue(0)
        model_id = self._get_selected_tag()
        self.thread = InstallerThread(model_id, action="pull")
        self.thread.progress.connect(self.progress_bar.setValue)
        self.thread.status.connect(self.status_label.setText)
        self.thread.finished.connect(self.on_finished)
        self.thread.start()

    # ----------------------------------------------------- delete
    def start_deletion(self):
        self.set_ui_busy(True); self.progress_bar.setValue(0)
        model_id = self._get_selected_tag()
        self.thread = InstallerThread(model_id, action="delete")
        self.thread.progress.connect(self.progress_bar.setValue)
        self.thread.status.connect(self.status_label.setText)
        self.thread.finished.connect(self.on_finished)
        self.thread.start()

    # ----------------------------------------------------- finished
    def on_finished(self, success, message):
        self.set_ui_busy(False); self.success_state = success
        self.status_label.setText(message)
        self.status_label.setStyleSheet(
            "color: #4CAF50; font-weight: bold;" if success else "color: #FF4D4D; font-weight: bold;")

    def get_selected_model(self):
        return self._get_selected_tag()

    def close_dialog(self):
        self.accept() if self.success_state else self.reject()
