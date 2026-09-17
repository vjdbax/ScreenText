#!/usr/bin/env python3
"""
Hotkey management for ScreenText Helper
"""

import keyboard
import threading
import logging
from typing import Callable, Dict, Optional
from settings import settings


class HotkeyManager:
    """Класс для управления горячими клавишами"""
    
    def __init__(self):
        self.hotkeys: Dict[str, Callable] = {}
        self.listeners: Dict[str, threading.Thread] = {}
        self.running = False
        self.logger = logging.getLogger(__name__)
        
    def register_hotkey(self, action: str, hotkey: str, callback: Callable) -> bool:
        """Регистрация горячей клавиши"""
        try:
            # Удаляем существующую горячую клавишу, если есть
            if action in self.hotkeys:
                self.unregister_hotkey(action)
            
            # Регистрируем новую горячую клавишу с параметром suppress=True,
            # чтобы перехватывать нажатие монопольно (другие программы его не увидят)
            keyboard.add_hotkey(hotkey, callback, suppress=True)
            self.hotkeys[action] = hotkey
            self.logger.info(f"Зарегистрирована монопольная горячая клавиша: {action} -> {hotkey}")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка регистрации горячей клавиши {action}: {e}")
            return False
    
    def unregister_hotkey(self, action: str) -> bool:
        """Отмена регистрации горячей клавиши (идемпотентный и безопасный метод)"""
        try:
            if action not in self.hotkeys:
                self.logger.debug(f"Горячая клавиша {action} не найдена в реестре, пропуск")
                return False
            
            hotkey_str = self.hotkeys[action]
            
            # Пытаемся удалить из библиотеки keyboard (может не существовать)
            try:
                keyboard.remove_hotkey(hotkey_str)
                self.logger.info(f"Отменена регистрация горячей клавиши: {action} -> {hotkey_str}")
            except KeyError:
                # Горячая клавиша не была зарегистрирована в keyboard - это нормально
                self.logger.debug(f"Горячая клавиша {hotkey_str} не найдена в keyboard (возможно, не была зарегистрирована)")
            except Exception as e:
                self.logger.warning(f"Предупреждение при удалении горячей клавиши {hotkey_str}: {e}")
            
            # Удаляем из нашего словаря в любом случае
            del self.hotkeys[action]
            return True
        except Exception as e:
            self.logger.error(f"Ошибка отмены регистрации горячей клавиши {action}: {e}")
            return False
    
    def register_system_hotkeys(self, ocr_callback: Callable, translate_callback: Callable) -> bool:
        """Регистрация системных горячих клавиш"""
        try:
            # Регистрируем горячие клавиши из настроек
            ocr_hotkey = settings.get_hotkey("ocr")
            translate_hotkey = settings.get_hotkey("translate")
            
            # Регистрируем OCR горячую клавишу
            if ocr_hotkey and self.register_hotkey("ocr", ocr_hotkey, ocr_callback):
                self.logger.info(f"OCR горячая клавиша зарегистрирована: {ocr_hotkey}")
            
            # Регистрируем перевод горячую клавишу
            if translate_hotkey and self.register_hotkey("translate", translate_hotkey, translate_callback):
                self.logger.info(f"Translate горячая клавиша зарегистрирована: {translate_hotkey}")
                
            return True
        except Exception as e:
            self.logger.error(f"Ошибка регистрации системных горячих клавиш: {e}")
            return False
    
    def unregister_all_hotkeys(self) -> bool:
        """Отмена регистрации всех горячих клавиш"""
        try:
            for action in list(self.hotkeys.keys()):
                self.unregister_hotkey(action)
            return True
        except Exception as e:
            self.logger.error(f"Ошибка отмены регистрации горячих клавиш: {e}")
            return False
    
    def start_listening(self):
        """Начало прослушивания горячих клавиш"""
        if not self.running:
            self.running = True
            # keyboard.listen() работает в отдельном потоке
            keyboard.wait()  # Бесконечное ожидание
    
    def stop_listening(self):
        """Остановка прослушивания горячих клавиш"""
        if self.running:
            self.running = False
            keyboard.unhook_all()
            self.logger.info("Прослушивание горячих клавиш остановлено")


class HotkeyCaptureDialog:
    """Диалог для захвата горячих клавиш (заглушка)"""
    
    def __init__(self, parent=None):
        self.parent = parent
        self.captured_hotkey = None
        
    def capture_hotkey(self) -> Optional[str]:
        """Захват горячей клавиши"""
        return None


# Глобальный экземпляр менеджера горячих клавиш
hotkey_manager = HotkeyManager()