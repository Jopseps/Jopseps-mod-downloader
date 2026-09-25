"""Small shared widgets: buttons with design variants, labels, spinner, toast, dialog shell."""
from PySide6.QtCore import QPropertyAnimation, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QDialog, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QPushButton,
                               QSizePolicy, QVBoxLayout, QWidget)

from jmd.ui import icons
from jmd.ui.tokens import C, FONT_MONO


def restyle(widget):
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def button(text="", kind=None, size=None, icon=None, icon_color=None, icon_size=15, tooltip=None, parent=None):
    btn = QPushButton(text, parent)
    if kind:
        btn.setProperty("kind", kind)
    if size:
        btn.setProperty("size", size)
    if icon:
        color = icon_color or (C["on-accent"] if kind == "primary" else C["text"])
        btn.setIcon(icons.icon(icon, color, icon_size, 2.5 if kind == "primary" else 2.0,
                               disabled=C["text-faint"]))
        btn.setIconSize(QSize(icon_size, icon_size))
    if tooltip:
        btn.setToolTip(tooltip)
    btn.setCursor(Qt.PointingHandCursor)
    return btn


def icon_button(name, tooltip="", size=28, icon_size=16, color=None, parent=None):
    btn = QPushButton(parent)
    btn.setProperty("kind", "icon")
    btn.setFixedSize(size, size)
    btn.setIcon(icons.icon(name, color or C["text"], icon_size, disabled=C["text-disabled"]))
    btn.setIconSize(QSize(icon_size, icon_size))
    btn.setToolTip(tooltip)
    btn.setCursor(Qt.PointingHandCursor)
    return btn


def label(text="", role=None, wrap=False, parent=None):
    lbl = QLabel(text, parent)
    if role:
        lbl.setProperty("role", role)
    if wrap:
        lbl.setWordWrap(True)
    return lbl


def mono_font(size=12):
    f = QFont(FONT_MONO)
    f.setPixelSize(round(size))
    return f


def hbox(*widgets, spacing=8, margins=(0, 0, 0, 0)):
    lay = QHBoxLayout()
    lay.setSpacing(spacing)
    lay.setContentsMargins(*margins)
    for w in widgets:
        if w is None:
            lay.addStretch(1)
        elif isinstance(w, int):
            lay.addSpacing(w)
        else:
            lay.addWidget(w)
    return lay


def vbox(*widgets, spacing=8, margins=(0, 0, 0, 0)):
    lay = QVBoxLayout()
    lay.setSpacing(spacing)
    lay.setContentsMargins(*margins)
    for w in widgets:
        if w is None:
            lay.addStretch(1)
        elif isinstance(w, int):
            lay.addSpacing(w)
        elif hasattr(w, "addWidget") and not isinstance(w, QWidget):
            lay.addLayout(w)
        else:
            lay.addWidget(w)
    return lay


def framed(name, layout):
    frame = QFrame()
    frame.setObjectName(name)
    frame.setLayout(layout)
    return frame


class Spinner(QWidget):
    """12px ring, 2px stroke, 0.8s per turn (design: Progress · spinner)."""

    def __init__(self, size=12, width=2, parent=None):
        super().__init__(parent)
        self._angle = 0
        self._width = width
        self.setFixedSize(size, size)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

    def _tick(self):
        self._angle = (self._angle + 15) % 360
        self.update()

    def paintEvent(self, _):
        paint_spinner(QPainter(self), QRectF(self.rect()), self._angle, self._width)


def paint_spinner(p, rect, angle, width=2):
    p.setRenderHint(QPainter.Antialiasing)
    r = rect.adjusted(width / 2, width / 2, -width / 2, -width / 2)
    p.setPen(QPen(QColor("#2f4254"), width))
    p.drawEllipse(r)
    p.setPen(QPen(QColor(C["steam-blue"]), width))
    p.drawArc(r, int((90 - angle) * 16), int(-90 * 16))


class Toast(QFrame):
    """Bottom-centered confirmation that fades out after ~2.8s."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("Toast")
        self._icon = QLabel()
        self._icon.setPixmap(icons.pixmap("check", "#6fbf4a", 14, 2.5))
        self._text = QLabel()
        self._text.setStyleSheet(f"color:{C['text-strong']};font-size:12px;background:transparent;")
        lay = hbox(self._icon, self._text, spacing=8, margins=(14, 9, 14, 9))
        self.setLayout(lay)
        self._fx = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._fx)
        self._anim = QPropertyAnimation(self._fx, b"opacity", self)
        self._anim.setDuration(220)
        self._anim.finished.connect(self.hide)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade)
        self.hide()

    def show_message(self, text):
        self._text.setText(text)
        self.adjustSize()
        self.reposition()
        self._anim.stop()
        self._fx.setOpacity(1.0)
        self.show()
        self.raise_()
        self._timer.start(2800)

    def reposition(self):
        par = self.parentWidget()
        self.move((par.width() - self.width()) // 2, par.height() - self.height() - 44)

    def _fade(self):
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.start()


class Dialog(QDialog):
    """Design dialog shell: body (panel, 16px padding) + footer bar (bg, top border, right-aligned buttons)."""

    def __init__(self, title, width, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(width)
        self.resize(width, 10)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.header = QVBoxLayout()
        self.header.setContentsMargins(0, 0, 0, 0)
        outer.addLayout(self.header)
        self.body = QFrame()
        self.body.setObjectName("DialogBody")
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(16, 16, 16, 16)
        self.body_layout.setSpacing(12)
        outer.addWidget(self.body, 1)
        self.footer = QFrame()
        self.footer.setObjectName("DialogFooter")
        self.footer_layout = QHBoxLayout(self.footer)
        self.footer_layout.setContentsMargins(16, 12, 16, 12)
        self.footer_layout.setSpacing(8)
        outer.addWidget(self.footer)


class Line(QFrame):
    def __init__(self, color=None, parent=None):
        super().__init__(parent)
        self.setFixedHeight(1)
        self.setStyleSheet(f"background:{color or C['border']};")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
