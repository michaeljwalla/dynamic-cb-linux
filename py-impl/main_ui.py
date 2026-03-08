import os
import tkinter as tk
from PIL import Image, ImageTk
import src.preview as preview
from src.classes.clipboard import Clipboard
from src.classes.models import _format_bytes
import src.processes.watcher as watcher
import src.processes.server as server
from src import config

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "ui")

COLOR_BG     = "#1e2d3e"   # widget background (darkest)
COLOR_ITEM   = "#2f4a6a"   # item base color
COLOR_ACCENT = "#4a7ab5"   # accent / highlight border (lighter)
COLOR_PIN    = "#b57a4a"   # warm amber — pinned item border highlight
COLOR_SELECT = "#7ab54a"   # green accent — selected item border highlight (highest priority)
COLOR_HOVER  = "#3d6a9b"   # item hover color
COLOR_STATUS = "#253545"   # status bar background (slightly lighter than bg)

BUTTON_SIZE    = 11   # reduced by ~75%
BUTTON_PAD_R   = 3    # gap from right edge of frame (halved)
BUTTON_GAP     = 3    # vertical gap between the two buttons (halved)
BUTTON_PAD_TOP = 3    # gap from top edge of frame (halved)


# Global clipboard and UI state
clipboard = Clipboard()
item_dict = {}  # hash -> UI_ClipboardItem
ui_clipboard = None  # Will be set in demo

def alerting(cbitem):
    global ui_clipboard
    hash = cbitem.hash
    if hash not in item_dict:
        # First call: add in loading state
        item = ui_clipboard.add(cbitem)
        item_dict[hash] = item
    else:
        # Second call: update if ready
        if cbitem._ready.is_set():
            ui_clipboard.add(cbitem, item_dict[hash])
    ui_clipboard._update_no_history()
    ui_clipboard._update_status()


def _load_icon(filename: str, size: int, opacity: float = 1.0) -> ImageTk.PhotoImage:
    """Load a PNG icon from the assets dir, recolor to white, optionally reduce opacity."""
    img = Image.open(os.path.join(ASSETS_DIR, filename)).convert("RGBA")
    img = img.resize((size, size), Image.LANCZOS)
    *_, a = img.split()
    if opacity < 1.0:
        a = a.point(lambda p: int(p * opacity))
    white = Image.new("L", img.size, 255)
    return ImageTk.PhotoImage(Image.merge("RGBA", (white, white, white, a)))


class UI_OptionsMenu(tk.Toplevel):
    """Context menu for options button with Pin/Unpin, Save, Delete."""
    
    def __init__(self, parent: tk.Frame, cbitem, item: "UI_ClipboardItem"):
        super().__init__(parent, bg=COLOR_ITEM, relief="raised", borderwidth=1)
        self.cbitem = cbitem
        self.item = item
        
        # Remove window decorations
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        
        pin_text = "Unpin" if cbitem.pinned else "Pin"
        self.pin_btn = tk.Button(self, text=pin_text, command=self._on_pin, bg=COLOR_ITEM, fg="white", relief="flat")
        self.save_btn = tk.Button(self, text="Save", command=self._on_save, bg=COLOR_ITEM, fg="white", relief="flat")
        self.delete_btn = tk.Button(self, text="Delete", command=self._on_delete, bg=COLOR_ITEM, fg="white", relief="flat")
        
        self.pin_btn.pack(fill=tk.X, padx=5, pady=2)
        self.save_btn.pack(fill=tk.X, padx=5, pady=2)
        self.delete_btn.pack(fill=tk.X, padx=5, pady=2)
        
        # Position relative to the options button
        options_btn = item.options
        # Get absolute position
        x = options_btn.winfo_rootx() + options_btn.winfo_width() + 5
        y = options_btn.winfo_rooty()
        self.geometry(f"+{x}+{y}")
        
        # Bind to destroy on focus out
        self.bind("<FocusOut>", lambda e: self.destroy())
        self.focus_set()
    
    def _on_pin(self):
        self.item._on_pin_click()
        self.destroy()
    
    def _on_save(self):
        # TODO: Implement save functionality
        print("Save not implemented")
        self.destroy()
    
    def _on_delete(self):
        # Remove from UI
        self.item._cb.remove(self.item)
        # Remove from clipboard
        clipboard.remove(self.cbitem)
        self.item._cb._update_no_history()
        self.item._cb._update_status()
        self.destroy()


