#!/usr/bin/env python3
"""
Translation management for ScreenText Helper
"""

import logging
from typing import Optional, Dict, Any
from googletrans import Translator
from settings import settings


class TranslatorManager:
    """Класс для управления переводом текста"""
    
    def __init__(self):
        self.translator = None
        self.logger = logging.getLogger(__name__)
        self.initialize_translator()
        
    def initialize_translator(self) -> bool:
        """Инициализация переводчика"""
        try:
            self.translator = Translator()
            self.logger.info("Переводчик успешно инициализирован")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка инициализации переводчика: {e}")
            return False
    
    def translate_text(self, text: str, target_lang: str = None) -> Optional[str]:
        """Перевод текста"""
        try:
            if not text.strip():
                return None
            
            # Если целевой язык не указан, используем настройку
            if target_lang is None:
                target_lang = settings.get_translate_target_language()
            
            # Определяем язык текста (опционально)
            try:
                detection = self.translator.detect(text)
                source_lang = detection.lang
                self.logger.info(f"Обнаружен язык: {source_lang}")
            except:
                source_lang = 'auto'  # Автоопределение
            
            # Выполняем перевод
            result = self.translator.translate(text, src=source_lang, dest=target_lang)
            
            if result and result.text:
                self.logger.info(f"Перевод выполнен: '{text}' -> '{result.text}'")
                return result.text
            else:
                self.logger.error("Ошибка перевода: пустой результат")
                return None
                
        except Exception as e:
            self.logger.error(f"Ошибка перевода текста: {e}")
            return None
    
    def get_supported_languages(self) -> Dict[str, str]:
        """Получение списка поддерживаемых языков"""
        return {
            'en': 'English',
            'ru': 'Русский',
            'zh': 'Chinese',
            'es': 'Spanish',
            'fr': 'French',
            'de': 'German',
            'it': 'Italian',
            'pt': 'Portuguese',
            'ar': 'Arabic',
            'ja': 'Japanese',
            'ko': 'Korean',
            'hi': 'Hindi'
        }
    
    def get_available_language_codes(self) -> list:
        """Получение кодов доступных языков"""
        return list(self.get_supported_languages().keys())
    
    def is_available(self) -> bool:
        """Проверка доступности переводчика"""
        return self.translator is not None


class TranslationOverlay:
    """Класс для отображения перевода поверх экрана (заглушка)"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def show_translation(self, text: str, translated_text: str, position: tuple, duration: int = 5000):
        """Отображение перевода поверх экрана"""
        try:
            # В реальном приложении здесь будет создание прозрачного окна
            # с отображением перевода в указанной позиции
            
            self.logger.info(f"Показ перевода: {translated_text}")
            self.logger.info(f"Позиция: {position}, Длительность: {duration}ms")
            
            # Здесь может быть логика создания PyQt окна
            # или использования других методов отображения
            
            return True
        except Exception as e:
            self.logger.error(f"Ошибка отображения перевода: {e}")
            return False
    
    def hide_translation(self):
        """Скрытие окна перевода"""
        try:
            # В реальном приложении здесь будет скрытие окна перевода
            self.logger.info("Окно перевода скрыто")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка скрытия окна перевода: {e}")
            return False
    
    def update_translation(self, translated_text: str):
        """Обновление текста в окне перевода"""
        try:
            self.logger.info(f"Обновление перевода: {translated_text}")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка обновления перевода: {e}")
            return False


# Глобальные экземпляры
translator_manager = TranslatorManager()
translation_overlay = TranslationOverlay()


def main():
    """Тестовая функция для демонстрации работы переводчика"""
    # Проверяем доступность переводчика
    if translator_manager.is_available():
        print("Переводчик успешно инициализирован")
        
        # Пример перевода
        test_text = "Hello, world!"
        result = translator_manager.translate_text(test_text, 'ru')
        
        if result:
            print(f"Перевод: '{test_text}' -> '{result}'")
        else:
            print("Ошибка перевода")
        
        # Показываем поддерживаемые языки
        print("\nПоддерживаемые языки:")
        for code, name in translator_manager.get_supported_languages().items():
            print(f"{code}: {name}")
    else:
        print("Ошибка инициализации переводчика")


if __name__ == "__main__":
    main()