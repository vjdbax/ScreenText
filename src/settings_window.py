#!/usr/bin/env encoding
import sys
import os
import logging
import importlib
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    requests = None
    HAS_REQUESTS = False
import pyperclip
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QComboBox, QCheckBox, QDialog, QGroupBox,
    QSpinBox, QColorDialog, QMessageBox, QApplication, QTabWidget, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QThread
from settings import settings
try:
    import qtawesome as qta
except ImportError:
    qta = None
try:
    from ollama_installer import OllamaInstallerDialog, OllamaUpdateCheckerWorker
    HAS_OLLAMA_INSTALLER = True
except ImportError:
    OllamaInstallerDialog = None
    OllamaUpdateCheckerWorker = None
    HAS_OLLAMA_INSTALLER = False

# Статус native библиотек (без загрузки — только find_spec)
OCR_AVAILABLE = importlib.util.find_spec("easyocr") is not None
CV2_AVAILABLE = importlib.util.find_spec("cv2") is not None

# Микроскопический JPEG для теста зрения ИИ
TINY_JPEG_B64 = "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="


def evaluate_model_compatibility(model_id: str, is_vision_confirmed: bool = False) -> tuple:
    """
    Оценка пригодности модели для Vision/OCR.
    Возвращает кортеж: (score: int, badge: str, display_name: str)
    """
    m = model_id.lower()

    has_vision = is_vision_confirmed or any(k in m for k in [
        "-vl", "_vl", "vl:", "vl-", "vl_", "vision", "gemini", "gpt-4o", "pixtral", "minicpm",
    ])

    if has_vision:
        if any(k in m for k in ["qwen2.5vl", "qwen2.5-vl", "qwen-2.5-vl", "qwen2-vl"]):
            return (100, "🟢", f"🟢 100% | {model_id}")
        if any(k in m for k in ["gemini-1.5", "gemini-2.0", "gpt-4o"]):
            return (100, "🟢", f"🟢 100% | {model_id}")
        if any(k in m for k in ["llama-3.2", "pixtral"]):
            return (80, "🟢", f"🟢 80% | {model_id}")
        return (70, "🟡", f"🟡 70% | {model_id}")

    text_only = ["code", "coder", "whisper", "embed", "deepseek-r1", "glm-5", "llama-3.1", "liquid", "thinking", "math", "bert"]
    if any(k in m for k in text_only):
        return (0, "❌", f"❌ 0% | {model_id} (только текст)")

    return (10, "❓", f"❓ 10% | {model_id}")


def _extract_model_id(display_name: str) -> str:
    """Извлечь чистый model_id из display_name с бейджем."""
    if "|" in display_name:
        return display_name.split("|", 1)[-1].strip()
    return display_name.strip()


def get_model_info_card(model_id: str) -> str:
    """Генерирует форматированный HTML с описанием возможностей и назначения модели."""
    if not model_id:
        return "<i>Выберите модель для просмотра описания.</i>"

    m = model_id.lower()

    if "qwen" in m and ("72b" in m or "7b" in m) and ("vl" in m or "vision" in m):
        return (
            "<b>Флагман OCR и перевода.</b> Книги, комиксы, манга, мелкий текст и таблицы. "
            "Превосходный литературный русский язык.<br>"
            "<span style='color:#00E5FF;'>Рекомендация:</span> Идеально для чтения больших текстов и сложной верстки."
        )

    if "qwen" in m and ("3b" in m or "2b" in m) and ("vl" in m or "vision" in m):
        return (
            "<b>Турбо-модель (Скорость).</b> Сверхбыстрый отклик (0.5–1.5 сек). "
            "Отлично переводит субтитры, диалоги в играх и надписи в интерфейсах.<br>"
            "<span style='color:#00E5FF;'>Рекомендация:</span> Лучший выбор для гейминга в реальном времени."
        )

    if "gpt-4o" in m:
        return (
            "<b>Золотой стандарт OpenAI.</b> Максимальная точность распознавания и адаптивный стиль перевода. "
            "Точно сохраняет структуру абзацев.<br>"
            "<span style='color:#4CAF50;'>Рекомендация:</span> Универсальный эталон для любых задач."
        )

    if "gemini" in m:
        return (
            "<b>Высокоскоростной облачный Vision.</b> Отличное распознавание текста на сложных фонах, фотографиях и скриншотах.<br>"
            "<span style='color:#4CAF50;'>Рекомендация:</span> Высокая скорость и отличное качество русского языка."
        )

    if "llama-3.2" in m or "pixtral" in m:
        return (
            "<b>Открытая Vision-модель.</b> Уверенное оптическое распознавание английского языка. "
            "Перевод на русский может быть слегка буквальным (калька).<br>"
            "<span style='color:#E5C07B;'>Рекомендация:</span> Хорошо подходит для четких печатных документов."
        )

    if "minicpm" in m:
        return (
            "<b>Компактная архитектура.</b> Быстро читает английский текст, "
            "но на сложном русском контексте может допускать сбои или артефакты.<br>"
            "<span style='color:#FFA726;'>Внимание:</span> Рекомендуется использовать с четкими скриншотами."
        )

    text_patterns = ["code", "coder", "whisper", "embed", "glm", "liquid", "thinking", "math", "bert"]
    if any(p in m for p in text_patterns) and not any(v in m for v in ["vl", "vision", "4o"]):
        return (
            "<span style='color:#FF6B6B;'><b>Внимание: Модель только для текста!</b></span><br>"
            "Не поддерживает скриншоты (Ctrl+End вызовет ошибку). "
            "Используется только для перевода выделенного текста (Ctrl+Home)."
        )

    return "<b>Универсальная модель.</b> Базовый профиль распознавания и перевода текста."


class NetworkWorker(QThread):
    """Base worker class for async network operations"""
    finished = pyqtSignal(object)  # Result object
    error = pyqtSignal(str)  # Error message
    
    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
    
    def run(self):
        try:
            result = self.func(*self.args, **self.kwargs)
            self.finished.emit(result)
        except requests.exceptions.Timeout:
            self.error.emit("timeout")
        except requests.exceptions.ConnectionError:
            self.error.emit("connection")
        except Exception as e:
            self.error.emit(str(e))


class ScanModelsWorker(QThread):
    """Worker for scanning available AI models (universal: OpenAI-compatible + Ollama fallback)"""
    finished = pyqtSignal(list)  # List of dicts: [{"id": str, "modalities": list|None}, ...]
    error = pyqtSignal(str)  # Error message

    def __init__(self, base_url, api_key):
        super().__init__()
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key

    def _strip_v1(self, url):
        if url.endswith('/v1'):
            return url[:-3]
        return url

    def _is_openrouter(self, url):
        return "openrouter" in url.lower()

    def _try_openai_models(self, base_url, api_key):
        try:
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            response = requests.get(f"{base_url}/models", headers=headers, timeout=8)
            if response.status_code == 200:
                data = response.json().get("data", [])
                if not data:
                    return None
                models = []
                for m in data:
                    mid = m.get("id")
                    if not mid:
                        continue
                    if self._is_openrouter(base_url):
                        pricing = m.get("pricing", {})
                        if pricing.get("prompt") != "0":
                            continue
                    arch = m.get("architecture", {})
                    modalities = arch.get("input_modalities") or m.get("modalities") or m.get("input_modalities")
                    if isinstance(modalities, str):
                        modalities = [modalities]
                    models.append({"id": mid, "modalities": modalities})
                return models if models else None
            return None
        except Exception:
            return None

    def _try_ollama_tags(self, base_url, api_key):
        root = self._strip_v1(base_url)
        try:
            response = requests.get(f"{root}/api/tags", timeout=8)
            if response.status_code == 200:
                data = response.json().get("models", [])
                models = []
                for m in data:
                    name = m.get("name")
                    if not name:
                        continue
                    nl = name.lower()
                    if ":cloud" in nl or "cloud" in nl:
                        continue
                    models.append({"id": name, "modalities": None})
                return models if models else None
            return None
        except Exception:
            return None

    def run(self):
        try:
            models = self._try_openai_models(self.base_url, self.api_key)
            if not models:
                models = self._try_ollama_tags(self.base_url, self.api_key)
            if models:
                self.finished.emit(models)
            else:
                self.error.emit("empty")
        except requests.exceptions.Timeout:
            self.error.emit("timeout")
        except requests.exceptions.ConnectionError:
            self.error.emit("connection")
        except Exception as e:
            self.error.emit(str(e))


