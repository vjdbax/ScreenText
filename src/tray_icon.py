#!/usr/bin/env python3
import sys
import os
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QMessageBox, QApplication
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import QObject, pyqtSignal
import qtawesome as qta
from settings import settings

class TrayIcon(QSystemTrayIcon):
    show_settings = pyqtSignal()
    show_about = pyqtSignal()
    quit_application = pyqtSignal()
    
    def __init__(self, app):
        try:
            icon = qta.icon('fa5s.language', color='#007ACC')
        except Exception:
            if getattr(sys, 'frozen', False):
                project_root = os.path.dirname(sys.executable)
            else:
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            icon_path = os.path.join(project_root, "assets", "icon.png")
            if os.path.exists(icon_path): icon = QIcon(icon_path)
            else: icon = app.style().standardIcon(app.style().StandardPixmap.SP_ComputerIcon)
                
        super().__init__(icon, app)
        self.app = app
        self.setup_tray_icon()
        
    def setup_tray_icon(self):
        from __init__ import __version__
        self.setToolTip(f"ScreenText Helper v{__version__}")
        menu = QMenu()
        
        # Кнопка быстрой активации ИИ
        self.smart_translate_action = QAction("Умный перевод (ИИ)", self.app)
        self.smart_translate_action.setCheckable(True)
        self.smart_translate_action.setChecked(settings.get("llm.use_smart_translate", False))
        self.smart_translate_action.triggered.connect(self.toggle_smart_translate)
        menu.addAction(self.smart_translate_action)
        
        menu.addSeparator()
        
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
        
        self.setContextMenu(menu)
        self.activated.connect(self.on_tray_icon_activated)
        
    def toggle_smart_translate(self, checked):
        """Быстрое включение/выключение ИИ без захода в настройки"""
        settings.set("llm.use_smart_translate", checked)
        settings.save_settings()
        
    def update_smart_translate_action(self):
        """Обновляет состояние галочки при сохранении настроек из главного меню"""
        self.smart_translate_action.setChecked(settings.get("llm.use_smart_translate", False))
        
    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_settings.emit()