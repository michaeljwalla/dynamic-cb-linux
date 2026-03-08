import os
import tkinter as tk
from PIL import Image, ImageTk
import src.preview as preview
from src.classes.clipboard import Clipboard
import src.processes.watcher as watcher
import src.processes.server as server

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "ui")

COLOR_BG     = "#1e2d3e"   # widget background (darkest)
COLOR_ITEM   = "#2f4a6a"   # item base color
COLOR_ACCENT = "#4a7ab5"   # accent / highlight border (lighter)
COLOR_HOVER  = "#3d6a9b"   # item hover color

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


def _load_icon(filename: str, size: int, opacity: float = 1.0) -> ImageTk.PhotoImage:
    """Load a PNG icon from the assets dir, recolor to white, optionally reduce opacity."""
    img = Image.open(os.path.join(ASSETS_DIR, filename)).convert("RGBA")
    img = img.resize((size, size), Image.LANCZOS)
    *_, a = img.split()
    if opacity < 1.0:
        a = a.point(lambda p: int(p * opacity))
    white = Image.new("L", img.size, 255)
    return ImageTk.PhotoImage(Image.merge("RGBA", (white, white, white, a)))


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

    def __init__(self, cb: "UI_ClipboardWidget", cbitem=None):
        super().__init__(
            cb,
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

        # Set initial loading preview
        if cbitem:
            self.set_preview("Loading...", is_path=False)

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
            self._cb.items.remove(self)
            self._cb.items.append(self)
        else:
            # Pin: move to bottom of pinned section (top if no other pinned items)
            self._pinned = True
            self.pin.set_opacity(1.0)
            self._cb.items.remove(self)
            # Find first unpinned item and insert before it
            insert_idx = len(self._cb.items)
            for i, item in enumerate(self._cb.items):
                if not item._pinned:
                    insert_idx = i
                    break
            self._cb.items.insert(insert_idx, self)
        self._cb._repack_items()
        self.on_pin_clicked()

    def _on_click(self):
        """Set the clipboard selection to this item."""
        if self.cbitem and self.cbitem._ready.is_set():
            cbitem = clipboard.getByHash(self.cbitem.hash)
            if cbitem:
                clipboard.focus(cbitem)
                server.set(cbitem)
            else:
                # Reset or ignore
                pass
        # If not ready, ignore

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

        # relwidth=1 with negative width offset fills the frame minus reserved areas
        lbl.place(
            x=PAD_L, y=PAD_V,
            relwidth=1, width=-(PAD_L + right_gap),
            height=self._height - PAD_V * 2,
        )
        self._preview = lbl


class UI_ClipboardWidget(tk.Frame):
    def __init__(self, root: tk.Tk, w: int = 240, h: int = 400):
        super().__init__(root, bg=COLOR_BG, width=w, height=h)
        self.items: list[UI_ClipboardItem] = []
        self.pack_propagate(False)
        self.pack()

    def add(self, cbitem=None, item=None) -> "UI_ClipboardItem":
        if item is None:
            item = UI_ClipboardItem(self, cbitem)
            # Insert at top of unpinned items (after pinned)
            insert_idx = 0
            for i, existing_item in enumerate(self.items):
                if not existing_item._pinned:
                    insert_idx = i
                    break
            else:
                insert_idx = len(self.items)
            self.items.insert(insert_idx, item)
        else:
            item.update_with_cbitem(cbitem)
        self._repack_items()
        return item

    def remove(self, item: "UI_ClipboardItem"):
        if item in self.items:
            self.items.remove(item)
            item.destroy()
            self._repack_items()

    def add_async(self, cbitem, item=None):
        self.after(0, lambda: self.add(cbitem, item))

    def remove_async(self, item):
        self.after(0, lambda: self.remove(item))

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

#TODO: connect main_ui.py with preview module and clipboard module and write data
# rememebre the ... mode in which you should not read data and just keep as ellipses / (writing........)