class TestModelWorker(QThread):
    """Worker for testing AI model connection"""
    finished = pyqtSignal(bool)  # Success status
    error = pyqtSignal(str)  # Error message with server details
    
    def __init__(self, base_url, api_key, model):
        super().__init__()
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
    
    def run(self):
        try:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "user", "content": "Hello"}
                ],
                "max_tokens": 10
            }
            r = requests.post(f"{self.base_url}/chat/completions", headers=headers, json=payload, timeout=15)
            if r.status_code == 200:
                self.finished.emit(True)
            else:
                try:
                    err_data = r.json()
                    err_msg = err_data.get("error", {}).get("message", r.text)
                except Exception:
                    err_msg = r.text or f"HTTP {r.status_code}"
                self.error.emit(f"Код {r.status_code}: {err_msg[:120]}")
        except requests.exceptions.Timeout:
            self.error.emit("Таймаут соединения (15 сек)")
        except requests.exceptions.ConnectionError:
            self.error.emit("Сервер недоступен")
        except Exception as e:
            self.error.emit(str(e))


class CheckGoogleWorker(QThread):
    """Worker for checking Google Translate availability"""
    finished = pyqtSignal(bool)  # Success status
    error = pyqtSignal(str)  # Error message
    
    def run(self):
        try:
            r = requests.get("https://translate.google.com", timeout=8)
            if r.status_code == 200:
                self.finished.emit(True)
            else:
                self.error.emit(f"http_{r.status_code}")
        except requests.exceptions.Timeout:
            self.error.emit("timeout")
        except requests.exceptions.ConnectionError:
            self.error.emit("connection")
        except Exception as e:
            self.error.emit(str(e))


class CheckDeepLWorker(QThread):
    """Worker for checking DeepL API status"""
    finished = pyqtSignal(dict)  # Usage data {limit, count}
    error = pyqtSignal(str)  # Error message
    
    def __init__(self, api_key):
        super().__init__()
        self.api_key = api_key
    
    def run(self):
        try:
            base = "https://api-free.deepl.com/v2/usage" if self.api_key.endswith(":fx") else "https://api.deepl.com/v2/usage"
            headers = {"Authorization": f"DeepL-Auth-Key {self.api_key}"}
            r = requests.get(base, headers=headers, timeout=10)
            if r.status_code == 200:
                d = r.json()
                self.finished.emit({
                    "limit": d.get("character_limit", 0),
                    "count": d.get("character_count", 0)
                })
            elif r.status_code == 403:
                self.error.emit("403")
            else:
                self.error.emit(f"http_{r.status_code}")
        except requests.exceptions.Timeout:
            self.error.emit("timeout")
        except requests.exceptions.ConnectionError:
            self.error.emit("connection")
        except Exception as e:
            self.error.emit(str(e))


class HotkeyCaptureDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Запись горячей клавиши")
        self.setFixedSize(320, 110)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)
        self.captured_hotkey = ""
        self.setup_ui()
        
    def setup_ui(self):
        self.setStyleSheet("""
            QDialog { background-color: #1E1E1E; border: 2px solid #3C3C3C; border-radius: 8px; }
            QLabel { color: #CCCCCC; font-family: "Segoe UI", Arial, sans-serif; font-size: 12px; font-weight: bold; background: transparent; }
        """)
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        self.label = QLabel("Нажмите комбинацию клавиш...\n\n(Для отмены нажмите Esc)")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)
        self.setLayout(layout)
        
    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta): return
        if key == Qt.Key.Key_Escape: self.reject(); return
        modifiers = event.modifiers()
        parts = []
        if modifiers & Qt.KeyboardModifier.ControlModifier: parts.append("ctrl")
        if modifiers & Qt.KeyboardModifier.AltModifier: parts.append("alt")
        if modifiers & Qt.KeyboardModifier.ShiftModifier: parts.append("shift")
        if modifiers & Qt.KeyboardModifier.MetaModifier: parts.append("win")
            
        key_name = ""
        if Qt.Key.Key_F1 <= key <= Qt.Key.Key_F12: key_name = f"f{key - Qt.Key.Key_F1 + 1}"
        elif key == Qt.Key.Key_Home: key_name = "home"
        elif key == Qt.Key.Key_End: key_name = "end"
        elif key == Qt.Key.Key_PageUp: key_name = "page up"
        elif key == Qt.Key.Key_PageDown: key_name = "page down"
        elif key == Qt.Key.Key_Insert: key_name = "insert"
        elif key == Qt.Key.Key_Delete: key_name = "delete"
        elif key == Qt.Key.Key_Left: key_name = "left"
        elif key == Qt.Key.Key_Right: key_name = "right"
        elif key == Qt.Key.Key_Up: key_name = "up"
        elif key == Qt.Key.Key_Down: key_name = "down"
        elif key == Qt.Key.Key_Space: key_name = "space"
        elif key == Qt.Key.Key_Tab: key_name = "tab"
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter): key_name = "enter"
        else:
            text = event.text().strip().lower()
            if text: key_name = text
            else: key_name = chr(key).lower() if 32 <= key <= 126 else ""
                
        if key_name:
            parts.append(key_name)
            self.captured_hotkey = "+".join(parts)
            self.accept()
        else:
            event.accept()

