import threading

import src.builder as clipwatch
from src import config
from src.classes.models import CBItem
from src.classes.clipboard import Clipboard
from src.wrapper import trackthread

_watcher_thread: threading.Thread | None = None
_watcher_stop:   threading.Event  | None = None

from time import perf_counter_ns as tick

def start(clipboard: Clipboard, alerting=None):
    global _watcher_thread, _watcher_stop

    if _watcher_stop:
        _watcher_stop.set()
    if _watcher_thread and _watcher_thread.is_alive():
        _watcher_thread.join(timeout=1.0)

    stop = threading.Event()
    _watcher_stop = stop
    _watcher_thread = threading.Thread(target=_poll_loop, args=(clipboard, stop, alerting), daemon=True)

    _watcher_thread.start()


def stop():
    global _watcher_stop
    if _watcher_stop:
        _watcher_stop.set()


@trackthread("WATCHER")
def _poll_loop(clipboard: Clipboard, stop: threading.Event, alerting=None):
    while not stop.is_set():
        stop.wait(config.WATCH_POLL_INTERVAL)
        if stop.is_set():
            break

        if not clipwatch.check():
            continue

        # Mark clipboard as processing: a new CBItem is being instantiated
        clipboard._ready.clear()

        snapshot: CBItem | None = None
        appended = False

        try:
            builder = clipwatch.builder(assert_all_types=False)
            types = next(builder)
            filtered = types # [t for t in types if t in config.MIME_TYPES["SUPPORT"]]

            if not filtered:
                continue  # finally will release clipboard._ready

            builder.send(filtered)
            builder.send(filtered[0])
            if config.DEBUG: print("BUILDING CBItem of datatype", filtered[0])
            try:
                x = tick()
                while not stop.is_set():
                    y = tick()
                    snapshot, *_ = next(builder)
                    if snapshot == clipwatch.BuilderState.FAIL_LOADPRIMARY:
                        print("FAILED to load CBItem of datatype", _[0])
                        break #do not add
                    elif snapshot == clipwatch.BuilderState.FAIL_LOADREGULAR:
                        continue

                    if not appended and snapshot.hash != "INVALID_STATE":
                        # Deduplicate: reuse existing item if hash is already known
                        if snapshot in clipboard:
                            snapshot = clipboard.getByHash(snapshot.hash)
                            break

                        # First type fetched — item is identifiable; put it in the clipboard
                        # while it is still in Processing state (_ready cleared).
                        state, value = clipboard.append(snapshot)
                        appended = True

                        # Alert loading state
                        if alerting:
                            alerting(snapshot, state, value)

                        # Release the clipboard lock so observers can see the new slot.
                        # The item itself remains Processing until all types are fetched.
                        clipboard._ready.set()
                        if not state: break #item exists or too much pinned, no point continuing

            except StopIteration:
                pass  # BuilderState; data is whatever was accumulated
        finally:
            # Idempotent: ensures clipboard is never left locked on any exit path
            # (empty filtered list, stop signal mid-fetch, unexpected exception, etc.)
            clipboard._ready.set()
            if config.DEBUG:
                print("COMPLETE")
                print()
                total = clipwatch.blame["INIT"]
                print("INIT", f"{clipwatch.blame["INIT"] * 1e-6:.2f}")
                for k in clipwatch.blame["TYPES"]:
                    print(f"{k:>25}", f"{clipwatch.blame["TYPES"][k] * 1e-6:.2f}")
                    total += clipwatch.blame["TYPES"][k]
                print("TOTAL", f"{(total)*1e-6:.3f}")
                print()
            # Mark item ready only if we own it (not a duplicate reuse)
            if not isinstance(snapshot, CBItem): continue
            snapshot._ready.set()
            if not alerting: continue
            
            alerting(snapshot, state, None)
            