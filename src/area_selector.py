#!/usr/bin/env python3
"""
Multi-screen area selector — one overlay widget per monitor.

Architecture (like Lightshot / ShareX):
  AreaSelector          – manager, same public API as before
  ScreenCoverWidget     – one frameless fullscreen widget per physical screen,
                          shows the per-screen screenshot + darkening overlay,
                          forwards mouse events in global virtual-desktop coords.

Selection rectangle lives in **global (virtual-desktop) coordinates** and may
span several monitors.  Each ScreenCoverWidget paints the portion of the
selection that overlaps its own screen geometry.
"""

import sys
import os
import logging
import tempfile
from enum import Enum, auto
from typing import List, Optional, Dict

from PyQt6.QtWidgets import QWidget, QApplication, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal, QTimer, QBuffer, QIODevice
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QFont, QCursor, QPixmap,
    QGuiApplication, QPolygon, QRegion, QScreen, QImage,
)
from PIL import Image


# ── constants ────────────────────────────────────────────────────────────

class _Handle(Enum):
    TOP_LEFT = auto()
    TOP = auto()
    TOP_RIGHT = auto()
    RIGHT = auto()
    BOTTOM_RIGHT = auto()
    BOTTOM = auto()
    BOTTOM_LEFT = auto()
    LEFT = auto()


HANDLE_SIZE = 8
_MIN_SEL = 10
_MASK_ALPHA = 100
_HINT_ALPHA = 153


# ── per-screen overlay widget ───────────────────────────────────────────

