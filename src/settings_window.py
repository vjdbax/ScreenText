#!/usr/bin/env python3
"""
Settings window implementation for ScreenText Helper
"""

import sys
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QComboBox, QCheckBox, QDialog, QGroupBox,
    QSpinBox, QColorDialog, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from settings import settings


class SettingsWindow(QDialog):
    """Окно настроек приложения"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки ScreenText Helper")
        self.setWindowIcon(QIcon("assets/icon.png"))
        self.setFixedSize(400, 500)
        self.setup_ui()
        
    def setup_ui(self):
        """Настройка интерфейса окна настроек"""
        layout = QVBoxLayout()
        
        # Горячие клавиши
        hotkeys_group = QGroupBox("Горячие клавиши")
        hotkeys_layout = QVBoxLayout()
        
        # OCR горячая клавиша
        ocr_layout = QHBoxLayout()
        ocr_layout.addWidget(QLabel("OCR (Распознавание текста):"))
        self.ocr_hotkey_input = QLineEdit(settings.get_hotkey("ocr"))
        self.ocr_hotkey_input.setReadOnly(True)
        ocr_layout.addWidget(self.ocr_hotkey_input)
        self.ocr_hotkey_btn = QPushButton("Изменить")
        self.ocr_hotkey_btn.clicked.connect(lambda: self.set_hotkey("ocr"))
        ocr_layout.addWidget(self.ocr_hotkey_btn)
        hotkeys_layout.addLayout(ocr_layout)
        
        # Перевод горячая клавиша
        translate_layout = QHBoxLayout()
        translate_layout.addWidget(QLabel("Перевод текста:"))
        self.translate_hotkey_input = QLineEdit(settings.get_hotkey("translate"))
        self.translate_hotkey_input.setReadOnly(True)
        translate_layout.addWidget(self.translate_hotkey_input)
        self.translate_hotkey_btn = QPushButton("Изменить")
        self.translate_hotkey_btn.clicked.connect(lambda: self.set_hotkey("translate"))
        translate_layout.addWidget(self.translate_hotkey_btn)
        hotkeys_layout.addLayout(translate_layout)
        
        hotkeys_group.setLayout(hotkeys_layout)
        layout.addWidget(hotkeys_group)
        
        # Языки
        languages_group = QGroupBox("Языки")
        languages_layout = QVBoxLayout()
        
        # Язык OCR
        ocr_lang_layout = QHBoxLayout()
        ocr_lang_layout.addWidget(QLabel("Язык распознавания:"))
        self.ocr_lang_combo = QComboBox()
        self.ocr_lang_combo.addItems(["rus", "eng", "rus+eng"])
        self.ocr_lang_combo.setCurrentText(settings.get_ocr_language())
        ocr_lang_layout.addWidget(self.ocr_lang_combo)
        languages_layout.addLayout(ocr_lang_layout)
        
        # Целевой язык перевода
        translate_lang_layout = QHBoxLayout()
        translate_lang_layout.addWidget(QLabel("Целевой язык перевода:"))
        self.translate_lang_combo = QComboBox()
        self.translate_lang_combo.addItems(["en", "ru", "zh", "es", "fr", "de"])
        self.translate_lang_combo.setCurrentText(settings.get_translate_target_language())
        translate_lang_layout.addWidget(self.translate_lang_combo)
        languages_layout.addLayout(translate_lang_layout)
        
        languages_group.setLayout(languages_layout)
        layout.addWidget(languages_group)
        
        # Внешний вид
        appearance_group = QGroupBox("Внешний вид")
        appearance_layout = QVBoxLayout()
        
        # Прозрачность окна выделения
        opacity_layout = QHBoxLayout()
        opacity_layout.addWidget(QLabel("Прозрачность окна:"))
        self.opacity_spin = QSpinBox()
        self.opacity_spin.setRange(10, 90)
        self.opacity_spin.setValue(int(settings.get("window_opacity", 30) * 100))
        self.opacity_spin.setSuffix("%")
        opacity_layout.addWidget(self.opacity_spin)
        appearance_layout.addLayout(opacity_layout)
        
        # Цвет рамки
        border_layout = QHBoxLayout()
        border_layout.addWidget(QLabel("Цвет рамки:"))
        self.border_color_btn = QPushButton()
        self.border_color_btn.setStyleSheet(f"background-color: {settings.get('border_color', '#FF0000')}")
        self.border_color_btn.clicked.connect(self.choose_border_color)
        border_layout.addWidget(self.border_color_btn)
        appearance_layout.addLayout(border_layout)
        
        appearance_group.setLayout(appearance_layout)
        layout.addWidget(appearance_group)
        
        # Поведение
        behavior_group = QGroupBox("Поведение")
        behavior_layout = QVBoxLayout()
        
        # Автозагрузка
        self.auto_start_check = QCheckBox("Автозагрузка при старте Windows")
        self.auto_start_check.setChecked(settings.get_auto_start())
        behavior_layout.addWidget(self.auto_start_check)
        
        behavior_group.setLayout(behavior_layout)
        layout.addWidget(behavior_group)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        self.save_btn = QPushButton("Сохранить")
        self.save_btn.clicked.connect(self.save_settings)
        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.clicked.connect(self.reject)
        self.reset_btn = QPushButton("Сбросить")
        self.reset_btn.clicked.connect(self.reset_settings)
        
        buttons_layout.addWidget(self.save_btn)
        buttons_layout.addWidget(self.reset_btn)
        buttons_layout.addWidget(self.cancel_btn)
        layout.addLayout(buttons_layout)
        
        self.setLayout(layout)
        
    def set_hotkey(self, action: str):
        """Установка горячей клавиши (заглушка)"""
        # В реальном приложении здесь будет логика захвата горячих клавиш
        QMessageBox.information(self, "Горячие клавиши", 
                               f"Нажмите комбинацию клавиш для {action}")
        
    def choose_border_color(self):
        """Выбор цвета рамки"""
        color = QColorDialog.getColor()
        if color.isValid():
            self.border_color_btn.setStyleSheet(f"background-color: {color.name()}")
            
    def save_settings(self):
        """Сохранение настроек"""
        # Сохраняем горячие клавиши
        settings.set_hotkey("ocr", self.ocr_hotkey_input.text())
        settings.set_hotkey("translate", self.translate_hotkey_input.text())
        
        # Сохраняем языки
        settings.set_ocr_language(self.ocr_lang_combo.currentText())
        settings.set_translate_target_language(self.translate_lang_combo.currentText())
        
        # Сохраняем внешний вид
        settings.set("window_opacity", self.opacity_spin.value() / 100)
        settings.set("border_color", self.border_color_btn.styleSheet().split(": ")[1].replace(";", ""))
        
        # Сохраняем поведение
        settings.set_auto_start(self.auto_start_check.isChecked())
        
        # Сохраняем настройки в файл
        if settings.save_settings():
            QMessageBox.information(self, "Успех", "Настройки успешно сохранены")
            self.accept()
        else:
            QMessageBox.warning(self, "Ошибка", "Не удалось сохранить настройки")
            
    def reset_settings(self):
        """Сброс настроек к значениям по умолчанию"""
        reply = QMessageBox.question(self, "Сброс настроек", 
                                   "Вы уверены, что хотите сбросить все настройки к значениям по умолчанию?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            settings.reset_to_defaults()
            self.setup_ui()  # Обновляем интерфейс


def main():
    """Тестовая функция для запуска окна настроек"""
    app = QApplication(sys.argv)
    
    window = SettingsWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    main()