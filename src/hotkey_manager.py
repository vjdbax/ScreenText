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
            
            # Регистрируем новую горячую клавишу
            keyboard.add_hotkey(hotkey, callback)
            self.hotkeys[action] = hotkey
            self.logger.info(f"Зарегистрирована горячая клавиша: {action} -> {hotkey}")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка регистрации горячей клавиши {action}: {e}")
            return False
    
    def unregister_hotkey(self, action: str) -> bool:
        """Отмена регистрации горячей клавиши"""
        try:
            if action in self.hotkeys:
                keyboard.remove_hotkey(self.hotkeys[action])
                del self.hotkeys[action]
                self.logger.info(f"Отменена регистрация горячей клавиши: {action}")
                return True
            return False
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
        # В реальном приложении здесь будет логика захвата комбинации клавиш
        # keyboard.hook() для отслеживания нажатий
        return None


# Глобальный экземпляр менеджера горячих клавиш
hotkey_manager = HotkeyManager()


def main():
    """Тестовая функция для демонстрации работы горячих клавиш"""
    def on_ocr():
        print("OCR горячая клавиша нажата!")
    
    def on_translate():
        print("Translate горячая клавиша нажата!")
    
    # Создаем экземпляр менеджера
    manager = HotkeyManager()
    
    # Регистрируем горячие клавиши
    manager.register_hotkey("ocr", "ctrl+alt+s", on_ocr)
    manager.register_hotkey("translate", "ctrl+alt+t", on_translate)
    
    print("Горячие клавиши зарегистрированы. Нажмите Ctrl+Alt+S или Ctrl+Alt+T для теста.")
    print("Нажмите Esc для выхода...")
    
    # Запускаем прослушивание в отдельном потоке
    import threading
    def listen_thread():
        manager.start_listening()
    
    thread = threading.Thread(target=listen_thread, daemon=True)
    thread.start()
    
    # Ожидаем нажатия Esc для выхода
    keyboard.wait('esc')
    manager.stop_listening()
    print("Программа завершена")


if __name__ == "__main__":
    main()