"""
IPC socket server — lets a bash command show/hide/toggle the clipboard window.

Usage (bash):
    echo "show"   | socat - UNIX-CONNECT:/tmp/dynamic-cb.sock
    echo "hide"   | socat - UNIX-CONNECT:/tmp/dynamic-cb.sock
    echo "toggle" | socat - UNIX-CONNECT:/tmp/dynamic-cb.sock

start(root, frame) launches the listener thread.
stop()             shuts it down.
"""

import socket
import threading
import os

SOCKET_PATH = "/tmp/dynamic-cb.sock"

_thread: threading.Thread | None = None
_stop:   threading.Event  | None = None


def start(root, frame):
    """
    root  — tk.Tk instance (used for after() scheduling and pointer coords)
    frame — the tk widget to show/hide/move
    """
    global _thread, _stop

    if _stop:
        _stop.set()
    if _thread and _thread.is_alive():
        _thread.join(timeout=1.0)

    _stop = threading.Event()
    _thread = threading.Thread(
        target=_serve,
        args=(root, frame, _stop),
        daemon=True,
    )
    _thread.start()


def stop():
    global _stop
    if _stop:
        _stop.set()



def _show(root, frame):
    mx = root.winfo_pointerx()
    my = root.winfo_pointery()
    root.geometry(f"+{mx + 20}+{my}")
    root.deiconify()
    root.lift()
    root.focus_force()


def _hide(root):
    root.withdraw()


def _toggle(root, frame):
    if root.state() == "withdrawn":
        _show(root, frame)
    else:
        _hide(root)


def _dispatch(root, frame, cmd: str):
    cmd = cmd.strip().lower()
    if cmd == "show":
        root.after(0, lambda: _show(root, frame))
    elif cmd == "hide":
        root.after(0, lambda: _hide(root))
    elif cmd == "toggle":
        root.after(0, lambda: _toggle(root, frame))


def _serve(root, frame, stop: threading.Event):
    # Clean up stale socket
    try:
        os.unlink(SOCKET_PATH)
    except FileNotFoundError:
        pass

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as srv:
        srv.bind(SOCKET_PATH)
        os.chmod(SOCKET_PATH, 0o666)  # allow anyone to connect
        srv.listen(5)
        srv.settimeout(1.0)  # so we can check stop periodically

        while not stop.is_set():
            try:
                conn, _ = srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            with conn:
                try:
                    data = conn.recv(256).decode("utf-8", errors="ignore")
                    _dispatch(root, frame, data)
                except Exception as e:
                    print("IPC ERR", e)

    try:
        os.unlink(SOCKET_PATH)
    except FileNotFoundError:
        pass
