#!/usr/bin/env python3
"""
Area selector module - реализация выбора области как в Scissors/Ножницах
"""

import sys
import logging
from PyQt6.QtWidgets import QWidget, QApplication, QVBoxLayout, QLabel, QHBoxLayout, QPushButton
from PyQt6.QtCore import Qt, QTimer, QPoint, QRect, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QCursor, QPixmap, QScreen
from PIL import Image, ImageGrab
import tempfile
import os


class AreaSelector(QWidget):
    """
    Окно для выбора области экрана как в Scissors
    Поддерживает:
    - Затемнение всего экрана кроме выделенной области
    - Рисование прямоугольника мышкой
    - Визуальную обратную связь
    - Отмену по Esc
    """
    
    # Сигнал о завершении выбора области
    area_selected = pyqtSignal(tuple)  # (x, y, width, height)
    area_selection_canceled = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.setup_window()
        self.setup_variables()
        
    def setup_window(self):
        """Настройка окна"""
        # Устанавливаем флаги для полноэкранного режима
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
        
        # Включаем обработку событий мыши
        self.setAttribute(Qt.WidgetAttribute.WA_MouseTracking, True)
        
    def setup_variables(self):
        """Инициализация переменных"""
        self.selection_start = None
        self.selection_end = None
        self.is_selecting = False
        self.current_rect = QRect()
        self.screenshot_path = None
        
        # Цвета из настроек
        self.mask_color = QColor(0, 0, 0, 180)  # Полупрозрачный черный
        self.border_color = QColor(255, 0, 0)    # Красная рамка
        self.border_width = 2
        self.corner_size = 10
        
    def capture_screen(self):
        """Захватываем весь экран как фон"""
        try:
            # Делаем скриншот всего экрана
            screenshot = ImageGrab.grab()
            
            # Сохраняем во временный файл
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                screenshot.save(temp_file.name)
                self.screenshot_path = temp_file.name
            
            self.logger.info(f"Скриншот экрана сохранен: {self.screenshot_path}")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка захвата экрана: {e}")
            return False
    
    def paintEvent(self, event):
        """Рисование интерфейса"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 1. Рисуем фон (скриншот)
        if self.screenshot_path and os.path.exists(self.screenshot_path):
            pixmap = QPixmap(self.screenshot_path)
            painter.drawPixmap(0, 0, pixmap)
        
        # 2. Рисуем затемнение (маску)
        if self.selection_start and self.selection_end:
            # Рассчитываем прямоугольник выделения
            selection_rect = QRect(
                min(self.selection_start.x(), self.selection_end.x()),
                min(self.selection_start.y(), self.selection_end.y()),
                abs(self.selection_end.x() - self.selection_start.x()),
                abs(self.selection_end.y() - self.selection_start.y())
            )
            
            # Рисуем черную маску с отверстием для выделенной области
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self.mask_color)
            
            # Рисуем верхнюю часть маски
            painter.drawRect(0, 0, self.width(), selection_rect.top())
            
            # Рисуем левую часть маски
            painter.drawRect(0, selection_rect.top(), selection_rect.left(), selection_rect.height())
            
            # Рисуем правую часть маски
            painter.drawRect(selection_rect.right(), selection_rect.top(), 
                          self.width() - selection_rect.right(), selection_rect.height())
            
            # Рисуем нижнюю часть маски
            painter.drawRect(0, selection_rect.bottom(), self.width(), 
                          self.height() - selection_rect.bottom())
            
            # 3. Рисуем рамку выделенной области
            painter.setPen(QPen(self.border_color, self.border_width))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(selection_rect)
            
            # 4. Рисуем углы прямоугольника для лучшей видимости
            painter.setBrush(self.border_color)
            
            # Левый верхний угол
            painter.drawRect(selection_rect.left(), selection_rect.top(), 
                           self.corner_size, self.corner_size)
            
            # Правый верхний угол  
            painter.drawRect(selection_rect.right() - self.corner_size, selection_rect.top(),
                           self.corner_size, self.corner_size)
            
            # Левый нижний угол
            painter.drawRect(selection_rect.left(), selection_rect.bottom() - self.corner_size,
                           self.corner_size, self.corner_size)
            
            # Правый нижний угол
            painter.drawRect(selection_rect.right() - self.corner_size, selection_rect.bottom() - self.corner_size,
                           self.corner_size, self.corner_size)
            
            # 5. Рисуем информацию о размере
            self.draw_size_info(painter, selection_rect)
    
    def draw_size_info(self, painter, rect):
        """Рисование информации о размере выделенной области"""
        try:
            # Создаем текст с размерами
            width = rect.width()
            height = rect.height()
            size_text = f"{width} × {height}"
            
            # Устанавливаем шрифт
            font = QFont("Arial", 12, QFont.Weight.Bold)
            painter.setFont(font)
            
            # Рассчитываем позицию для текста (в центре прямоугольника)
            text_rect = QRect(rect.left() + 10, rect.top() + 10, rect.width() - 20, 30)
            
            # Рисуем фон для текста
            painter.setBrush(QColor(0, 0, 0, 180))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(text_rect, 5, 5)
            
            # Рисуем текст
            painter.setPen(QColor(255, 255, 255))  # Белый текст
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, size_text)
            
        except Exception as e:
            self.logger.error(f"Ошибка рисования информации о размере: {e}")
    
    def mousePressEvent(self, event):
        """Обработка нажатия мыши"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.selection_start = event.pos()
            self.selection_end = event.pos()
            self.is_selecting = True
            self.update()
    
    def mouseMoveEvent(self, event):
        """Обработка движения мыши"""
        if self.is_selecting:
            self.selection_end = event.pos()
            self.current_rect = QRect(
                min(self.selection_start.x(), self.selection_end.x()),
                min(self.selection_start.y(), self.selection_end.y()),
                abs(self.selection_end.x() - self.selection_start.x()),
                abs(self.selection_end.y() - self.selection_start.y())
            )
            self.update()
    
    def mouseReleaseEvent(self, event):
        """Обработка отпускания кнопки мыши"""
        if event.button() == Qt.MouseButton.LeftButton and self.is_selecting:
            self.selection_end = event.pos()
            self.is_selecting = False
            
            # Получаем координаты выделенной области
            x = min(self.selection_start.x(), self.selection_end.x())
            y = min(self.selection_start.y(), self.selection_end.y())
            width = abs(self.selection_end.x() - self.selection_start.x())
            height = abs(self.selection_end.y() - self.selection_start.y())
            
            # Проверяем, что область имеет минимальный размер
            if width > 10 and height > 10:
                self.area_selected.emit((x, y, width, height))
            else:
                # Если область слишком маленькая, отменяем выбор
                self.area_selection_canceled.emit()
            
            self.close()
    
    def keyPressEvent(self, event):
        """Обработка нажатия клавиш"""
        if event.key() == Qt.Key.Key_Escape:
            self.area_selection_canceled.emit()
            self.close()
        elif event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            if self.current_rect.isValid() and self.current_rect.width() > 10 and self.current_rect.height() > 10:
                x = self.current_rect.x()
                y = self.current_rect.y()
                width = self.current_rect.width()
                height = self.current_rect.height()
                self.area_selected.emit((x, y, width, height))
                self.close()
    
    def closeEvent(self, event):
        """Обработка закрытия окна"""
        # Очищаем временный файл со скриншотом
        if self.screenshot_path and os.path.exists(self.screenshot_path):
            try:
                os.unlink(self.screenshot_path)
            except:
                pass
        
        # Уведомляем о отмене выбора
        self.area_selection_canceled.emit()
        super().closeEvent(event)
    
    def show_selector(self):
        """Показать селектор области"""
        try:
            # Захватываем экран
            if not self.capture_screen():
                self.logger.error("Не удалось захватить экран")
                return False
            
            # Показываем окно
            self.show()
            self.setFocus()
            
            self.logger.info("Селектор области показан")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка показа селектора области: {e}")
            return False


