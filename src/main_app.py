#!/usr/bin/env python3
import sys
import os
import logging
import time
import pyperclip
import pyautogui
import keyboard
import threading
import concurrent.futures
import requests
import re

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal, QPoint, QTimer, Qt
from PyQt6.QtGui import QCursor, QIcon

from tray_icon import TrayIcon
from settings_window import SettingsWindow
from hotkey_manager import HotkeyManager as hotkey_manager
from ocr_manager import OCRManager
from translator import TranslatorManager
from screen_capture import ScreenCapture
from overlay_window import TranslationOverlay as OverlayTranslationWindow, StartupLoaderWidget
from area_selector import AreaSelector
from settings import settings
from ai_translator import SmartTranslator
from text_formatter import TextFormatter, create_formatter_from_settings
from translation_worker import TranslationPipelineWorker
from constants import (
    APP_NAME, OPENROUTER_MODELS_URL, OLLAMA_MODELS_URL,
    OCR_INITIALIZATION_DELAY_SEC,
    ERROR_API_KEY_MISSING, ERROR_MODEL_NO_IMAGE_SUPPORT, ERROR_TRANSLATION_FAILED,
    ERROR_TEXT_NOT_SELECTED, ERROR_NETWORK, ERROR_API,
    SUCCESS_TRANSLATION_RECEIVED, STATUS_AI_PROCESSING, STATUS_STANDARD_TRANSLATION,
    STATUS_GOOGLE_UNAVAILABLE, STATUS_COPYING_TEXT, STATUS_TRANSLATING_TEXT
)
from utils import get_data_dir

try:
    from ollama_installer import OllamaUpdateCheckerWorker
    HAS_OLLAMA_CHECKER = True
except ImportError:
    OllamaUpdateCheckerWorker = None
    HAS_OLLAMA_CHECKER = False

# Мини-картинка для проверки Vision
TINY_JPEG_B64 = "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="