class UI_OptionsButton(tk.Label):
    """Three-dot options button — anchored to top-right of parent frame."""
    _pad_top = BUTTON_PAD_TOP

    def __init__(self, parent: tk.Frame):
        photo = _load_icon("ellipses.png", BUTTON_SIZE)
        super().__init__(
            parent,
            image=photo,
            bg=parent["bg"],
            cursor="hand2",
            width=BUTTON_SIZE,
            height=BUTTON_SIZE,
        )
        self._photo = photo  # prevent GC

    def place_in_parent(self):
        self.place(
            width=BUTTON_SIZE, height=BUTTON_SIZE,
            relx=1, rely=0,
            x=-(BUTTON_SIZE + BUTTON_PAD_R),
            y=self._pad_top,
        )

    def sync_bg(self, color: str):
        self.configure(bg=color)


class UI_PinButton(tk.Label):
    """Thumbtack pin button — anchored below the options button on the right."""
    _pad_top = BUTTON_PAD_TOP + BUTTON_SIZE + BUTTON_GAP

    def __init__(self, parent: tk.Frame):
        photo = _load_icon("thumbtack.png", BUTTON_SIZE, opacity=0.25)
        super().__init__(
            parent,
            image=photo,
            bg=parent["bg"],
            cursor="hand2",
            width=BUTTON_SIZE,
            height=BUTTON_SIZE,
        )
        self._photo = photo
        self._opacity = 0.25

    def place_in_parent(self):
        self.place(
            width=BUTTON_SIZE, height=BUTTON_SIZE,
            relx=1, rely=0,
            x=-(BUTTON_SIZE + BUTTON_PAD_R),
            y=self._pad_top,
        )

    def sync_bg(self, color: str):
        self.configure(bg=color)

    def set_opacity(self, opacity: float):
        """Update the button's opacity (0.0 to 1.0)."""
        self._opacity = opacity
        photo = _load_icon("thumbtack.png", BUTTON_SIZE, opacity=opacity)
        self.configure(image=photo)
        self._photo = photo


class UI_ClipboardItem(tk.Frame):
    _height    = 80
    _bg        = COLOR_ITEM
    _bg_hover  = COLOR_HOVER
    _bg_accent = COLOR_ACCENT

    def __init__(self, cb: "UI_ClipboardWidget", cbitem=None, parent=None):
        actual_parent = parent if parent is not None else cb
        super().__init__(
            actual_parent,
            bg=self._bg,
            height=self._height,
            highlightthickness=1,
            highlightbackground=self._bg_accent,
        )
        self._cb       = cb
        self._preview: tk.Label | None = None
        self._pinned   = False
        self.cbitem = cbitem
        self.on_pin_clicked = lambda: clipboard.togglepin(self.cbitem) if self.cbitem else None  # custom callback, override as needed

        self.pack_propagate(False)
        self.options = UI_OptionsButton(self)
        self.pin     = UI_PinButton(self)

        # Outer padding separates items from each other and the widget edges
        self.pack(fill=tk.X, padx=8, pady=4)
        self.options.place_in_parent()
        self.pin.place_in_parent()

        # Bind interactions
        self.bind("<Enter>", lambda _e: self._hover(True))
        self.bind("<Leave>", lambda _e: self._hover(False))
        self.bind("<Button-1>", lambda _e: self._on_click())
        self.pin.bind("<Button-1>", lambda _e: self._on_pin_click())
        self.options.bind("<Button-1>", lambda _e: self._on_options_click())

        # Bind mousewheel events to delegate scroll to clipboard widget
        self.bind("<Button-4>",   lambda _e: self._cb._on_mousewheel(_e))
        self.bind("<Button-5>",   lambda _e: self._cb._on_mousewheel(_e))
        self.bind("<MouseWheel>", lambda _e: self._cb._on_mousewheel(_e))

        # Set initial loading preview
        if cbitem:
            self.set_preview("( ... processing ... )" , is_path=False)

    def _update_pin_accent(self):
        color = COLOR_PIN if self._pinned else COLOR_ACCENT
        self.configure(highlightbackground=color)

    def _update_accent(self):
        """Update accent color with priority: selected > pinned > normal."""
        if self._cb.selected_item == self:
            color = COLOR_SELECT
        elif self._pinned:
            color = COLOR_PIN
        else:
            color = COLOR_ACCENT
        self.configure(highlightbackground=color)

    def _hover(self, active: bool):
        color = self._bg_hover if active else self._bg
        self.configure(bg=color)
        self.options.sync_bg(color)
        self.pin.sync_bg(color)
        if self._preview:
            self._preview.configure(bg=color)

    def _on_pin_click(self):
        """Toggle pin state: pin moves to top (full opacity), unpin moves to bottom (25% opacity)."""
        if self._pinned:
            # Unpin: move to bottom of unpinned section
            self._pinned = False
            self.pin.set_opacity(0.25)
            self._update_accent()
            self._cb.items.remove(self)
            self._cb.items.append(self)
        else:
            # Pin: move to bottom of pinned section (top if no other pinned items)
            self._pinned = True
            self.pin.set_opacity(1.0)
            self._update_accent()
            self._cb.items.remove(self)
            # Find first unpinned item and insert before it
            insert_idx = len(self._cb.items)
            for i, item in enumerate(self._cb.items):
                if not item._pinned:
                    insert_idx = i
                    break
            self._cb.items.insert(insert_idx, self)
        self._cb._repack_items()
        self._cb._update_status()
        self.on_pin_clicked()

    def _on_click(self):
        """Set the clipboard selection to this item."""
        if self.cbitem and self.cbitem._ready.is_set():
            cbitem = clipboard.getByHash(self.cbitem.hash)
            if cbitem:
                clipboard.focus(cbitem)
                server.set(cbitem)
                # Update UI selection
                self._cb._set_selection(self)
            else:
                # Reset or ignore
                pass
        # If not ready, ignore

    def _on_options_click(self):
        """Open the options menu."""
        if self.cbitem:
            UI_OptionsMenu(self, self.cbitem, self)

    def update_with_cbitem(self, cbitem):
        self.cbitem = cbitem
        result, is_path = preview.generate(cbitem)
        self.set_preview(result, is_path=is_path)

    def set_preview(self, text: str = "", text_truncate: int = 40, is_path: bool = False):
        """
        Set the left-side preview content.
        - is_path=True : shows ellipses.png as a placeholder image (default until real path
                         resolution is wired up)
        - is_path=False: shows text truncated to text_truncate chars, appending "..."
        The preview is left-justified and stops before the two buttons on the right.
        """
        if self._preview:
            self._preview.destroy()
            self._preview = None

        PAD_L     = 8
        PAD_V     = 6
        right_gap = BUTTON_SIZE + BUTTON_PAD_R + 6  # room for buttons + small gap

        if is_path:
            if os.path.exists(text):
                img = Image.open(text)
                img.thumbnail((196, 68))  # fit within available space
                photo = ImageTk.PhotoImage(img)
                lbl = tk.Label(self, image=photo, bg=self["bg"], anchor="nw")
                lbl._photo = photo
            else:
                # placeholder
                photo = _load_icon("ellipses.png", 32)
                lbl = tk.Label(self, image=photo, bg=self["bg"], anchor="nw")
                lbl._photo = photo
        else:
            display = text[:text_truncate] + "..." if len(text) > text_truncate else text
            lbl = tk.Label(
                self,
                text=display,
                bg=self["bg"],
                fg="white",
                anchor="nw",
                justify="left",
                font=("Helvetica", 9),
                wraplength=180,
            )

        # Make the preview clickable
        lbl.bind("<Button-1>", lambda e: self._on_click())
        lbl.configure(cursor="hand2")

        # relwidth=1 with negative width offset fills the frame minus reserved areas
        lbl.place(
            x=PAD_L, y=PAD_V,
            relwidth=1, width=-(PAD_L + right_gap),
            height=self._height - PAD_V * 2,
        )
        self._preview = lbl


