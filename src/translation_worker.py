#!/usr/bin/env python3
"""
Background worker for translation pipeline operations
"""

import os
import re
import logging
from PyQt6.QtCore import QThread, pyqtSignal
from settings import settings
from text_formatter import create_formatter_from_settings


class TranslationPipelineWorker(QThread):
    """
    Фоновый воркер для выполнения тяжелых операций:
    - OCR распознавание
    - LLM Vision перевод
    - Стандартный перевод
    """
    
    # Режимы работы
    MODE_SCREENSHOT = "screenshot"
    MODE_TEXT = "text"
    
    # Сигналы
    status_changed = pyqtSignal(str)  # Обновление статуса в UI
    finished_success = pyqtSignal(dict)  # Результат выполнения
    failed = pyqtSignal(str)  # Ошибка
    stream_token = pyqtSignal(str)  # Токен стриминга (накопленный текст)
    
    def __init__(self, mode, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.logger = logging.getLogger(__name__)
        self.text_formatter = create_formatter_from_settings()
        
        # Параметры для MODE_SCREENSHOT
        self.screenshot_path = None
        self.screenshot_size = None
        
        # Параметры для MODE_TEXT
        self.selected_text = None
        
        # Флаги настроек — читаются ПЕРЕД каждым запросом, не при создании
        self._is_cancelled = False
        self._translator = None
    
    @property
    def current_model(self) -> str:
        return settings.get("llm.model", "AI")

    def cancel(self):
        """
        Мгновенная отмена воркера.
        Разрывает HTTP-соединение и ставит флаг остановки.
        """
        self._is_cancelled = True
        if self._translator is not None:
            try:
                self._translator.cancel()
            except Exception:
                pass
    
    @property
    def is_cancelled(self):
        return self._is_cancelled
    
    def set_screenshot_params(self, screenshot_path, screenshot_size):
        """Установка параметров для режима скриншота"""
        self.screenshot_path = screenshot_path
        self.screenshot_size = screenshot_size
    
    def set_text_params(self, selected_text):
        """Установка параметров для режима текста"""
        self.selected_text = selected_text
    
    def run(self):
        """Основной метод выполнения в фоновом потоке"""
        try:
            if self._is_cancelled:
                return
            if self.mode == self.MODE_SCREENSHOT:
                self._process_screenshot()
            elif self.mode == self.MODE_TEXT:
                self._process_text()
            else:
                self.failed.emit(f"Неизвестный режим: {self.mode}")
        except Exception as e:
            if not self._is_cancelled:
                self.logger.error(f"Критическая ошибка воркера: {e}")
                self.failed.emit(str(e))
        finally:
            # Гарантированное удаление временного скриншота
            if self.screenshot_path and os.path.exists(self.screenshot_path):
                try:
                    os.unlink(self.screenshot_path)
                except Exception as e:
                    self.logger.debug(f"Ошибка удаления кропа: {e}")
    
    def _process_screenshot(self):
        """Обработка скриншота: OCR + перевод"""
        if not self.screenshot_path or not os.path.exists(self.screenshot_path):
            self.failed.emit("Файл скриншота не найден")
            return
        
        use_smart = settings.get("llm.use_smart_translate", False)
        if use_smart:
            self._process_screenshot_with_ai()
        else:
            self._process_screenshot_with_ocr()
    
    def _process_screenshot_with_ai(self):
        """Обработка скриншота с помощью ИИ (LLM Vision) с поддержкой стриминга"""
        from ai_translator import SmartTranslator
        
        if self._is_cancelled:
            return
        
        translate_with_standard = settings.get("llm.translate_with_standard_engine", False)
        current_model = settings.get("llm.model", "AI")
        current_base_url = settings.get("llm.base_url", "")
        
        self.status_changed.emit("ИИ обрабатывает область...")
        ai = SmartTranslator()
        self._translator = ai
        
        def stream_callback(text):
            if not self._is_cancelled:
                self.stream_token.emit(text)
        
        try:
            if translate_with_standard:
                orig_html, raw_orig_text = ai.translate_vision(
                    self.screenshot_path,
                    use_hybrid=True,
                    stream_callback=stream_callback
                )
                
                if self._is_cancelled:
                    return
                
                is_ai_error = (
                    not raw_orig_text
                    or raw_orig_text.startswith("<b>Ошибка")
                    or raw_orig_text.startswith("<b style='color:red;'>")
                    or raw_orig_text.startswith("<b style=\"color:red;\">")
                    or "Ошибка API" in raw_orig_text
                    or "Ошибка соединения" in raw_orig_text
                    or "Ошибка сервиса" in raw_orig_text
                )
                if not is_ai_error:
                    self.status_changed.emit("Стандартный перевод...")
                    from translator import TranslatorManager
                    translator_manager = TranslatorManager()
                    trans_t = translator_manager.translate_text(raw_orig_text)
                    
                    if self._is_cancelled:
                        return
                    
                    if not trans_t:
                        self.status_changed.emit("Google недоступен, перевод через ИИ...")
                        _, final_html = ai.translate_vision(
                            self.screenshot_path, 
                            use_hybrid=False,
                            stream_callback=stream_callback
                        )
                    else:
                        final_html = self.text_formatter.format_to_book_html(trans_t)
                else:
                    final_html = raw_orig_text
                    orig_html = self.text_formatter.format_to_book_html(
                        "(Не удалось распознать текст на изображении)"
                    )
            else:
                orig_html, final_html = ai.translate_vision(
                    self.screenshot_path,
                    use_hybrid=False,
                    stream_callback=stream_callback
                )
            
            if self._is_cancelled:
                return
            
            # Гарантируем непустой orig_html
            if not orig_html or not orig_html.strip() or orig_html.strip() in ('<b>Ошибка</b>', ''):
                orig_html = self.text_formatter.format_to_book_html(
                    "(Оригинальный текст распознан моделью)"
                )
            
            result = self._build_screenshot_result(orig_html, final_html, current_model, current_base_url)
            self.finished_success.emit(result)
        except Exception as e:
            if not self._is_cancelled:
                self.logger.error(f"Ошибка ИИ-обработки: {e}")
                self.failed.emit(f"Ошибка ИИ: {str(e)}")
        finally:
            self._translator = None
    
    def _process_screenshot_with_ocr(self):
        """Обработка скриншота с помощью стандартного OCR"""
        from ocr_manager import OCRManager
        from translator import TranslatorManager
        
        if self._is_cancelled:
            return
        
        ocr_manager = OCRManager()
        translator_manager = TranslatorManager()
        
        # Инициализация OCR если нужно
        if ocr_manager.reader is None:
            self.status_changed.emit("Загрузка OCR...")
            ocr_manager.initialize_ocr()
        
        if ocr_manager.reader is None:
            self.failed.emit("OCR недоступен (EasyOCR не загружен)")
            return
        
        if self._is_cancelled:
            return
        
        self.status_changed.emit("Распознавание текста...")
        ocr_data = ocr_manager.extract_text_from_area(self.screenshot_path, (0, 0, 0, 0))
        
        if self._is_cancelled:
            return
        
        if not ocr_data:
            self.failed.emit("Текст не распознан")
            return
        
        self.status_changed.emit("Обработка текста...")
        structured = self.text_formatter.structure_ocr_results(ocr_data)
        orig_md, orig_h = self.text_formatter.post_process_text(structured)
        clean_p = self.text_formatter.extract_paragraphs_from_lines(structured)
        clean_t = "\n\n".join(clean_p)
        
        if not clean_t.strip():
            self.failed.emit("Распознанный текст пуст")
            return
        
        if self._is_cancelled:
            return
        
        self.status_changed.emit("Перевод текста...")
        trans_t = translator_manager.translate_text(clean_t)
        
        if self._is_cancelled:
            return
        
        if not trans_t:
            self.failed.emit("Ошибка перевода")
            return
        
        if clean_t.isupper():
            trans_t = trans_t.upper()
        
        final_h = self.text_formatter.format_to_book_html(trans_t)
        
        result = self._build_screenshot_result(orig_h, final_h)
        result['orig_raw'] = orig_md
        self.finished_success.emit(result)
    
    def _build_screenshot_result(self, orig_html, trans_html, model_name=None, base_url=None):
        """Формирование словаря результатов для скриншота"""
        clipboard_text = trans_html.replace('</h1>', '\n\n').replace('</p>', '\n\n')
        clean_clipboard = re.sub(r'<[^<]+?>', '', clipboard_text).strip()
        
        orig_clipboard_text = orig_html.replace('</h1>', '\n\n').replace('</p>', '\n\n')
        orig_raw = re.sub(r'<[^<]+?>', '', orig_clipboard_text).strip()
        
        use_smart = settings.get("llm.use_smart_translate", False)
        
        return {
            'mode': self.MODE_SCREENSHOT,
            'orig_raw': orig_raw,
            'orig_html': orig_html,
            'trans_html': trans_html,
            'clean_clipboard': clean_clipboard,
            'model_name': model_name if use_smart else None,
            'base_url': base_url if use_smart else None,
            'pos': None,
            'size': self.screenshot_size
        }
    
    def _process_text(self):
        """Обработка выделенного текста: перевод (ИИ или стандартный)"""
        if not self.selected_text or not self.selected_text.strip():
            self.failed.emit("Текст не выделен")
            return

        try:
            if self._is_cancelled:
                return

            clean_t = self._preprocess_text(self.selected_text)

            if not clean_t.strip():
                self.failed.emit("Текст пуст после обработки")
                return

            if self._is_cancelled:
                return

            use_smart = settings.get("llm.use_smart_translate", False)
            current_model = settings.get("llm.model", "AI") if use_smart else None
            current_base_url = settings.get("llm.base_url", "") if use_smart else None

            if use_smart:
                trans_t = self._process_text_with_ai(clean_t)
            else:
                from translator import TranslatorManager
                self.status_changed.emit("Перевод текста...")
                translator_manager = TranslatorManager()
                trans_t = translator_manager.translate_text(clean_t)

            if self._is_cancelled:
                return

            if not trans_t:
                self.failed.emit("Ошибка перевода")
                return

            final_h = self.text_formatter.format_to_book_html(trans_t)
            orig_h = self.text_formatter.format_to_book_html(clean_t)

            clipboard_text = final_h.replace('</h1>', '\n\n').replace('</p>', '\n\n')
            clean_clipboard = re.sub(r'<[^<]+?>', '', clipboard_text).strip()

            result = {
                'mode': self.MODE_TEXT,
                'orig_raw': self.selected_text,
                'orig_html': orig_h,
                'trans_html': final_h,
                'clean_clipboard': clean_clipboard,
                'model_name': current_model,
                'base_url': current_base_url,
                'pos': None,
                'size': None,
                'selected_text': self.selected_text
            }

            self.finished_success.emit(result)

        except Exception as e:
            self.logger.error(f"Ошибка обработки текста: {e}")
            self.failed.emit(str(e))

    def _process_text_with_ai(self, clean_t: str) -> str:
        """Перевод текста через ИИ с автоматическим fallback на Google Translate."""
        from ai_translator import SmartTranslator

        self.status_changed.emit("ИИ переводит текст...")
        ai = SmartTranslator()
        self._translator = ai

        def stream_callback(text):
            if not self._is_cancelled:
                self.stream_token.emit(text)

        try:
            trans_t = ai.translate_text(clean_t, stream_callback=stream_callback)

            if self._is_cancelled:
                return ""

            if trans_t:
                return trans_t

            # Пустой результат — fallback
            self.status_changed.emit("ИИ не вернул результат, перевод через Google...")
            return self._fallback_google(clean_t)

        except Exception as e:
            if self._is_cancelled:
                return ""
            self.logger.warning(f"ИИ недоступен ({e}), fallback на Google Translate")
            self.status_changed.emit("ИИ недоступен, перевод через Google...")
            return self._fallback_google(clean_t)

        finally:
            self._translator = None

    def _fallback_google(self, text: str) -> str:
        """Стандартный перевод через Google Translate."""
        from translator import TranslatorManager
        translator_manager = TranslatorManager()
        return translator_manager.translate_text(text)
    
    def _preprocess_text(self, text):
        """Предобработка текста: объединение строк, разорванных дефисами"""
        raw = [l.strip() for l in text.split("\n")]
        cl = []
        
        for i, line in enumerate(raw):
            if line.endswith('-') and i < len(raw) - 1:
                cl.append(line[:-1])
            else:
                if i > 0 and raw[i-1].endswith('-'):
                    cl[-1] = cl[-1] + line
                else:
                    cl.append(line)
        
        para = []
        cur = []
        for l in cl:
            if not l:
                if cur:
                    para.append(" ".join(cur))
                    cur = []
            else:
                cur.append(l)
        
        if cur:
            para.append(" ".join(cur))
        
        return "\n\n".join(para)
