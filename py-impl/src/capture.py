import threading
from Xlib import X, display as xdisplay
from .classes.models import CBItem, Representation


_serve_thread: threading.Thread | None = None
_serve_stop:   threading.Event  | None = None


# Seam for disk storage: right now all data lives in rep.data
def _fetch_rep(rep: Representation) -> bytes:
    return rep.data


def set_clipboard(item: CBItem):
    global _serve_thread, _serve_stop

    if _serve_stop:
        _serve_stop.set()
    if _serve_thread and _serve_thread.is_alive():
        _serve_thread.join(timeout=1.0)

    stop = threading.Event()
    _serve_stop = stop
    _serve_thread = threading.Thread(target=_serve_loop, args=(item, stop), daemon=True)
    _serve_thread.start()


def _serve_loop(item: CBItem, stop: threading.Event):
    d = xdisplay.Display()
    s = d.screen()
    w = s.root.create_window(-1, -1, 1, 1, 0, s.root_depth)

    CLIPBOARD = d.intern_atom('CLIPBOARD')
    TARGETS   = d.intern_atom('TARGETS')

    # advertisements: every mime type the item can serve
    ads: dict[int, Representation] = {
        d.intern_atom(rep.mime_type): rep for rep in item.types
    }

    w.set_selection_owner(CLIPBOARD, X.CurrentTime)
    d.flush()

    while not stop.is_set():
        if not d.pending_events():
            stop.wait(0.005)
            continue

        event = d.next_event()

        if event.type == X.SelectionClear:
            break  # another app took ownership

        if event.type != X.SelectionRequest:
            continue

        req = event
        target = req.target

        if target == TARGETS:
            _respond(d, req, TARGETS, list(ads.keys()), fmt=32)
        elif target in ads:
            _respond(d, req, target, _fetch_rep(ads[target]), fmt=8)
        else:
            _refuse(d, req)

    w.destroy()
    d.close()


def _respond(d, req, prop_atom, value, fmt):
    req.requestor.change_property(req.property, prop_atom, fmt, value)
    _notify(d, req, req.property)

def _refuse(d, req):
    _notify(d, req, X.NONE)

def _notify(d, req, prop):
    ev = req.requestor.create_event({
        'type':      X.SelectionNotify,
        'time':      req.time,
        'requestor': req.requestor,
        'selection': req.selection,
        'target':    req.target,
        'property':  prop,
    })
    req.requestor.send_event(ev)
    d.flush()
