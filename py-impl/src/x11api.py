from .classes.models import Representation
from . import config

from Xlib import X, display
from time import perf_counter as tick, sleep

d = display.Display()
screen = d.screen()
root = screen.root
window = root.create_window(-1,-1,1,1,0, screen.root_depth)

CLIPBOARD = d.intern_atom('CLIPBOARD')
TARGETS = d.intern_atom('TARGETS')
TIMESTAMP = d.intern_atom('TIMESTAMP')

timestamp = -1

#just check if 
def check() -> bool: #bool
    global timestamp
    last = timestamp
    timestamp = get_timestamp()
    return last != timestamp

def get_timestamp() -> int:
    window.convert_selection(CLIPBOARD, TIMESTAMP, TIMESTAMP, X.CurrentTime)
    d.flush()

    while True:
        event = d.next_event()
        if event.type == X.SelectionNotify:
            break

    if event.property == X.NONE:
        return 0

    prop = window.get_full_property(TIMESTAMP, X.AnyPropertyType)
    return prop.value[0] if prop else 0
timestamp = get_timestamp() - 1 #initialize timestamp at startup

def get_targets() -> list[str]:
    window.convert_selection(CLIPBOARD, TARGETS, TARGETS, X.CurrentTime)
    d.flush()

    while True:
        event = d.next_event()
        if event.type == X.SelectionNotify:
            break

    if event.property == X.NONE:
        return []

    prop = window.get_full_property(TARGETS, X.AnyPropertyType)
    if not prop:
        return []

    names = [d.get_atom_name(a) for a in prop.value]
    return [n for n in names if '/' in n]

# Call once at startup, not inside fetch_data
window.change_attributes(event_mask=X.PropertyChangeMask)
d.flush()

INCR_ATOM = d.intern_atom("INCR")


def _drain_events():
    while d.pending_events():
        d.next_event()


def _fetch_incr(target_atom, timeout=config.WATCH_TIMEOUT) -> bytes:
    window.delete_property(target_atom)
    d.flush()

    chunks = []

    start = tick()
    while tick() - start < timeout:
        if not d.pending_events():
            sleep(config.WATCH_POLL_RETRY_INTERVAL)
            continue

        event = d.next_event()
        if event.type != X.PropertyNotify:
            continue
        if event.atom != target_atom:
            continue
        if event.state != X.PropertyNewValue:
            continue
        
        start = tick()
        prop = window.get_full_property(target_atom, X.AnyPropertyType)
        if not prop or len(prop.value) == 0:
            window.delete_property(target_atom)
            d.flush()
            break

        chunks.append(bytes(prop.value))
        window.delete_property(target_atom)
        d.flush()
    else:
        return b""
    return b"".join(chunks)


def fetch_data(target_name, timeout=config.WATCH_TIMEOUT) -> Representation | None:
    if config.DEBUG: print("START", target_name)
    target_atom = d.intern_atom(target_name)

    start = tick()
    #will let multithreading cancel workers
    while tick() - start < timeout:
        _drain_events()

        window.convert_selection(CLIPBOARD, target_atom, target_atom, X.CurrentTime)
        d.flush()

        deadline = tick() + timeout
        while tick() < deadline:
            if d.pending_events():
                event = d.next_event()
                if event.type == X.SelectionNotify:
                    break
            else:
                sleep(config.WATCH_POLL_RETRY_INTERVAL)
                pass
        else:
            return None  # owner never responded within timeout

        if event.property == X.NONE:
            continue  # Clipboard doesn't support this type

        #restart timeout window
        prop = window.get_full_property(target_atom, X.AnyPropertyType)
        if not prop:
            # continue
            if config.DEBUG: print("Fail prop")
            return None
        
        if config.DEBUG: print("GOT PROP")
        start = tick()
        if prop.property_type == INCR_ATOM:
            data = _fetch_incr(target_atom, timeout=timeout)
            if not data: return None
        else:
            data = bytes(prop.value)
            window.delete_property(target_atom)
            d.flush()

        return Representation(target_name, data, len(data), True, "")
    else:
        return None