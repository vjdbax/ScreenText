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
    QSpinBox, QColorDialog, QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from settings import settings
try:
    import qtawesome as qta
except ImportError:
    qta = None
try:
    from ollama_installer import OllamaInstallerDialog
    HAS_OLLAMA_INSTALLER = True
except ImportError:
    OllamaInstallerDialog = None
    HAS_OLLAMA_INSTALLER = False

# Статус native библиотек (без загрузки — только find_spec)
OCR_AVAILABLE = importlib.util.find_spec("easyocr") is not None
CV2_AVAILABLE = importlib.util.find_spec("cv2") is not None

# Микроскопический JPEG для теста зрения ИИ
TINY_JPEG_B64 = "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="

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
        
        # Растянутый размер окна по вертикали
        self.setMinimumSize(520, 950)
        self.resize(540, 1120)
        
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
            QGroupBox { background-color: #1E1E1E; border: 1px solid #3C3C3C; border-radius: 6px; margin-top: 10px; padding-top: 12px; color: #FFFFFF; font-weight: bold; font-size: 11px; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 10px; padding: 0 5px; background-color: #1E1E1E; }
            QLabel { color: #CCCCCC; background: transparent; font-size: 11px; }
            QLineEdit, QSpinBox { background-color: #2D2D2D; color: #CCCCCC; border: 1px solid #3C3C3C; border-radius: 4px; padding: 4px; font-size: 11px; }
            QLineEdit:focus, QSpinBox:focus { border: 1px solid #007ACC; }
            QComboBox { background-color: #2D2D2D; color: #CCCCCC; border: 1px solid #3C3C3C; border-radius: 4px; padding: 4px; font-size: 11px; }
            QComboBox:focus { border: 1px solid #007ACC; }
            QComboBox QAbstractItemView { background-color: #252526; color: rgba(255, 255, 255, 0.8); border: 1px solid #3C3C3C; selection-background-color: #094771; selection-color: #FFFFFF; }
            QCheckBox { color: #CCCCCC; spacing: 6px; font-size: 11px; }
            QCheckBox::indicator { width: 14px; height: 14px; border: 1px solid #3C3C3C; border-radius: 3px; background-color: #2D2D2D; }
            QCheckBox::indicator:hover { border: 1px solid #007ACC; }
            QCheckBox::indicator:checked { background-color: #0E639C; border: 1px solid #0E639C; }
            QPushButton { background-color: #2D2D2D; color: #CCCCCC; border: 1px solid #3C3C3C; border-radius: 4px; padding: 5px 12px; font-size: 11px; font-weight: bold; }
            QPushButton:hover { background-color: #3C3C3C; color: #FFFFFF; border: 1px solid #454545; }
            QPushButton#save_btn { background-color: #0E639C; color: #FFFFFF; border: 1px solid #1177BB; }
            QPushButton#save_btn:hover { background-color: #1177BB; }
            QPushButton#test_btn { background-color: #2D2D2D; color: #007ACC; border: 1px solid #007ACC; }
            QPushButton#test_btn:hover { background-color: #007ACC; color: #FFFFFF; }
            QPushButton#bench_btn { background-color: #2D2D2D; color: #E5C07B; border: 1px solid #E5C07B; }
            QPushButton#bench_btn:hover { background-color: #E5C07B; color: #1E1E1E; }
            QMessageBox { background-color: #1E1E1E; color: #CCCCCC; border: 1px solid #3C3C3C; }
            QToolTip { background-color: #2D2D2D; color: #FFFFFF; border: 1px solid #555555; border-radius: 4px; padding: 10px; font-family: "Segoe UI"; font-size: 11px; }
        """)

    def get_current_url(self):
        data = self.base_url_input.currentData()
        return data if data else self.base_url_input.currentText().strip()

    def get_error_help_html(self, error_str):
        """Возвращает HTML-подсказку на основе кода ошибки"""
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
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # 1. Горячие клавиши
        hotkeys_group = QGroupBox("Горячие клавиши")
        hotkeys_layout = QVBoxLayout()
        hotkeys_layout.setContentsMargins(10, 15, 10, 10)
        hotkeys_layout.setSpacing(5)
        
        ocr_layout = QHBoxLayout()
        ocr_layout.addWidget(QLabel("OCR (Распознавание текста):"))
        self.ocr_hotkey_input = QLineEdit(settings.get_hotkey("ocr"))
        self.ocr_hotkey_input.setReadOnly(True)
        ocr_layout.addWidget(self.ocr_hotkey_input)
        self.ocr_hotkey_btn = QPushButton("Изменить")
        self.ocr_hotkey_btn.clicked.connect(lambda: self.set_hotkey("ocr"))
        ocr_layout.addWidget(self.ocr_hotkey_btn)
        hotkeys_layout.addLayout(ocr_layout)
        
        translate_layout = QHBoxLayout()
        translate_layout.addWidget(QLabel("Перевод текста:"))
        self.translate_hotkey_input = QLineEdit(settings.get_hotkey("translate"))
        self.translate_hotkey_input.setReadOnly(True)
        translate_layout.addWidget(self.translate_hotkey_input)
        self.translate_hotkey_btn = QPushButton("Изменить")
        self.translate_hotkey_btn.clicked.connect(lambda: self.set_hotkey("translate"))
        translate_layout.addWidget(self.translate_hotkey_btn)
        hotkeys_layout.addLayout(translate_layout)
        hotkeys_group.setLayout(hotkeys_layout)
        layout.addWidget(hotkeys_group)

        # 2. ИИ (LLM Vision)
        ai_group = QGroupBox("Умный перевод (ИИ Vision)")
        ai_layout = QVBoxLayout()
        ai_layout.setContentsMargins(10, 15, 10, 10)
        ai_layout.setSpacing(5)
        
        self.use_ai_check = QCheckBox("Использовать Vision-to-Text (ИИ)")
        self.use_ai_check.setChecked(settings.get("llm.use_smart_translate", False))
        ai_layout.addWidget(self.use_ai_check)
        
        self.translate_with_standard_check = QCheckBox("Переводить ИИ-текст стандартным движком")
        self.translate_with_standard_check.setChecked(settings.get("llm.translate_with_standard_engine", False))
        ai_layout.addWidget(self.translate_with_standard_check)
        
        ai_layout.addWidget(QLabel("Сервис ИИ (провайдер):"))
        self.base_url_input = QComboBox()
        self.base_url_input.setEditable(True)
        
        ai_providers = [
            ("Локальная ИИ (Ollama)", "http://localhost:11434/v1"),
            ("DeepSeek API", "https://api.deepseek.com"),
            ("OpenRouter (Бесплатные модели)", "https://openrouter.ai/api/v1"),
            ("OpenAI (ChatGPT)", "https://api.openai.com/v1")
        ]
        for name, url in ai_providers:
            self.base_url_input.addItem(name, url)

        self.base_url_input.currentTextChanged.connect(self.on_base_url_changed)
        saved_url = settings.get("llm.base_url", "https://api.openai.com/v1")
        idx = self.base_url_input.findData(saved_url)
        if idx != -1: self.base_url_input.setCurrentIndex(idx)
        else: self.base_url_input.setEditText(saved_url)
        ai_layout.addWidget(self.base_url_input)
        
        ai_layout.addWidget(QLabel("API Ключ:"))
        key_control_layout = QHBoxLayout()
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.textChanged.connect(self.on_api_key_changed)
        self.show_key_btn = QPushButton("Показать"); self.show_key_btn.setFixedWidth(90)
        self.show_key_btn.clicked.connect(self.toggle_api_key_visibility)
        key_control_layout.addWidget(self.api_key_input); key_control_layout.addWidget(self.show_key_btn)
        ai_layout.addLayout(key_control_layout)
        
        ai_layout.addWidget(QLabel("Модель:"))
        model_layout = QHBoxLayout()
        self.model_input = QComboBox(); self.model_input.setEditable(True)
        self.model_input.currentTextChanged.connect(self.on_model_changed)
        model_layout.addWidget(self.model_input)
        self.scan_models_btn = QPushButton("Сканировать")
        self.scan_models_btn.setStyleSheet("color: #007ACC; border: 1px solid #007ACC;")
        self.scan_models_btn.clicked.connect(self.scan_free_models)
        model_layout.addWidget(self.scan_models_btn)
        ai_layout.addLayout(model_layout)
        
        test_layout = QHBoxLayout()
        self.test_ai_btn = QPushButton("Проверить модель"); self.test_ai_btn.setObjectName("test_btn")
        self.test_ai_btn.clicked.connect(self.test_ai_connection)
        self.run_benchmark_btn = QPushButton("Авто-подбор"); self.run_benchmark_btn.setObjectName("bench_btn")
        self.run_benchmark_btn.clicked.connect(self.run_on_demand_test)
        self.ai_status_label = QLabel("")
        test_layout.addWidget(self.test_ai_btn); test_layout.addWidget(self.run_benchmark_btn); test_layout.addWidget(self.ai_status_label); test_layout.addStretch()
        ai_layout.addLayout(test_layout)
        
        if HAS_OLLAMA_INSTALLER:
            self.install_local_ai_btn = QPushButton("Установить локальный ИИ (Ollama) на ПК")
            self.install_local_ai_btn.setStyleSheet("color: #4CAF50; border: 1px solid #4CAF50; padding: 6px; font-weight: bold;")
            self.install_local_ai_btn.clicked.connect(self.launch_ollama_installer)
            ai_layout.addWidget(self.install_local_ai_btn)
        
        ai_group.setLayout(ai_layout)
        layout.addWidget(ai_group)
        
        # 3. Языки
        languages_group = QGroupBox("Языки")
        languages_layout = QVBoxLayout(); languages_layout.setContentsMargins(10, 15, 10, 10)
        self.engine_combo = QComboBox()
        self.engine_combo.addItem("Google Translate (онлайн)", "google")
        self.engine_combo.addItem("DeepL (API онлайн)", "deepl")
        self.engine_combo.addItem("Argos Translate (офлайн)", "argos")
        eng_set = settings.get("languages.translator_engine", "google")
        idx_map = {"google": 0, "deepl": 1, "argos": 2}
        self.engine_combo.setCurrentIndex(idx_map.get(eng_set, 0))
        self.engine_combo.currentIndexChanged.connect(self._on_engine_changed)
        
        self.ocr_lang_combo = QComboBox(); self.ocr_lang_combo.addItems(["rus", "eng", "rus+eng"])
        self.ocr_lang_combo.setCurrentText(settings.get_ocr_language())
        
        self.translate_lang_combo = QComboBox(); self.translate_lang_combo.addItems(["en", "ru", "be-latn", "zh", "es", "fr", "de"])
        self.translate_lang_combo.setCurrentText(settings.get_translate_target_language())
        
        languages_layout.addWidget(QLabel("Движок стандартного перевода:"))
        languages_layout.addWidget(self.engine_combo)

        # Google status check
        google_row = QHBoxLayout()
        self.google_check_btn = QPushButton("Проверить Google")
        self.google_check_btn.setStyleSheet("color: #4CAF50; border: 1px solid #4CAF50; padding: 3px;")
        self.google_check_btn.clicked.connect(self._check_google)
        self.google_status_label = QLabel("")
        self.google_status_label.setStyleSheet("color: #888; font-size: 9px;")
        google_row.addWidget(self.google_check_btn)
        google_row.addWidget(self.google_status_label)
        google_row.addStretch()
        languages_layout.addLayout(google_row)

        # DeepL settings container
        self.deepl_widget = QWidget()
        deepl_layout = QVBoxLayout(self.deepl_widget)
        deepl_layout.setContentsMargins(0, 5, 0, 5)
        deepl_api_row = QHBoxLayout()
        self.deepl_api_input = QLineEdit()
        self.deepl_api_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.deepl_api_input.setPlaceholderText("Введите DeepL API-ключ...")
        self.deepl_api_input.setText(settings.get("languages.deepl_api_key", ""))
        deepl_api_row.addWidget(self.deepl_api_input)
        self.deepl_key_btn = QPushButton("Показать")
        self.deepl_key_btn.setFixedWidth(80)
        self.deepl_key_btn.clicked.connect(lambda: self._toggle_deepl_key())
        deepl_api_row.addWidget(self.deepl_key_btn)
        deepl_layout.addLayout(deepl_api_row)
        deepl_check_row = QHBoxLayout()
        self.deepl_check_btn = QPushButton("Проверить статус и лимит")
        self.deepl_check_btn.setStyleSheet("color: #4CAF50; border: 1px solid #4CAF50; padding: 3px;")
        self.deepl_check_btn.clicked.connect(self._check_deepl)
        self.deepl_status_label = QLabel("")
        self.deepl_status_label.setStyleSheet("color: #888; font-size: 9px;")
        deepl_check_row.addWidget(self.deepl_check_btn)
        deepl_check_row.addWidget(self.deepl_status_label)
        deepl_check_row.addStretch()
        deepl_layout.addLayout(deepl_check_row)
        languages_layout.addWidget(self.deepl_widget)

        languages_layout.addWidget(QLabel("Язык распознавания (OCR):"))
        languages_layout.addWidget(self.ocr_lang_combo)
        languages_layout.addWidget(QLabel("Целевой язык перевода:"))
        languages_layout.addWidget(self.translate_lang_combo)

        # Статус библиотек
        libs_row = QHBoxLayout()
        libs_style = "color: #888888; font-size: 9px; font-family: Consolas, monospace;"
        for name, ok in [("EasyOCR", OCR_AVAILABLE), ("OpenCV", CV2_AVAILABLE), ("Requests", HAS_REQUESTS), ("Ollama", HAS_OLLAMA_INSTALLER), ("QAwesome", qta is not None)]:
            lbl = QLabel(f"{name}: {'✅' if ok else '❌'}")
            lbl.setStyleSheet(libs_style)
            libs_row.addWidget(lbl)
        libs_row.addStretch()
        languages_layout.addLayout(libs_row)

        self.retry_ocr_btn = QPushButton("Перезагрузить OCR (EasyOCR)")
        self.retry_ocr_btn.setStyleSheet("color: #E5C07B; border: 1px solid #E5C07B; padding: 4px;")
        self.retry_ocr_btn.clicked.connect(self.ocr_reload_requested.emit)
        languages_layout.addWidget(self.retry_ocr_btn)
        languages_group.setLayout(languages_layout)
        layout.addWidget(languages_group)

        self._on_engine_changed(self.engine_combo.currentIndex())
        
        # 4. Внешний вид
        appearance_group = QGroupBox("Внешний вид и текст")
        appearance_layout = QVBoxLayout(); appearance_layout.setContentsMargins(10, 15, 10, 10)
        self.opacity_spin = QSpinBox(); self.opacity_spin.setRange(10, 100); self.opacity_spin.setValue(int(settings.get("window_opacity", 0.95) * 100)); self.opacity_spin.setSuffix("%")
        self.border_color_btn = QPushButton(); self.border_color_btn.setFixedSize(50, 22); self.border_color_btn.setStyleSheet(f"background-color: {settings.get('border_color', '#555555')}"); self.border_color_btn.clicked.connect(self.choose_border_color)
        self.bg_color_btn = QPushButton(); self.bg_color_btn.setFixedSize(50, 22); self.bg_color_btn.setStyleSheet(f"background-color: {settings.get('bg_color', '#FFFFFF')}"); self.bg_color_btn.clicked.connect(self.choose_bg_color)
        self.font_color_btn = QPushButton(); self.font_color_btn.setFixedSize(50, 22); self.font_color_btn.setStyleSheet(f"background-color: {settings.get('font_color', '#000000')}"); self.font_color_btn.clicked.connect(self.choose_font_color)
        
        appearance_layout.addLayout(self._create_row("Плотность окна (непрозрачность):", self.opacity_spin))
        appearance_layout.addLayout(self._create_row("Цвет внешней рамки:", self.border_color_btn))
        appearance_layout.addLayout(self._create_row("Цвет фона подложки:", self.bg_color_btn))
        appearance_layout.addLayout(self._create_row("Цвет шрифта текста:", self.font_color_btn))

        self.fs_p_spin = QSpinBox(); self.fs_p_spin.setRange(6, 24); self.fs_p_spin.setValue(settings.get("font_size_p", 10))
        self.fs_h2_spin = QSpinBox(); self.fs_h2_spin.setRange(8, 28); self.fs_h2_spin.setValue(settings.get("font_size_h2", 12))
        self.fs_h1_spin = QSpinBox(); self.fs_h1_spin.setRange(10, 36); self.fs_h1_spin.setValue(settings.get("font_size_h1", 14))
        
        appearance_layout.addLayout(self._create_row("Размер текста (обычный):", self.fs_p_spin))
        appearance_layout.addLayout(self._create_row("Размер Заголовка 2:", self.fs_h2_spin))
        appearance_layout.addLayout(self._create_row("Размер Заголовка 1:", self.fs_h1_spin))
        appearance_group.setLayout(appearance_layout); layout.addWidget(appearance_group)
        
        # 5. Поведение
        behavior_group = QGroupBox("Поведение")
        behavior_layout = QVBoxLayout()
        self.auto_start_check = QCheckBox("Автозагрузка при старте Windows")
        self.auto_start_check.setChecked(settings.get_auto_start())
        behavior_layout.addWidget(self.auto_start_check)
        behavior_group.setLayout(behavior_layout); layout.addWidget(behavior_group)
        
        # Кнопки
        btns_layout = QHBoxLayout()
        self.save_btn = QPushButton("Сохранить"); self.save_btn.setObjectName("save_btn"); self.save_btn.clicked.connect(self.save_settings)
        self.cancel_btn = QPushButton("Отмена"); self.cancel_btn.clicked.connect(self.reject)
        self.reset_btn = QPushButton("Сбросить"); self.reset_btn.clicked.connect(self.reset_settings)
        btns_layout.addWidget(self.save_btn); btns_layout.addWidget(self.reset_btn); btns_layout.addWidget(self.cancel_btn)
        layout.addLayout(btns_layout)
        
        self.setLayout(layout)
        self.on_base_url_changed(self.base_url_input.currentText())

    def _create_row(self, label_text, widget):
        row = QHBoxLayout(); row.addWidget(QLabel(label_text)); row.addWidget(widget); return row

    # --- ЛОГИКА ---

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

    def on_api_key_changed(self, text):
        url = self.get_current_url()
        if url:
            keys = settings.get("llm.keys_dict", {}); keys[url] = text.strip(); settings.set("llm.keys_dict", keys)

    def on_model_changed(self, text):
        url = self.get_current_url()
        if url and text:
            models = settings.get("llm.models_dict", {}); models[url] = text.strip(); settings.set("llm.models_dict", models)

    def on_base_url_changed(self, text):
        if not hasattr(self, 'api_key_input'):
            return
        url = self.get_current_url()
        keys = settings.get("llm.keys_dict", {})
        self.api_key_input.blockSignals(True); self.api_key_input.setText(keys.get(url, "")); self.api_key_input.blockSignals(False)
        models = settings.get("llm.models_dict", {}); saved_model = models.get(url, "")
        self.model_input.blockSignals(True); self.model_input.clear()
        url_l = url.lower()
        if "openrouter" in url_l: def_m = ["openrouter/free", "google/gemini-1.5-flash:free", "qwen/qwen-2-vl-7b-instruct:free"]
        elif "openai" in url_l: def_m = ["gpt-4o-mini", "gpt-4o"]
        elif "deepseek" in url_l: def_m = ["deepseek-chat"]
        elif "localhost" in url_l or "127.0.0.1" in url_l: def_m = ["qwen2.5vl:3b", "qwen2.5vl:7b", "openbmb/minicpm-v4.6:latest", "llava"]
        else: def_m = ["gpt-4o-mini"]
        if saved_model and saved_model not in def_m: def_m.insert(0, saved_model)
        self.model_input.addItems(def_m); self.model_input.setCurrentText(saved_model if saved_model else def_m[0]); self.model_input.blockSignals(False)

    def scan_free_models(self):
        if not HAS_REQUESTS:
            self.ai_status_label.setText("❌ Библиотека requests не найдена"); return
        self.ai_status_label.setText("⏳ Поиск..."); self.ai_status_label.setToolTip(""); QApplication.processEvents()
        base_url = self.get_current_url().rstrip('/')
        api_key = self.api_key_input.text().strip()
        try:
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            response = requests.get(f"{base_url}/models", headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json().get("data", [])
                models = [m.get("id") for m in data if m.get("id")]
                if "openrouter" in base_url.lower():
                    models = [m.get("id") for m in data if m.get("pricing", {}).get("prompt") == "0"]
                if models:
                    self.model_input.clear(); self.model_input.addItems(models); self.ai_status_label.setText(f"✅ Найдено: {len(models)}")
                else: self.ai_status_label.setText("❌ Модели не найдены")
            else:
                self.ai_status_label.setText(f"❌ Код {response.status_code}"); self.ai_status_label.setToolTip(self.get_error_help_html(str(response.status_code)))
        except Exception as e:
            self.ai_status_label.setText("❌ Ошибка"); self.ai_status_label.setToolTip(self.get_error_help_html(str(e)))

    def test_ai_connection(self):
        if not HAS_REQUESTS:
            self.ai_status_label.setText("❌ Библиотека requests не найдена"); return
        api_key = self.api_key_input.text().strip()
        base_url = self.get_current_url().rstrip('/')
        model = self.model_input.currentText().strip()
        if not api_key and "localhost" not in base_url:
            self.ai_status_label.setText("❌ Нет ключа"); return
        self.ai_status_label.setText("⏳ Проверка..."); self.ai_status_label.setToolTip(""); QApplication.processEvents()
        headers = {"Content-Type": "application/json"}
        if api_key: headers["Authorization"] = f"Bearer {api_key}"
        payload = {"model": model, "messages": [{"role": "user", "content": [{"type": "text", "text": "ping"}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{TINY_JPEG_B64}"}}]}], "max_tokens": 1}
        try:
            r = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=15)
            if r.status_code == 200: self.ai_status_label.setText("✅ Успешно!")
            else:
                self.ai_status_label.setText(f"❌ Код {r.status_code}"); self.ai_status_label.setToolTip(self.get_error_help_html(str(r.status_code)))
        except Exception as e:
            self.ai_status_label.setText("❌ Ошибка"); self.ai_status_label.setToolTip(self.get_error_help_html(str(e)))

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
        self.google_status_label.setText("⏳ Проверка...")
        QApplication.processEvents()
        try:
            r = requests.get("https://translate.google.com", timeout=8)
            if r.status_code == 200:
                self.google_status_label.setText("✅ Доступен")
            else:
                self.google_status_label.setText(f"❌ Ошибка {r.status_code}")
        except Exception as e:
            self.google_status_label.setText("❌ Недоступен")

    def _check_deepl(self):
        if not HAS_REQUESTS:
            self.deepl_status_label.setText("❌ Библиотека requests не найдена"); return
        key = self.deepl_api_input.text().strip()
        if not key:
            self.deepl_status_label.setText("❌ Введите API-ключ"); return
        self.deepl_status_label.setText("⏳ Проверка...")
        QApplication.processEvents()
        try:
            base = "https://api-free.deepl.com/v2/usage" if key.endswith(":fx") else "https://api.deepl.com/v2/usage"
            headers = {"Authorization": f"DeepL-Auth-Key {key}"}
            r = requests.get(base, headers=headers, timeout=10)
            if r.status_code == 200:
                d = r.json()
                limit = d.get("character_limit", 0)
                count = d.get("character_count", 0)
                self.deepl_status_label.setText(f"✅ Активен. Доступно: {limit - count} / {limit} символов")
            elif r.status_code == 403:
                self.deepl_status_label.setText("❌ Неверный API-ключ")
            else:
                self.deepl_status_label.setText(f"❌ Ошибка {r.status_code}")
        except Exception:
            self.deepl_status_label.setText("❌ Ошибка соединения")

    def choose_border_color(self):
        c = QColorDialog.getColor(); 
        if c.isValid(): self.border_color_btn.setStyleSheet(f"background-color: {c.name()}")
    def choose_bg_color(self):
        c = QColorDialog.getColor(); 
        if c.isValid(): self.bg_color_btn.setStyleSheet(f"background-color: {c.name()}")
    def choose_font_color(self):
        c = QColorDialog.getColor(); 
        if c.isValid(): self.font_color_btn.setStyleSheet(f"background-color: {c.name()}")

    def save_settings(self):
        self.set_windows_autostart(self.auto_start_check.isChecked())
        settings.set_hotkey("ocr", self.ocr_hotkey_input.text().strip().lower())
        settings.set_hotkey("translate", self.translate_hotkey_input.text().strip().lower())
        settings.set("llm.use_smart_translate", self.use_ai_check.isChecked())
        settings.set("llm.translate_with_standard_engine", self.translate_with_standard_check.isChecked())
        settings.set("llm.base_url", self.get_current_url())
        settings.set("llm.api_key", self.api_key_input.text().strip())
        settings.set("llm.model", self.model_input.currentText().strip())
        settings.set("languages.translator_engine", self.engine_combo.currentData())
        settings.set("languages.deepl_api_key", self.deepl_api_input.text().strip())
        settings.set_ocr_language(self.ocr_lang_combo.currentText())
        settings.set_translate_target_language(self.translate_lang_combo.currentText())
        settings.set("window_opacity", self.opacity_spin.value() / 100)
        settings.set("border_color", self.border_color_btn.styleSheet().split(": ")[1])
        settings.set("bg_color", self.bg_color_btn.styleSheet().split(": ")[1])
        settings.set("font_color", self.font_color_btn.styleSheet().split(": ")[1])
        settings.set("font_size_p", self.fs_p_spin.value())
        settings.set("font_size_h2", self.fs_h2_spin.value())
        settings.set("font_size_h1", self.fs_h1_spin.value())
        settings.set_auto_start(self.auto_start_check.isChecked())
        if settings.save_settings():
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