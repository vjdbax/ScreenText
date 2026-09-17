#!/usr/bin/env python3
"""
OCR (Optical Character Recognition) management for ScreenText Helper
Native libraries (cv2, easyocr/torch) are loaded LAZILY — only on actual OCR call.
This prevents DLL conflicts with Qt in compiled builds.
"""

import sys
import os
import importlib.util
import logging
import threading
import time
from typing import List, Dict, Optional, Tuple
from PIL import Image
import pyperclip
from settings import settings
from utils import get_resource_path

from PyQt6.QtCore import QObject, pyqtSignal


EASYOCR_AVAILABLE = importlib.util.find_spec("easyocr") is not None
CV2_AVAILABLE = importlib.util.find_spec("cv2") is not None
NUMPY_AVAILABLE = importlib.util.find_spec("numpy") is not None


def _get_numpy():
    if not NUMPY_AVAILABLE:
        return None
    if _get_numpy._module is None:
        import numpy as m
        _get_numpy._module = m
    return _get_numpy._module
_get_numpy._module = None


def _get_bundled_model_path():
    candidate = get_resource_path('easyocr_models')
    if os.path.isdir(candidate):
        return candidate
    return None


def _get_easyocr():
    if not EASYOCR_AVAILABLE:
        return None
    if _get_easyocr._module is None:
        import easyocr as m
        _get_easyocr._module = m
    return _get_easyocr._module
_get_easyocr._module = None


def _get_cv2():
    if not CV2_AVAILABLE:
        return None
    if _get_cv2._module is None:
        import cv2 as m
        _get_cv2._module = m
    return _get_cv2._module
_get_cv2._module = None


class OCRManager(QObject):
    ocr_ready = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.reader = None
        self.logger = logging.getLogger(__name__)

    def start_initialization(self, delay_sec: float = 3.0):
        """Отложенный запуск инициализации OCR (ждём, пока GUI полностью загрузится)"""
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(int(delay_sec * 1000), lambda: threading.Thread(target=self.initialize_ocr, daemon=True).start())

    def initialize_ocr(self) -> bool:
        bundled = _get_bundled_model_path()
        if bundled:
            os.environ['EASYOCR_MODULE_PATH'] = bundled
            self.logger.info(f"EasyOCR models from bundle: {bundled}")

        if not EASYOCR_AVAILABLE:
            self.logger.warning("EasyOCR не установлен. OCR-функции недоступны.")
            self.ocr_ready.emit()
            return False
        try:
            easyocr = _get_easyocr()
            ocr_language = settings.get_ocr_language()
            if ocr_language == "rus":
                languages = ['ru']
            elif ocr_language == "eng":
                languages = ['en']
            elif ocr_language == "rus+eng":
                languages = ['ru', 'en']
            else:
                languages = ['ru', 'en']
            self.reader = easyocr.Reader(languages)
            self.logger.info(f"OCR успешно инициализирован с языками: {languages}")
            self.ocr_ready.emit()
            return True
        except Exception as e:
            self.logger.error(f"Ошибка инициализации OCR: {e}")
            self.ocr_ready.emit()
            return False

    def extract_text_from_area(self, image_path: str, area: Tuple[int, int, int, int]) -> Optional[List]:
        if not CV2_AVAILABLE or not NUMPY_AVAILABLE:
            self.logger.error("OpenCV (cv2) или NumPy не установлены")
            return None
        cv2 = _get_cv2()
        np = _get_numpy()
        try:
            if self.reader is None:
                self.logger.warning("OCR ридер еще загружается. Ожидание...")
                for _ in range(25):
                    if self.reader is not None:
                        break
                    time.sleep(0.2)
                if self.reader is None:
                    self.logger.error("Превышено время ожидания загрузки OCR")
                    return None
            image = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                self.logger.error("Не удалось загрузить изображение")
                return None
            x, y, width, height = area
            if x == 0 and y == 0:
                cropped_image = image
            else:
                cropped_image = image[y:y+height, x:x+width]
            cropped_image_rgb = cv2.cvtColor(cropped_image, cv2.COLOR_BGR2RGB)
            results = self.reader.readtext(cropped_image_rgb)
            return results
        except Exception as e:
            self.logger.error(f"Ошибка извлечения текста: {e}")
            return None

    def extract_text_from_image(self, image_path: str) -> List[Dict]:
        if not CV2_AVAILABLE or not EASYOCR_AVAILABLE or not NUMPY_AVAILABLE:
            return []
        cv2 = _get_cv2()
        np = _get_numpy()
        try:
            if self.reader is None:
                return []
            image = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                self.logger.error("Не удалось загрузить изображение")
                return []
            results = self.reader.readtext(image)
            text_data = []
            for (bbox, text, confidence) in results:
                if confidence > 0.4:
                    text_data.append({'text': text, 'bbox': bbox, 'confidence': confidence})
            self.logger.info(f"Распознано {len(text_data)} текстовых блоков")
            return text_data
        except Exception as e:
            self.logger.error(f"Ошибка распознавания текста: {e}")
            return []

    def reinitialize_ocr(self) -> bool:
        self.reader = None
        self.logger.info("OCR перезагрузка запущена в фоновом потоке")
        self.start_initialization(delay_sec=0.5)
        return True

    def copy_text_to_clipboard(self, text: str) -> bool:
        try:
            pyperclip.copy(text)
            self.logger.info(f"Текст скопирован в буфер обмена")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка копирования текста в буфер обмена: {e}")
            return False
