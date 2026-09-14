#!/usr/bin/env encoding
import sys
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QApplication, QFrame
from PyQt6.QtCore import Qt, QTimer, QPoint, pyqtSignal, QRect
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QCursor, QBrush, QTextDocument
import logging
from settings import settings

class TranslationOverlay(QWidget):
    hidden = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.drag_position = None  
        self.is_showing_original = False
        self.base_html_text = ""       
        self.original_base_html = ""   
        self.initial_width = 450
        self.manual_scale = 1.0        
        self.setup_window()
        
    def setup_window(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        
        bg_color = settings.get("bg_color", "#FFFFFF")
        border_color = settings.get("border_color", "#555555")
        font_color = settings.get("font_color", "#000000")
        self.setWindowOpacity(settings.get("window_opacity", 0.95))
        
        self.container_widget = QFrame(self)
        self.container_widget.setObjectName("ContainerWidget")
        self.container_widget.setStyleSheet(f"""
            QFrame#ContainerWidget {{ background-color: {bg_color}; border: 2px solid {border_color}; border-radius: 8px; }}
            QLabel {{ background: transparent; border: none; color: {font_color}; }}
            QPushButton#close_btn {{ background: transparent; color: {font_color}; border: none; font-size: 18px; font-weight: bold; }}
            QPushButton#close_btn:hover {{ background-color: #FF4D4D; color: white; border-radius: 4px; }}
            QPushButton#action_btn, QPushButton#scale_btn {{ 
                background-color: rgba(120, 120, 120, 30); 
                color: {font_color}; 
                border: 1px solid rgba(120, 120, 120, 50); 
                border-radius: 5px; padding: 5px 10px; font-size: 10px; font-weight: bold; 
            }}
            QPushButton#action_btn:hover, QPushButton#scale_btn:hover {{ background-color: rgba(120, 120, 120, 60); }}
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.container_widget)
        
        self.cont_layout = QVBoxLayout(self.container_widget)
        self.cont_layout.setContentsMargins(15, 30, 15, 15)
        
        self.translation_label = QLabel()
        self.translation_label.setWordWrap(True)
        self.translation_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.cont_layout.addWidget(self.translation_label)
        self.cont_layout.addStretch()
        
        btns = QHBoxLayout()
        self.original_button = QPushButton("Оригинал", objectName="action_btn", clicked=self.toggle_original)
        self.copy_button = QPushButton("Копировать", objectName="action_btn", clicked=self.copy_translation)
        self.dec_btn = QPushButton("А-", objectName="scale_btn", clicked=self.decrease_font)
        self.inc_btn = QPushButton("А+", objectName="scale_btn", clicked=self.increase_font)
        btns.addWidget(self.original_button); btns.addWidget(self.dec_btn); btns.addWidget(self.inc_btn); btns.addWidget(self.copy_button)
        self.cont_layout.addLayout(btns)
        
        self.close_button = QPushButton("×", self, objectName="close_btn", clicked=self.close)
        self.close_button.setFixedSize(28, 28)
        self.ai_info_label = QLabel("", self)
        self.ai_info_label.setStyleSheet("color: rgba(128, 128, 128, 200); font-size: 9px; font-weight: bold; font-style: italic;")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.close_button.move(self.width() - 32, 4)
        self.ai_info_label.setGeometry(12, 8, self.width() - 50, 15)
        self.update_scaled_text()
        
    def update_scaled_text(self):
        if self.base_html_text:
            total_scale = (self.width() / self.initial_width) * self.manual_scale
            active_base = self.original_base_html if self.is_showing_original else self.base_html_text
            def repl(m): return f'font-size:{max(6, int(float(m.group(1)) * total_scale))}pt'
            import re
            self.translation_label.setText(re.sub(r'font-size\s*:\s*([\d.]+)pt', repl, active_base))
            
    def increase_font(self): self.manual_scale += 0.1; self.adjust_overlay_size()
    def decrease_font(self): self.manual_scale = max(0.4, self.manual_scale - 0.1); self.adjust_overlay_size()
    def toggle_original(self):
        self.is_showing_original = not self.is_showing_original
        self.original_button.setText("Перевод" if self.is_showing_original else "Оригинал")
        self.update_scaled_text(); self.adjust_overlay_size()
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and self.drag_position:
            self.move(event.globalPosition().toPoint() - self.drag_position); event.accept()
    def mouseReleaseEvent(self, event): self.drag_position = None; event.accept()
        
    def show_translation(self, orig, trans, pos, size=None, orig_h=None, model_name=None):
        self.base_html_text = trans
        self.original_base_html = orig_h if orig_h else orig
        
        # ЛОГИКА ОТОБРАЖЕНИЯ МОДЕЛИ
        if model_name:
            short_model = model_name.split('/')[-1]
            self.ai_info_label.setText(f"✨ ИИ: {short_model}")
        else:
            self.ai_info_label.setText("🌐 Стандартный перевод")
        
        target_w = max(450, size[0] if size else 450)
        self.initial_width = target_w
        self.resize(target_w, 150)
        
        if isinstance(pos, QPoint): self.move(pos)
        self.update_scaled_text()
        self.show()
        QTimer.singleShot(50, self.adjust_overlay_size)
        
    def adjust_overlay_size(self):
        self.translation_label.adjustSize()
        doc = QTextDocument()
        doc.setHtml(self.translation_label.text())
        doc.setTextWidth(self.width() - 30)
        new_height = int(doc.size().height()) + 110
        final_h = max(160, new_height)
        curr_geom = self.geometry()
        diff = final_h - curr_geom.height()
        self.setGeometry(curr_geom.left(), curr_geom.top() - diff, curr_geom.width(), final_h)

    def copy_translation(self):
        import pyperclip, re
        text = re.sub('<[^<]+?>', '', self.translation_label.text().replace('</p>', '\n\n').replace('</h1>', '\n\n')).strip()
        pyperclip.copy(text)

class StartupLoaderWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.angle = 0
        self.is_loaded = False
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        screen = QApplication.primaryScreen().geometry()
        self.resize(310, 80)
        self.move(screen.width() - 330, screen.height() - 130)
        layout = QHBoxLayout(self); layout.setContentsMargins(15, 10, 15, 10)
        self.icon_placeholder = QWidget(); self.icon_placeholder.setFixedSize(40, 40)
        layout.addWidget(self.icon_placeholder)
        text_layout = QVBoxLayout(); text_layout.setSpacing(2)
        self.title_label = QLabel("ScreenText Helper")
        self.title_label.setStyleSheet("color: white; font-weight: bold; font-size: 13px;")
        self.status_label = QLabel("Подготовка...")
        self.status_label.setStyleSheet("color: #BBBBBB; font-size: 11px;")
        text_layout.addWidget(self.title_label); text_layout.addWidget(self.status_label)
        layout.addLayout(text_layout)
        self.timer = QTimer(self); self.timer.timeout.connect(self.rotate); self.timer.start(16)
    def rotate(self): self.angle = (self.angle + 6) % 360; self.update()
    def set_text(self, title, status): self.title_label.setText(title); self.status_label.setText(status); self.show()
    def set_loaded(self, status_text="Готов к работе! 👍"):
        self.is_loaded = True; self.timer.stop(); self.status_label.setText(status_text)
        self.status_label.setStyleSheet("color: #007ACC; font-weight: bold;"); self.update()
        QTimer.singleShot(2500, self.close)
    def paintEvent(self, event):
        painter = QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor(25, 25, 25, 230))); painter.setPen(QPen(QColor(80, 80, 80, 200), 2))
        painter.drawRoundedRect(1, 1, self.width()-2, self.height()-2, 8, 8)
        cx, cy, r = 35, 40, 14
        if not self.is_loaded:
            painter.setPen(QPen(QColor(60, 60, 60, 150), 3)); painter.drawEllipse(QPoint(cx, cy), r, r)
            painter.setPen(QPen(QColor(0, 120, 215), 3)); painter.drawArc(cx-r, cy-r, r*2, r*2, -self.angle*16, 110*16)
        else:
            painter.setPen(QPen(QColor(0, 122, 204), 4)); painter.drawLine(cx-8, cy, cx-2, cy+6); painter.drawLine(cx-2, cy+6, cx+8, cy-6)