"""Painted queue/installed rows (design: 'Queue row · every status'). One delegate beats one widget per
row when a 179-item collection lands in the list."""
import time
import zlib

from PySide6.QtCore import QEvent, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QStyle, QStyledItemDelegate

from jmd.core import models
from jmd.core.models import Group
from jmd.ui import icons
from jmd.ui.queue_model import DepthRole, NodeRole
from jmd.ui.tokens import C, FONT_MONO, FONT_UI, LOGIN_TEXT, SIZE, STATUS, status_color
from jmd.ui.widgets import paint_spinner


# === HELPERS ===
def font(px, weight=QFont.Normal, family=FONT_UI):
    f = QFont(family)
    f.setPixelSize(px)
    f.setWeight(weight)
    return f


F_TITLE = font(13, QFont.DemiBold)
F_SUB = font(12)
F_SUB_MED = font(12, QFont.Medium)
F_MONO_11 = font(11, family=FONT_MONO)
F_MONO_9 = font(9, family=FONT_MONO)
F_BTN = font(12, QFont.DemiBold)
F_BADGE = font(11, QFont.DemiBold)


def fmt_size(num):
    mb = num / 1_000_000
    if mb >= 1000:
        return f"{mb / 1000:.2f} GB"
    if mb < 1:
        return f"{max(1, round(num / 1000))} KB"
    return f"{mb:.1f} MB"


def fmt_date(ts):
    if not ts:
        return "unknown"
    t = time.localtime(ts)
    return f"{t.tm_mday} {time.strftime('%b %Y', t)}"  # no %-d: Windows strftime lacks it


def initials(title):
    words = [w for w in "".join(ch if ch.isalnum() or ch == " " else " " for ch in title or "").split() if w]
    return "".join(w[0] for w in words[:2]).upper()


def placeholder_brush(key, rect):
    """Hue-from-id gradient (same idea as the design mock) until the real thumbnail arrives."""
    h = zlib.crc32(str(key).encode()) % 360
    g = QLinearGradient(rect.topLeft(), rect.bottomRight())
    g.setColorAt(0, QColor.fromHsl(h, 82, 92))
    g.setColorAt(1, QColor.fromHsl((h + 50) % 360, 71, 46))
    return QBrush(g)


def elide(text, fm, width):
    return fm.elidedText(text, Qt.ElideRight, max(0, int(width)))


def rounded(p, rect, radius, fill=None, line=None):
    p.save()
    p.setPen(QPen(QColor(line), 1) if line else Qt.NoPen)
    p.setBrush(QColor(fill) if fill else Qt.NoBrush)
    r = QRectF(rect)
    if line:
        r = r.adjusted(0.5, 0.5, -0.5, -0.5)
    p.drawRoundedRect(r, radius, radius)
    p.restore()


def draw_checkbox(p, rect, on, mixed=False, hover=False):
    if on or mixed:
        rounded(p, rect, 2, C["accent"], C["accent"])
        if mixed:
            p.fillRect(QRectF(rect.center().x() - 4, rect.center().y() - 1, 8, 2), QColor(C["on-accent"]))
        else:
            icons.paint(p, "check", QRectF(rect).adjusted(2, 2, -2, -2), C["on-accent"], 3.5)
    else:
        rounded(p, rect, 2, C["sunken"], C["border-hover"] if hover else C["border-strong"])


def draw_thumb(p, rect, pixmap, key, text):
    path = QPainterPath()
    path.addRoundedRect(QRectF(rect), 2, 2)
    p.save()
    p.setClipPath(path)
    if pixmap:
        p.drawPixmap(rect, pixmap)
    else:
        p.fillRect(rect, placeholder_brush(key, rect))
        if text:
            p.setFont(F_MONO_9)
            p.setPen(QColor(255, 255, 255, 153))
            p.drawText(rect.adjusted(4, 0, 0, -3), Qt.AlignLeft | Qt.AlignBottom, text)
    p.restore()


class _Base(QStyledItemDelegate):
    def __init__(self, controller, thumbs, parent=None):
        super().__init__(parent)
        self.ctl = controller
        self.thumbs = thumbs
        self.angle = 0
        self.hover = (-1, None)

    def _pixmap(self, key, url):
        return self.thumbs.get(key, url) if url else None


