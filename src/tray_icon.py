#!/usr/bin/env python3
"""
System tray icon implementation for ScreenText Helper
"""

import sys
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QMessageBox
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import QObject, pyqtSignal


class TrayIcon(QSystemTrayIcon):
    """Класс для создания и управления иконкой в системном трее"""
    
    # Сигналы для взаимодействия с основным приложением
    show_settings = pyqtSignal()
    show_about = pyqtSignal()
    quit_application = pyqtSignal()
    
    def __init__(self, app):
        """Инициализация иконки в системном трее"""
        super().__init__(app.style().standardIcon(app.style().StandardPixmap.SP_ComputerIcon), app)
        
        self.app = app
        self.setup_tray_icon()
        
    def setup_tray_icon(self):
        """Настройка иконки и контекстного меню"""
        # Устанавливаем подсказку
        self.setToolTip("ScreenText Helper")
        
        # Создаем контекстное меню
        menu = QMenu()
        
        # Добавляем действия в меню
        settings_action = QAction("Настройки", self.app)
        settings_action.triggered.connect(self.show_settings.emit)
        menu.addAction(settings_action)
        
        about_action = QAction("О программе", self.app)
        about_action.triggered.connect(self.show_about.emit)
        menu.addAction(about_action)
        
        menu.addSeparator()
        
        quit_action = QAction("Выход", self.app)
        quit_action.triggered.connect(self.quit_application.emit)
        menu.addAction(quit_action)
        
        # Устанавливаем меню для иконки
        self.setContextMenu(menu)
        
        # Подключаем обработчик двойного клика (необязательно)
        self.activated.connect(self.on_tray_icon_activated)
        
    def on_tray_icon_activated(self, reason):
        """Обработка активации иконки (двойной клик, правый клик и т.д.)"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            # При двойном клике можно показывать окно настроек или другую информацию
            pass


def main():
    """Тестовая функция для запуска только системного трея"""
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    tray_icon = TrayIcon(app)
    tray_icon.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()