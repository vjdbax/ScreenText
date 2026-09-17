#!/usr/bin/env python3
"""
Screen capture functionality for ScreenText Helper
"""

import cv2
import numpy as np
import pyautogui
import logging
from typing import Tuple, Optional, List
from PIL import Image, ImageGrab
import tempfile
import os


class ScreenCapture:
    """Класс для захвата экрана"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def capture_full_screen(self) -> Optional[str]:
        """Захват всего экрана"""
        try:
            # Используем ImageGrab с поддержкой всех экранов
            screenshot = ImageGrab.grab(all_screens=True)
            
            # Сохраняем во временный файл
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                screenshot.save(temp_file.name)
                temp_path = temp_file.name
            
            self.logger.info(f"Скриншот сохранен: {temp_path}")
            return temp_path
            
        except Exception as e:
            self.logger.error(f"Ошибка захвата экрана: {e}")
            return None
    
    def capture_area(self, area: Tuple[int, int, int, int]) -> Optional[str]:
        """Захват указанной области экрана"""
        try:
            x, y, width, height = area
            
            # ВАЖНО: Добавлен параметр all_screens=True для поддержки второго монитора и High-DPI
            screenshot = ImageGrab.grab(bbox=(x, y, x + width, y + height), all_screens=True)
            
            # Сохраняем во временный файл
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                screenshot.save(temp_file.name)
                temp_path = temp_file.name
            
            self.logger.info(f"Скриншот области сохранен: {temp_path}")
            return temp_path
            
        except Exception as e:
            self.logger.error(f"Ошибка захвата области экрана: {e}")
            return None
    
    def get_screen_resolution(self) -> Tuple[int, int]:
        """Получение разрешения экрана"""
        try:
            width, height = pyautogui.size()
            self.logger.info(f"Разрешение экрана: {width}x{height}")
            return (width, height)
        except Exception as e:
            self.logger.error(f"Ошибка получения разрешения экрана: {e}")
            return (1920, 1080)  # Значение по умолчанию
    
    def get_active_window_info(self) -> Optional[dict]:
        """Получение информации об активном окне"""
        try:
            active_window = pyautogui.getActiveWindow()
            if active_window:
                return {
                    'title': active_window.title,
                    'left': active_window.left,
                    'top': active_window.top,
                    'width': active_window.width,
                    'height': active_window.height
                }
            return None
        except Exception as e:
            self.logger.error(f"Ошибка получения информации об активном окне: {e}")
            return None