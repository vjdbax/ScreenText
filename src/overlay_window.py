#!/usr/bin/env encoding
import sys
import re
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout,
    QApplication, QFrame, QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QPoint, pyqtSignal, QRect, QPropertyAnimation, QEasingCurve, QEvent
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
        self.original_base_text = ""
        self.initial_width = 450
        self.manual_scale = 1.0
        self.text_formatter = None

        self._stream_buffer = []
        self._stream_resize_timer = QTimer(self)
        self._stream_resize_timer.setSingleShot(True)
        self._stream_resize_timer.timeout.connect(self._debounced_stream_resize)
        self._is_streaming = False

        self._fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self._fade_animation.setDuration(200)
        self._fade_animation.setEasingCurve(QEasingCurve.Type.InQuad)

        self.setup_window()

    def setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.NoDropShadowWindowHint
        )
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
            QScrollArea {{ border: none; background: transparent; }}
            QScrollBar:vertical {{
                width: 4px;
                background: transparent;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(120, 120, 120, 80);
                min-height: 30px;
                border-radius: 2px;
            }}
            QScrollBar::handle:vertical:hover {{ background: rgba(120, 120, 120, 160); }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; background: none; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
            QScrollBar:horizontal {{ height: 0px; }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.container_widget)

        cont_layout = QVBoxLayout(self.container_widget)
        cont_layout.setContentsMargins(15, 8, 15, 10)
        cont_layout.setSpacing(6)

        # ── Header ──────────────────────────────────────────────────
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(4)
        self.ai_info_label = QLabel("")
        self.ai_info_label.setStyleSheet(
            "color: rgba(128, 128, 128, 200); font-size: 9px; font-weight: bold; font-style: italic;"
        )
        self.close_button = QPushButton("×", objectName="close_btn", clicked=self.close)
        self.close_button.setFixedSize(28, 28)
        header.addWidget(self.ai_info_label, 1)
        header.addStretch()
        header.addWidget(self.close_button)
        cont_layout.addLayout(header)

        # ── Center: ScrollArea with text ────────────────────────────
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.translation_label = QLabel()
        self.translation_label.setWordWrap(True)
        self.translation_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.translation_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self.scroll_area.setWidget(self.translation_label)
        cont_layout.addWidget(self.scroll_area, 1)

        # ── Footer: buttons ─────────────────────────────────────────
        btns = QHBoxLayout()
        btns.setContentsMargins(0, 0, 0, 0)
        btns.setSpacing(6)
        self.original_button = QPushButton("Оригинал", objectName="action_btn", clicked=self.toggle_original)
        self.copy_button = QPushButton("Копировать", objectName="action_btn", clicked=self.copy_translation)
        self.dec_btn = QPushButton("А-", objectName="scale_btn", clicked=self.decrease_font)
        self.inc_btn = QPushButton("А+", objectName="scale_btn", clicked=self.increase_font)
        btns.addWidget(self.original_button)
        btns.addWidget(self.dec_btn)
        btns.addWidget(self.inc_btn)
        btns.addWidget(self.copy_button)
        cont_layout.addLayout(btns)

    # ── Resize ──────────────────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_scaled_text()

    def adjust_overlay_size(self):
        """Подгонка высоты окна под содержимое через QTextDocument."""
        if not self.translation_label.text().strip():
            return

        doc = QTextDocument()
        doc.setDefaultStyleSheet(self.container_widget.styleSheet())
        doc.setHtml(self.translation_label.text())
        available_width = self.container_widget.width() - 30
        doc.setTextWidth(max(200, available_width))

        content_height = int(doc.size().height())
        chrome_height = 120
        needed_total_height = content_height + chrome_height

        screen = QApplication.screenAt(self.pos()) or QApplication.primaryScreen()
        max_allowed_h = int(screen.availableGeometry().height() * 0.75)

        final_height = max(180, min(needed_total_height, max_allowed_h))

        geom = self.geometry()
        screen_bottom = screen.availableGeometry().bottom()
        if geom.top() + final_height > screen_bottom:
            new_top = max(screen.availableGeometry().top(), screen_bottom - final_height - 10)
            self.setGeometry(geom.left(), new_top, geom.width(), final_height)
        else:
            self.resize(geom.width(), final_height)

    # ── Text display ────────────────────────────────────────────────

    def update_scaled_text(self):
        if not self.base_html_text:
            return

        base_pt = settings.get("font_size_p", 11)
        if not isinstance(base_pt, (int, float)) or base_pt <= 0:
            base_pt = 11
        scale = getattr(self, 'manual_scale', 1.0)
        if not isinstance(scale, (int, float)) or scale <= 0:
            scale = 1.0
        current_pt = max(8, int(base_pt * scale))
        title_pt = current_pt + 3
        font_color = settings.get("font_color", "#FFFFFF")

        if self.is_showing_original:
            active_base = self.original_base_html if self.original_base_html else (
                self._fallback_format_html(self.original_base_text) if self.original_base_text else ""
            )
            if not active_base:
                active_base = (
                    f'<p style="color:gray; font-style:italic;">Оригинальный текст недоступен</p>'
                )
        else:
            active_base = self.base_html_text

        clean_html = re.sub(r'font-size\s*:\s*[^;"]+[;]?', '', active_base)

        styled_html = f"""<style>
    h1, h2 {{ font-family: 'Segoe UI', Arial, sans-serif; font-size: {title_pt}pt; font-weight: bold; color: {font_color}; margin-bottom: 6px; }}
    p {{ font-family: 'Segoe UI', Arial, sans-serif; font-size: {current_pt}pt; color: {font_color}; line-height: 140%; margin-bottom: 6px; }}
</style>
<div>{clean_html}</div>"""

        self.translation_label.setText(styled_html)

        sb = self.scroll_area.verticalScrollBar()
        if sb:
            sb.setValue(0)
        self.adjust_overlay_size()

    def increase_font(self):
        self.manual_scale += 0.1
        self.update_scaled_text()

    def decrease_font(self):
        self.manual_scale = max(0.4, self.manual_scale - 0.1)
        self.update_scaled_text()

    # ── Original text ───────────────────────────────────────────────

    def set_original_text(self, raw_orig: str, html_orig: str):
        if html_orig and html_orig.strip():
            self.original_base_html = html_orig
        elif raw_orig and raw_orig.strip():
            self.original_base_html = self.text_formatter.format_to_book_html(raw_orig) if hasattr(self, 'text_formatter') and self.text_formatter else self._fallback_format_html(raw_orig)
        if raw_orig and raw_orig.strip():
            self.original_base_text = raw_orig

    def _fallback_format_html(self, text: str) -> str:
        if not text or not text.strip():
            return ""
        paragraphs = text.split("\n\n")
        parts = []
        for p in paragraphs:
            p = p.strip()
            if p:
                parts.append(f'<p>{p}</p>')
        return "".join(parts)

    def toggle_original(self):
        self.is_showing_original = not self.is_showing_original
        self.original_button.setText("Перевод" if self.is_showing_original else "Оригинал")
        self.update_scaled_text()

    def _get_provider_label(self, base_url):
        if not base_url:
            return ""
        url = base_url.lower()
        if "localhost" in url or "127.0.0.1" in url:
            return "🖥️ Локальная"
        if "groq" in url:
            return "⚡ Groq Cloud"
        if "openrouter" in url:
            return "🌐 OpenRouter"
        if "openai" in url:
            return "🟢 OpenAI"
        if "deepseek" in url:
            return "🔵 DeepSeek"
        if "trycloudflare" in url or ":" in url.replace("https://", "").replace("http://", ""):
            return "☁️ Удаленный сервер"
        return "🔗 Сервер"

    # ── Streaming ───────────────────────────────────────────────────

    def start_stream(self):
        self._stream_buffer = []
        self._is_streaming = True
        self.base_html_text = ""
        self.original_base_html = ""
        self.translation_label.setText("")

    def append_stream_token(self, text: str):
        if not self._is_streaming:
            return

        self._stream_buffer = [text]

        paragraphs = text.split('\n')
        html_parts = []
        for p in paragraphs:
            p = p.strip()
            if p:
                html_parts.append(f'<p>{p}</p>')

        html_text = ''.join(html_parts) if html_parts else '<p>...</p>'

        self.base_html_text = html_text
        self.update_scaled_text()

        if not self._stream_resize_timer.isActive():
            self._stream_resize_timer.start(150)

    def _debounced_stream_resize(self):
        if self._is_streaming and self.base_html_text:
            self.adjust_overlay_size()

    def finish_stream(self, final_trans_html=None, orig_html=None):
        self._is_streaming = False
        self._stream_resize_timer.stop()

        if final_trans_html:
            self.base_html_text = final_trans_html
        if orig_html:
            self.original_base_html = orig_html

        self.is_showing_original = False
        self.original_button.setText("Оригинал")

        if self.base_html_text:
            self.update_scaled_text()
            self.adjust_overlay_size()

    # ── Show methods ────────────────────────────────────────────────

    def show_error(self, error_text: str):
        html = f'<p style="color:#E06C75;">❌ Ошибка: {error_text}</p>'
        self.base_html_text = html
        self.translation_label.setText(html)
        self.adjust_overlay_size()

    def show_streaming(self, pos, size=None, model_name=None, base_url=None):
        self.is_showing_original = False
        self.original_button.setText("Оригинал")
        if model_name:
            short_model = model_name.split('/')[-1]
            prefix = self._get_provider_label(base_url)
            self.ai_info_label.setText(f"{prefix}: {short_model}" if prefix else f"✨ ИИ: {short_model}")
        else:
            self.ai_info_label.setText("🌐 Стриминг...")

        target_w = max(450, size[0] if size else 450)
        self.initial_width = target_w
        self.resize(target_w, 180)

        if isinstance(pos, QPoint):
            self.move(pos)

        self.start_stream()
        self.show()
        self.raise_()
        self.activateWindow()

    def show_translation(self, orig, trans, pos, size=None, orig_h=None, model_name=None, base_url=None):
        self.is_showing_original = False
        self.original_button.setText("Оригинал")
        self.base_html_text = trans
        self.original_base_html = orig_h if orig_h else orig

        if model_name:
            short_model = model_name.split('/')[-1]
            prefix = self._get_provider_label(base_url)
            self.ai_info_label.setText(f"{prefix}: {short_model}" if prefix else f"✨ ИИ: {short_model}")
        else:
            self.ai_info_label.setText("🌐 Стандартный перевод")

        target_w = max(450, size[0] if size else 450)
        self.initial_width = target_w
        self.resize(target_w, 180)

        if isinstance(pos, QPoint):
            self.move(pos)
        self.update_scaled_text()
        self.show()
        self.raise_()
        self.activateWindow()
        QTimer.singleShot(50, self.adjust_overlay_size)

    # ── Mouse ───────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and self.drag_position:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.drag_position = None
        event.accept()

    # ── Actions ─────────────────────────────────────────────────────

    def copy_translation(self):
        import pyperclip
        text = re.sub('<[^<]+?>', '', self.translation_label.text().replace('</p>', '\n\n').replace('</h1>', '\n\n')).strip()
        pyperclip.copy(text)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.animated_close()
        else:
            super().keyPressEvent(event)

    def changeEvent(self, event):
        super().changeEvent(event)

    def animated_close(self):
        self._fade_animation.stop()
        self._fade_animation.setStartValue(self.windowOpacity())
        self._fade_animation.setEndValue(0.0)
        self._fade_animation.finished.connect(self._on_fade_finished)
        self._fade_animation.start()

    def _on_fade_finished(self):
        try:
            self._fade_animation.finished.disconnect(self._on_fade_finished)
        except TypeError:
            pass
        self.hide()
        self.setWindowOpacity(settings.get("window_opacity", 0.95))
        self.hidden.emit()


class StartupLoaderWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.angle = 0
        self.is_loaded = False
        self._on_click_callback = None
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(320, 85)
        layout = QHBoxLayout(self); layout.setContentsMargins(15, 10, 15, 10)
        self.icon_placeholder = QWidget(); self.icon_placeholder.setFixedSize(40, 40)
        layout.addWidget(self.icon_placeholder)
        text_layout = QVBoxLayout(); text_layout.setSpacing(2)
        self.title_label = QLabel("ScreenText Helper")
        self.title_label.setStyleSheet("color: white; font-weight: bold; font-size: 13px;")
        self.status_label = QLabel("Подготовка...")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #BBBBBB; font-size: 11px;")
        text_layout.addWidget(self.title_label); text_layout.addWidget(self.status_label)
        layout.addLayout(text_layout)
        self.timer = QTimer(self); self.timer.timeout.connect(self.rotate); self.timer.start(16)
        self.reposition_to_bottom_right()

    def reposition_to_bottom_right(self):
        cursor_pos = QCursor.pos()
        screen = QApplication.screenAt(cursor_pos) or QApplication.primaryScreen()
        avail = screen.availableGeometry()
        margin = 20
        x = avail.right() - self.width() - margin
        y = avail.bottom() - self.height() - margin
        self.move(x, y)

    def rotate(self): self.angle = (self.angle + 6) % 360; self.update()
    def set_text(self, title, status):
        self.title_label.setText(title); self.status_label.setText(status)
        self.reposition_to_bottom_right()
        self.show()
    def set_loaded(self, status_text="Готов к работе! 👍"):
        self.is_loaded = True; self.timer.stop(); self.status_label.setText(status_text)
        self.status_label.setStyleSheet("color: #007ACC; font-weight: bold;"); self.update()
        self.reposition_to_bottom_right()
        QTimer.singleShot(2500, self.close)
    def show_update_message(self, local_ver, latest_ver, on_click_callback=None):
        self.is_loaded = True
        self.timer.stop()
        self.title_label.setText("ScreenText Helper")
        self.status_label.setText("Доступна новая Ollama. Обновите в Настройках ⚙️")
        self.status_label.setStyleSheet("color: #00A3FF; font-weight: bold; font-size: 11px;")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._on_click_callback = on_click_callback
        self.reposition_to_bottom_right()
        self.show()
        self.raise_()
        self.activateWindow()
        QTimer.singleShot(15000, self.close)
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._on_click_callback:
            cb = self._on_click_callback
            self._on_click_callback = None
            self.close()
            try:
                cb()
            except Exception:
                pass
        else:
            super().mousePressEvent(event)
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
