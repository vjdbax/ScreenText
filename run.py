#!/usr/bin/env python3
"""
Запуск ScreenText Helper с проверкой на единственную копию
"""

import sys
import os
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QSharedMemory

def main_entry():
    # 1. Рассчитываем корневую директорию проекта и переходим в нее
    if getattr(sys, 'frozen', False):
        project_root = os.path.dirname(sys.executable)
    else:
        project_root = os.path.dirname(os.path.abspath(__file__))

    os.chdir(project_root)

    # 2. Добавляем директорию src в sys.path
    sys.path.insert(0, os.path.join(project_root, 'src'))

    # 3. Принудительно переключаем раскладку на английскую (США) на время работы программы
    # Это критически важно для корректной работы keyboard/pynput/pyautogui
    if os.name == 'nt':
        try:
            import ctypes
            user32 = ctypes.windll.user32
            # Загружаем и активируем английскую раскладку (LCID 0x0409 = en-US)
            user32.LoadKeyboardLayoutW("00000409", 0x0001)
        except Exception:
            pass

    # 4. Настройка ID приложения для корректного отображения иконки в панели задач Windows
    if os.name == 'nt':
        try:
            import ctypes
            myappid = 'screentext.helper.version.1.0'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

    # 5. Создаем экземпляр QApplication (необходим для работы QSharedMemory и диалогов)
    app = QApplication(sys.argv)

    # 6. ПРОВЕРКА НА ЗАПУЩЕННУЮ КОПИЮ
    # Создаем уникальный ключ для нашего приложения
    shared_mem_key = "ScreenTextHelper_Unique_Instance_Key_12345"
    shared_memory = QSharedMemory(shared_mem_key)

    # Пытаемся создать сегмент памяти размером 1 байт
    # Если сегмент уже существует (create вернет False), значит приложение уже запущено
    if not shared_memory.create(1):
        # Показываем предупреждение пользователю
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("ScreenText Helper")
        msg.setText("Приложение уже запущено.")
        msg.setInformativeText("Проверьте иконку в системном трее (возле часов).")
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        
        # Пытаемся сделать окно стильным (темным), если это возможно
        msg.setStyleSheet("background-color: #1E1E1E; color: #CCCCCC; QPushButton { background-color: #2D2D2D; color: white; padding: 5px; min-width: 60px; }")
        
        msg.exec()
        sys.exit(0)

    # 7. Если проверка пройдена, импортируем и запускаем основное приложение
    try:
        from main_app import ScreenTextHelper
        helper = ScreenTextHelper()
        if helper.initialize_application():
            return app.exec()
    except Exception as e:
        print(f"Критическая ошибка при запуске: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main_entry())