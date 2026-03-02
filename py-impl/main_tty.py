import src.storage as storage
from src.classes.models import *
from src.classes.clipboard import Clipboard
import src.config as config

import src.builder as clipwatch
from src import tty
from src.processes import watcher, server

from time import perf_counter_ns as tick

x = Clipboard()
watcher.start(x)


def menu_select_general(c:Clipboard, header) -> CBItem|None:
    options = ["Pinned", "Unpinned", "Cancel"]
    action_choice = options[ tty.get_menus(options, header=header) - 1 ]
    if action_choice == "Cancel":
        tty.msgwait("Canceled")
        return None
    pinned, unpinned = c.data
    choice:CBItem = None
    if action_choice == "Pinned":
        if not len(pinned):
            tty.msgwait("No pinned items.")
            return None
        selection_choice = tty.get_range(max=len(pinned), query=f"Select [ {1} - {len(pinned)} ]") - 1
        choice = pinned.at(selection_choice)
        #
    else:
        if not len(unpinned):
            tty.msgwait("No unpinned items.")
            return None
        selection_choice = tty.get_range(max=len(unpinned), query=f" Select[ {1} - {len(unpinned)} ]") - 1
        choice = unpinned.at(selection_choice)
    
    if choice.data._processing():
        tty.msgwait("This item is still processing.")
        return None
    return choice.data
    

def menu_select(c: Clipboard):
    print()
    choice = menu_select_general(c, "Updating Clipboard Selection:")
    if choice: server.set( choice )
        
def menu_pinning(c: Clipboard):
    print()
    choice = menu_select_general(c, "Pin/Unpin Items")
    if choice: c.togglepin( choice )

menu_options = [menu_select, menu_pinning, None]

#main loop
while True:
    print("\n" + tty.output_clipboard(x))
    options = ["Select", "Pin/Unpin", "Cancel"]
    action_choice = print() or menu_options[ tty.get_menus(options) - 1 ]

    if not action_choice:
        continue

    action_choice(x)
