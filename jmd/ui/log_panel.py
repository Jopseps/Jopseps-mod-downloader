from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCharFormat, QColor, QTextCursor
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QVBoxLayout

from jmd.ui import icons
from jmd.ui.tokens import C, SIZE
from jmd.ui.widgets import button


class LogHeader(QFrame):
    def __init__(self, on_click, parent=None):
        super().__init__(parent)
        self.setObjectName("LogHeader")
        self.setFixedHeight(SIZE["log"])
        self.setCursor(Qt.PointingHandCursor)
        self._on_click = on_click

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._on_click()


class LogPanel(QFrame):
    """Collapsible SteamCMD output dock at the bottom of the window (28px closed / +180px open)."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.ctl = controller
        self.setObjectName("LogPanel")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        head = LogHeader(self.toggle)
        hl = QHBoxLayout(head)
        hl.setContentsMargins(10, 0, 10, 0)
        hl.setSpacing(8)
        self.chev = QLabel()
        term = QLabel()
        term.setPixmap(icons.pixmap("terminal", C["text-dim"], 13))
        title = QLabel("SteamCMD log")
        title.setStyleSheet(f"color:{C['text-dim']};font-size:12px;font-weight:600;background:transparent;")
        self.last = QLabel()
        self.last.setStyleSheet(f"color:{C['text-faint']};font-family:'JetBrains Mono';font-size:11px;background:transparent;")
        self.last.setMinimumWidth(10)
        self.clear_btn = button("Clear", size="sm")
        self.clear_btn.setStyleSheet(f"font-size:11px;font-weight:400;background:transparent;border-color:{C['border']};"
                                     f"color:{C['text-dim']};min-height:18px;max-height:20px;")
        self.clear_btn.clicked.connect(self.clear)
        for w in (self.chev, term, title):
            hl.addWidget(w)
        hl.addWidget(self.last, 1)
        hl.addWidget(self.clear_btn)
        root.addWidget(head)
        self.text = QPlainTextEdit()
        self.text.setObjectName("Log")
        self.text.setReadOnly(True)
        self.text.setFixedHeight(SIZE["log-open"])
        self.text.setMaximumBlockCount(2000)
        root.addWidget(self.text)
        for line, color in controller.log:
            self.append(line, color)
        controller.logLine.connect(self.append)
        self.set_open(False)

    def set_open(self, on):
        self.open = on
        self.text.setVisible(on)
        self.clear_btn.setVisible(on)
        self.chev.setPixmap(icons.pixmap("chevron-down" if on else "chevron-right", C["text-dim"], 12, 2.5))

    def toggle(self):
        self.set_open(not self.open)

    def append(self, line, color=""):
        cur = self.text.textCursor()
        cur.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color or C["text-dim"]))
        if not self.text.document().isEmpty():
            cur.insertBlock()
        cur.insertText(line, fmt)
        self.text.verticalScrollBar().setValue(self.text.verticalScrollBar().maximum())
        self.last.setText(self.last.fontMetrics().elidedText(line, Qt.ElideRight, max(50, self.last.width())))

    def clear(self):
        self.text.clear()
        self.last.clear()
        self.ctl.clear_log()
