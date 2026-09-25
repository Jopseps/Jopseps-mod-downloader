"""QWebChannel object the injected Workshop script talks to. Lives in an isolated JS world."""
from PySide6.QtCore import QFile, QIODevice, QObject, QTimer, Signal, Slot

from jmd import paths
from jmd.core.models import Group


class WorkshopBridge(QObject):
    queuedChanged = Signal(list)

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.ctl = controller
        self._timer = QTimer(self, singleShot=True, interval=120, timeout=self._push)
        controller.queueChanged.connect(self._timer.start)
        controller.profileChanged.connect(self._timer.start)

    def queued_ids(self):
        ids = [i.id for i in self.ctl.queue.items()]
        ids += [n.id for n in self.ctl.queue.nodes if isinstance(n, Group)]
        return ids

    def _push(self):
        self.queuedChanged.emit(self.queued_ids())

    @Slot(result=list)
    def snapshot(self):
        return self.queued_ids()

    @Slot(str)
    def add(self, mod_id):
        if mod_id.isdigit():
            self.ctl.add_ids([mod_id])

    @Slot(str)
    def remove(self, mod_id):
        if self.ctl.run and mod_id in self.ctl.run["ids"]:
            self.ctl.toast.emit("Can't remove while downloading")
            return
        self.ctl.remove_id(mod_id)


def script_source():
    """qwebchannel.js (bundled with QtWebChannel) + our injector, as one script."""
    import PySide6.QtWebChannel  # noqa: F401 - registers the :/qtwebchannel resource
    f = QFile(":/qtwebchannel/qwebchannel.js")
    channel_js = ""
    if f.open(QIODevice.ReadOnly):
        channel_js = bytes(f.readAll()).decode("utf-8")
        f.close()
    with open(paths.asset("inject.js"), "r", encoding="utf-8") as fh:
        return channel_js + "\n" + fh.read()
