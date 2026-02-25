from .classes.models import Representation
from Xlib import X, display

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
    d.next_event()
    prop = window.get_full_property(TIMESTAMP, X.AnyPropertyType)
    return prop.value[0] if prop else None

def get_targets() -> list[str]:
    window.convert_selection(CLIPBOARD, TARGETS, TARGETS, X.CurrentTime)
    d.flush()
    d.next_event()
    prop = window.get_full_property(TARGETS, X.AnyPropertyType)
    if not prop:
        return []
    names = [d.get_atom_name(a) for a in prop.value]
    return [n for n in names if '/' in n]

def fetch_data(target_name) -> Representation | None:
    target_atom = d.intern_atom(target_name)
    window.convert_selection(CLIPBOARD, target_atom, target_atom, X.CurrentTime)
    d.flush()
    d.next_event()
    prop = window.get_full_property(target_atom, X.AnyPropertyType)
    if not prop: return None
    data = bytes(prop.value)

    return Representation(target_name, data, len(data))