class UI_ClipboardWidget(tk.Frame):
    def __init__(self, root: tk.Tk, w: int = int(240*1.5), h: int = int(300*1.5)):
        super().__init__(root, bg=COLOR_BG, width=w, height=h)
        self.items: list[UI_ClipboardItem] = []
        self.selected_item: UI_ClipboardItem | None = None  # Track currently selected item
        self.pack_propagate(False)
        self.pack()

        # Header frame (non-scrollable)
        self.header_frame = tk.Frame(self, bg=COLOR_BG, height=0)
        self.header_frame.pack(side=tk.TOP, fill=tk.X)
        self.header_frame.pack_propagate(True)

        # Status frame at bottom
        self.status_frame = tk.Frame(self, bg=COLOR_STATUS, height=20)
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_frame.pack_propagate(False)

        self.status_left = tk.Label(
            self.status_frame,
            text="",
            bg=COLOR_STATUS,
            fg="white",
            font=("Helvetica", 8),
            anchor="w"
        )
        self.status_left.pack(side=tk.LEFT, padx=5)

        self.status_right = tk.Label(
            self.status_frame,
            text="",
            bg=COLOR_STATUS,
            fg="white",
            font=("Helvetica", 8),
            anchor="e"
        )
        self.status_right.pack(side=tk.RIGHT, padx=5)

        # Scrollbar
        self._scrollbar = tk.Scrollbar(self, orient=tk.VERTICAL)
        self._scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Canvas for scrolling
        self._canvas = tk.Canvas(
            self,
            bg=COLOR_BG,
            highlightthickness=0,
            yscrollcommand=self._scrollbar.set
        )
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._scrollbar.configure(command=self._canvas.yview)

        # Frame inside canvas to hold items
        self._scroll_frame = tk.Frame(self._canvas, bg=COLOR_BG)
        self._canvas_window = self._canvas.create_window((0, 0), window=self._scroll_frame, anchor="nw")

        # Bind canvas configure to update scroll region
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._scroll_frame.bind("<Configure>", self._on_scroll_frame_configure)

        # No history label (placed on canvas, centered)
        self.no_history_label = tk.Label(
            self._canvas,
            text="No history, copy something!",
            bg=self["bg"],
            fg="white",
            font=("Helvetica", 12),
        )
        self._no_history_window = None  # placeholder for canvas window ID

        # Ensure header is on top
        self.header_frame.lift()

        self._update_no_history()
        self._update_status()

    def _set_selection(self, item: "UI_ClipboardItem"):
        """Set the selected item and update accent colors."""
        # Reset previous selection
        if self.selected_item:
            self.selected_item._update_accent()
        
        # Set new selection
        self.selected_item = item
        item._update_accent()

    def _on_canvas_configure(self, event):
        """Update scroll frame width to match canvas width and center no_history label."""
        self._canvas.itemconfig(self._canvas_window, width=event.width)
        # Center the no_history label in the canvas viewport
        if self._no_history_window is not None:
            self._canvas.coords(self._no_history_window, event.width / 2, event.height / 2)

    def _on_scroll_frame_configure(self, event):
        """Update canvas scroll region when scroll frame size changes."""
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_mousewheel(self, event):
        """Handle mousewheel scroll events."""
        if event.num == 4:
            self._canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self._canvas.yview_scroll(1, "units")
        else:
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def add(self, cbitem=None, item=None) -> "UI_ClipboardItem":
        if item is None:
            item = UI_ClipboardItem(self, cbitem, parent=self._scroll_frame)
            # Insert at top of unpinned items (after pinned)
            insert_idx = 0
            for i, existing_item in enumerate(self.items):
                if not existing_item._pinned:
                    insert_idx = i
                    break
            else:
                insert_idx = len(self.items)
            self.items.insert(insert_idx, item)
            # Set initial accent color
            item._update_accent()
            # Check if this item should be selected (matches clipboard selection)
            if cbitem and clipboard.selection and cbitem.hash == clipboard.selection.hash:
                self._set_selection(item)
        else:
            item.update_with_cbitem(cbitem)
            # Update accent in case pin state changed
            item._update_accent()
            # Check if this updated item should be selected
            if cbitem and clipboard.selection and cbitem.hash == clipboard.selection.hash:
                self._set_selection(item)
        self._repack_items()
        self._update_no_history()
        self._update_status()
        return item

    def remove(self, item: "UI_ClipboardItem"):
        if item in self.items:
            self.items.remove(item)
            item.destroy()
            self._repack_items()
            self._update_no_history()
            self._update_status()

    def _update_no_history(self):
        if len(self.items) == 0:
            self.no_history_label.configure(text="No history, copy something!")
            # Create or show the canvas window
            if self._no_history_window is None:
                self._no_history_window = self._canvas.create_window(
                    self._canvas.winfo_width() / 2,
                    self._canvas.winfo_height() / 2,
                    window=self.no_history_label
                )
        else:
            # Hide the label by removing the canvas window
            if self._no_history_window is not None:
                self._canvas.delete(self._no_history_window)
                self._no_history_window = None

    def _update_status(self):
        x = len(self.items)
        max_items = config.MAX_ITEMS
        y = sum(1 for item in self.items if item._pinned)
        total_memory = sum(item.cbitem.total_size for item in self.items if hasattr(item, 'cbitem'))
        # Calculate cached memory size by summing each cached representation
        a = sum(rep.size for item in self.items if hasattr(item, 'cbitem') for rep in item.cbitem.types if rep.cached)
        # Show only non-cached memory
        used_memory = total_memory - a
        z = _format_bytes(used_memory, symbols=False)
        max_memory_mb = config.MEM_THRESHOLD_MB
        max_memory = _format_bytes(max_memory_mb * 1e6)
        a_formatted = _format_bytes(a)

        self.status_left.configure(text=f"Clipboard {x}/{max_items} ({y} pinned)")
        self.status_right.configure(text=f"{z}/{max_memory} ({a_formatted} cached)")

    def add_async(self, cbitem, item=None):
        self.after(0, lambda c=cbitem, i=item: self.add(c, i))

    def remove_async(self, item):
        self.after(0, lambda i=item: self.remove(i))

    def _repack_items(self):
        """Repack all items in order to match self.items list order."""
        for item in self.items:
            item.pack_forget()
        for item in self.items:
            item.pack(fill=tk.X, padx=8, pady=4)


# ── demo ──────────────────────────────────────────────────────────────────────
root = tk.Tk()
root.configure(bg=COLOR_BG)

ui_clipboard = UI_ClipboardWidget(root)

# Start watcher with alerting
watcher.start(clipboard, alerting)

root.mainloop()