class QueueDelegate(_Base):
    loginRequested = Signal()

    def sizeHint(self, option, index):
        node = index.data(NodeRole)
        return QSize(option.rect.width(), SIZE["group"] if isinstance(node, Group) else SIZE["row"])

    # === LAYOUT (shared by paint + hit-test) ===
    def layout(self, rect, node, depth):
        cy = rect.center().y() + 1
        L = {}
        if isinstance(node, Group):
            x = rect.left() + 4
            L["chevron"] = QRect(x, cy - 10, 20, 20)
            L["check"] = QRect(x + 28, cy - 8, 16, 16)
            L["remove"] = QRect(rect.right() - 8 - 22, cy - 11, 22, 22)
            L["title_x"] = x + 52
            return L
        x = rect.left() + 8 + depth * 22
        L["check"] = QRect(x, cy - 8, 16, 16)
        L["thumb"] = QRect(x + 26, cy - 20, 40, 40)
        right = rect.right() - 8
        L["remove"] = QRect(right - 22, cy - 11, 22, 22)
        right -= 22 + 10
        st = node.status
        if st == models.FAILED and not node.blocked:
            L["retry"] = QRect(right - 26, cy - 13, 26, 26)
            right -= 26 + 10
        elif st == models.LOGIN:
            w = QFontMetrics(F_BTN).horizontalAdvance("Log in") + 18
            L["login"] = QRect(right - w, cy - 12, w, 24)
            right -= w + 10
        L["text"] = QRect(x + 76, rect.top(), right - (x + 76), rect.height())
        return L

    def hit(self, rect, node, depth, pos):
        for key, r in self.layout(rect, node, depth).items():
            if isinstance(r, QRect) and key not in ("text", "thumb") and r.adjusted(-3, -3, 3, 3).contains(pos):
                return key
        return None

    # === PAINT ===
    def paint(self, p, option, index):
        node = index.data(NodeRole)
        depth = index.data(DepthRole)
        rect = option.rect
        hovered = bool(option.state & QStyle.State_MouseOver)
        hot = self.hover[1] if self.hover[0] == index.row() else None
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        if isinstance(node, Group):
            self._paint_group(p, rect, node, hovered, hot)
        else:
            self._paint_item(p, rect, node, depth, hovered, hot)
        p.restore()

    def _paint_group(self, p, rect, g, hovered, hot):
        p.fillRect(rect, QColor(C["group-hover"] if hovered else C["panel-alt"]))
        p.fillRect(QRect(rect.left(), rect.bottom(), rect.width(), 1), QColor(C["border"]))
        L = self.layout(rect, g, 0)
        if hot == "chevron":
            rounded(p, L["chevron"], 2, C["border"])
        p.save()
        c = QRectF(L["chevron"]).center()
        p.translate(c)
        if g.open:
            p.rotate(90)
        icons.paint(p, "chevron-right", QRectF(-7, -7, 14, 14), C["text-strong"] if hot == "chevron" else C["text-dim"])
        p.restore()
        checked = sum(1 for i in g.items if i.checked)
        draw_checkbox(p, L["check"], checked == len(g.items) and checked > 0, 0 < checked < len(g.items))
        sel = f"{checked}/{len(g.items)}"
        p.setFont(F_MONO_11)
        fm = QFontMetrics(F_MONO_11)
        sw = fm.horizontalAdvance(sel)
        sel_rect = QRect(L["remove"].left() - 8 - sw, rect.top(), sw, rect.height())
        p.setPen(QColor(C["text-dim"]))
        p.drawText(sel_rect, Qt.AlignVCenter | Qt.AlignRight, sel)
        p.setFont(F_TITLE)
        p.setPen(QColor(C["text-strong"]))
        tw = sel_rect.left() - 6 - L["title_x"]
        p.drawText(QRect(L["title_x"], rect.top(), tw, rect.height()), Qt.AlignVCenter,
                   elide(g.title or g.id, QFontMetrics(F_TITLE), tw))
        self._paint_remove(p, L["remove"], hot == "remove")

    def _paint_item(self, p, rect, it, depth, hovered, hot):
        if hovered:
            p.fillRect(rect, QColor(C["row-hover"]))
        p.fillRect(QRect(rect.left(), rect.bottom(), rect.width(), 1), QColor(C["divider"]))
        L = self.layout(rect, it, depth)
        dim = not it.checked
        if dim:
            p.setOpacity(0.55)
        draw_checkbox(p, L["check"], it.checked, hover=hot == "check")
        resolving = it.status == models.RESOLVING
        tr = L["text"]
        if resolving:
            rounded(p, L["thumb"], 2, C["thumb-empty"])
            block_top = tr.center().y() - 16
            rounded(p, QRect(tr.left(), block_top + 3, int(tr.width() * 0.62), 10), 2, C["skeleton"])
            sub_y = block_top + 19
            paint_spinner(p, QRectF(tr.left(), sub_y + 2, 12, 12), self.angle)
            p.setFont(F_SUB)
            p.setPen(QColor(STATUS["resolving"][1]))
            p.drawText(QRect(tr.left() + 18, sub_y, 200, 16), Qt.AlignVCenter, "Resolving…")
            w = QFontMetrics(F_SUB).horizontalAdvance("Resolving…")
            p.setFont(F_MONO_11)
            p.setPen(QColor(C["text-faint"]))
            p.drawText(QRect(tr.left() + 24 + w, sub_y, tr.width(), 16), Qt.AlignVCenter, it.id)
        else:
            draw_thumb(p, L["thumb"], self._pixmap(it.id, it.preview_url), it.id, initials(it.title))
            st = it.display_status
            label, color = self._status_label(it, st)
            extra = self._extra(it, st)
            bar = st == models.DOWNLOADING
            block_h = 18 + 3 + 16 + (6 if bar else 0)
            top = tr.center().y() - block_h // 2 + 1
            p.setFont(F_TITLE)
            p.setPen(QColor(C["text-strong"]))
            p.drawText(QRect(tr.left(), top, tr.width(), 18), Qt.AlignVCenter,
                       elide(it.title or it.id, QFontMetrics(F_TITLE), tr.width()))
            sy = top + 21
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(color))
            p.drawEllipse(QRectF(tr.left(), sy + 5, 6, 6))
            x = tr.left() + 12
            p.setFont(F_SUB_MED)
            p.setPen(QColor(color))
            lw = QFontMetrics(F_SUB_MED).horizontalAdvance(label)
            p.drawText(QRect(x, sy, lw + 2, 16), Qt.AlignVCenter, label)
            x += lw + 6
            if extra and x < tr.right() - 20:
                p.setFont(F_SUB)
                p.setPen(QColor(C["border-strong"]))
                p.drawText(QRect(x, sy, 10, 16), Qt.AlignVCenter, "·")
                x += 12
                p.setPen(QColor(C["text-dim"]))
                p.drawText(QRect(x, sy, tr.right() - x, 16), Qt.AlignVCenter,
                           elide(extra, QFontMetrics(F_SUB), tr.right() - x))
            if bar:
                track = QRect(tr.left(), sy + 19, tr.width(), 3)
                rounded(p, track, 1.5, C["sunken"])
                rounded(p, QRect(track.left(), track.top(), int(track.width() * it.progress / 100), 3), 1.5,
                        C["steam-blue"])
        p.setOpacity(1.0)
        if "retry" in L:
            r = L["retry"]
            rounded(p, r, 3, C["btn-secondary-hover"] if hot == "retry" else C["btn-secondary"], C["border-strong"])
            icons.paint(p, "refresh", QRectF(r).adjusted(6, 6, -6, -6), "#ffffff" if hot == "retry" else C["text"])
        if "login" in L:
            r = L["login"]
            rounded(p, r, 3, "#342b52" if hot == "login" else STATUS["login"][2], STATUS["login"][3])
            p.setFont(F_BTN)
            p.setPen(QColor(LOGIN_TEXT))
            p.drawText(r, Qt.AlignCenter, "Log in")
        self._paint_remove(p, L["remove"], hot == "remove")

    def _paint_remove(self, p, r, hot):
        if hot:
            rounded(p, r, 2, C["border"])
        icons.paint(p, "x", QRectF(r).adjusted(4, 4, -4, -4), C["danger"] if hot else C["text-faint"])

    def _status_label(self, it, st):
        color = status_color(st)
        if st == models.DOWNLOADING:
            return f"Downloading {int(it.progress)}%", color
        if st == models.RETRYING:
            return f"Retrying {max(1, it.attempt)}/{self.ctl.settings.retries}", color
        if st == models.FAILED:
            return f"Failed · {it.error or 'Timeout'}", color
        return STATUS.get(st, STATUS["queued"])[0], color

    @staticmethod
    def _extra(it, st):
        if it.required_by:
            return f"Required by {it.required_by}"
        if st == models.DOWNLOADING and it.file_size:
            return f"{fmt_size(it.file_size * it.progress / 100)} / {fmt_size(it.file_size)}"
        return fmt_size(it.file_size) if it.file_size else ""

    # === INPUT ===
    def editorEvent(self, event, model, option, index):
        node = index.data(NodeRole)
        depth = index.data(DepthRole)
        if event.type() == QEvent.MouseMove:
            target = self.hit(option.rect, node, depth, event.position().toPoint())
            if self.hover != (index.row(), target):
                self.hover = (index.row(), target)
                self.parent().viewport().update()
            return False
        if event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
            target = self.hit(option.rect, node, depth, event.position().toPoint())
            if isinstance(node, Group):
                if target == "check":
                    self.ctl.toggle_checked(node)
                elif target == "remove":
                    self.ctl.remove(node)
                else:
                    self.ctl.toggle_open(node)
                return True
            if target == "check":
                self.ctl.toggle_checked(node)
            elif target == "remove":
                self.ctl.remove(node)
            elif target == "retry":
                self.ctl.retry_item(node)
            elif target == "login":
                self.loginRequested.emit()
            return True
        return False