class SettingsWindow(QDialog):
    settings_saved = pyqtSignal()
    run_benchmark_requested = pyqtSignal()
    ocr_reload_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        from __init__ import __version__
        self.setWindowTitle(f"Настройки ScreenText Helper v{__version__}")
        self.logger = logging.getLogger(__name__) 
        if qta:
            try: self.setWindowIcon(qta.icon('fa5s.language', color='#007ACC'))
            except: pass
        
        self.setFixedSize(620, 580)
        
        self._workers = []
        
        self.setup_styles()
        try:
            self.setup_ui()
        except Exception as e:
            self.logger.error(f"Ошибка инициализации UI настроек: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить настройки: {e}")
            raise
        
    def setup_styles(self):
        self.setStyleSheet("""
            QDialog { background-color: #1E1E1E; color: #CCCCCC; font-family: "Segoe UI", Arial, sans-serif; }
            QTabWidget::pane { border: 1px solid #3C3C3C; border-radius: 4px; background-color: #1E1E1E; top: -1px; }
            QTabBar::tab { background-color: #2D2D2D; color: #999999; border: 1px solid #3C3C3C; border-bottom: none; border-top-left-radius: 6px; border-top-right-radius: 6px; padding: 8px 16px; margin-right: 2px; font-size: 11px; font-weight: bold; min-height: 20px; }
            QTabBar::tab:selected { background-color: #0E639C; color: #FFFFFF; border-color: #0E639C; }
            QTabBar::tab:hover:!selected { background-color: #3C3C3C; color: #CCCCCC; }
            QGroupBox { background-color: #1E1E1E; border: 1px solid #3C3C3C; border-radius: 6px; margin-top: 14px; padding-top: 14px; padding-bottom: 8px; padding-left: 8px; padding-right: 8px; color: #FFFFFF; font-weight: bold; font-size: 11px; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 10px; padding: 0 5px; background-color: #1E1E1E; }
            QLabel { color: #CCCCCC; background: transparent; font-size: 11px; min-height: 22px; }
            QLineEdit, QSpinBox { background-color: #2D2D2D; color: #CCCCCC; border: 1px solid #3C3C3C; border-radius: 4px; padding: 5px 6px; font-size: 11px; min-height: 28px; }
            QLineEdit:focus, QSpinBox:focus { border: 1px solid #007ACC; }
            QComboBox { background-color: #2D2D2D; color: #CCCCCC; border: 1px solid #3C3C3C; border-radius: 4px; padding: 5px 6px; font-size: 11px; min-height: 28px; }
            QComboBox:focus { border: 1px solid #007ACC; }
            QComboBox QAbstractItemView { background-color: #252526; color: rgba(255, 255, 255, 0.8); border: 1px solid #3C3C3C; selection-background-color: #094771; selection-color: #FFFFFF; }
            QCheckBox { color: #CCCCCC; spacing: 6px; font-size: 11px; min-height: 22px; }
            QCheckBox::indicator { width: 14px; height: 14px; border: 1px solid #3C3C3C; border-radius: 3px; background-color: #2D2D2D; }
            QCheckBox::indicator:hover { border: 1px solid #007ACC; }
            QCheckBox::indicator:checked { background-color: #0E639C; border: 1px solid #0E639C; }
            QPushButton { background-color: #2D2D2D; color: #CCCCCC; border: 1px solid #3C3C3C; border-radius: 4px; padding: 5px 14px; font-size: 11px; font-weight: bold; min-height: 28px; }
            QPushButton:hover { background-color: #3C3C3C; color: #FFFFFF; border: 1px solid #454545; }
            QPushButton:disabled { background-color: #1E1E1E; color: #666666; border: 1px solid #2D2D2D; }
            QPushButton#save_btn { background-color: #0E639C; color: #FFFFFF; border: 1px solid #1177BB; }
            QPushButton#save_btn:hover { background-color: #1177BB; }
            QPushButton#test_btn { background-color: #2D2D2D; color: #007ACC; border: 1px solid #007ACC; }
            QPushButton#test_btn:hover { background-color: #007ACC; color: #FFFFFF; }
            QPushButton#bench_btn { background-color: #2D2D2D; color: #E5C07B; border: 1px solid #E5C07B; }
            QPushButton#bench_btn:hover { background-color: #E5C07B; color: #1E1E1E; }
            QMessageBox { background-color: #1E1E1E; color: #CCCCCC; border: 1px solid #3C3C3C; }
            QToolTip { background-color: #2D2D2D; color: #FFFFFF; border: 1px solid #555555; border-radius: 4px; padding: 10px; font-family: "Segoe UI"; font-size: 11px; }
        """)

    def get_current_url(self) -> str:
        idx = self.base_url_input.currentIndex()
        if idx < 0:
            return settings.get("llm.base_url", "https://api.openai.com/v1")
        data = self.base_url_input.itemData(idx)
        if data == "custom":
            custom = self.custom_url_input.text().strip()
            return custom if custom else "http://localhost:11434/v1"
        if data and data.startswith("http"):
            return data
        return settings.get("llm.base_url", "https://api.openai.com/v1")

    def get_current_model(self) -> str:
        """Возвращает чистый идентификатор модели без эмодзи, скоров и префиксов."""
        idx = self.model_input.currentIndex()
        if idx >= 0:
            data = self.model_input.itemData(idx)
            if data and isinstance(data, str) and "|" not in data:
                return data.strip()
        text = self.model_input.currentText().strip()
        if "|" in text:
            return text.split("|")[-1].strip()
        return text

    def get_error_help_html(self, error_str):
        code = "".join(filter(str.isdigit, error_str))
        url = self.get_current_url().lower()
        is_local = "localhost" in url or "127.0.0.1" in url
        
        if code == "401":
            return "<b>Ошибка 401 (Неавторизован)</b><br><br>Неверный API ключ. Проверьте правильность ключа в кабинете провайдера."
        elif code == "404":
            if is_local:
                return "<b>Ошибка 404 (Не найдено)</b><br><br>Модель не найдена в Ollama. Нажмите кнопку 'Сканировать' или установите модель через мастер."
            return "<b>Ошибка 404 (Не найдено)</b><br><br>Данная модель недоступна у провайдера или указан неверный URL сервиса."
        elif code == "429":
            return "<b>Ошибка 429 (Лимит запросов)</b><br><br>Слишком много запросов или закончились средства на балансе (для платных API)."
        elif code == "502" or code == "503":
            if is_local:
                return "<b>Ошибка 502/503 (Сервис недоступен)</b><br><br><b>Причина:</b> Программа Ollama не запущена.<br><b>Решение:</b> Запустите Ollama (иконка в трее) и попробуйте снова."
            return "<b>Ошибка 502/503</b><br><br>Сервис провайдера временно недоступен или проблемы с вашим интернет-соединением."
        elif "connection" in error_str.lower() or "timeout" in error_str.lower():
            if is_local:
                return "<b>Ошибка подключения</b><br><br>Ollama не отвечает по адресу localhost:11434. Убедитесь, что приложение Ollama открыто."
            return "<b>Ошибка сети</b><br><br>Не удалось связаться с сервером. Проверьте интернет или настройки VPN/Прокси."
            
        return f"<b>Ошибка {error_str}</b><br><br>Наведите курсор позже или проверьте лог-файл для деталей."
        
    def setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        tabs = QTabWidget()
        tabs.setDocumentMode(False)

        # ── TAB 1: Hotkeys & Behavior ──
        tab1 = QWidget()
        tab1_l = QVBoxLayout(tab1)
        tab1_l.setContentsMargins(12, 12, 12, 12)
        tab1_l.setSpacing(10)

        hk_group = QGroupBox("Горячие клавиши")
        hk_lay = QVBoxLayout()
        hk_lay.setContentsMargins(10, 16, 10, 8)
        hk_lay.setSpacing(6)

        ocr_row = QHBoxLayout()
        ocr_row.addWidget(QLabel("OCR (Распознавание текста):"))
        self.ocr_hotkey_input = QLineEdit(settings.get_hotkey("ocr"))
        self.ocr_hotkey_input.setReadOnly(True)
        ocr_row.addWidget(self.ocr_hotkey_input)
        self.ocr_hotkey_btn = QPushButton("Изменить")
        self.ocr_hotkey_btn.setFixedWidth(90)
        self.ocr_hotkey_btn.clicked.connect(lambda: self.set_hotkey("ocr"))
        ocr_row.addWidget(self.ocr_hotkey_btn)
        hk_lay.addLayout(ocr_row)

        tr_row = QHBoxLayout()
        tr_row.addWidget(QLabel("Перевод текста:"))
        self.translate_hotkey_input = QLineEdit(settings.get_hotkey("translate"))
        self.translate_hotkey_input.setReadOnly(True)
        tr_row.addWidget(self.translate_hotkey_input)
        self.translate_hotkey_btn = QPushButton("Изменить")
        self.translate_hotkey_btn.setFixedWidth(90)
        self.translate_hotkey_btn.clicked.connect(lambda: self.set_hotkey("translate"))
        tr_row.addWidget(self.translate_hotkey_btn)
        hk_lay.addLayout(tr_row)

        hk_group.setLayout(hk_lay)
        tab1_l.addWidget(hk_group)

        beh_group = QGroupBox("Поведение")
        beh_lay = QVBoxLayout()
        beh_lay.setContentsMargins(10, 16, 10, 8)
        beh_lay.setSpacing(6)

        self.auto_start_check = QCheckBox("Автозагрузка при старте Windows")
        self.auto_start_check.setChecked(settings.get_auto_start())
        beh_lay.addWidget(self.auto_start_check)

        self.close_on_blur_check = QCheckBox("Закрывать оверлей при потере фокуса (клик вне окна)")
        self.close_on_blur_check.setChecked(settings.get("close_overlay_on_blur", True))
        beh_lay.addWidget(self.close_on_blur_check)

        ac_row = QHBoxLayout()
        ac_row.addWidget(QLabel("Автозакрытие оверлея:"))
        self.auto_close_spin = QSpinBox()
        self.auto_close_spin.setRange(0, 300)
        self.auto_close_spin.setValue(settings.get("overlay_auto_close_sec", 0))
        self.auto_close_spin.setSuffix(" сек")
        self.auto_close_spin.setFixedWidth(100)
        self.auto_close_spin.setToolTip("0 — автозакрытие выключено.\nЕсли > 0, оверлей закроется через указанное время.\nТаймер сбрасывается при наведении курсора.")
        ac_row.addWidget(self.auto_close_spin)
        ac_row.addStretch()
        beh_lay.addLayout(ac_row)

        beh_group.setLayout(beh_lay)
        tab1_l.addWidget(beh_group)
        tab1_l.addStretch()

        tabs.addTab(tab1, "📑 Горячие клавиши")

        # ── TAB 2: AI Vision ──
        tab2 = QWidget()
        tab2_l = QVBoxLayout(tab2)
        tab2_l.setContentsMargins(12, 12, 12, 12)
        tab2_l.setSpacing(8)

        self.use_ai_check = QCheckBox("Использовать Vision-to-Text (ИИ)")
        self.use_ai_check.setChecked(settings.get("llm.use_smart_translate", False))
        tab2_l.addWidget(self.use_ai_check)

        self.translate_with_standard_check = QCheckBox("Переводить ИИ-текст стандартным движком")
        self.translate_with_standard_check.setChecked(settings.get("llm.translate_with_standard_engine", False))
        tab2_l.addWidget(self.translate_with_standard_check)

        tab2_l.addWidget(QLabel("Сервис ИИ (провайдер):"))
        self.base_url_input = QComboBox()
        self.base_url_input.setEditable(True)
        ai_providers = [
            ("Локальная ИИ (Ollama)", "http://localhost:11434/v1"),
            ("DeepSeek API", "https://api.deepseek.com"),
            ("OpenRouter (Бесплатные модели)", "https://openrouter.ai/api/v1"),
            ("OpenAI (ChatGPT)", "https://api.openai.com/v1"),
            ("Groq Cloud (Сверхбыстрый API)", "https://api.groq.com/openai/v1"),
            ("Свой сервер (Кастомный URL)", "custom")
        ]
        for name, url in ai_providers:
            self.base_url_input.addItem(name, url)
        self.base_url_input.currentTextChanged.connect(self.on_base_url_changed)

        self.custom_url_row = QWidget()
        custom_url_layout = QHBoxLayout(self.custom_url_row)
        custom_url_layout.setContentsMargins(0, 0, 0, 0)
        self.custom_url_label = QLabel("URL сервера:")
        self.custom_url_input = QLineEdit()
        self.custom_url_input.setPlaceholderText("http://localhost:11434/v1  или  https://xxx.trycloudflare.com/v1")
        self.custom_url_input.setText(settings.get("llm.custom_base_url", ""))
        self.custom_url_input.textChanged.connect(self._on_custom_url_changed)
        self.custom_url_input.textChanged.connect(self._validate_custom_url)
        custom_url_layout.addWidget(self.custom_url_label)
        custom_url_layout.addWidget(self.custom_url_input)
        tab2_l.addWidget(self.custom_url_row)

        saved_url = settings.get("llm.base_url", "https://api.openai.com/v1")
        preset_urls = [self.base_url_input.itemData(i) for i in range(self.base_url_input.count())]
        if saved_url in preset_urls:
            idx = self.base_url_input.findData(saved_url)
            if idx != -1: self.base_url_input.setCurrentIndex(idx)
        else:
            idx = self.base_url_input.findData("custom")
            if idx != -1: self.base_url_input.setCurrentIndex(idx)
            self.custom_url_input.setText(saved_url)
        tab2_l.addWidget(self.base_url_input)

        tab2_l.addWidget(QLabel("API Ключ:"))
        key_row = QHBoxLayout()
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.textChanged.connect(self.on_api_key_changed)
        self.show_key_btn = QPushButton("Показать")
        self.show_key_btn.setFixedWidth(90)
        self.show_key_btn.clicked.connect(self.toggle_api_key_visibility)
        key_row.addWidget(self.api_key_input)
        key_row.addWidget(self.show_key_btn)
        tab2_l.addLayout(key_row)

        tab2_l.addWidget(QLabel("Модель:"))
        model_row = QHBoxLayout()
        self.model_input = QComboBox()
        self.model_input.setEditable(True)
        self.model_input.currentTextChanged.connect(self.on_model_changed)
        model_row.addWidget(self.model_input)
        self.scan_models_btn = QPushButton("Сканировать")
        self.scan_models_btn.setFixedWidth(100)
        self.scan_models_btn.clicked.connect(self.scan_free_models)
        model_row.addWidget(self.scan_models_btn)
        tab2_l.addLayout(model_row)

        self.model_desc_frame = QFrame()
        self.model_desc_frame.setObjectName("desc_box")
        self.model_desc_frame.setStyleSheet("""
            QFrame#desc_box {
                background-color: #252526;
                border: 1px solid #3C3C3C;
                border-radius: 6px;
                margin-top: 4px;
                margin-bottom: 6px;
            }
        """)
        desc_layout = QVBoxLayout(self.model_desc_frame)
        desc_layout.setContentsMargins(10, 8, 10, 8)
        self.model_desc_label = QLabel("")
        self.model_desc_label.setWordWrap(True)
        self.model_desc_label.setStyleSheet("color: #BBBBBB; font-size: 11px; line-height: 140%;")
        desc_layout.addWidget(self.model_desc_label)
        tab2_l.addWidget(self.model_desc_frame)
        self.update_model_description()

        test_row = QHBoxLayout()
        self.test_ai_btn = QPushButton("Проверить модель")
        self.test_ai_btn.setObjectName("test_btn")
        self.test_ai_btn.clicked.connect(self.test_ai_connection)
        self.run_benchmark_btn = QPushButton("Авто-подбор")
        self.run_benchmark_btn.setObjectName("bench_btn")
        self.run_benchmark_btn.clicked.connect(self.run_on_demand_test)
        self.ai_status_label = QLabel("")
        test_row.addWidget(self.test_ai_btn)
        test_row.addWidget(self.run_benchmark_btn)
        test_row.addWidget(self.ai_status_label)
        test_row.addStretch()
        tab2_l.addLayout(test_row)

        if HAS_OLLAMA_INSTALLER:
            self.install_local_ai_btn = QPushButton("Установить локальный ИИ (Ollama) на ПК")
            self.install_local_ai_btn.setStyleSheet("color: #4CAF50; border: 1px solid #4CAF50; font-weight: bold;")
            self.install_local_ai_btn.clicked.connect(self.launch_ollama_installer)
            tab2_l.addWidget(self.install_local_ai_btn)

            if OllamaUpdateCheckerWorker:
                self.ollama_update_banner = QLabel("")
                self.ollama_update_banner.setWordWrap(True)
                self.ollama_update_banner.setStyleSheet(
                    "QLabel { background-color: #332b00; border: 1px solid #997a00; "
                    "border-radius: 4px; padding: 6px 10px; color: #e5c100; font-size: 11px; }"
                )
                self.ollama_update_banner.setVisible(False)
                tab2_l.addWidget(self.ollama_update_banner)

                self.ollama_update_btn = QPushButton("⚡ Обновить Ollama")
                self.ollama_update_btn.setStyleSheet(
                    "QPushButton { color: #00E5FF; border: 1px solid #00B4D8; background-color: #1E262C; "
                    "padding: 6px; font-weight: bold; border-radius: 4px; } "
                    "QPushButton:hover { background-color: #263238; }"
                )
                self.ollama_update_btn.setVisible(False)
                self.ollama_update_btn.clicked.connect(self.launch_ollama_installer)
                tab2_l.addWidget(self.ollama_update_btn)

                self._ollama_update_worker = None

        tab2_l.addStretch()
        tabs.addTab(tab2, "🧠 ИИ Vision")

        # ── TAB 3: Languages & Engines ──
        tab3 = QWidget()
        tab3_l = QVBoxLayout(tab3)
        tab3_l.setContentsMargins(12, 12, 12, 12)
        tab3_l.setSpacing(8)

        eng_group = QGroupBox("Движок перевода")
        eng_lay = QVBoxLayout()
        eng_lay.setContentsMargins(10, 16, 10, 8)
        eng_lay.setSpacing(6)

        self.engine_combo = QComboBox()
        self.engine_combo.addItem("Google Translate (онлайн)", "google")
        self.engine_combo.addItem("DeepL (API онлайн)", "deepl")
        self.engine_combo.addItem("Argos Translate (офлайн)", "argos")
        eng_set = settings.get("languages.translator_engine", "google")
        idx_map = {"google": 0, "deepl": 1, "argos": 2}
        self.engine_combo.setCurrentIndex(idx_map.get(eng_set, 0))
        self.engine_combo.currentIndexChanged.connect(self._on_engine_changed)
        eng_lay.addWidget(QLabel("Стандартный движок перевода:"))
        eng_lay.addWidget(self.engine_combo)

        google_row = QHBoxLayout()
        self.google_check_btn = QPushButton("Проверить Google")
        self.google_check_btn.setStyleSheet("color: #4CAF50; border: 1px solid #4CAF50;")
        self.google_check_btn.clicked.connect(self._check_google)
        self.google_status_label = QLabel("")
        self.google_status_label.setStyleSheet("color: #888; font-size: 9px;")
        google_row.addWidget(self.google_check_btn)
        google_row.addWidget(self.google_status_label)
        google_row.addStretch()
        eng_lay.addLayout(google_row)

        self.deepl_widget = QWidget()
        deepl_lay = QVBoxLayout(self.deepl_widget)
        deepl_lay.setContentsMargins(0, 4, 0, 4)
        deepl_api_row = QHBoxLayout()
        self.deepl_api_input = QLineEdit()
        self.deepl_api_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.deepl_api_input.setPlaceholderText("Введите DeepL API-ключ...")
        self.deepl_api_input.setText(settings.get("languages.deepl_api_key", ""))
        self.deepl_key_btn = QPushButton("Показать")
        self.deepl_key_btn.setFixedWidth(80)
        self.deepl_key_btn.clicked.connect(lambda: self._toggle_deepl_key())
        deepl_api_row.addWidget(self.deepl_api_input)
        deepl_api_row.addWidget(self.deepl_key_btn)
        deepl_lay.addLayout(deepl_api_row)
        deepl_chk_row = QHBoxLayout()
        self.deepl_check_btn = QPushButton("Проверить статус и лимит")
        self.deepl_check_btn.setStyleSheet("color: #4CAF50; border: 1px solid #4CAF50;")
        self.deepl_check_btn.clicked.connect(self._check_deepl)
        self.deepl_status_label = QLabel("")
        self.deepl_status_label.setStyleSheet("color: #888; font-size: 9px;")
        deepl_chk_row.addWidget(self.deepl_check_btn)
        deepl_chk_row.addWidget(self.deepl_status_label)
        deepl_chk_row.addStretch()
        deepl_lay.addLayout(deepl_chk_row)
        eng_lay.addWidget(self.deepl_widget)

        eng_group.setLayout(eng_lay)
        tab3_l.addWidget(eng_group)

        lang_group = QGroupBox("Языки")
        lang_lay = QVBoxLayout()
        lang_lay.setContentsMargins(10, 16, 10, 8)
        lang_lay.setSpacing(6)

        self.ocr_lang_combo = QComboBox()
        self.ocr_lang_combo.addItems(["rus", "eng", "rus+eng"])
        self.ocr_lang_combo.setCurrentText(settings.get_ocr_language())
        lang_lay.addWidget(QLabel("Язык распознавания (OCR):"))
        lang_lay.addWidget(self.ocr_lang_combo)

        self.translate_lang_combo = QComboBox()
        self.translate_lang_combo.addItems(["en", "ru", "be-latn", "zh", "es", "fr", "de"])
        self.translate_lang_combo.setCurrentText(settings.get_translate_target_language())
        lang_lay.addWidget(QLabel("Целевой язык перевода:"))
        lang_lay.addWidget(self.translate_lang_combo)

        lang_group.setLayout(lang_lay)
        tab3_l.addWidget(lang_group)

        libs_row = QHBoxLayout()
        libs_style = "color: #888888; font-size: 9px; font-family: Consolas, monospace;"
        for name, ok in [("EasyOCR", OCR_AVAILABLE), ("OpenCV", CV2_AVAILABLE), ("Requests", HAS_REQUESTS), ("Ollama", HAS_OLLAMA_INSTALLER), ("QAwesome", qta is not None)]:
            lbl = QLabel(f"{name}: {'✅' if ok else '❌'}")
            lbl.setStyleSheet(libs_style)
            libs_row.addWidget(lbl)
        libs_row.addStretch()
        tab3_l.addLayout(libs_row)

        self.retry_ocr_btn = QPushButton("Перезагрузить OCR (EasyOCR)")
        self.retry_ocr_btn.setStyleSheet("color: #E5C07B; border: 1px solid #E5C07B;")
        self.retry_ocr_btn.clicked.connect(self.ocr_reload_requested.emit)
        tab3_l.addWidget(self.retry_ocr_btn)

        tab3_l.addStretch()
        tabs.addTab(tab3, "🌐 Языки")

        # ── TAB 4: Appearance ──
        tab4 = QWidget()
        tab4_l = QVBoxLayout(tab4)
        tab4_l.setContentsMargins(12, 12, 12, 12)
        tab4_l.setSpacing(8)

        win_group = QGroupBox("Параметры окна")
        win_lay = QVBoxLayout()
        win_lay.setContentsMargins(10, 16, 10, 8)
        win_lay.setSpacing(6)

        self.opacity_spin = QSpinBox()
        self.opacity_spin.setRange(10, 100)
        self.opacity_spin.setValue(int(settings.get("window_opacity", 0.95) * 100))
        self.opacity_spin.setSuffix("%")
        self.opacity_spin.setFixedWidth(80)
        win_lay.addLayout(self._create_row("Непрозрачность окна:", self.opacity_spin))

        self.border_color_btn = QPushButton()
        self.border_color_btn.setFixedSize(60, 28)
        self.border_color_btn.setStyleSheet(f"background-color: {settings.get('border_color', '#555555')}; border: 1px solid #555555;")
        self.border_color_btn.clicked.connect(self.choose_border_color)
        win_lay.addLayout(self._create_row("Цвет внешней рамки:", self.border_color_btn))

        self.bg_color_btn = QPushButton()
        self.bg_color_btn.setFixedSize(60, 28)
        self.bg_color_btn.setStyleSheet(f"background-color: {settings.get('bg_color', '#FFFFFF')}; border: 1px solid #555555;")
        self.bg_color_btn.clicked.connect(self.choose_bg_color)
        win_lay.addLayout(self._create_row("Цвет фона подложки:", self.bg_color_btn))

        self.font_color_btn = QPushButton()
        self.font_color_btn.setFixedSize(60, 28)
        self.font_color_btn.setStyleSheet(f"background-color: {settings.get('font_color', '#000000')}; border: 1px solid #555555;")
        self.font_color_btn.clicked.connect(self.choose_font_color)
        win_lay.addLayout(self._create_row("Цвет шрифта текста:", self.font_color_btn))

        win_group.setLayout(win_lay)
        tab4_l.addWidget(win_group)

        fs_group = QGroupBox("Размеры шрифтов")
        fs_lay = QVBoxLayout()
        fs_lay.setContentsMargins(10, 16, 10, 8)
        fs_lay.setSpacing(6)

        self.fs_p_spin = QSpinBox()
        self.fs_p_spin.setRange(6, 24)
        self.fs_p_spin.setValue(settings.get("font_size_p", 10))
        self.fs_p_spin.setFixedWidth(80)
        fs_lay.addLayout(self._create_row("Обычный текст (P):", self.fs_p_spin))

        self.fs_h2_spin = QSpinBox()
        self.fs_h2_spin.setRange(8, 28)
        self.fs_h2_spin.setValue(settings.get("font_size_h2", 12))
        self.fs_h2_spin.setFixedWidth(80)
        fs_lay.addLayout(self._create_row("Заголовок H2:", self.fs_h2_spin))

        self.fs_h1_spin = QSpinBox()
        self.fs_h1_spin.setRange(10, 36)
        self.fs_h1_spin.setValue(settings.get("font_size_h1", 14))
        self.fs_h1_spin.setFixedWidth(80)
        fs_lay.addLayout(self._create_row("Заголовок H1:", self.fs_h1_spin))

        fs_group.setLayout(fs_lay)
        tab4_l.addWidget(fs_group)
        tab4_l.addStretch()

        tabs.addTab(tab4, "🎨 Внешний вид")

        root.addWidget(tabs, 1)

        # Bottom buttons — fixed
        btns = QHBoxLayout()
        btns.setContentsMargins(0, 4, 0, 0)
        self.save_btn = QPushButton("Сохранить")
        self.save_btn.setObjectName("save_btn")
        self.save_btn.clicked.connect(self.save_settings)
        self.reset_btn = QPushButton("Сбросить")
        self.reset_btn.clicked.connect(self.reset_settings)
        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.clicked.connect(self.reject)
        btns.addWidget(self.save_btn)
        btns.addWidget(self.reset_btn)
        btns.addWidget(self.cancel_btn)
        root.addLayout(btns)

        self.on_base_url_changed(self.base_url_input.currentText())

        self._on_engine_changed(self.engine_combo.currentIndex())

    def _create_row(self, label_text, widget):
        row = QHBoxLayout()
        row.addWidget(QLabel(label_text))
        row.addWidget(widget)
        row.addStretch()
        return row

    # --- LOGIC (unchanged) ---

    def toggle_api_key_visibility(self):
        if self.api_key_input.echoMode() == QLineEdit.EchoMode.Password:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Normal); self.show_key_btn.setText("Скрыть")
        else:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password); self.show_key_btn.setText("Показать")

    def launch_ollama_installer(self):
        if not HAS_OLLAMA_INSTALLER:
            QMessageBox.warning(self, "Недоступно", "Модуль установки Ollama не найден. Переустановите программу.")
            return
        dialog = OllamaInstallerDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.base_url_input.setCurrentIndex(0); self.model_input.setCurrentText(dialog.get_selected_model()); self.use_ai_check.setChecked(True)
            if hasattr(self, 'ollama_update_banner'):
                self.start_ollama_update_check()

    def start_ollama_update_check(self):
        if not HAS_OLLAMA_INSTALLER or not OllamaUpdateCheckerWorker:
            return
        if self._ollama_update_worker and self._ollama_update_worker.isRunning():
            return
        self._ollama_update_worker = OllamaUpdateCheckerWorker()
        self._ollama_update_worker.update_available.connect(self._on_ollama_update_available)
        self._ollama_update_worker.up_to_date.connect(self._on_ollama_up_to_date)
        self._ollama_update_worker.check_failed.connect(self._on_ollama_check_failed)
        self._ollama_update_worker.start()

    def _on_ollama_update_available(self, current, latest):
        self.ollama_update_banner.setText(
            f"Ollama устарела: {current} → доступна {latest}"
        )
        self.ollama_update_banner.setVisible(True)
        self.ollama_update_btn.setText(f"⚡ Обновить Ollama ({latest})")
        self.ollama_update_btn.setVisible(True)

    def _on_ollama_up_to_date(self, version):
        if hasattr(self, 'ollama_update_banner'):
            self.ollama_update_banner.setVisible(False)
            self.ollama_update_btn.setVisible(False)

    def _on_ollama_check_failed(self):
        if hasattr(self, 'ollama_update_banner'):
            self.ollama_update_banner.setVisible(False)
            self.ollama_update_btn.setVisible(False)

    def _launch_ollama_update(self):
        import webbrowser
        webbrowser.open("https://ollama.com/download")

    def on_api_key_changed(self, text):
        url = self.get_current_url()
        if url:
            keys = settings.get("llm.keys_dict", {}); keys[url] = text.strip(); settings.set("llm.keys_dict", keys)

    def _on_custom_url_changed(self, text):
        settings.set("llm.custom_base_url", text.strip())

    def _validate_custom_url(self, text):
        import re as _re
        pattern = r'^https?://(?:[a-zA-Z0-9\-]+\.)+[a-zA-Z0-9]+(?::\d+)?(?:/.*)?$'
        is_valid = bool(_re.match(pattern, text.strip())) or "localhost" in text.lower() or "127.0.0.1" in text.lower()
        if not text.strip():
            self.custom_url_input.setStyleSheet("")
        elif is_valid:
            self.custom_url_input.setStyleSheet(
                "QLineEdit { color: #00E5FF; border: 1px solid #00B4D8; background-color: #1E262C; font-weight: bold; }"
            )
        else:
            self.custom_url_input.setStyleSheet(
                "QLineEdit { color: #FF8A80; border: 1px solid #D32F2F; background-color: #2A1E1E; }"
            )

    def on_model_changed(self, text):
        url = self.get_current_url()
        if url and text:
            mid = self.model_input.currentData()
            if not mid:
                mid = _extract_model_id(text)
            models = settings.get("llm.models_dict", {}); models[url] = mid; settings.set("llm.models_dict", models)
        self.update_model_description()

    def update_model_description(self):
        clean_id = self.get_current_model()
        info_html = get_model_info_card(clean_id)
        self.model_desc_label.setText(info_html)

    def on_base_url_changed(self, text):
        if not hasattr(self, 'api_key_input'):
            return
        idx = self.base_url_input.currentIndex()
        data = self.base_url_input.itemData(idx) if idx >= 0 else None
        is_custom = (data == "custom")
        self.custom_url_row.setVisible(is_custom)
        url = self.get_current_url()
        keys = settings.get("llm.keys_dict", {})
        saved_key = keys.get(url, "") or settings.get("llm.api_key", "")
        self.api_key_input.blockSignals(True)
        self.api_key_input.setText(saved_key)
        self.api_key_input.blockSignals(False)
        models_dict = settings.get("llm.models_dict", {})
        saved_model = models_dict.get(url, "")
        self.model_input.blockSignals(True)
        self.model_input.clear()
        url_l = url.lower()
        if is_custom:
            def_m = [saved_model] if saved_model else []
        elif "groq" in url_l:
            def_m = ["qwen/qwen3.8-27b", "llama-3.3-70b-versatile", "meta-llama/llama-4-scout-17b-16e-instruct"]
        elif "openrouter" in url_l:
            def_m = ["openrouter/free", "google/gemini-1.5-flash:free", "qwen/qwen-2-vl-7b-instruct:free"]
        elif "openai" in url_l:
            def_m = ["gpt-4o-mini", "gpt-4o"]
        elif "deepseek" in url_l:
            def_m = ["deepseek-chat"]
        elif "localhost" in url_l or "127.0.0.1" in url_l:
            def_m = ["qwen2.5vl:7b", "qwen2.5vl:3b", "openbmb/minicpm-v4.6:latest"]
        else:
            def_m = [saved_model] if saved_model else []
        scored = []
        for mid in def_m:
            score, badge, display = evaluate_model_compatibility(mid)
            scored.append((score, display, mid))
        scored.sort(key=lambda x: -x[0])
        for _, display, mid in scored:
            self.model_input.addItem(display, mid)
        if saved_model:
            for i, (_, _, mid) in enumerate(scored):
                if mid == saved_model:
                    self.model_input.setCurrentIndex(i)
                    break
            else:
                if scored:
                    self.model_input.setCurrentIndex(0)
        elif scored:
            self.model_input.setCurrentIndex(0)
        self.model_input.blockSignals(False)
        self.update_model_description()

    def scan_free_models(self):
        if not HAS_REQUESTS:
            self.ai_status_label.setText("❌ Библиотека requests не найдена"); return
        self.scan_models_btn.setEnabled(False)
        self.ai_status_label.setText("⏳ Поиск..."); self.ai_status_label.setToolTip("")
        base_url = self.get_current_url()
        if not base_url:
            self.scan_models_btn.setEnabled(True)
            self.ai_status_label.setText("❌ Укажите URL сервера"); return
        api_key = self.api_key_input.text().strip()
        worker = ScanModelsWorker(base_url, api_key)
        worker.finished.connect(self._on_scan_models_finished)
        worker.error.connect(self._on_scan_models_error)
        self._workers.append(worker)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        worker.error.connect(lambda: self._cleanup_worker(worker))
        worker.start()

    def _on_scan_models_finished(self, models):
        self.scan_models_btn.setEnabled(True)
        if models:
            scored = []
            for item in models:
                mid = item["id"] if isinstance(item, dict) else item
                modalities = item.get("modalities") if isinstance(item, dict) else None
                is_vision = isinstance(modalities, list) and "image" in modalities
                score, badge, display = evaluate_model_compatibility(mid, is_vision)
                scored.append((score, badge, display, mid))
            scored.sort(key=lambda x: -x[0])

            self.model_input.blockSignals(True)
            self.model_input.clear()
            for score, badge, display, mid in scored:
                self.model_input.addItem(display, mid)
            self.model_input.setCurrentIndex(0)
            self.model_input.blockSignals(False)
            self.update_model_description()
            self.ai_status_label.setText(f"✅ Найдено моделей: {len(models)}")
        else:
            self.ai_status_label.setText("❌ Модели не найдены")

    def _on_scan_models_error(self, error_msg):
        self.scan_models_btn.setEnabled(True)
        if error_msg.startswith("http_"):
            code = error_msg.replace("http_", "")
            self.ai_status_label.setText(f"❌ Код {code}"); self.ai_status_label.setToolTip(self.get_error_help_html(code))
        else:
            self.ai_status_label.setText("❌ Ошибка"); self.ai_status_label.setToolTip(self.get_error_help_html(error_msg))

    def test_ai_connection(self):
        if not HAS_REQUESTS:
            self.ai_status_label.setText("❌ Библиотека requests не найдена"); return
        api_key = self.api_key_input.text().strip()
        base_url = self.get_current_url().rstrip('/')
        model = self.get_current_model()
        if not api_key and "localhost" not in base_url:
            self.ai_status_label.setText("❌ Нет ключа"); return
        self.test_ai_btn.setEnabled(False)
        self.ai_status_label.setText("⏳ Проверка..."); self.ai_status_label.setToolTip("")
        worker = TestModelWorker(base_url, api_key, model)
        worker.finished.connect(self._on_test_model_finished)
        worker.error.connect(self._on_test_model_error)
        self._workers.append(worker)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        worker.error.connect(lambda: self._cleanup_worker(worker))
        worker.start()

    def _on_test_model_finished(self, success):
        self.test_ai_btn.setEnabled(True)
        if success:
            self.ai_status_label.setText("✅ Успешно!")
        else:
            self.ai_status_label.setText("❌ Ошибка")

    def _on_test_model_error(self, error_msg):
        self.test_ai_btn.setEnabled(True)
        if error_msg.startswith("Код "):
            code = error_msg.split(":")[0].replace("Код ", "")
            self.ai_status_label.setText(f"❌ {error_msg[:80]}")
            self.ai_status_label.setToolTip(self.get_error_help_html(code))
        else:
            self.ai_status_label.setText(f"❌ {error_msg[:80]}")
            self.ai_status_label.setToolTip("")

    def set_hotkey(self, a):
        d = HotkeyCaptureDialog(self)
        if d.exec() == QDialog.DialogCode.Accepted:
            if a == "ocr": self.ocr_hotkey_input.setText(d.captured_hotkey)
            else: self.translate_hotkey_input.setText(d.captured_hotkey)

    def _on_engine_changed(self, index):
        code = self.engine_combo.itemData(index)
        self.deepl_widget.setVisible(code == "deepl")

    def _toggle_deepl_key(self):
        if self.deepl_api_input.echoMode() == QLineEdit.EchoMode.Password:
            self.deepl_api_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.deepl_key_btn.setText("Скрыть")
        else:
            self.deepl_api_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.deepl_key_btn.setText("Показать")

    def _check_google(self):
        if not HAS_REQUESTS:
            self.google_status_label.setText("❌ Библиотека requests не найдена"); return
        self.google_check_btn.setEnabled(False)
        self.google_status_label.setText("⏳ Проверка...")
        worker = CheckGoogleWorker()
        worker.finished.connect(self._on_check_google_finished)
        worker.error.connect(self._on_check_google_error)
        self._workers.append(worker)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        worker.error.connect(lambda: self._cleanup_worker(worker))
        worker.start()

    def _on_check_google_finished(self, success):
        self.google_check_btn.setEnabled(True)
        if success:
            self.google_status_label.setText("✅ Доступен")
        else:
            self.google_status_label.setText("❌ Ошибка")

    def _on_check_google_error(self, error_msg):
        self.google_check_btn.setEnabled(True)
        if error_msg.startswith("http_"):
            code = error_msg.replace("http_", "")
            self.google_status_label.setText(f"❌ Ошибка {code}")
        else:
            self.google_status_label.setText("❌ Недоступен")

    def _check_deepl(self):
        if not HAS_REQUESTS:
            self.deepl_status_label.setText("❌ Библиотека requests не найдена"); return
        key = self.deepl_api_input.text().strip()
        if not key:
            self.deepl_status_label.setText("❌ Введите API-ключ"); return
        self.deepl_check_btn.setEnabled(False)
        self.deepl_status_label.setText("⏳ Проверка...")
        worker = CheckDeepLWorker(key)
        worker.finished.connect(self._on_check_deepl_finished)
        worker.error.connect(self._on_check_deepl_error)
        self._workers.append(worker)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        worker.error.connect(lambda: self._cleanup_worker(worker))
        worker.start()

    def _on_check_deepl_finished(self, data):
        self.deepl_check_btn.setEnabled(True)
        limit = data.get("limit", 0)
        count = data.get("count", 0)
        self.deepl_status_label.setText(f"✅ Активен. Доступно: {limit - count} / {limit} символов")

    def _on_check_deepl_error(self, error_msg):
        self.deepl_check_btn.setEnabled(True)
        if error_msg == "403":
            self.deepl_status_label.setText("❌ Неверный API-ключ")
        elif error_msg.startswith("http_"):
            code = error_msg.replace("http_", "")
            self.deepl_status_label.setText(f"❌ Ошибка {code}")
        else:
            self.deepl_status_label.setText("❌ Ошибка соединения")

    def _cleanup_worker(self, worker):
        if worker in self._workers:
            self._workers.remove(worker)

    def choose_border_color(self):
        c = QColorDialog.getColor(); 
        if c.isValid(): self.border_color_btn.setStyleSheet(f"background-color: {c.name()}; border: 1px solid #555555;")
    def choose_bg_color(self):
        c = QColorDialog.getColor(); 
        if c.isValid(): self.bg_color_btn.setStyleSheet(f"background-color: {c.name()}; border: 1px solid #555555;")
    def choose_font_color(self):
        c = QColorDialog.getColor(); 
        if c.isValid(): self.font_color_btn.setStyleSheet(f"background-color: {c.name()}; border: 1px solid #555555;")

    def save_settings(self):
        ocr_hotkey = self.ocr_hotkey_input.text().strip().lower()
        translate_hotkey = self.translate_hotkey_input.text().strip().lower()
        
        if ocr_hotkey and translate_hotkey and ocr_hotkey == translate_hotkey:
            QMessageBox.warning(
                self, 
                "Ошибка валидации", 
                "Горячие клавиши для OCR и перевода совпадают!\n\n"
                f"Текущая комбинация: {ocr_hotkey}\n\n"
                "Пожалуйста, назначьте разные горячие клавиши для каждого действия.",
                QMessageBox.StandardButton.Ok
            )
            return
        
        self.set_windows_autostart(self.auto_start_check.isChecked())
        settings.set_hotkey("ocr", ocr_hotkey)
        settings.set_hotkey("translate", translate_hotkey)
        settings.set("llm.use_smart_translate", self.use_ai_check.isChecked())
        settings.set("llm.translate_with_standard_engine", self.translate_with_standard_check.isChecked())

        selected_url = self.get_current_url()
        selected_model = self.get_current_model()
        selected_key = self.api_key_input.text().strip()

        models = settings.get("llm.models_dict", {})
        keys = settings.get("llm.keys_dict", {})

        if selected_url:
            models[selected_url] = selected_model
            keys[selected_url] = selected_key

        settings.set("llm.base_url", selected_url)
        settings.set("llm.model", selected_model)
        settings.set("llm.api_key", selected_key)
        settings.set("llm.models_dict", models)
        settings.set("llm.keys_dict", keys)

        settings.set("languages.translator_engine", self.engine_combo.currentData())
        settings.set("languages.deepl_api_key", self.deepl_api_input.text().strip())
        settings.set_ocr_language(self.ocr_lang_combo.currentText())
        settings.set_translate_target_language(self.translate_lang_combo.currentText())
        settings.set("window_opacity", self.opacity_spin.value() / 100)
        settings.set("border_color", self.border_color_btn.styleSheet().split(": ")[1].split(";")[0])
        settings.set("bg_color", self.bg_color_btn.styleSheet().split(": ")[1].split(";")[0])
        settings.set("font_color", self.font_color_btn.styleSheet().split(": ")[1].split(";")[0])
        settings.set("font_size_p", self.fs_p_spin.value())
        settings.set("font_size_h2", self.fs_h2_spin.value())
        settings.set("font_size_h1", self.fs_h1_spin.value())
        settings.set_auto_start(self.auto_start_check.isChecked())
        settings.set("close_overlay_on_blur", self.close_on_blur_check.isChecked())
        settings.set("overlay_auto_close_sec", self.auto_close_spin.value())

        saved_ok = settings.save_settings()
        self.logger.info(f"СОХРАНЕНИЕ НАСТРОЕК (успех={saved_ok}): base_url={selected_url}, model={selected_model}")
        if saved_ok:
            self.settings_saved.emit()
            self.save_btn.setText("СОХРАНЕНО! ✅"); self.save_btn.setEnabled(False)
            QTimer.singleShot(1500, lambda: (self.save_btn.setText("Сохранить"), self.save_btn.setEnabled(True)))

    def set_windows_autostart(self, e):
        try:
            import winreg
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_WRITE)
            if e: 
                p = sys.executable if getattr(sys, 'frozen', False) else f'"{sys.executable}" "{os.path.abspath("run.py")}"'
                winreg.SetValueEx(k, "ScreenTextHelper", 0, winreg.REG_SZ, p)
            else:
                try: winreg.DeleteValue(k, "ScreenTextHelper")
                except: pass
            winreg.CloseKey(k)
        except: pass

    def run_on_demand_test(self): self.run_benchmark_requested.emit()
    def reset_settings(self):
        if QMessageBox.question(self, "Сброс", "Сбросить?") == QMessageBox.StandardButton.Yes:
            settings.reset_to_defaults(); self.accept()
    def set_benchmark_status(self, t): self.ai_status_label.setText(t)
    def set_benchmark_result(self, m, r): 
        self.model_input.setCurrentText(m); self.ai_status_label.setText(f"✅ {r:.1f}s")
