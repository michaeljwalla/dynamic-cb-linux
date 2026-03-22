import select
import threading
from Xlib import X, display as xdisplay
from Xlib.protocol import event as xevent
from ..classes.models import CBItem, Representation
from .. import config
from .. import x11api as api

_serve_thread: threading.Thread | None = None
_serve_stop:   threading.Event  | None = None


def _fetch_rep(rep: Representation) -> bytes:
    return rep.data


def set(item: CBItem):
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

    w = s.root.create_window(
        -1, -1, 1, 1, 0,
        s.root_depth,
        event_mask=X.PropertyChangeMask
    )

    CLIPBOARD    = d.intern_atom('CLIPBOARD')
    TARGETS      = d.intern_atom('TARGETS')
    INCR         = d.intern_atom('INCR')
    ATOM         = d.intern_atom('ATOM')
    TIMESTAMP    = d.intern_atom('TIMESTAMP')
    MULTIPLE     = d.intern_atom('MULTIPLE')
    SAVE_TARGETS = d.intern_atom('SAVE_TARGETS')

    UTF8_STRING     = d.intern_atom('UTF8_STRING')
    TEXT            = d.intern_atom('TEXT')
    TEXT_PLAIN      = d.intern_atom('text/plain')
    TEXT_PLAIN_UTF8 = d.intern_atom('text/plain;charset=utf-8')
    STRING          = d.intern_atom('STRING')

    ads: dict[int, Representation] = {
        d.intern_atom(rep.mime_type): rep for rep in item.types
    }

    # Synthesise text aliases so Firefox always finds a text target
    _text_rep = (
        ads.get(UTF8_STRING) or
        ads.get(TEXT_PLAIN_UTF8) or
        ads.get(TEXT_PLAIN) or
        next((r for r in item.types if 'text' in r.mime_type), None)
    )
    for alias in (UTF8_STRING, TEXT, TEXT_PLAIN, TEXT_PLAIN_UTF8, STRING):
        if alias not in ads and _text_rep is not None:
            ads[alias] = _text_rep

    static_targets = [TARGETS, TIMESTAMP, SAVE_TARGETS, MULTIPLE]
    all_targets    = list(ads.keys()) + static_targets

    incr: dict[tuple[int, int], tuple] = {}
    CHUNK = 65536

    w.change_property(CLIPBOARD, STRING, 8, b'')
    d.flush()


    real_time = None
    while not stop.is_set():
        readable, _, _ = select.select([d.fileno()], [], [], config.SERVE_CHECK_INTERVAL)
        if stop.is_set():
            break
        if not readable:
            continue
        while d.pending_events():
            e = d.next_event()
            if e.type == X.PropertyNotify and e.window == w:
                real_time = e.time
                break
        if real_time is not None:
            break

    if real_time is None:
        w.destroy()
        d.close()
        return

    w.set_selection_owner(CLIPBOARD, real_time)
    api.timestamp = real_time
    d.flush()

    if d.get_selection_owner(CLIPBOARD) != w:
        w.destroy()
        d.close()
        return

    try:
        done = False
        while not stop.is_set() and not done:
            readable, _, _ = select.select([d.fileno()], [], [], config.SERVE_CHECK_INTERVAL)
            if stop.is_set():
                break
            if not readable:
                continue
            while d.pending_events():
                event = d.next_event()

                if event.type == X.SelectionClear:
                    done = True
                    break

            if event.type == X.PropertyNotify:
                key = (event.window.id, event.atom)
                if event.state == X.PropertyDelete and key in incr:
                    win, target_atom, data, offset = incr[key]
                    chunk = data[offset:offset + CHUNK]
                    win.change_property(event.atom, target_atom, 8, chunk)
                    d.flush()
                    if chunk:
                        incr[key] = (win, target_atom, data, offset + len(chunk))
                    else:
                        del incr[key]
                continue

            if event.type != X.SelectionRequest:
                continue

            req    = event
            target = req.target
            prop   = req.property if req.property != X.NONE else req.target

            if target == TARGETS:
                req.requestor.change_property(prop, ATOM, 32, all_targets)
                _notify(d, req, prop)

            elif target == TIMESTAMP:
                req.requestor.change_property(prop, ATOM, 32, [api.timestamp])
                _notify(d, req, prop)

            elif target == SAVE_TARGETS:
                req.requestor.change_property(prop, ATOM, 32, [])
                _notify(d, req, prop)

            elif target == MULTIPLE:
                pairs_prop = req.requestor.get_full_property(prop, X.AnyPropertyType)
                if pairs_prop and len(pairs_prop.value) % 2 == 0:
                    atoms  = list(pairs_prop.value)
                    result = []
                    for i in range(0, len(atoms), 2):
                        t, p = atoms[i], atoms[i + 1]
                        if t in ads and p != X.NONE:
                            data = _fetch_rep(ads[t])
                            req.requestor.change_property(p, t, 8, data)
                            result += [t, p]
                        else:
                            result += [t, X.NONE]
                    req.requestor.change_property(prop, MULTIPLE, 32, result)
                _notify(d, req, prop)

            elif target in ads:
                if config.DEBUG:
                    print("SERVE", d.get_atom_name(target))

                data = _fetch_rep(ads[target])

                if len(data) > CHUNK:
                    req.requestor.change_attributes(event_mask=X.PropertyChangeMask)
                    req.requestor.change_property(prop, INCR, 32, [len(data)])
                    _notify(d, req, prop)
                    incr[(req.requestor.id, prop)] = (req.requestor, target, data, 0)
                else:
                    req.requestor.change_property(prop, target, 8, data)
                    _notify(d, req, prop)

            else:
                _refuse(d, req)

    except Exception as e:
        print("SERVE ERR", e)

    w.destroy()
    d.close()


def _refuse(d, req):
    _notify(d, req, X.NONE)


def _notify(d, req, prop):
    ev = xevent.SelectionNotify(
        time      = req.time,
        requestor = req.requestor,
        selection = req.selection,
        target    = req.target,
        property  = prop,
    )
    req.requestor.send_event(ev)
    d.flush()
    