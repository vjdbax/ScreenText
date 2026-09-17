#!/usr/bin/env python3
"""
ScreenText Helper - Main application entry point
Windows приложение для захвата области экрана, распознавания текста и перевода
"""

import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

# Импортируем qtawesome для стильных векторных иконок
import qtawesome as qta
from utils import get_resource_path, get_data_dir


def main():
    """Главная функция запуска приложения"""
    project_root = get_resource_path("")
    os.chdir(project_root)

    # Гарантируем наличие папки assets (в dev — рядом с исходниками)
    assets_dir = get_resource_path("assets")
    os.makedirs(assets_dir, exist_ok=True)
    
    icon_png = os.path.join(assets_dir, "icon.png")
    icon_ico = os.path.join(assets_dir, "icon.ico")
    
    # Создаем экземпляр приложения
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    # Генерация стильной иконки на лету (если файлов нет на диске)
    try:
        icon_theme = qta.icon('fa5s.language', color='#007ACC')
        
        if not os.path.exists(icon_png):
            icon_theme.pixmap(256, 256).save(icon_png, "PNG")
            
        if not os.path.exists(icon_ico):
            icon_theme.pixmap(256, 256).save(icon_ico, "ICO")
            
        app.setWindowIcon(icon_theme)
    except Exception as e:
        if os.path.exists(icon_png):
            app.setWindowIcon(QIcon(icon_png))
        else:
            app.setWindowIcon(app.style().standardIcon(app.style().StandardPixmap.SP_ComputerIcon))
    
    # Импортируем и запускаем трей после настройки путей и генерации иконок
    from tray_icon import TrayIcon
    tray_icon = TrayIcon(app)
    tray_icon.show()
    
    # Запускаем главный цикл приложения
    sys.exit(app.exec())


if __name__ == "__main__":
    main()