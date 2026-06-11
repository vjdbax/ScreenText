#!/usr/bin/env python3
"""
Main application logic for ScreenText Helper
"""

import sys
import logging
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal
from tray_icon import TrayIcon
from settings_window import SettingsWindow
from hotkey_manager import HotkeyManager as hotkey_manager
from ocr_manager import OCRManager
from translator import TranslatorManager, TranslationOverlay
from screen_capture import ScreenCapture, SelectionOverlay
from overlay_window import SelectionOverlay as OverlaySelectionWindow, TranslationOverlay as OverlayTranslationWindow


class ScreenTextHelper(QObject):
    """Основной класс приложения"""
    
    # Сигналы
    show_settings_requested = pyqtSignal()
    show_about_requested = pyqtSignal()
    quit_application_requested = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.app = None
        self.tray_icon = None
        self.settings_window = None
        self.hotkey_manager = hotkey_manager()
        self.ocr_manager = OCRManager()
        self.translator_manager = TranslatorManager()
        self.screen_capture = ScreenCapture()
        
        # Переменные состояния
        self.is_running = False
        
        # Настройка логирования
        self.setup_logging()
        
    def setup_logging(self):
        """Настройка системы логирования"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('screentext_helper.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def initialize_application(self):
        """Инициализация приложения"""
        try:
            self.logger.info("Инициализация ScreenText Helper")
            
            # Создаем экземпляр приложения
            self.app = QApplication(sys.argv)
            self.app.setQuitOnLastWindowClosed(False)
            
            # Создаем иконку в системном трее
            self.tray_icon = TrayIcon(self.app)
            self.tray_icon.show()
            
            # Подключаем сигналы
            self.setup_signal_handlers()
            
            # Регистрируем горячие клавиши
            self.register_hotkeys()
            
            self.logger.info("Приложение успешно инициализировано")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка инициализации приложения: {e}")
            return False
    
    def setup_signal_handlers(self):
        """Настройка обработчиков сигналов"""
        # Сигналы от иконки в трее
        self.tray_icon.show_settings.connect(self.show_settings)
        self.tray_icon.show_about.connect(self.show_about)
        self.tray_icon.quit_application.connect(self.quit_application)
        
        # Сигналы от окна настроек
        if self.settings_window:
            self.settings_window.settings_saved.connect(self.on_settings_saved)
    
    def register_hotkeys(self):
        """Регистрация горячих клавиш"""
        try:
            # OCR горячая клавиша
            def on_ocr():
                self.handle_ocr_hotkey()
            
            # Перевод горячая клавиша
            def on_translate():
                self.handle_translate_hotkey()
            
            # Регистрируем горячие клавиши
            self.hotkey_manager.register_system_hotkeys(on_ocr, on_translate)
            
            self.logger.info("Горячие клавиши успешно зарегистрированы")
            
        except Exception as e:
            self.logger.error(f"Ошибка регистрации горячих клавиш: {e}")
    
    def handle_ocr_hotkey(self):
        """Обработка горячей клавиши OCR"""
        try:
            self.logger.info("Активирована OCR горячая клавиша")
            # Запуск селектора области для OCR
            from area_selector import AreaSelector
            selector = AreaSelector()
            selector.area_selected.connect(self.on_selection_completed_ocr)
            selector.area_selection_canceled.connect(lambda: self.logger.info('Отмена выбора области OCR'))
            selector.show_selector()
            
        except Exception as e:
            self.logger.error(f"Ошибка обработки OCR горячей клавиши: {e}")
    
    def handle_translate_hotkey(self):
        """Обработка горячей клавиши перевода"""
        try:
            self.logger.info("Активирована translate горячая клавиша")
            # Запуск селектора области для перевода
            from area_selector import AreaSelector
            selector = AreaSelector()
            selector.area_selected.connect(self.on_selection_completed_translate)
            selector.area_selection_canceled.connect(lambda: self.logger.info('Отмена выбора области перевода'))
            selector.show_selector()
            
        except Exception as e:
            self.logger.error(f"Ошибка обработки translate горячей клавиши: {e}")
    
    def show_selection_window(self, callback):
        """Показать окно выделения области"""
        try:
            # Создаем окно выделения
            selection_window = OverlaySelectionWindow()
            
            # Подключаем сигнал о завершении выделения
            selection_window.selection_made.connect(callback)
            
            # Показываем окно
            selection_window.show()
            
        except Exception as e:
            self.logger.error(f"Ошибка показа окна выделения: {e}")
    
    def on_selection_completed_ocr(self, x, y, width, height):
        """Обработка завершения выделения для OCR: захват области, распознавание EasyOCR и копирование в буфер"""
        try:
            if width > 0 and height > 0:
                self.logger.info(f"Выделена область для OCR: {x}, {y}, {width}, {height}")

                # 1. Захватываем область экрана
                screenshot_path = self.screen_capture.capture_area((x, y, width, height))
                if not screenshot_path:
                    self.logger.error("Не удалось захватить область экрана для OCR")
                    return

                # 2. Распознаём текст с помощью EasyOCR
                ocr_text = self.ocr_manager.extract_text_from_area(screenshot_path, (0, 0, width, height))
                if not ocr_text:
                    self.logger.warning("OCR не распознал текст в выделенной области")
                    return

                # 3. Копируем результат в буфер обмена
                if self.ocr_manager.copy_text_to_clipboard(ocr_text):
                    self.logger.info(f"Текст OCR скопирован в буфер: {ocr_text}")
                else:
                    self.logger.error("Не удалось скопировать текст OCR в буфер обмена")

                # 4. Удаляем временный файл скриншота
                import os
                if os.path.exists(screenshot_path):
                    os.unlink(screenshot_path)

        except Exception as e:
            self.logger.error(f"Ошибка обработки выделенной области для OCR: {e}")
    
    def on_selection_completed_translate(self, x, y, width, height):
        """Обработка завершения выделения для перевода: захват, OCR, перевод и всплывающее окно"""
        try:
            if width > 0 and height > 0:
                self.logger.info(f"Выделена область для перевода: {x}, {y}, {width}, {height}")

                # 1. Захватываем область экрана
                screenshot_path = self.screen_capture.capture_area((x, y, width, height))
                if not screenshot_path:
                    self.logger.error("Не удалось захватить область экрана для перевода")
                    return

                # 2. Распознаём текст (OCR) в захваченной области
                ocr_text = self.ocr_manager.extract_text_from_area(screenshot_path, (0, 0, width, height))
                if not ocr_text:
                    self.logger.warning("OCR не распознал текст в выделенной области для перевода")
                    # Удаляем временный скриншот и выходим
                    import os
                    if os.path.exists(screenshot_path):
                        os.unlink(screenshot_path)
                    return

                # 3. Переводим полученный текст через Google Translate API
                translated_text = self.translator_manager.translate_text(ocr_text)
                if not translated_text:
                    self.logger.warning("Не удалось перевести распознанный текст")
                    # Очистка временного файла
                    import os
                    if os.path.exists(screenshot_path):
                        os.unlink(screenshot_path)
                    return

                # 4. Отображаем перевод во всплывающем окне поверх всех окон
                # Позиция окна будет в левом верхнем углу выделенной области
                self.show_translation_overlay(ocr_text, translated_text, (x, y))

                # 5. Удаляем временный скриншот после использования
                import os
                if os.path.exists(screenshot_path):
                    os.unlink(screenshot_path)
            
        except Exception as e:
            self.logger.error(f"Ошибка обработки выделенной области для перевода: {e}")
    
    def show_translation_overlay(self, original_text, translated_text, position):
        """Показать окно перевода"""
        try:
            # Создаем окно перевода
            translation_window = OverlayTranslationWindow()
            
            # Подключаем сигнал скрытия
            translation_window.hidden.connect(self.on_translation_hidden)
            
            # Показываем перевод
            translation_window.show_translation(original_text, translated_text, position)
            
        except Exception as e:
            self.logger.error(f"Ошибка показа окна перевода: {e}")
    
    def on_translation_hidden(self):
        """Обработка скрытия окна перевода"""
        self.logger.info("Окно перевода скрыто")
    
    def show_settings(self):
        """Показать окно настроек"""
        try:
            if self.settings_window is None:
                self.settings_window = SettingsWindow()
            
            self.settings_window.show()
            
        except Exception as e:
            self.logger.error(f"Ошибка показа окна настроек: {e}")
    
    def show_about(self):
        """Показать информацию о программе"""
        try:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.about(
                None,
                "О ScreenText Helper",
                "ScreenText Helper v1.0\n\n"
                "Приложение для захвата области экрана,\n"
                "распознавания текста (OCR) и перевода.\n\n"
                "Горячие клавиши:\n"
                "Ctrl+Alt+S - Распознать текст\n"
                "Ctrl+Alt+T - Перевести текст"
            )
        except Exception as e:
            self.logger.error(f"Ошибка показа информации о программе: {e}")
    
    def quit_application(self):
        """Завершение работы приложения"""
        try:
            self.logger.info("Завершение работы приложения")
            
            # Останавливаем горячие клавиши
            self.hotkey_manager.stop_listening()
            
            # Скрываем все окна
            if self.settings_window:
                self.settings_window.close()
            
            # Завершаем приложение
            self.app.quit()
            
        except Exception as e:
            self.logger.error(f"Ошибка завершения работы приложения: {e}")
    
    def on_settings_saved(self):
        """Обработка сохранения настроек"""
        try:
            self.logger.info("Настройки сохранены")
            
            # Перезагружаем горячие клавиши с новыми настройками
            self.hotkey_manager.unregister_all_hotkeys()
            self.register_hotkeys()
            
        except Exception as e:
            self.logger.error(f"Ошибка перезагрузки горячих клавиш: {e}")
    
    def run(self):
        """Запуск приложения"""
        try:
            if self.initialize_application():
                self.is_running = True
                self.logger.info("Приложение запущено")
                return self.app.exec()
            else:
                self.logger.error("Не удалось инициализировать приложение")
                return 1
                
        except Exception as e:
            self.logger.error(f"Ошибка запуска приложения: {e}")
            return 1


def main():
    """Главная функция запуска приложения"""
    app = ScreenTextHelper()
    return app.run()


if __name__ == "__main__":
    sys.exit(main())