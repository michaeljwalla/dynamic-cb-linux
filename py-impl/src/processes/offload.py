import threading

import src.builder as clipwatch
from src import config
from src.classes.models import CBItem
from src.classes.clipboard import Clipboard

_watcher_thread: threading.Thread | None = None
_watcher_stop:   threading.Event  | None = None

from time import perf_counter_ns as tick

def start(clipboard: Clipboard):
    global _watcher_thread, _watcher_stop

    if _watcher_stop:
        _watcher_stop.set()
    if _watcher_thread and _watcher_thread.is_alive():
        _watcher_thread.join(timeout=1.0)

    stop = threading.Event()
    _watcher_stop = stop
    _watcher_thread = threading.Thread(target=_poll_loop, args=(clipboard, stop), daemon=True)
    _watcher_thread.start()


def stop():
    global _watcher_stop
    if _watcher_stop:
        _watcher_stop.set()

def _poll_loop(clipboard: Clipboard, stop: threading.Event):
    while not stop.is_set():
        stop.wait(config.OFFLOAD_POLL_INTERVAL)
        if stop.is_set():
            break

        if not clipboard._ready.is_set():
            continue
        
        
        # # Mark clipboard as processing: a new CBItem is being instantiated
        # clipboard._ready.clear()