class InstalledDelegate(_Base):
    def sizeHint(self, option, index):
        return QSize(option.rect.width(), SIZE["row"])

    def paint(self, p, option, index):
        rec = index.data(NodeRole)
        rect = option.rect
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        if option.state & QStyle.State_MouseOver:
            p.fillRect(rect, QColor(C["row-hover"]))
        p.fillRect(QRect(rect.left(), rect.bottom(), rect.width(), 1), QColor(C["divider"]))
        cy = rect.center().y() + 1
        thumb = QRect(rect.left() + 12, cy - 20, 40, 40)
        draw_thumb(p, thumb, self._pixmap(rec.id, rec.preview_url), rec.id, initials(rec.title))
        right = rect.right() - 10
        updating = rec.id in self.ctl.updating
        fresh = rec.id in self.ctl.fresh and not rec.outdated
        if rec.outdated and not updating:
            p.setFont(F_BADGE)
            w = QFontMetrics(F_BADGE).horizontalAdvance("Outdated") + 14
            badge = QRect(right - w, cy - 10, w, 20)
            _, fg, bg, line = STATUS["outdated"]
            rounded(p, badge, 10, bg, line)
            p.setPen(QColor(fg))
            p.drawText(badge, Qt.AlignCenter, "Outdated")
            right = badge.left() - 10
        elif fresh:
            p.setFont(F_SUB)
            w = QFontMetrics(F_SUB).horizontalAdvance("Updated") + 17
            r = QRect(right - w, cy - 10, w, 20)
            icons.paint(p, "check", QRectF(r.left(), cy - 6.5, 13, 13), STATUS["done"][1], 2.5)
            p.setPen(QColor(STATUS["done"][1]))
            p.drawText(r.adjusted(17, 0, 0, 0), Qt.AlignVCenter, "Updated")
            right = r.left() - 10
        tx = thumb.right() + 11
        tw = right - tx
        block_h = 18 + 3 + 16 + (6 if updating else 0)
        top = cy - block_h // 2
        p.setFont(F_TITLE)
        p.setPen(QColor(C["text-strong"]))
        p.drawText(QRect(tx, top, tw, 18), Qt.AlignVCenter, elide(rec.title or rec.id, QFontMetrics(F_TITLE), tw))
        sy = top + 21
        p.setFont(F_SUB)
        if updating:
            pct = self.ctl.updating.get(rec.id, 0.0)
            p.setPen(QColor(C["steam-blue"]))
            p.drawText(QRect(tx, sy, tw, 16), Qt.AlignVCenter, f"Updating {int(pct)}%")
            track = QRect(tx, sy + 19, tw, 3)
            rounded(p, track, 1.5, C["sunken"])
            rounded(p, QRect(tx, track.top(), int(tw * pct / 100), 3), 1.5, C["steam-blue"])
        else:
            if rec.outdated:
                sub = f"Installed {fmt_date(rec.time_updated)} · update available"
            else:
                sub = f"Updated {fmt_date(rec.time_updated)}"
            if rec.file_size:
                sub += f" · {fmt_size(rec.file_size)}"
            p.setPen(QColor(C["text-dim"]))
            p.drawText(QRect(tx, sy, tw, 16), Qt.AlignVCenter, elide(sub, QFontMetrics(F_SUB), tw))
        p.restore()
