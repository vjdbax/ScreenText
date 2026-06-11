#!/usr/bin/env python3
"""
OCR (Optical Character Recognition) management for ScreenText Helper
"""

import easyocr
import cv2
import numpy as np
import logging
from typing import List, Dict, Optional, Tuple
from PIL import Image
import pyperclip
from settings import settings


class OCRManager:
    """Класс для управления распознаванием текста"""
    
    def __init__(self):
        self.reader = None
        self.logger = logging.getLogger(__name__)
        self.initialize_ocr()
        
    def initialize_ocr(self) -> bool:
        """Инициализация OCR движка"""
        try:
            # Определяем языки для распознавания
            ocr_language = settings.get_ocr_language()
            
            if ocr_language == "rus":
                languages = ['ru']
            elif ocr_language == "eng":
                languages = ['en']
            elif ocr_language == "rus+eng":
                languages = ['ru', 'en']
            else:
                languages = ['ru']  # язык по умолчанию
            
            # Инициализируем EasyOCR
            self.reader = easyocr.Reader(languages)
            self.logger.info(f"OCR инициализирован с языками: {languages}")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка инициализации OCR: {e}")
            return False
    
    def extract_text_from_area(self, image_path: str, area: Tuple[int, int, int, int]) -> Optional[str]:
        """Извлечение текста из указанной области изображения"""
        try:
            # Загружаем изображение
            image = cv2.imread(image_path)
            if image is None:
                self.logger.error("Не удалось загрузить изображение")
                return None
            
            # Вырезаем указанную область (x, y, width, height)
            x, y, width, height = area
            cropped_image = image[y:y+height, x:x+width]
            
            # Конвертируем в RGB для PIL
            cropped_image_rgb = cv2.cvtColor(cropped_image, cv2.COLOR_BGR2RGB)
            
            # Распознаем текст
            results = self.reader.readtext(cropped_image_rgb)
            
            # Извлекаем текст из результатов
            extracted_text = []
            for (bbox, text, confidence) in results:
                if confidence > 0.5:  # Фильтр по уверенности
                    extracted_text.append(text)
            
            # Объединяем все распознанный текст
            full_text = ' '.join(extracted_text).strip()
            
            if full_text:
                self.logger.info(f"Распознан текст: {full_text}")
                return full_text
            else:
                self.logger.warning("Текст не распознан")
                return None
                
        except Exception as e:
            self.logger.error(f"Ошибка извлечения текста: {e}")
            return None
    
    def extract_text_from_image(self, image_path: str) -> List[Dict]:
        """Распознавание текста на всем изображении с координатами"""
        try:
            # Загружаем изображение
            image = cv2.imread(image_path)
            if image is None:
                self.logger.error("Не удалось загрузить изображение")
                return []
            
            # Распознаем текст
            results = self.reader.readtext(image)
            
            # Форматируем результаты
            text_data = []
            for (bbox, text, confidence) in results:
                if confidence > 0.5:  # Фильтр по уверенности
                    text_data.append({
                        'text': text,
                        'bbox': bbox,
                        'confidence': confidence
                    })
            
            self.logger.info(f"Распознано {len(text_data)} текстовых блоков")
            return text_data
            
        except Exception as e:
            self.logger.error(f"Ошибка распознавания текста: {e}")
            return []
    
    def copy_text_to_clipboard(self, text: str) -> bool:
        """Копирование текста в буфер обмена"""
        try:
            pyperclip.copy(text)
            self.logger.info(f"Текст скопирован в буфер обмена: {text}")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка копирования текста в буфер обмена: {e}")
            return False
    
    def capture_screenshot(self, area: Optional[Tuple[int, int, int, int]] = None) -> str:
        """Захват экрана (заглушка)"""
        # В реальном приложении здесь будет логика захвата экрана
        # с помощью PIL, mss или другой библиотеки
        return "screenshot.png"
    
    def process_selected_area(self, area: Tuple[int, int, int, int]) -> Optional[str]:
        """Обработка выделенной области"""
        try:
            # Захватываем скриншот области
            screenshot_path = self.capture_screenshot(area)
            
            # Извлекаем текст из области
            text = self.extract_text_from_area(screenshot_path, area)
            
            if text:
                # Копируем текст в буфер обмена
                self.copy_text_to_clipboard(text)
                return text
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Ошибка обработки выделенной области: {e}")
            return None
    
    def get_supported_languages(self) -> List[str]:
        """Получение списка поддерживаемых языков"""
        return ['ru', 'en', 'zh', 'es', 'fr', 'de', 'it', 'pt', 'ar', 'ja']
    
    def is_available(self) -> bool:
        """Проверка доступности OCR"""
        return self.reader is not None


def main():
    """Тестовая функция для демонстрации работы OCR"""
    # Создаем экземпляр OCR менеджера
    ocr_manager = OCRManager()
    
    if ocr_manager.is_available():
        print("OCR успешно инициализирован")
        
        # Пример обработки области (заглушка)
        test_area = (100, 100, 200, 50)  # x, y, width, height
        result = ocr_manager.process_selected_area(test_area)
        
        if result:
            print(f"Распознанный текст: {result}")
        else:
            print("Текст не распознан")
    else:
        print("Ошибка инициализации OCR")


if __name__ == "__main__":
    main()