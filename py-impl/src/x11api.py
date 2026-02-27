from .classes.models import Representation
from Xlib import X, display
import time

d = display.Display()
screen = d.screen()
root = screen.root
window = root.create_window(-1,-1,1,1,0, screen.root_depth)

CLIPBOARD = d.intern_atom('CLIPBOARD')
TARGETS = d.intern_atom('TARGETS')
TIMESTAMP = d.intern_atom('TIMESTAMP')

def get_timestamp() -> int | None:
    window.convert_selection(CLIPBOARD, TIMESTAMP, TIMESTAMP, X.CurrentTime)
    d.flush()

    while True:
        event = d.next_event()
        if event.type == X.SelectionNotify:
            break

    if event.property == X.NONE:
        return None

    prop = window.get_full_property(TIMESTAMP, X.AnyPropertyType)
    return prop.value[0] if prop else None

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

# def fetch_data(target_name) -> Representation | None:
#     target_atom = d.intern_atom(target_name)
#     window.convert_selection(CLIPBOARD, target_atom, target_atom, X.CurrentTime)
#     d.flush()
#     d.next_event()
#     prop = window.get_full_property(target_atom, X.AnyPropertyType)
#     if not prop:
#         return None
#     data = bytes(prop.value)

#     return Representation(target_name, data, len(data), True, "")

# Call once at startup, not inside fetch_data
window.change_attributes(event_mask=X.PropertyChangeMask)
d.flush()

INCR_ATOM = d.intern_atom("INCR")


def _drain_events():
    """Discard any queued events before starting a new request."""
    while d.pending_events():
        d.next_event()


def _fetch_incr(target_atom) -> bytes:
    window.delete_property(target_atom)
    d.flush()

    chunks = []

    while True:
        event = d.next_event()
        if event.type != X.PropertyNotify:
            continue
        if event.atom != target_atom:
            continue
        if event.state != X.PropertyNewValue:
            continue

        prop = window.get_full_property(target_atom, X.AnyPropertyType)
        if not prop or len(prop.value) == 0:
            window.delete_property(target_atom)
            d.flush()
            break

        chunks.append(bytes(prop.value))
        window.delete_property(target_atom)
        d.flush()

    return b"".join(chunks)


def fetch_data(target_name) -> Representation | None:
    target_atom = d.intern_atom(target_name)

    _drain_events()

    window.convert_selection(CLIPBOARD, target_atom, target_atom, X.CurrentTime)
    d.flush()

    while True:
        event = d.next_event()
        if event.type == X.SelectionNotify:
            break

    if event.property == X.NONE:
        return None

    prop = window.get_full_property(target_atom, X.AnyPropertyType)
    if not prop:
        return None

    if prop.property_type == INCR_ATOM:
        data = _fetch_incr(target_atom)
    else:
        data = bytes(prop.value)
        window.delete_property(target_atom)
        d.flush()

    return Representation(target_name, data, len(data), True, "")