class ScreenTextHelper(QObject):
    ocr_triggered = pyqtSignal()      
    translate_triggered = pyqtSignal() 
    ai_model_testing_signal = pyqtSignal(str)
    ai_benchmark_finished = pyqtSignal(str, float)
    
    def __init__(self):
        super().__init__()
        self.app = None
        self.tray_icon = None
        self.settings_window = None
        self.hotkey_manager = hotkey_manager()
        self.ocr_manager = OCRManager()
        self.translator_manager = TranslatorManager()
        self.screen_capture = ScreenCapture()
        self.text_formatter = create_formatter_from_settings()
        self.area_selector = AreaSelector()
        
        self.translation_window = None
        self.startup_loader = None
        self.old_text_clipboard = ""
        self.last_translated_text = ""  
        self.is_running = False
        self.benchmark_mode = "startup"
        self._current_pipeline_worker = None  # Ссылка на текущий воркер перевода
        self._is_worker_busy = False  # Флаг занятости воркера
        self.setup_logging()
        
    def setup_logging(self):
        try:
            app_dir = get_data_dir()
            log_file_path = os.path.join(app_dir, 'screentext_helper.log')
            
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.FileHandler(log_file_path, encoding='utf-8'),
                    logging.StreamHandler()
                ]
            )
            self.logger = logging.getLogger(__name__)
        except Exception as e:
            print(f"Критическая ошибка: {e}")
        
    def initialize_application(self):
        try:
            self.logger.info("Инициализация ScreenText Helper")
            self.app = QApplication.instance() or QApplication(sys.argv)
            self.app.setQuitOnLastWindowClosed(False)
            
            if os.name == 'nt':
                try:
                    import ctypes
                    myappid = 'screentext.helper.version.1.0'
                    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
                except: pass

            self.startup_loader = StartupLoaderWidget()
            self.startup_loader.show()
            
            self.tray_icon = TrayIcon(self.app)
            self.tray_icon.show()
            
            self.setup_signal_handlers()
            self.register_hotkeys()
            
            # Отложенный запуск OCR (ждём 3с, чтобы Qt полностью загрузился без DLL-конфликтов)
            self.ocr_manager.start_initialization(delay_sec=OCR_INITIALIZATION_DELAY_SEC)

            self._ollama_check_worker = None
            if HAS_OLLAMA_CHECKER:
                QTimer.singleShot(5000, self._start_ollama_background_check)

            self.logger.info("Приложение успешно инициализировано")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка инициализации: {e}")
            return False
            
    def setup_signal_handlers(self):
        self.tray_icon.show_settings.connect(self.show_settings)
        self.tray_icon.show_about.connect(self.show_about)
        self.tray_icon.quit_application.connect(self.quit_application)
        
        # Area selector signals
        self.area_selector.area_captured.connect(self._on_area_captured)
        self.area_selector.area_selection_canceled.connect(self._on_area_selection_canceled)
        
        def on_ready_event():
            self.startup_loader.set_loaded()
            print("\n" + "="*50)
            print(" [SUCCESS] ScreenText Helper загружен и готов!")
            print(" Используйте горячие клавиши для перевода.")
            print("="*50 + "\n")
            
        self.ocr_manager.ocr_ready.connect(on_ready_event)
        self.ai_model_testing_signal.connect(self.on_ai_model_testing)
        self.ai_benchmark_finished.connect(self.on_ai_benchmark_completed)
        self.ocr_triggered.connect(self.handle_ocr_hotkey)
        self.translate_triggered.connect(self.handle_translate_selected_text)
            
    def release_all_modifiers(self):
        try:
            pyautogui.keyUp('ctrl'); pyautogui.keyUp('shift'); pyautogui.keyUp('win'); pyautogui.keyUp('alt')
            time.sleep(0.05)
        except: pass

    def _start_ollama_background_check(self):
        if self._ollama_check_worker and self._ollama_check_worker.isRunning():
            return
        self._ollama_check_worker = OllamaUpdateCheckerWorker()
        self._ollama_check_worker.update_available.connect(self._on_ollama_update_available)
        self._ollama_check_worker.start()

    def _on_ollama_update_available(self, current, latest):
        try:
            if self.startup_loader:
                self.startup_loader.show_update_message(
                    current, latest,
                    on_click_callback=self.show_settings
                )
        except Exception:
            pass

    def run_ai_benchmark(self):
        api_key = settings.get("llm.api_key")
        base_url = settings.get("llm.base_url").rstrip('/')
        is_local = "localhost" in base_url.lower() or "127.0.0.1" in base_url.lower()
        if not api_key and not is_local:
            self.ai_benchmark_finished.emit("Skipped", 0.0)
            return
            
        try:
            self.ai_model_testing_signal.emit("__SCANNING__")
            candidates = []
            if "openrouter" in base_url.lower():
                response = requests.get(OPENROUTER_MODELS_URL, timeout=6)
                if response.status_code == 200:
                    data = response.json().get("data", [])
                    for model in data:
                        model_id = model.get("id", "")
                        pricing = model.get("pricing", {})
                        is_free = model_id.endswith(":free") or (pricing.get("prompt") == "0" and pricing.get("completion") == "0")
                        arch = model.get("architecture", {})
                        is_vision = "image" in arch.get("input_modalities", []) or "vision" in model_id.lower() or "vl" in model_id.lower()
                        if is_free and is_vision and model_id != "openrouter/free":
                            candidates.append(model_id)
            else:
                headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
                response = requests.get(f"{base_url}/models", headers=headers, timeout=6)
                if response.status_code == 200:
                    data = response.json().get("data", [])
                    models = [m.get("id") for m in data if m.get("id")]
                    if "openai" in base_url.lower():
                        candidates = [m for m in models if "gpt-4" in m.lower() or "vision" in m.lower()]
                    else: candidates = models
            
            candidates = sorted(candidates, key=lambda x: ("gemini" in x or "qwen" in x or "gpt-4o" in x), reverse=True)[:6]
            if not candidates:
                current_model = settings.get("llm.model", "gpt-4o-mini")
                candidates = [current_model]
                
            best_model, best_rtt = None, float('inf')
            for m_id in candidates:
                self.ai_model_testing_signal.emit(m_id)
                time.sleep(0.1)
                _, rtt = self.ping_model(m_id, api_key, base_url)
                if rtt < best_rtt: best_rtt = rtt; best_model = m_id
                            
            if best_rtt == float('inf') or best_model is None: self.ai_benchmark_finished.emit("Failed", 999.0)
            else: self.ai_benchmark_finished.emit(best_model, best_rtt)
        except: self.ai_benchmark_finished.emit("Failed", 999.0)

    def ping_model(self, model_id, api_key, base_url):
        self.ai_model_testing_signal.emit(model_id)
        headers = {"Content-Type": "application/json"}
        if api_key: headers["Authorization"] = f"Bearer {api_key}"
        is_local = "localhost" in base_url or "127.0.0.1" in base_url
        img_payload = f"data:image/jpeg;base64,{TINY_JPEG_B64}" if is_local else {"url": f"data:image/jpeg;base64,{TINY_JPEG_B64}"}
        payload = {"model": model_id, "messages": [{"role": "user", "content": [{"type": "text", "text": "ping"}, {"type": "image_url", "image_url": img_payload}]}], "max_tokens": 1}
        start = time.time()
        try:
            r = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=2.0)
            if r.status_code == 200: return model_id, time.time() - start
        except: pass
        return model_id, float('inf')

    def on_ai_model_testing(self, model_id):
        if model_id == "__SCANNING__": text = "ИИ: Сканирование базового URL..."
        else: text = f"Тест ИИ: {model_id.split('/')[-1]}..."
        if self.benchmark_mode == "startup" and self.startup_loader:
            self.startup_loader.status_label.setText(text)
            self.startup_loader.status_label.setStyleSheet(f"color: #BBBBBB; font-size: {'8' if len(text)>35 else '9' if len(text)>25 else '11'}px;")
        elif self.benchmark_mode == "settings" and self.settings_window:
            self.settings_window.set_benchmark_status(f"⏳ {text}")

    def on_ai_benchmark_completed(self, best_model, rtt):
        if best_model == "Skipped": return
        if self.benchmark_mode == "startup":
            if best_model == "Failed" or (best_model == "openrouter/free" and rtt == 999.0):
                self.startup_loader.set_loaded("ИИ: Превышен лимит или нет сети ❌")
            else:
                settings.set("llm.model", best_model); settings.save_settings()
                self.startup_loader.set_loaded(f"ИИ готов! Модель: {best_model.split('/')[-1]} ({rtt:.1f}s) 🚀")
        elif self.benchmark_mode == "settings" and self.settings_window:
            if best_model != "Failed": settings.set("llm.model", best_model); settings.save_settings()
            self.settings_window.set_benchmark_result(best_model, rtt)

    def run_on_demand_benchmark(self):
        self.benchmark_mode = "settings"
        threading.Thread(target=self.run_ai_benchmark, daemon=True).start()

    def register_hotkeys(self):
        try:
            self.hotkey_manager.unregister_all_hotkeys()
            self.hotkey_manager.register_system_hotkeys(lambda: self.ocr_triggered.emit(), lambda: self.translate_triggered.emit())
        except: pass
    
    def handle_ocr_hotkey(self):
        """Handle OCR hotkey - show area selector"""
        # Защита от повторного вызова
        if self._is_worker_busy:
            self.logger.info("Игнорируем Ctrl+End: воркер занят")
            return
        if self.area_selector.isVisible():
            self.logger.info("Игнорируем Ctrl+End: селектор уже открыт")
            return
        
        self.release_all_modifiers()
        self.old_text_clipboard = pyperclip.paste().strip()
        
        # Show area selector
        if not self.area_selector.start_capture():
            self.startup_loader.set_loaded("Ошибка запуска селектора области")
    
    def _on_area_captured(self, file_path, screen_pos, physical_size):
        """
        Handle successful area capture from AreaSelector.
        
        Args:
            file_path: Path to cropped screenshot
            screen_pos: QPoint with logical screen position
            physical_size: tuple (width, height) in physical pixels
        """
        # Verify the crop file exists before starting the worker
        if not os.path.exists(file_path):
            self.logger.error(
                f"Файл скриншота не найден при запуске воркера: {file_path}"
            )
            self.startup_loader.set_loaded("Ошибка: файл скриншота не найден ❌")
            return

        self.logger.info(
            f"Запуск воркера: файл={file_path}, "
            f"позиция=({screen_pos.x()}, {screen_pos.y()}), "
            f"размер={physical_size[0]}x{physical_size[1]}"
        )
        self.startup_loader.set_text(APP_NAME, STATUS_AI_PROCESSING)
        
        # Start pipeline worker with captured area
        self._start_pipeline_worker(
            mode=TranslationPipelineWorker.MODE_SCREENSHOT,
            screenshot_path=file_path,
            screenshot_size=physical_size
        )
    
    def _on_area_selection_canceled(self):
        """Handle area selection cancellation"""
        pass  # No action needed - selector handles its own cleanup

    def handle_translate_selected_text(self):
        # Защита от повторного вызова
        if self._is_worker_busy:
            self.logger.info("Игнорируем Ctrl+Home: воркер занят")
            return
        
        self.release_all_modifiers()
        self.startup_loader.set_text(APP_NAME, STATUS_COPYING_TEXT)
        QApplication.processEvents()
        pre_existing = pyperclip.paste().strip()
        temp_m = "---SCREENTEXT_TEMP_MARKER---"
        pyperclip.copy(temp_m); time.sleep(0.25)
        try:
            pyautogui.hotkey('ctrl', 'c')
        except: pass
        time.sleep(0.15)
        sel = pyperclip.paste().strip()
        if sel == temp_m or not sel: 
            pyautogui.hotkey('ctrl', 'c'); time.sleep(0.15); sel = pyperclip.paste().strip()
        if (sel == temp_m or not sel) and pre_existing and pre_existing != temp_m: sel = pre_existing
        if not sel or sel == temp_m:
            self.startup_loader.set_loaded(ERROR_TEXT_NOT_SELECTED); return
        
        # Создаем и запускаем воркер для перевода текста
        self._start_pipeline_worker(
            mode=TranslationPipelineWorker.MODE_TEXT,
            selected_text=sel
        )
    
    def _start_pipeline_worker(self, mode, screenshot_path=None, screenshot_size=None, selected_text=None):
        """
        Запуск фонового воркера для обработки перевода.
        
        Args:
            mode: Режим работы (MODE_SCREENSHOT или MODE_TEXT)
            screenshot_path: Путь к файлу скриншота (для MODE_SCREENSHOT)
            screenshot_size: Размер скриншота (для MODE_SCREENSHOT)
            selected_text: Выделенный текст (для MODE_TEXT)
        """
        # Останавливаем предыдущий воркер если есть
        if self._current_pipeline_worker is not None:
            self._stop_pipeline_worker(self._current_pipeline_worker)
        
        # Создаем новый воркер
        worker = TranslationPipelineWorker(mode=mode)
        
        # Устанавливаем параметры
        if mode == TranslationPipelineWorker.MODE_SCREENSHOT:
            worker.set_screenshot_params(screenshot_path, screenshot_size)
        elif mode == TranslationPipelineWorker.MODE_TEXT:
            worker.set_text_params(selected_text)
        
        # Подключаем сигналы
        worker.status_changed.connect(self._on_pipeline_status_changed)
        worker.finished_success.connect(self._on_pipeline_finished)
        worker.failed.connect(self._on_pipeline_failed)
        worker.stream_token.connect(self._on_pipeline_stream_token)
        
        # Сохраняем ссылку для предотвращения сборки мусора
        self._current_pipeline_worker = worker
        self._is_worker_busy = True
        
        # Запускаем
        worker.start()
    
    def _stop_pipeline_worker(self, worker):
        """
        Безопасная остановка воркера:
        1. Вызывает cancel() для мгновенного разрыва HTTP
        2. Отключает все сигналы
        3. Ждет завершения потока
        """
        if worker is None:
            return
        
        # Отключаем сигналы ДО cancel, чтобы запоздалые события не летели в UI
        self._disconnect_worker_signals(worker)
        
        # Мгновенная отмена (разрыв HTTP + флаг)
        try:
            worker.cancel()
        except Exception:
            pass
        
        # Ждем завершения потока (с таймаутом)
        if worker.isRunning():
            worker.wait(2000)
            # Если всё ещё работает — принудительно
            if worker.isRunning():
                worker.terminate()
    
    def _disconnect_worker_signals(self, worker):
        """Отключение всех сигналов воркера от слотов UI"""
        try:
            worker.status_changed.disconnect(self._on_pipeline_status_changed)
        except (TypeError, RuntimeError):
            pass
        try:
            worker.finished_success.disconnect(self._on_pipeline_finished)
        except (TypeError, RuntimeError):
            pass
        try:
            worker.failed.disconnect(self._on_pipeline_failed)
        except (TypeError, RuntimeError):
            pass
        try:
            worker.stream_token.disconnect(self._on_pipeline_stream_token)
        except (TypeError, RuntimeError):
            pass
    
    def _on_pipeline_stream_token(self, text_chunk: str):
        """
        Обработка токена стриминга от воркера.
        Инициализирует оверлей при первом токене и скрывает лоадер.
        """
        # Инициализируем оверлей при первом токене стриминга
        if self.translation_window is None or not self.translation_window.isVisible():
            cursor_pos = QCursor.pos()
            worker = self._current_pipeline_worker
            
            if worker and worker.mode in (TranslationPipelineWorker.MODE_SCREENSHOT,
                                          TranslationPipelineWorker.MODE_TEXT):
                self.translation_window = OverlayTranslationWindow()
                size = worker.screenshot_size if worker.mode == TranslationPipelineWorker.MODE_SCREENSHOT else None
                model_name = getattr(worker, 'current_model', settings.get("llm.model", "AI"))
                base_url = settings.get("llm.base_url", "")
                self.translation_window.show_streaming(
                    cursor_pos,
                    size,
                    model_name,
                    base_url=base_url
                )
                # Скрываем лоадер - оверлей виден
                if self.startup_loader:
                    self.startup_loader.close()
        
        # Передаем токен в оверлей
        if self.translation_window is not None:
            self.translation_window.append_stream_token(text_chunk)
    
    def _on_pipeline_status_changed(self, status_text):
        """Обработка обновления статуса от воркера"""
        if self.startup_loader:
            self.startup_loader.set_text(APP_NAME, status_text)
    
    def _on_pipeline_finished(self, result):
        """Обработка успешного завершения воркера"""
        self._is_worker_busy = False
        try:
            # Определяем был ли стриминг
            was_streaming = (
                self.translation_window is not None and 
                self.translation_window._is_streaming
            )
            
            # Завершаем стриминг если был активен
            if was_streaming:
                self.translation_window.finish_stream(
                    final_trans_html=result.get('trans_html', ''),
                    orig_html=result.get('orig_html', '')
                )
                # Гарантируем сохранение оригинала в оверлее
                if self.translation_window:
                    self.translation_window.set_original_text(
                        result.get('orig_raw', ''),
                        result.get('orig_html', '')
                    )
            
            # Обновляем буфер обмена
            if result.get('clean_clipboard'):
                self.last_translated_text = result['clean_clipboard']
                pyperclip.copy(result['clean_clipboard'])
            
            # Если стриминга не было - показываем оверлей классически
            if not was_streaming:
                cursor_pos = QCursor.pos()
                self.show_translation_overlay(
                    result.get('orig_raw', ''),
                    result.get('trans_html', ''),
                    cursor_pos,
                    result.get('size'),
                    result.get('orig_html'),
                    model_name=result.get('model_name')
                )
            
            # Скрываем лоадер
            if self.startup_loader:
                self.startup_loader.set_loaded(SUCCESS_TRANSLATION_RECEIVED)
            
        except Exception as e:
            self.logger.error(f"Ошибка обработки результата: {e}")
            if self.startup_loader:
                self.startup_loader.set_loaded(f"Ошибка: {e}")
        finally:
            # Очищаем ссылку на воркер
            self._current_pipeline_worker = None
    
    def _on_pipeline_failed(self, error_text):
        """Обработка ошибки от воркера"""
        self._is_worker_busy = False
        self.logger.error(f"Ошибка перевода: {error_text}")
        
        if self.translation_window is not None:
            if self.translation_window._is_streaming:
                self.translation_window.finish_stream()
            
            try:
                self.translation_window.show_error(error_text)
            except Exception:
                self.translation_window.append_stream_token(f"\n\n❌ Ошибка: {error_text}")
        
        if self.startup_loader:
            self.startup_loader.set_loaded(f"Ошибка: {error_text} ❌")
        
        self._current_pipeline_worker = None
    
    def structure_ocr_results(self, results):
        """Обертка для TextFormatter.structure_ocr_results"""
        return self.text_formatter.structure_ocr_results(results)
    
    def extract_paragraphs_from_lines(self, sl):
        """Обертка для TextFormatter.extract_paragraphs_from_lines"""
        return self.text_formatter.extract_paragraphs_from_lines(sl)
    
    def post_process_text(self, sl):
        """Обертка для TextFormatter.post_process_text"""
        return self.text_formatter.post_process_text(sl)
    
    def show_translation_overlay(self, orig, trans, pos, size=None, orig_h=None, model_name=None):
        base_url = settings.get("llm.base_url", "")
        self.translation_window = OverlayTranslationWindow()
        self.translation_window.show_translation(orig, trans, pos, size, orig_h, model_name=model_name, base_url=base_url)
    
    def show_settings(self):
        try:
            if self.settings_window is not None and self.settings_window.isVisible():
                self.settings_window.setWindowState(
                    self.settings_window.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive
                )
                self.settings_window.raise_()
                self.settings_window.activateWindow()
                return

            self.settings_window = SettingsWindow()
            self.settings_window.run_benchmark_requested.connect(self.run_on_demand_benchmark)
            self.settings_window.settings_saved.connect(self.on_settings_saved)
            self.settings_window.ocr_reload_requested.connect(self.on_ocr_reload_requested)
            self.settings_window.show()
            self.settings_window.raise_()
            self.settings_window.activateWindow()
        except Exception as e:
            self.logger.error(f"Ошибка открытия окна настроек: {e}")
    
    def show_about(self):
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTabWidget, QWidget, QTextBrowser
        from PyQt6.QtCore import Qt
        from __init__ import __version__

        dlg = QDialog(self.app.activeWindow())
        dlg.setWindowTitle(f"О программе — ScreenText Helper v{__version__}")
        dlg.setMinimumSize(600, 560)
        layout = QVBoxLayout(dlg)

        tabs = QTabWidget()
        layout.addWidget(tabs)

        # --- Вкладка «О программе» ---
        about_page = QWidget()
        about_layout = QVBoxLayout(about_page)
        about_text = QTextBrowser()
        about_text.setOpenExternalLinks(True)
        about_text.setHtml(f"""
        <h2 style="color:#007ACC;">ScreenText Helper v{__version__}</h2>
        <p>Умный помощник для мгновенного захвата, распознавания (OCR) и перевода любого текста с экрана монитора.
        Незаменим при переводе игр, комиксов, видеороликов, PDF-документов и программ без поддержки русского языка.</p>
        <hr>
        <h3 style="color:#E5C07B;">Основные возможности</h3>
        <ul>
        <li><b>Перевод невыделяемого текста</b> — просто обведите область на экране, и программа прочитает и переведет текст.</li>
        <li><b>Локальный ИИ (Vision)</b> — мощные нейросети (Qwen, MiniCPM) распознают сложный текст и таблицы прямо на вашей видеокарте, без интернета.</li>
        <li><b>Удобный оверлей</b> — перевод поверх всех окон с возможностью менять шрифт, копировать текст и смотреть оригинал.</li>
        <li><b>Перевод выделенного текста</b> — быстрый перевод любого выделенного мышкой текста.</li>
        <li><b>Белорусская латиница</b> — конвертация кириллицы в латиницу (łacinka).</li>
        </ul>
        <h3 style="color:#E5C07B;">Как пользоваться</h3>
        <table cellpadding="4" cellspacing="0" border="0">
        <tr><td><b>Ctrl+End</b></td><td>— Захват области экрана → OCR + перевод</td></tr>
        <tr><td><b>Ctrl+Home</b></td><td>— Быстрый перевод выделенного текста</td></tr>
        </table>
        <p>Внешний вид окна перевода (цвета, шрифт, прозрачность) полностью настраивается в меню Настроек.</p>
        <hr>
        <p style="color:#888; font-size:10px;">Python + PyQt6 + EasyOCR + deep-translator</p>
        """)
        about_layout.addWidget(about_text)
        tabs.addTab(about_page, "О программе")

        # --- Вкладка «Справка» ---
        help_page = QWidget()
        help_layout = QVBoxLayout(help_page)
        help_text = QTextBrowser()
        help_text.setOpenExternalLinks(True)
        help_text.setHtml(f"""
        <h2 style="color:#007ACC;">Справка по использованию</h2>

        <h3 style="color:#E5C07B;">1. Горячие клавиши</h3>
        <p>По умолчанию настроены следующие комбинации (их можно изменить в Настройках):</p>
        <table cellpadding="4" cellspacing="0" border="0">
        <tr><td><b>Ctrl + End</b></td><td>— Распознавание и перевод области экрана</td></tr>
        <tr><td><b>Ctrl + Home</b></td><td>— Перевод выделенного текста</td></tr>
        </table>

        <p><b>Распознавание и перевод области экрана (Ctrl+End):</b></p>
        <ol>
        <li>Нажмите комбинацию клавиш.</li>
        <li>Экран потемнеет — выделите мышкой нужную область с текстом (в игре, на картинке или видео).</li>
        <li>Подождите пару секунд — поверх экрана появится окно с готовым переводом.</li>
        <li>Окно можно перетаскивать мышкой за любое место.</li>
        </ol>

        <p><b>Перевод выделенного текста (Ctrl+Home):</b></p>
        <ol>
        <li>Выделите любой текст в браузере или документе.</li>
        <li>Нажмите комбинацию клавиш.</li>
        <li>Программа автоматически скопирует текст и покажет оверлей с переводом.</li>
        </ol>

        <h3 style="color:#E5C07B;">2. Режимы работы</h3>
        <p>В настройках (через иконку в системном трее) можно выбрать режим перевода:</p>
        <ul>
        <li><b>Режим умного ИИ (рекомендуется!)</b> — включите галочку «Использовать Vision-to-Text (ИИ)».
            Программа использует нейросеть (через Ollama или облачные API).
            Это дает невероятное качество перевода и распознавание даже самого мелкого шрифта.</li>
        <li><b>Стандартный режим</b> — быстрый режим, использующий стандартный распознаватель текста и онлайн-переводчик.</li>
        </ul>
        <p><i>Примечание: Google может временно блокировать частые запросы (ошибка "Error 500").
        Если это происходит, переключитесь на режим локального ИИ.</i></p>

        <h3 style="color:#E5C07B;">3. Управление окном перевода</h3>
        <p>Когда на экране появляется перевод, вам доступны кнопки в нижней части окна:</p>
        <ul>
        <li><b>Оригинал / Перевод</b> — мгновенное переключение между исходным текстом и переводом.</li>
        <li><b>А- / А+</b> — уменьшение или увеличение размера шрифта.</li>
        <li><b>Копировать</b> — копирует очищенный текст в буфер обмена.</li>
        <li><b>Крестик (×)</b> — закрыть окно.</li>
        </ul>

        <h3 style="color:#E5C07B;">4. Настройка ИИ</h3>
        <ol>
        <li>В настройках включите галочку <b>«Использовать Vision-to-Text (ИИ)»</b>.</li>
        <li>Выберите провайдера:
            <ul>
            <li><b>Ollama</b> — локальный ИИ, не требует интернета. Установите Ollama и модель через меню «Установить локальный ИИ».</li>
            <li><b>OpenRouter</b> — бесплатные модели (openrouter/free).</li>
            <li><b>DeepSeek</b> — российская модель, нужен API-ключ.</li>
            <li><b>OpenAI</b> — GPT-4o, нужен API-ключ.</li>
            </ul>
        </li>
        <li>Введите API-ключ (если не Ollama) и нажмите «Проверить модель».</li>
        </ol>

        <h3 style="color:#E5C07B;">5. Управление локальными моделями (Ollama)</h3>
        <ol>
        <li>В трее правый клик → Настройки → «Установить локальный ИИ (Ollama)».</li>
        <li>В открывшемся менеджере можно <b>скачать</b> или <b>удалить</b> модели.</li>
        <li>Рекомендуется <b>qwen2.5vl:3b</b> — оптимальное соотношение скорость/качество.</li>
        <li>После скачивания выберите модель в списке моделей.</li>
        </ol>

        <h3 style="color:#E5C07B;">6. Полезные советы</h3>
        <ul>
        <li>Чтобы программа запускалась вместе с Windows, поставьте галочку «Автозагрузка при старте Windows».</li>
        <li>Внешний вид окна перевода (цвет фона, рамки, прозрачность, шрифт) полностью настраивается.</li>
        </ul>

        <h3 style="color:#E5C07B;">7. Решение проблем</h3>
        <ul>
        <li><b>OCR не работает:</b> нажмите «Перезагрузить OCR» в настройках.</li>
        <li><b>Google ошибка 500/429:</b> подождите или переключитесь на ИИ.</li>
        <li><b>ИИ не отвечает:</b> проверьте API-ключ и доступность сервера.</li>
        <li><b>Модель не поддерживает изображения:</b> выберите Vision-модель (qwen2.5vl, gpt-4o и т.д.).</li>
        </ul>
        """)
        help_layout.addWidget(help_text)
        tabs.addTab(help_page, "Справка")

        dlg.exec()
    
    def on_ocr_reload_requested(self):
        self.logger.info("Принудительная перезагрузка OCR")
        self.ocr_manager.reinitialize_ocr()

    def quit_application(self):
        self._cleanup_orphaned_temp_files()
        self.hotkey_manager.stop_listening()
        self.app.quit()
    
    def _cleanup_orphaned_temp_files(self):
        """Удаление зависших временных файлов скриншотов при выходе"""
        import tempfile
        import glob
        temp_dir = tempfile.gettempdir()
        for pattern in ('screentext_*.png', 'screentext_*.jpg'):
            for fpath in glob.glob(os.path.join(temp_dir, pattern)):
                try:
                    os.unlink(fpath)
                except Exception:
                    pass
    
    def on_settings_saved(self):
        self.hotkey_manager.unregister_all_hotkeys(); self.register_hotkeys()
        if self.tray_icon: self.tray_icon.update_smart_translate_action()
    
    def run(self):
        if self.initialize_application():
            self.is_running = True
            return self.app.exec()
        return 1

def main():
    app = ScreenTextHelper()
    return app.run()

if __name__ == "__main__":
    sys.exit(main())