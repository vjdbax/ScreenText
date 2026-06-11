#!/usr/bin/env python3
"""
Overlay window for ScreenText Helper
"""

import sys
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QApplication
from PyQt6.QtCore import Qt, QTimer, QPoint, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QCursor
import logging
from settings import settings


class SelectionOverlay(QWidget):
    """Окно для выделения области экрана"""
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.setup_window()
        self.selection_start = None
        self.selection_end = None
        self.is_selecting = False
        
    def setup_window(self):
        """Настройка окна выделения"""
        # Устанавливаем окно в полноэкранный режим
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.NoDropShadowWindowHint
        )
        
        # Устанавливаем размер экрана
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(0, 0, screen.width(), screen.height())
        
        # Делаем фон полупрозрачным
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Устанавливаем стиль
        self.setStyleSheet("background-color: rgba(0, 0, 0, 100);")
        
        # Отключаем обработку событий мыши для фона
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
    def paintEvent(self, event):
        """Рисование рамки выделения"""
        if self.selection_start and self.selection_end:
            painter = QPainter(self)
            
            # Получаем цвет рамки из настроек
            border_color = settings.get("border_color", "#FF0000")
            color = QColor(border_color)
            
            # Устанавливаем толщину линии
            pen = QPen(color, 2)
            painter.setPen(pen)
            
            # Рассчитываем координаты прямоугольника
            x = min(self.selection_start.x(), self.selection_end.x())
            y = min(self.selection_start.y(), self.selection_end.y())
            width = abs(self.selection_end.x() - self.selection_start.x())
            height = abs(self.selection_end.y() - self.selection_start.y())
            
            # Рисуем прямоугольник
            painter.drawRect(x, y, width, height)
            
            # Рисуем углы прямоугольника для лучшей видимости
            corner_size = 10
            painter.fillRect(x, y, corner_size, corner_size, color)
            painter.fillRect(x + width - corner_size, y, corner_size, corner_size, color)
            painter.fillRect(x, y + height - corner_size, corner_size, corner_size, color)
            painter.fillRect(x + width - corner_size, y + height - corner_size, corner_size, corner_size, color)
    
    def mousePressEvent(self, event):
        """Обработка нажатия мыши"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.selection_start = event.pos()
            self.selection_end = event.pos()
            self.is_selecting = True
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            self.update()
    
    def mouseMoveEvent(self, event):
        """Обработка движения мыши"""
        if self.is_selecting:
            self.selection_end = event.pos()
            self.update()
    
    def mouseReleaseEvent(self, event):
        """Обработка отпускания кнопки мыши"""
        if event.button() == Qt.MouseButton.LeftButton and self.is_selecting:
            self.selection_end = event.pos()
            self.is_selecting = False
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            
            # Получаем координаты выделенной области
            x = min(self.selection_start.x(), self.selection_end.x())
            y = min(self.selection_start.y(), self.selection_end.y())
            width = abs(self.selection_end.x() - self.selection_start.x())
            height = abs(self.selection_end.y() - self.selection_start.y())
            
            # Закрываем окно и возвращаем результат
            self.selection_made.emit(x, y, width, height)
            self.close()
    
    # Сигнал о завершении выделения
    selection_made = pyqtSignal(int, int, int, int)
    
    def closeEvent(self, event):
        """Обработка закрытия окна"""
        self.selection_made.emit(0, 0, 0, 0)  # Сигнал о отмене
        super().closeEvent(event)


class TranslationOverlay(QWidget):
    """Окно для отображения перевода поверх экрана"""
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.setup_window()
        
    def setup_window(self):
        """Настройка окна перевода"""
        # Устанавливаем флаги окна
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.NoDropShadowWindowHint
        )
        
        # Устанавливаем размер
        self.setFixedSize(300, 150)
        
        # Делаем фон полупрозрачным
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Создаем виджеты
        self.setup_ui()
        
    def setup_ui(self):
        """Настройка интерфейса"""
        layout = QVBoxLayout()
        
        # Метка с исходным текстом
        self.original_label = QLabel("Исходный текст:")
        self.original_label.setStyleSheet("color: white; font-size: 12px;")
        layout.addWidget(self.original_label)
        
        # Метка с переводом
        self.translation_label = QLabel("Перевод:")
        self.translation_label.setStyleSheet("color: yellow; font-size: 14px; font-weight: bold;")
        layout.addWidget(self.translation_label)
        
        # Кнопка копирования
        self.copy_button = QPushButton("Копировать перевод")
        self.copy_button.clicked.connect(self.copy_translation)
        layout.addWidget(self.copy_button)
        
        self.setLayout(layout)
        
    def show_translation(self, original_text: str, translated_text: str, position: QPoint):
        """Показать перевод"""
        self.original_label.setText(f"Исходный текст: {original_text}")
        self.translation_label.setText(f"Перевод: {translated_text}")
        
        # Устанавливаем позицию
        self.move(position)
        
        # Показываем окно
        self.show()
        
        # Автоматическое скрытие через время (из настроек)
        duration = settings.get("translate_window_duration", 5000)
        QTimer.singleShot(duration, self.hide)
        
    def hideEvent(self, event):
        """Обработка скрытия окна"""
        self.hidden.emit()
        super().hideEvent(event)
        
    def copy_translation(self):
        """Копировать перевод в буфер обмена"""
        import pyperclip
        pyperclip.copy(self.translation_label.text().replace("Перевод: ", ""))
        
    # Сигналы
    hidden = pyqtSignal()
    
    def closeEvent(self, event):
        """Обработка закрытия окна"""
        self.hidden.emit()
        super().closeEvent(event)


def main():
    """Тестовая функция для демонстрации окон наложения"""
    app = QApplication(sys.argv)
    
    # Тестируем окно выделения
    selection_overlay = SelectionOverlay()
    selection_overlay.show()
    
    # Тестируем окно перевода
    translation_overlay = TranslationOverlay()
    translation_overlay.show_translation(
        "Hello, world!",
        "Привет, мир!",
        QPoint(100, 100)
    )
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()