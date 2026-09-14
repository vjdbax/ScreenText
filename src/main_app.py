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
from PIL import ImageGrab, Image

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QPoint
from PyQt6.QtGui import QCursor, QIcon

from tray_icon import TrayIcon
from settings_window import SettingsWindow
from hotkey_manager import HotkeyManager as hotkey_manager
from ocr_manager import OCRManager
from translator import TranslatorManager
from screen_capture import ScreenCapture
from overlay_window import TranslationOverlay as OverlayTranslationWindow, StartupLoaderWidget
from settings import settings
from ai_translator import SmartTranslator

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
        
        self.translation_window = None
        self.startup_loader = None
        self.clipboard_poll_timer = None
        self.clipboard_poll_counter = 0
        self.old_text_clipboard = ""
        self.last_translated_text = ""  
        self.is_running = False
        self.benchmark_mode = "startup"
        self.setup_logging()
        
    def setup_logging(self):
        try:
            appdata_root = os.environ.get("APPDATA", os.path.expanduser("~"))
            app_dir = os.path.join(appdata_root, "ScreenTextHelper")
            os.makedirs(app_dir, exist_ok=True)
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
            self.ocr_manager.start_initialization(delay_sec=3.0)

            self.logger.info("Приложение успешно инициализировано")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка инициализации: {e}")
            return False
            
    def setup_signal_handlers(self):
        self.tray_icon.show_settings.connect(self.show_settings)
        self.tray_icon.show_about.connect(self.show_about)
        self.tray_icon.quit_application.connect(self.quit_application)
        
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
                response = requests.get("https://openrouter.ai/api/v1/models", timeout=6)
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
    
    def restart_snipping_tool(self):
        try:
            import subprocess
            subprocess.run('taskkill /f /im SnippingTool.exe', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run('taskkill /f /im ScreenSketch.exe', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(0.1)  
        except: pass
            
    def handle_ocr_hotkey(self):
        self.release_all_modifiers()
        self.old_text_clipboard = pyperclip.paste().strip()
        pyperclip.copy("")
        self.restart_snipping_tool()
        time.sleep(0.25)
        try:
            pyautogui.hotkey('win', 'shift', 's')
        except: pass
        self.clipboard_poll_timer = QTimer()
        self.clipboard_poll_counter = 0
        self.clipboard_poll_timer.timeout.connect(self.poll_clipboard_for_image)
        self.clipboard_poll_timer.start(250)  
            
    def poll_clipboard_for_image(self):
        self.clipboard_poll_counter += 1
        img = ImageGrab.grabclipboard()
        if isinstance(img, Image.Image):
            self.clipboard_poll_timer.stop()
            ratio = 1.0
            try: ratio = QApplication.primaryScreen().devicePixelRatio()
            except: pass
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tf:
                rgb_img = img.convert('RGB')
                rgb_img.save(tf.name, format='JPEG', quality=85)
                screenshot_path = tf.name
            
            if settings.get("llm.use_smart_translate", False):
                self.startup_loader.set_text("ScreenText Helper", "ИИ обрабатывает область...")
                QApplication.processEvents() 
                ai = SmartTranslator()
                current_model = settings.get("llm.model", "AI")
                
                if settings.get("llm.translate_with_standard_engine", False):
                    orig_html, raw_orig_text = ai.translate_vision(screenshot_path)
                    if raw_orig_text and not raw_orig_text.startswith("<b>Ошибка"):
                        self.startup_loader.set_text("ScreenText Helper", "Стандартный перевод...")
                        QApplication.processEvents()
                        trans_t = self.translator_manager.translate_text(raw_orig_text)
                        if not trans_t:
                            self.startup_loader.set_text("ScreenText Helper", "Google недоступен, перевод через ИИ...")
                            QApplication.processEvents()
                            _, final_html = ai.translate_vision(screenshot_path, force_direct_translation=True)
                        else:
                            final_html = ai.format_text_to_html(trans_t)
                    else:
                        final_html = "<b>Ошибка распознавания</b>"
                else:
                    orig_html, final_html = ai.translate_vision(screenshot_path)
                    
                self.startup_loader.set_loaded("Перевод получен! 🎉")
                
                import re
                clipboard_text = final_html.replace('</h1>', '\n\n').replace('</p>', '\n\n')
                clean_text_for_clipboard = re.sub('<[^<]+?>', '', clipboard_text).strip()
                self.last_translated_text = clean_text_for_clipboard
                pyperclip.copy(clean_text_for_clipboard)
                
                cursor_pos = QCursor.pos()
                orig_clipboard_text = orig_html.replace('</h1>', '\n\n').replace('</p>', '\n\n')
                original_markdown = re.sub('<[^<]+?>', '', orig_clipboard_text).strip()
                
                self.show_translation_overlay(original_markdown, final_html, cursor_pos, (int(img.size[0]/ratio), int(img.size[1]/ratio)), orig_html, model_name=current_model)
                if os.path.exists(screenshot_path): os.unlink(screenshot_path)
                return
            
            if self.ocr_manager.reader is None:
                self.startup_loader.set_loaded("OCR недоступен ❌ (EasyOCR не загружен)")
                if os.path.exists(screenshot_path): os.unlink(screenshot_path)
                return
            ocr_data = self.ocr_manager.extract_text_from_area(screenshot_path, (0, 0, 0, 0))
            if os.path.exists(screenshot_path): os.unlink(screenshot_path)
            if not ocr_data: return
            structured = self.structure_ocr_results(ocr_data)
            orig_md, orig_h = self.post_process_text(structured)
            clean_p = self.extract_paragraphs_from_lines(structured)
            clean_t = "\n\n".join(clean_p)
            if not clean_t.strip(): return
            trans_t = self.translator_manager.translate_text(clean_t)
            if not trans_t: return
            if clean_t.isupper(): trans_t = trans_t.upper()
            f_color = settings.get("font_color", "#000000")
            p_sz = settings.get("font_size_p", 10)
            final_h = "".join([f'<p style="font-family:\'Georgia\'; font-size:{p_sz}pt; text-align:justify; text-indent:25px; color:{f_color};">{l.strip()}</p>' for l in trans_t.split("\n") if l.strip()])
            
            import re
            clipboard_text = final_h.replace('</h1>', '\n\n').replace('</p>', '\n\n')
            clean_text_for_clipboard = re.sub('<[^<]+?>', '', clipboard_text).strip()
            self.last_translated_text = clean_text_for_clipboard
            pyperclip.copy(clean_text_for_clipboard)
            
            self.show_translation_overlay(orig_md, final_h, QCursor.pos(), (int(img.size[0]/ratio), int(img.size[1]/ratio)), orig_h)
        elif self.clipboard_poll_counter > 80: self.clipboard_poll_timer.stop()

    def handle_translate_selected_text(self):
        self.release_all_modifiers()
        self.startup_loader.set_text("ScreenText Helper", "Копирование текста...")
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
            self.startup_loader.set_loaded("Ошибка: текст не выделен ❌"); return
        self.startup_loader.set_text("ScreenText Helper", "Перевод текста...")
        QApplication.processEvents()
        raw = [l.strip() for l in sel.split("\n")]
        cl = []
        for i, line in enumerate(raw):
            if line.endswith('-') and i < len(raw) - 1: cl.append(line[:-1])
            else:
                if i > 0 and raw[i-1].endswith('-'): cl[-1] = cl[-1] + line
                else: cl.append(line)
        para = []
        cur = []
        for l in cl:
            if not l:
                if cur: para.append(" ".join(cur)); cur = []
            else: cur.append(l)
        if cur: para.append(" ".join(cur))
        clean_t = "\n\n".join(para)
        trans_t = self.translator_manager.translate_text(clean_t)
        if not trans_t: self.startup_loader.set_loaded("Ошибка перевода ❌"); return
        self.startup_loader.set_loaded("Перевод получен! 🎉")
        p_sz = settings.get("font_size_p", 10); f_color = settings.get("font_color", "#000000")
        final_h = "".join([f'<p style="font-family:\'Georgia\'; font-size:{p_sz}pt; text-align:justify; text-indent:25px; color:{f_color};">{p.strip()}</p>' for p in trans_t.split("\n\n") if p.strip()])
        orig_h = "".join([f'<p style="font-family:\'Georgia\'; font-size:{p_sz}pt; text-align:justify; text-indent:25px; color:{f_color};">{p.strip()}</p>' for p in para if p.strip()])
        
        import re
        clipboard_text = final_h.replace('</h1>', '\n\n').replace('</p>', '\n\n')
        clean_text_for_clipboard = re.sub('<[^<]+?>', '', clipboard_text).strip()
        self.last_translated_text = clean_text_for_clipboard
        pyperclip.copy(clean_text_for_clipboard)
        
        self.show_translation_overlay(sel, final_h, QCursor.pos(), None, orig_h)
            
    def structure_ocr_results(self, results):
        if not results: return []
        blocks = []
        for bbox, text, conf in results:
            if conf > 0.4:
                x0 = min(p[0] for p in bbox); x1 = max(p[0] for p in bbox); y0 = min(p[1] for p in bbox); y1 = max(p[1] for p in bbox)
                blocks.append({'x0': x0, 'x1': x1, 'y0': y0, 'y1': y1, 'height': y1 - y0, 'cy': (y0 + y1) / 2, 'text': text})
        if not blocks: return []
        blocks.sort(key=lambda b: b['cy'])
        lines = []
        for b in blocks:
            matched = False
            for line in lines:
                avg_cy = sum(item['cy'] for item in line) / len(line)
                avg_h = sum(item['height'] for item in line) / len(line)
                if abs(b['cy'] - avg_cy) < avg_h * 0.5: line.append(b); matched = True; break
            if not matched: lines.append([b])
        structured = []
        for l in lines:
            l.sort(key=lambda b: b['x0'])
            structured.append({'text': " ".join(b['text'] for b in l).strip(), 'height': sum(b['height'] for b in l) / len(l), 'x0': l[0]['x0'], 'y0': l[0]['y0']})
        return sorted(structured, key=lambda l: l['y0'])

    def extract_paragraphs_from_lines(self, sl):
        if not sl: return []
        avg_h = sum([l['height'] for l in sl]) / len(sl) if sl else 20
        title = ""
        body = sl
        if len(sl) > 1 and sl[0]['height'] > avg_h * 1.15: title = sl[0]['text']; body = sl[1:]
        cleaned = []
        for i, line in enumerate(body):
            text = line['text']
            if text.endswith('-') and i < len(body) - 1: line['merge_next'] = True; line['clean_text'] = text[:-1]
            else: line['merge_next'] = False; line['clean_text'] = text
            cleaned.append(line)
        para = []; cur = []
        if title: para.append(title)
        for i, line in enumerate(cleaned):
            text = line['clean_text']
            if not cur: cur.append(text)
            else:
                if cleaned[i-1].get('merge_next', False): cur[-1] = cur[-1] + text
                else:
                    if cleaned[i-1]['text'].endswith(('.', '!', '?')): para.append(" ".join(cur)); cur = [text]
                    else: cur.append(text)
        if cur: para.append(" ".join(cur))
        return [p.replace(" . ", ". ").replace(" , ", ", ").replace(" )", ")").replace("( ", "(").strip() for p in para]

    def post_process_text(self, sl):
        p = self.extract_paragraphs_from_lines(sl)
        if not p: return "", ""
        avg_h = sum([l['height'] for l in sl]) / len(sl) if sl else 20
        has_t = len(sl) > 1 and sl[0]['height'] > avg_h * 1.15
        hl = []; ml = []; start = 0
        f_c = settings.get("font_color", "#000000"); p_sz = settings.get("font_size_p", 10); h1_sz = settings.get("font_size_h1", 14)
        if has_t:
            hl.append(f'<h1 style="font-family:\'Segoe UI\'; font-size:{h1_sz}pt; font-weight:bold; text-align:center; color:{f_c};">{p[0]}</h1>')
            ml.append(f"# {p[0]}\n"); start = 1
        for pr in p[start:]:
            hl.append(f'<p style="font-family:\'Georgia\'; font-size:{p_sz}pt; text-align:justify; text-indent:25px; color:{f_c};">{pr}</p>')
            ml.append(pr)
        return "\n\n".join(ml), "".join(hl)
    
    def show_translation_overlay(self, orig, trans, pos, size=None, orig_h=None, model_name=None):
        self.translation_window = OverlayTranslationWindow()
        self.translation_window.show_translation(orig, trans, pos, size, orig_h, model_name=model_name)
    
    def show_settings(self):
        try:
            self.settings_window = SettingsWindow()
            self.settings_window.run_benchmark_requested.connect(self.run_on_demand_benchmark)
            self.settings_window.settings_saved.connect(self.on_settings_saved)
            self.settings_window.ocr_reload_requested.connect(self.on_ocr_reload_requested)
            self.settings_window.show()
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
        self.hotkey_manager.stop_listening(); self.app.quit()
    
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