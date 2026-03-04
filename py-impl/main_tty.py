if __name__ != "__main__": exit()

from src.processes import offload as diskload
import src.db as db
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
    if not choice: return

    success = diskload.load(choice)
    if success:
        x.focus(choice)
        server.set( choice )
    else: tty.msgwait("Failed to load data.")
        
def menu_pinning(c: Clipboard):
    print()
    choice = menu_select_general(c, "Pin/Unpin Items")
    if choice: c.togglepin( choice )

def menu_loading(c: Clipboard):
    print()
    load_dialogs = ["Load", "Unload", "Clear Remnants", "Cancel"]
    option = load_dialogs[tty.get_menus(load_dialogs) - 1]
    if option == "Cancel":
        tty.msgwait("Canceled.")
        return
    elif option == "Clear Remnants":
        diskload.cleanup_remnants(c)
        return
    print()
    choice = menu_select_general(c, f"{option} Clipboard Items")
    if not choice: return
    if option == "Load": diskload.load( choice )
    elif option == "Unload":
        if x.selection == choice: tty.msgwait("Cannot unload the active selection. Copy something else!")
        else: diskload.offload( choice )
    

menu_options = [menu_select, menu_pinning, menu_loading, lambda x: None, None]

#main loop
while True:
    print("\n" + tty.output_clipboard(x))
    options = ["Select", "Pin/Unpin", "Load/Unload", "Reload", "Exit"]
    action_choice = print() or menu_options[ tty.get_menus(options) - 1 ]

    if not action_choice:
        break

    action_choice(x)
#exit
diskload.cleanup_remnants(x, clear_unpinned=True)