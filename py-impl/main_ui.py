import os
import tkinter as tk
from PIL import Image, ImageTk

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "ui")

COLOR_BG     = "#1e2d3e"   # widget background (darkest)
COLOR_ITEM   = "#2f4a6a"   # item base color
COLOR_ACCENT = "#4a7ab5"   # accent / highlight border (lighter)
COLOR_HOVER  = "#3d6a9b"   # item hover color

BUTTON_SIZE    = 11   # reduced by ~75%
BUTTON_PAD_R   = 3    # gap from right edge of frame (halved)
BUTTON_GAP     = 3    # vertical gap between the two buttons (halved)
BUTTON_PAD_TOP = 3    # gap from top edge of frame (halved)


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

    def __init__(self, cb: "UI_ClipboardWidget"):
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
        self.on_pin_clicked = lambda: None  # custom callback, override as needed

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
        self.pin.bind("<Button-1>", lambda _e: self._on_pin_click())

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
            photo = _load_icon("ellipses.png", 32)
            lbl = tk.Label(self, image=photo, bg=self["bg"], anchor="nw")
            lbl._photo = photo  # prevent GC
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

    def add(self) -> "UI_ClipboardItem":
        item = UI_ClipboardItem(self)
        self.items.append(item)
        return item

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

item1 = ui_clipboard.add()
item1.set_preview("Hello, this is a clipboard entry that is somewhat long", text_truncate=30)

item2 = ui_clipboard.add()
item2.set_preview("/home/user/documents/screenshot.jpg", is_path=True)

ui_clipboard.add()  # bare item, no preview yet

root.mainloop()