class AreaSelectorDialog(QWidget):
    """
    Альтернативный вариант селектора области - диалоговое окно
    """
    
    area_selected = pyqtSignal(tuple)
    area_selection_canceled = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.setup_dialog()
        
    def setup_dialog(self):
        """Настройка диалогового окна"""
        self.setWindowTitle("Выбор области")
        self.setFixedSize(400, 200)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint
        )
        
        layout = QVBoxLayout()
        
        # Информация
        info_label = QLabel("Нажмите и удерживайте левую кнопку мыши для выбора области\nили нажмите Esc для отмены")
        info_label.setStyleSheet("font-size: 14px; padding: 20px;")
        layout.addWidget(info_label)
        
        # Кнопки
        button_layout = QHBoxLayout()
        
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.cancel_selection)
        button_layout.addWidget(cancel_btn)
        
        capture_btn = QPushButton("Захватить")
        capture_btn.clicked.connect(self.capture_selected_area)
        button_layout.addWidget(capture_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
        # Переменные для выделения
        self.selection_start = None
        self.selection_end = None
        self.is_selecting = False
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.selection_start = event.pos()
            self.selection_end = event.pos()
            self.is_selecting = True
    
    def mouseMoveEvent(self, event):
        if self.is_selecting:
            self.selection_end = event.pos()
            self.update()
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_selecting:
            self.selection_end = event.pos()
            self.is_selecting = False
            self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        if self.selection_start and self.selection_end:
            rect = QRect(
                min(self.selection_start.x(), self.selection_end.x()),
                min(self.selection_start.y(), self.selection_end.y()),
                abs(self.selection_end.x() - self.selection_start.x()),
                abs(self.selection_end.y() - self.selection_start.y())
            )
            painter.setPen(QPen(QColor(255, 0, 0), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)
    
    def cancel_selection(self):
        self.area_selection_canceled.emit()
        self.close()
    
    def capture_selected_area(self):
        if self.selection_start and self.selection_end:
            x = min(self.selection_start.x(), self.selection_end.x())
            y = min(self.selection_start.y(), self.selection_end.y())
            width = abs(self.selection_end.x() - self.selection_start.x())
            height = abs(self.selection_end.y() - self.selection_start.y())
            
            if width > 10 and height > 10:
                self.area_selected.emit((x, y, width, height))
                self.close()


def main():
    """Тестовая функция для демонстрации селектора области"""
    app = QApplication(sys.argv)
    
    # Создаем и показываем селектор области
    selector = AreaSelector()
    selector.area_selected.connect(lambda area: print(f"Выбрана область: {area}"))
    selector.area_selection_canceled.connect(lambda: print("Выбор области отменен"))
    
    if selector.show_selector():
        print("Селектор области запущен")
    else:
        print("Ошибка запуска селектора области")
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()