class ScreenCoverWidget(QWidget):
    """
    Fullscreen frameless widget covering exactly **one** monitor.

    It draws:
      1. The screenshot of that monitor (background).
      2. A semi-transparent darkening mask over the whole screen.
      3. The clear (un-darkened) selection rectangle where it overlaps this screen.
      4. Resize handles when in "adjusting" phase.

    All coordinates are translated from global virtual-desktop coords to
    widget-local coords using the screen geometry offset.
    """

    # Emitted when mouse events happen — manager translates to global coords
    mouse_pressed = pyqtSignal(QPoint)   # global
    mouse_moved = pyqtSignal(QPoint)     # global
    mouse_released = pyqtSignal(QPoint)  # global
    mouse_double_clicked = pyqtSignal(QPoint)
    escape_pressed = pyqtSignal()

    def __init__(self, screen: QScreen, screenshot_pixmap: QPixmap,
                 sel_rect_global: QRect, phase: str,
                 handle_rects_global: Dict[_Handle, QRect],
                 parent=None):
        super().__init__(parent)
        self._screen = screen
        self._sg = screen.geometry()          # logical geometry of this screen
        self._screenshot_pixmap = screenshot_pixmap
        self._sel_rect_global = sel_rect_global
        self._phase = phase
        self._handle_rects_global = handle_rects_global

        self._mask_color = QColor(0, 0, 0, _MASK_ALPHA)
        self._border_color = QColor(0, 150, 255)
        self._border_width = 2
        self._handle_fill = QColor(0, 150, 255, 220)
        self._handle_border = QColor(255, 255, 255, 200)

        self._setup_window()

    def _setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_MouseTracking, True)
        self.setMouseTracking(True)
        # Place exactly over this screen
        self.setGeometry(self._sg)
        self.setCursor(Qt.CursorShape.CrossCursor)

    # ── coordinate translation ──────────────────────────────────────

    def _global_to_local(self, gpt: QPoint) -> QPoint:
        return gpt - self._sg.topLeft()

    def _local_to_global(self, lpt: QPoint) -> QPoint:
        return lpt + self._sg.topLeft()

    # ── external update (called by manager) ─────────────────────────

    def update_selection(self, sel_rect_global: QRect, phase: str,
                         handle_rects_global: Dict[_Handle, QRect]):
        self._sel_rect_global = sel_rect_global
        self._phase = phase
        self._handle_rects_global = handle_rects_global
        self.update()

    # ── painting ────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        local_w, local_h = self.width(), self.height()

        # 1) Draw screenshot (already cropped to this screen by manager)
        if self._screenshot_pixmap and not self._screenshot_pixmap.isNull():
            painter.drawPixmap(0, 0, self._screenshot_pixmap)

        # 2) Darkening mask + clear selection area
        sel_local = self._sel_rect_global.translated(-self._sg.x(), -self._sg.y())

        if sel_local.isValid() and sel_local.width() > 1 and sel_local.height() > 1:
            # Full-screen dark mask
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._mask_color)
            painter.drawRect(self.rect())

            # Clear the selection region (un-darken)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.drawRect(sel_local)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

            # Selection border
            painter.setPen(QPen(self._border_color, self._border_width))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(sel_local)

            # Resize handles
            if self._phase == "adjusting":
                self._draw_handles(painter, sel_local)
        else:
            # No selection yet — just dark mask + hint
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._mask_color)
            painter.drawRect(self.rect())
            self._draw_hint(painter)

        painter.end()

    def _draw_handles(self, painter: QPainter, sel_local: QRect):
        painter.setPen(QPen(self._handle_border, 1))
        painter.setBrush(self._handle_fill)
        s = HANDLE_SIZE
        hs = s // 2
        r = sel_local
        handle_points = {
            _Handle.TOP_LEFT:     (r.x() - hs,          r.y() - hs),
            _Handle.TOP:          (r.x() + r.width()//2 - hs, r.y() - hs),
            _Handle.TOP_RIGHT:    (r.right() - hs,       r.y() - hs),
            _Handle.RIGHT:        (r.right() - hs,       r.y() + r.height()//2 - hs),
            _Handle.BOTTOM_RIGHT: (r.right() - hs,       r.bottom() - hs),
            _Handle.BOTTOM:       (r.x() + r.width()//2 - hs, r.bottom() - hs),
            _Handle.BOTTOM_LEFT:  (r.x() - hs,           r.bottom() - hs),
            _Handle.LEFT:         (r.x() - hs,           r.y() + r.height()//2 - hs),
        }
        for hx, hy in handle_points.values():
            painter.drawEllipse(hx, hy, s, s)

    def _draw_hint(self, painter: QPainter):
        text = "Выделите область мышью  |  Esc — отмена"
        font = QFont("Segoe UI", 10)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        tw = metrics.horizontalAdvance(text)
        th = metrics.height()
        px, py = 14, 8
        pill_w, pill_h = tw + px * 2, th + py * 2

        margin = 20
        pill_x = self.width() - margin - pill_w
        pill_y = self.height() - margin - pill_h

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, _HINT_ALPHA))
        painter.drawRoundedRect(pill_x, pill_y, pill_w, pill_h, 6, 6)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(
            QRect(pill_x + px, pill_y + py, tw, th),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            text,
        )

    # ── mouse → global coords ───────────────────────────────────────

    def _pos_to_global(self, event) -> QPoint:
        return self._local_to_global(event.position().toPoint())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.mouse_pressed.emit(self._pos_to_global(event))
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        self.mouse_moved.emit(self._pos_to_global(event))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.mouse_released.emit(self._pos_to_global(event))
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.mouse_double_clicked.emit(self._pos_to_global(event))
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.escape_pressed.emit()
        super().keyPressEvent(event)


# ── main manager ─────────────────────────────────────────────────────────

class AreaSelector(QWidget):
    """
    Multi-screen area selector manager.

    Public API is identical to the old single-widget version:
      - area_captured(str, QPoint, tuple)
      - area_selection_canceled()
      - start_capture() -> bool
      - isVisible()
    """

    area_captured = pyqtSignal(str, QPoint, tuple)
    area_selection_canceled = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self._phase = "idle"
        self._cover_widgets: List[ScreenCoverWidget] = []
        self._toolbar_widget: Optional[QWidget] = None
        self._btn_confirm: Optional[QPushButton] = None
        self._btn_cancel: Optional[QPushButton] = None

        # Selection in global virtual-desktop coordinates
        self._sel_start = QPoint()
        self._sel_rect = QRect()

        # Drag state (for resize handles / move)
        self._drag_start = QPoint()
        self._drag_rect_snapshot = QRect()
        self._active_handle: Optional[_Handle] = None
        self._hover_handle: Optional[_Handle] = None

        # Per-screen screenshots keyed by screen name
        self._screen_pixmaps: Dict[str, QPixmap] = {}
        self._screen_shots: List[str] = []       # фоновые скриншоты мониторов
        self._crop_path: Optional[str] = None    # вырезанный кроп для перевода

        # Virtual-desktop bounding rect
        self._vd_rect = QRect()

    # ==================================================================
    # Public API
    # ==================================================================

    def start_capture(self) -> bool:
        try:
            screens = QGuiApplication.screens()
            if not screens:
                self.logger.error("No screens available")
                return False

            # 1) Compute virtual-desktop bounding rect
            self._vd_rect = QRect()
            for s in screens:
                self._vd_rect = self._vd_rect.united(s.geometry())

            # 2) Capture each screen individually
            self._capture_screens(screens)
            if not self._screen_pixmaps:
                self.logger.error("Failed to capture any screen")
                return False

            # 3) Reset selection state
            self._phase = "idle"
            self._sel_rect = QRect()
            self._sel_start = QPoint()
            self._active_handle = None

            # 4) Create per-screen overlay widgets
            self._create_cover_widgets(screens)

            self.logger.info(
                f"Area selector shown on {len(self._cover_widgets)} screen(s)"
            )
            return True

        except Exception as e:
            self.logger.error(f"Error starting capture: {e}")
            self._cleanup()
            return False

    def isVisible(self) -> bool:
        return any(w.isVisible() for w in self._cover_widgets)

    # ==================================================================
    # Screenshot capture
    # ==================================================================

    def _capture_screens(self, screens: List[QScreen]):
        self._screen_pixmaps.clear()
        self._screen_shots.clear()
        self._crop_path = None

        for screen in screens:
            try:
                # screen.grabWindow(0) — native Qt, correct DPI per screen
                pixmap = screen.grabWindow(0)
                if pixmap.isNull():
                    self.logger.warning(
                        f"grabWindow returned null for {screen.name()}"
                    )
                    continue
                self._screen_pixmaps[screen.name()] = pixmap
            except Exception as e:
                self.logger.warning(
                    f"Failed to grab screen {screen.name()}: {e}"
                )

    # ==================================================================
    # Cover-widget creation
    # ==================================================================

    def _create_cover_widgets(self, screens: List[QScreen]):
        self._destroy_cover_widgets()

        for screen in screens:
            name = screen.name()
            pixmap = self._screen_pixmaps.get(name)
            if pixmap is None:
                continue

            w = ScreenCoverWidget(
                screen=screen,
                screenshot_pixmap=pixmap,
                sel_rect_global=self._sel_rect,
                phase=self._phase,
                handle_rects_global=self._handle_rects_global(),
            )
            w.mouse_pressed.connect(self._on_mouse_pressed)
            w.mouse_moved.connect(self._on_mouse_moved)
            w.mouse_released.connect(self._on_mouse_released)
            w.mouse_double_clicked.connect(self._on_mouse_double_clicked)
            w.escape_pressed.connect(self._cancel)
            self._cover_widgets.append(w)
            w.show()
            w.raise_()
            w.activateWindow()

        # Focus first widget so key events work
        if self._cover_widgets:
            self._cover_widgets[0].setFocus()

    def _destroy_cover_widgets(self):
        for w in self._cover_widgets:
            w.hide()
            w.deleteLater()
        self._cover_widgets.clear()

    # ==================================================================
    # Global mouse handlers (connected to ScreenCoverWidget signals)
    # ==================================================================

    def _on_mouse_pressed(self, global_pos: QPoint):
        if self._phase == "adjusting":
            h = self._hit_handle(global_pos)
            if h is not None:
                # Click on edge/corner handle → start resize
                self._active_handle = h
                self._drag_start = global_pos
                self._drag_rect_snapshot = QRect(self._sel_rect)
                return
            else:
                # Click inside rect or outside → start new selection
                self._phase = "drawing"
                self._sel_start = global_pos
                self._sel_rect = QRect(global_pos, global_pos)
                self._active_handle = None
                self._hide_toolbar()
                self._sync_all()
                return

        if self._phase == "idle":
            self._phase = "drawing"
            self._sel_start = global_pos
            self._sel_rect = QRect(global_pos, global_pos)
            self._hide_toolbar()
            self._sync_all()

    def _on_mouse_moved(self, global_pos: QPoint):
        if self._phase == "drawing":
            self._sel_rect = QRect(self._sel_start, global_pos).normalized()
            self._sync_all()
            return

        if self._phase == "adjusting":
            if self._active_handle is not None:
                delta = global_pos - self._drag_start
                self._apply_resize(self._active_handle, delta)
                self._position_toolbar()
                self._sync_all()
            else:
                h = self._hit_handle(global_pos)
                if h != self._hover_handle:
                    self._hover_handle = h
                    cursor = self._cursor_for_handle(h)
                    for w in self._cover_widgets:
                        w.setCursor(cursor)

    def _on_mouse_released(self, global_pos: QPoint):
        if self._phase == "drawing":
            self._sel_rect = QRect(self._sel_start, global_pos).normalized()
            if self._sel_rect.width() > _MIN_SEL and self._sel_rect.height() > _MIN_SEL:
                self._phase = "adjusting"
                self._position_toolbar()
            else:
                self._sel_rect = QRect()
                self._phase = "idle"
            self._sync_all()
            return

        if self._phase == "adjusting" and self._active_handle is not None:
            self._active_handle = None
            self._sync_all()

    def _on_mouse_double_clicked(self, global_pos: QPoint):
        if self._phase == "adjusting" and self._sel_rect.isValid():
            self._confirm_selection()

    # ==================================================================
    # Handle geometry & hit-testing (global coords)
    # ==================================================================

    def _handle_rects_global(self) -> Dict[_Handle, QRect]:
        r = self._sel_rect
        if not r.isValid():
            return {}
        s = HANDLE_SIZE
        hs = s // 2
        return {
            _Handle.TOP_LEFT:     QRect(r.x() - hs, r.y() - hs, s, s),
            _Handle.TOP:          QRect(r.x() + r.width() // 2 - hs, r.y() - hs, s, s),
            _Handle.TOP_RIGHT:    QRect(r.right() - hs, r.y() - hs, s, s),
            _Handle.RIGHT:        QRect(r.right() - hs, r.y() + r.height() // 2 - hs, s, s),
            _Handle.BOTTOM_RIGHT: QRect(r.right() - hs, r.bottom() - hs, s, s),
            _Handle.BOTTOM:       QRect(r.x() + r.width() // 2 - hs, r.bottom() - hs, s, s),
            _Handle.BOTTOM_LEFT:  QRect(r.x() - hs, r.bottom() - hs, s, s),
            _Handle.LEFT:         QRect(r.x() - hs, r.y() + r.height() // 2 - hs, s, s),
        }

    def _hit_handle(self, pos: QPoint) -> Optional[_Handle]:
        """Detect if pos is on a resize handle or near a border edge (8px tolerance)."""
        r = self._sel_rect
        if not r.isValid():
            return None

        # 1) Check explicit handle rectangles first (highest priority)
        for h, hr in self._handle_rects_global().items():
            if hr.adjusted(-4, -4, 4, 4).contains(pos):
                return h

        # 2) Border-tolerance: if within 8px of an edge, treat as that edge's handle
        border = 8
        x, y = pos.x(), pos.y()
        on_left   = abs(x - r.left()) <= border and r.top() <= y <= r.bottom()
        on_right  = abs(x - r.right()) <= border and r.top() <= y <= r.bottom()
        on_top    = abs(y - r.top()) <= border and r.left() <= x <= r.right()
        on_bottom = abs(y - r.bottom()) <= border and r.left() <= x <= r.right()

        # Corners take priority over edges
        if on_top and on_left:     return _Handle.TOP_LEFT
        if on_top and on_right:    return _Handle.TOP_RIGHT
        if on_bottom and on_left:  return _Handle.BOTTOM_LEFT
        if on_bottom and on_right: return _Handle.BOTTOM_RIGHT
        if on_top:    return _Handle.TOP
        if on_bottom: return _Handle.BOTTOM
        if on_left:   return _Handle.LEFT
        if on_right:  return _Handle.RIGHT

        return None

    def _cursor_for_handle(self, h: Optional[_Handle]) -> Qt.CursorShape:
        mapping = {
            _Handle.TOP_LEFT:     Qt.CursorShape.SizeFDiagCursor,
            _Handle.TOP:          Qt.CursorShape.SizeVerCursor,
            _Handle.TOP_RIGHT:    Qt.CursorShape.SizeBDiagCursor,
            _Handle.RIGHT:        Qt.CursorShape.SizeHorCursor,
            _Handle.BOTTOM_RIGHT: Qt.CursorShape.SizeFDiagCursor,
            _Handle.BOTTOM:       Qt.CursorShape.SizeVerCursor,
            _Handle.BOTTOM_LEFT:  Qt.CursorShape.SizeBDiagCursor,
            _Handle.LEFT:         Qt.CursorShape.SizeHorCursor,
        }
        return mapping.get(h, Qt.CursorShape.CrossCursor)

    # ==================================================================
    # Resize logic
    # ==================================================================

    def _apply_resize(self, handle: _Handle, delta: QPoint):
        r = QRect(self._drag_rect_snapshot)
        if handle == _Handle.TOP_LEFT:
            r.setTopLeft(r.topLeft() + delta)
        elif handle == _Handle.TOP:
            r.setTop(r.top() + delta.y())
        elif handle == _Handle.TOP_RIGHT:
            r.setTopRight(r.topRight() + delta)
        elif handle == _Handle.RIGHT:
            r.setRight(r.right() + delta.x())
        elif handle == _Handle.BOTTOM_RIGHT:
            r.setBottomRight(r.bottomRight() + delta)
        elif handle == _Handle.BOTTOM:
            r.setBottom(r.bottom() + delta.y())
        elif handle == _Handle.BOTTOM_LEFT:
            r.setBottomLeft(r.bottomLeft() + delta)
        elif handle == _Handle.LEFT:
            r.setLeft(r.left() + delta.x())

        if r.width() >= _MIN_SEL and r.height() >= _MIN_SEL:
            self._sel_rect = r.normalized()

    # ==================================================================
    # Sync all cover widgets
    # ==================================================================

    def _sync_all(self):
        hr = self._handle_rects_global()
        for w in self._cover_widgets:
            w.update_selection(self._sel_rect, self._phase, hr)

    # ==================================================================
    # Toolbar (floating on primary screen)
    # ==================================================================

    def _ensure_toolbar(self):
        if self._toolbar_widget is not None:
            return

        self._toolbar_widget = QWidget()
        self._toolbar_widget.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self._toolbar_widget.setFixedHeight(36)
        self._toolbar_widget.setStyleSheet(
            "QWidget { background-color: #1E1E1E; border-radius: 6px; }"
        )

        lay = QHBoxLayout(self._toolbar_widget)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(6)

        self._btn_confirm = QPushButton("✓ Перевести")
        self._btn_confirm.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_confirm.setFixedHeight(26)
        self._btn_confirm.setStyleSheet(
            "QPushButton { background-color: #0E639C; color: white; border: none; "
            "border-radius: 4px; padding: 0 14px; font-weight: bold; font-size: 11px; }"
            "QPushButton:hover { background-color: #1177BB; }"
        )
        self._btn_confirm.clicked.connect(self._confirm_selection)

        self._btn_cancel = QPushButton("✕ Отмена")
        self._btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_cancel.setFixedHeight(26)
        self._btn_cancel.setStyleSheet(
            "QPushButton { background-color: #555555; color: #CCCCCC; border: none; "
            "border-radius: 4px; padding: 0 14px; font-weight: bold; font-size: 11px; }"
            "QPushButton:hover { background-color: #6E6E6E; color: white; }"
        )
        self._btn_cancel.clicked.connect(self._cancel)

        lay.addWidget(self._btn_confirm)
        lay.addWidget(self._btn_cancel)

    def _position_toolbar(self):
        if not self._sel_rect.isValid():
            self._hide_toolbar()
            return

        self._ensure_toolbar()
        tw = self._toolbar_widget.sizeHint().width()
        th = self._toolbar_widget.height()

        # Place below selection, on whichever screen the center is on
        cx = self._sel_rect.center().x()
        cy = self._sel_rect.bottom() + 8

        screen = QApplication.screenAt(QPoint(cx, cy)) or QApplication.primaryScreen()
        sg = screen.geometry()

        tx = max(sg.x() + 4, min(cx - tw // 2, sg.right() - tw - 4))
        ty = cy
        if ty + th > sg.bottom():
            ty = self._sel_rect.top() - th - 8

        self._toolbar_widget.move(tx, ty)
        self._toolbar_widget.show()
        self._toolbar_widget.raise_()

    def _hide_toolbar(self):
        if self._toolbar_widget is not None:
            self._toolbar_widget.hide()

    # ==================================================================
    # Confirm / Cancel
    # ==================================================================

    def _confirm_selection(self):
        sel = self._sel_rect
        if not sel.isValid() or sel.width() < _MIN_SEL or sel.height() < _MIN_SEL:
            return

        self._phase = "confirmed"
        self._hide_toolbar()

        # Hide all cover widgets
        for w in self._cover_widgets:
            w.hide()
        QApplication.processEvents()

        try:
            # Determine which screen(s) the selection overlaps
            screens = QGuiApplication.screens()
            crop_img = None

            for screen in screens:
                sg = screen.geometry()
                intersection = sel.intersected(sg)
                if intersection.isEmpty():
                    continue

                name = screen.name()
                pix = self._screen_pixmaps.get(name)
                if pix is None or pix.isNull():
                    continue

                # Convert global intersection to screen-local pixel coords
                local_x = intersection.x() - sg.x()
                local_y = intersection.y() - sg.y()
                local_w = intersection.width()
                local_h = intersection.height()

                # DPI scaling: pixmap may be larger than logical geometry
                sx = pix.width() / sg.width() if sg.width() > 0 else 1.0
                sy = pix.height() / sg.height() if sg.height() > 0 else 1.0

                px1 = int(local_x * sx)
                py1 = int(local_y * sy)
                px2 = int((local_x + local_w) * sx)
                py2 = int((local_y + local_h) * sy)

                # Crop from PIL to handle subpixel precisely
                pil_img = self._pixmap_to_pil(pix)
                piece = pil_img.crop((px1, py1, px2, py2))

                if crop_img is None:
                    crop_img = piece
                else:
                    if piece.width() * piece.height() > crop_img.width() * crop_img.height():
                        crop_img = piece

            if crop_img is None:
                self.logger.error("No screen data for selection")
                self.area_selection_canceled.emit()
                self.close()
                return

            # Save cropped image to temp file
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                crop_img.save(tmp.name, 'PNG')
                self._crop_path = tmp.name

            # Physical pixel size of the final crop
            phys_w, phys_h = crop_img.size

            # Emit result — screen_pos is the global top-left of the selection
            screen_pos = QPoint(sel.x(), sel.y())
            self.area_captured.emit(self._crop_path, screen_pos, (phys_w, phys_h))
            self.logger.info(
                f"Area captured: {self._crop_path} at ({sel.x()}, {sel.y()}) "
                f"size {phys_w}x{phys_h}"
            )

        except Exception as e:
            self.logger.error(f"Error completing selection: {e}")
            self.area_selection_canceled.emit()

        self.close()

    def _cancel(self):
        self._phase = "idle"
        self._sel_rect = QRect()
        self._hide_toolbar()
        self._sync_all()
        self.area_selection_canceled.emit()
        self.close()

    # ==================================================================
    # Cleanup
    # ==================================================================

    @staticmethod
    def _pixmap_to_pil(pixmap: QPixmap) -> Image.Image:
        """Convert QPixmap to PIL Image (compatible with all Pillow versions)."""
        qimg = pixmap.toImage()
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        qimg.save(buffer, "PNG")
        buffer.close()
        data = bytes(buffer.data())
        return Image.open(__import__("io").BytesIO(data))

    def _cleanup(self, keep_crop=False):
        self._destroy_cover_widgets()
        if self._toolbar_widget is not None:
            self._toolbar_widget.hide()
            self._toolbar_widget.deleteLater()
            self._toolbar_widget = None
            self._btn_confirm = None
            self._btn_cancel = None
        self._cleanup_screenshots(keep_crop=keep_crop)

    def _cleanup_screenshots(self, keep_crop: bool = False):
        # Удаляем все фоновые скриншоты мониторов
        if self._screen_shots:
            for path in self._screen_shots:
                if path and os.path.exists(path):
                    try:
                        os.unlink(path)
                    except Exception as e:
                        self.logger.debug(f"Не удалось удалить фоновый скриншот {path}: {e}")
            self._screen_shots.clear()

        # Файл кропа удаляем ТОЛЬКО если отмена (keep_crop == False)
        if not keep_crop and self._crop_path:
            if os.path.exists(self._crop_path):
                try:
                    os.unlink(self._crop_path)
                except Exception as e:
                    self.logger.debug(f"Не удалось удалить кроп {self._crop_path}: {e}")
            self._crop_path = None

        self._screen_pixmaps.clear()

    def closeEvent(self, event):
        # When closing without confirmation (Esc/cancel), delete all files including crop
        self._cleanup(keep_crop=(self._phase == "confirmed"))
        if self._phase != "confirmed":
            self.area_selection_canceled.emit()
        super().closeEvent(event)


# ── standalone test ──────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    selector = AreaSelector()

    def on_captured(path, pos, size):
        print(f"Captured: {path}")
        print(f"Position: ({pos.x()}, {pos.y()})")
        print(f"Size: {size[0]}x{size[1]}")

    def on_canceled():
        print("Selection canceled")

    selector.area_captured.connect(on_captured)
    selector.area_selection_canceled.connect(on_canceled)

    if selector.start_capture():
        print("Area selector started")
    else:
        print("Failed to start area selector")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
