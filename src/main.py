#!/usr/bin/env python3
"""
ScreenText Helper - Main application entry point
Windows приложение для захвата области экрана, распознавания текста и перевода
"""

import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from tray_icon import TrayIcon


def main():
    """Главная функция запуска приложения"""
    # Устанавливаем путь к директории приложения
    if getattr(sys, 'frozen', False):
        # Если приложение упаковано в PyInstaller
        application_path = os.path.dirname(sys.executable)
    else:
        # Если запускается как скрипт
        application_path = os.path.dirname(os.path.abspath(__file__))
    
    os.chdir(application_path)
    
    # Создаем экземпляр приложения
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    # Устанавливаем иконку приложения
    app.setWindowIcon(app.style().standardIcon(app.style().StandardPixmap.SP_ComputerIcon))
    
    # Создаем и запускаем иконку в системном трее
    tray_icon = TrayIcon(app)
    tray_icon.show()
    
    # Запускаем главный цикл приложения
    sys.exit(app.exec())


if __name__ == "__main__":
    main()