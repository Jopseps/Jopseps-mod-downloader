"""Run blocking core calls on the thread pool and get results back on the UI thread."""
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

_alive = set()


class _Relay(QObject):
    done = Signal(object)
    failed = Signal(object)


class _Task(QRunnable):
    def __init__(self, fn, relay):
        super().__init__()
        self.fn = fn
        self.relay = relay

    def run(self):
        try:
            result = self.fn()
        except Exception as e:  # noqa: BLE001 - surfaced to the UI via failed
            self.relay.failed.emit(e)
        else:
            self.relay.done.emit(result)


def run_async(fn, done=None, failed=None):
    """fn() runs on a worker; done(result) / failed(exc) run on the UI thread."""
    relay = _Relay()
    _alive.add(relay)

    def finish(cb, value):
        _alive.discard(relay)
        if cb:
            cb(value)

    relay.done.connect(lambda r: finish(done, r))
    relay.failed.connect(lambda e: finish(failed, e))
    QThreadPool.globalInstance().start(_Task(fn, relay))


class EventPipe(QObject):
    """Thread-safe callback: call it from any thread, handler runs on the UI thread."""
    event = Signal(tuple)

    def __init__(self, handler, parent=None):
        super().__init__(parent)
        self.event.connect(lambda args: handler(*args))

    def __call__(self, *args):
        self.event.emit(args)
