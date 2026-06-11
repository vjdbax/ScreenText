#!/usr/bin/env python3
"""
Settings management for ScreenText Helper
"""

import json
import os
from typing import Dict, Any


class Settings:
    """Класс для управления настройками приложения"""
    
    DEFAULT_SETTINGS = {
        "hotkeys": {
            "ocr": "ctrl+alt+s",
            "translate": "ctrl+alt+t"
        },
        "languages": {
            "ocr": "rus",
            "translate_target": "en"
        },
        "auto_start": False,
        "window_opacity": 0.3,
        "border_color": "#FF0000",
        "translate_window_duration": 5000  # milliseconds
    }
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = config_dir
        self.config_file = os.path.join(config_dir, "settings.json")
        self.settings = self.load_settings()
        
    def load_settings(self) -> Dict[str, Any]:
        """Загрузка настроек из файла или создание стандартных"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                # Создаем директорию, если не существует
                os.makedirs(self.config_dir, exist_ok=True)
                return self.DEFAULT_SETTINGS.copy()
        except (json.JSONDecodeError, IOError):
            return self.DEFAULT_SETTINGS.copy()
    
    def save_settings(self) -> bool:
        """Сохранение настроек в файл"""
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
            return True
        except IOError:
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """Получение значения настройки по ключу"""
        keys = key.split('.')
        value = self.settings
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any) -> None:
        """Установка значения настройки по ключу"""
        keys = key.split('.')
        current = self.settings
        
        # Проходим по вложенным ключам, создавая словари при необходимости
        for k in keys[:-1]:
            if k not in current or not isinstance(current[k], dict):
                current[k] = {}
            current = current[k]
        
        # Устанавливаем конечное значение
        current[keys[-1]] = value
    
    def get_hotkey(self, action: str) -> str:
        """Получение горячего клавиша для действия"""
        return self.get(f"hotkeys.{action}", self.DEFAULT_SETTINGS["hotkeys"][action])
    
    def set_hotkey(self, action: str, hotkey: str) -> None:
        """Установка горячего клавиша для действия"""
        self.set(f"hotkeys.{action}", hotkey)
    
    def get_ocr_language(self) -> str:
        """Получение языка для OCR"""
        return self.get("languages.ocr", self.DEFAULT_SETTINGS["languages"]["ocr"])
    
    def set_ocr_language(self, language: str) -> None:
        """Установка языка для OCR"""
        self.set("languages.ocr", language)
    
    def get_translate_target_language(self) -> str:
        """Получение целевого языка для перевода"""
        return self.get("languages.translate_target", self.DEFAULT_SETTINGS["languages"]["translate_target"])
    
    def set_translate_target_language(self, language: str) -> None:
        """Установка целевого языка для перевода"""
        self.set("languages.translate_target", language)
    
    def get_auto_start(self) -> bool:
        """Получение настройки автозагрузки"""
        return self.get("auto_start", self.DEFAULT_SETTINGS["auto_start"])
    
    def set_auto_start(self, auto_start: bool) -> None:
        """Установка настройки автозагрузки"""
        self.set("auto_start", auto_start)
    
    def reset_to_defaults(self) -> None:
        """Сброс настроек к значениям по умолчанию"""
        self.settings = self.DEFAULT_SETTINGS.copy()
        self.save_settings()


# Глобальный экземпляр настроек
settings = Settings()