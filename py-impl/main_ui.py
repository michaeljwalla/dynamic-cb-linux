from ast import Pass
from calendar import c
import os
import re
import subprocess
import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk
import src.preview as preview
from src.classes.clipboard import Clipboard
from src.classes.models import CBItem, _format_bytes
import src.processes.watcher as watcher
import src.processes.server as server
import src.processes.offload as offloader
import src.processes.ipc as ipc
import src.x11api as api
from src import config
from src import ui_themes
import time

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "ui")

COLOR_BG, COLOR_ITEM, COLOR_ACCENT, COLOR_PIN, COLOR_SELECT, COLOR_HOVER, COLOR_STATUS, COLOR_TEXT = ui_themes.Dracula

BUTTON_SIZE    = 11   # reduced by ~75%
BUTTON_PAD_R   = 3    # gap from right edge of frame (halved)
BUTTON_GAP     = 3    # vertical gap between the two buttons (halved)
BUTTON_PAD_TOP = 3    # gap from top edge of frame (halved)


# Global clipboard and UI state
clipboard = Clipboard()
item_dict:dict[str, "UI_ClipboardItem"] = {}  # hash -> UI_ClipboardItem
ui_clipboard = None  # Will be set in demo

errpopup:"TkPopup" = None
def alerting(cbitem, state, popped):
    global ui_clipboard
    if not state:
        if popped: return #alr exists
        else:
            errpopup.deiconify()
            errpopup.focus_set()
            #ui_clipboard.remove( item_dict[cbitem.hash] ) # too many pinned. remove from UI but not clipboard (since it is pinned, it won't be auto-removed)
            return
    
    hash = cbitem.hash
    if hash not in item_dict:
        if popped and popped.hash in item_dict:
            ui_clipboard.remove( item_dict[popped.hash] ) #this pops the last unpinned value
            # Remove from clipboard
            offloader.cleanup_remnants(clipboard, clear_unpinned=False)

            ui_clipboard._update_no_history()
            ui_clipboard._update_status()
        # First call: add in loading state
        item = ui_clipboard.add(cbitem)
        item_dict[hash] = item
    else:
        # Second call: update if ready
        if cbitem._ready.is_set():
            ui_clipboard.add(cbitem, item_dict[hash])
    ui_clipboard._update_no_history()
    ui_clipboard._update_status()

#update_preview; update_with_cbitem

offload_dict:dict[str, CBItem] = {} #hash -> UI_ClipboardItem
def offloading(state:bool, items:list[CBItem]=None):
    global ui_clipboard
    if not state:
        for item in offload_dict.values():
            if item.hash not in item_dict: continue
            ui = item_dict[item.hash]
            ui.update_with_cbitem(item)
        offload_dict.clear()
        ui_clipboard._update_status()
        return
    #
    for item in items:
        if item.hash not in item_dict: return

        offload_dict[item.hash] = item
        ui = item_dict[item.hash]
        ui.set_preview("( ... offloading ... )", is_path=False)
    ui_clipboard._update_status()
    return

    


def _load_icon(filename: str, size: int, opacity: float = 1.0) -> ImageTk.PhotoImage:
    """Load a PNG icon from the assets dir, recolor to white, optionally reduce opacity."""
    img = Image.open(os.path.join(ASSETS_DIR, filename)).convert("RGBA")
    img = img.resize((size, size), Image.LANCZOS)
    *_, a = img.split()
    if opacity < 1.0:
        a = a.point(lambda p: int(p * opacity))
    white = Image.new("L", img.size, 255)
    return ImageTk.PhotoImage(Image.merge("RGBA", (white, white, white, a)))


def _popup_monitor(win) -> tuple[int, int, int, int]:
    """Return (x, y, w, h) of the monitor containing the centre of win."""
    win.update_idletasks()
    cx = win.winfo_rootx() + win.winfo_width() // 2
    cy = win.winfo_rooty() + win.winfo_height() // 2
    try:
        for line in subprocess.check_output(["xrandr"], text=True).splitlines():
            if " connected" not in line:
                continue
            m = re.search(r"(\d+)x(\d+)\+(\d+)\+(\d+)", line)
            if not m:
                continue 
            mw, mh, mx, my = map(int, m.groups())
            if mx <= cx < mx + mw and my <= cy < my + mh:
                return mx, my, mw, mh
    except Exception:
        pass
    return 0, 0, win.winfo_screenwidth(), win.winfo_screenheight()


def _native_save_dialog(default_name: str, mime_type: str) -> str | None:
    """
    Try zenity (GTK/GNOME) then kdialog (KDE) for a native save dialog.
    Falls back to tkinter filedialog if neither is available.
    Returns the chosen path string, or None if cancelled.
    """
    ext = mime_type.split("/")[-1]
    filename = f"{default_name}.{ext}"
    # zenity (GNOME / GTK)
    try:
        result = subprocess.run(
            ["zenity", "--file-selection", "--save", "--confirm-overwrite",
             f"--filename={filename}", f"--file-filter={mime_type} | *.{ext}"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip() or None
        return None  # user cancelled
    except FileNotFoundError:
        pass
    # kdialog (KDE)
    try:
        result = subprocess.run(
            ["kdialog", "--getsavefilename", filename, f"*.{ext}"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip() or None
        return None
    except FileNotFoundError:
        pass
    # fallback
    return filedialog.asksaveasfilename(
        defaultextension=f".{ext}",
        filetypes=[(mime_type, f"*.{ext}"), ("All files", "*.*")],
    ) or None


def _bind_drag(window):
    """Make window draggable by clicking anywhere except buttons."""
    def start(e):
        if isinstance(e.widget, tk.Button): return
        window._drag_x = e.x_root
        window._drag_y = e.y_root
    def drag(e):
        if not hasattr(window, '_drag_x'): return
        dx = e.x_root - window._drag_x
        dy = e.y_root - window._drag_y
        window._drag_x = e.x_root
        window._drag_y = e.y_root
        window.geometry(f"+{window.winfo_x() + dx}+{window.winfo_y() + dy}")
    window.bind("<ButtonPress-1>", start, add=True)
    window.bind("<B1-Motion>",     drag,  add=True)


class TkPopup(tk.Toplevel):
    """Non-blocking popup with a message and an OK button."""

    def __init__(self, message: str, button_label: str = "Ok"):
        super().__init__(bg=COLOR_ITEM,
                         highlightbackground=COLOR_ACCENT, highlightthickness=2)
        self.withdraw()  # hide while building to prevent black-screen flash

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.wm_attributes("-type", "splash")  # suppress taskbar entry on X11
        self.resizable(False, False)

        # Outer frame with slight inset so the bg border is visible but tight
        inner = tk.Frame(self, bg=COLOR_ITEM, padx=14, pady=10)
        inner.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            inner,
            text=message,
            bg=COLOR_ITEM,
            fg=COLOR_TEXT,
            wraplength=300,
            justify="center",
            font=("Helvetica", 10),
        ).pack(pady=(8, 8))

        tk.Button(
            inner,
            text=button_label,
            command=self.withdraw,
            bg=COLOR_ACCENT,
            fg=COLOR_TEXT,
            relief="flat",
            font=("Helvetica", 10),
            padx=16,
            pady=4,
        ).pack(pady=(0, 6))

        # Auto-size, then center on the monitor containing the root window
        self.update_idletasks()
        W, H = self.winfo_reqwidth(), self.winfo_reqheight()
        mx, my, mw, mh = _popup_monitor(self.master)
        x = mx + (mw - W) // 2
        y = my + (mh - H) // 2
        self.geometry(f"{W}x{H}+{x}+{y}")
        _bind_drag(self)
        self.deiconify()
        self.update()


class TkSavePopup(tk.Toplevel):
    """Non-blocking save-as popup listing all Representations of a CBItem."""

    _MAX_H = 320

    def __init__(self, cbitem):
        super().__init__(bg=COLOR_BG,
                         highlightbackground=COLOR_ACCENT, highlightthickness=2)
        self.withdraw()

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.wm_attributes("-type", "splash")
        self.resizable(False, False)

        self._debounced = False

        # Load all representations into memory before building buttons
        offloader.load(cbitem)

        tk.Label(
            self,
            text="Save as…",
            bg=COLOR_BG,
            fg=COLOR_TEXT,
            font=("Helvetica", 10, "bold"),
        ).pack(padx=12, pady=(10, 4))

        # Scrollable button list
        container = tk.Frame(self, bg=COLOR_BG)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        scrollbar = tk.Scrollbar(container, orient=tk.VERTICAL,
                                 bg=COLOR_ITEM, troughcolor=COLOR_BG,
                                 activebackground=COLOR_ACCENT,
                                 highlightthickness=0, borderwidth=0)
        canvas = tk.Canvas(
            container, bg=COLOR_BG, highlightthickness=0,
            yscrollcommand=scrollbar.set,
        )
        scrollbar.configure(command=canvas.yview)
        inner = tk.Frame(canvas, bg=COLOR_BG)
        inner.bind(
            "<Configure>",
            lambda _e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=inner, anchor="nw")

        for rep in cbitem.types:
            if rep.mime_type in config.LEGACY_TEXT_TYPES: continue
            mime = rep.mime_type
            ext  = mime.split("/")[-1]
            tk.Button(
                inner,
                text=mime,
                anchor="w",
                bg=COLOR_ITEM,
                fg=COLOR_TEXT,
                activebackground=COLOR_HOVER,
                activeforeground=COLOR_TEXT,
                relief="flat",
                font=("Helvetica", 9),
                command=lambda r=rep, e=ext: self._save(r, e),
            ).pack(fill=tk.X, padx=4, pady=2)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        cancel_btn = tk.Button(
            self,
            text="Cancel",
            command=self.destroy,
            bg=COLOR_ITEM,
            fg=COLOR_TEXT,
            activebackground=COLOR_HOVER,
            activeforeground=COLOR_TEXT,
            relief="flat",
            font=("Helvetica", 9),
        )
        cancel_btn.pack(fill=tk.X, padx=10, pady=(0, 8))

        # Derive width from the widest button, cap height
        self.update_idletasks()
        inner_w = inner.winfo_reqwidth()
        sb_w    = scrollbar.winfo_reqwidth()
        PAD     = 20 + 8  # container padx*2 + inner button padx*2
        W = max(inner_w + sb_w + PAD, 200)
        inner_h = inner.winfo_reqheight()
        CHROME  = 50 + cancel_btn.winfo_reqheight() + 8  # title + cancel + padding
        H = min(inner_h + CHROME, self._MAX_H)
        canvas.configure(width=inner_w + sb_w, height=H - CHROME)

        mx, my, mw, mh = _popup_monitor(self.master)
        x = mx + (mw - W) // 2
        y = my + (mh - H) // 2
        self.geometry(f"{W}x{H}+{x}+{y}")
        _bind_drag(self)
        self.deiconify()
        self.update()
        self.focus_set()

    def _save(self, rep, ext):
        if self._debounced:
            return
        self._debounced = True

        self.withdraw()
        path = _native_save_dialog("untitled", rep.mime_type)
        if path:
            with open(path, "wb") as f:
                f.write(rep.data)
        self.destroy()


class UI_OptionsMenu(tk.Toplevel):
    """Context menu for options button with Pin/Unpin, Save, Delete."""
    
    def __init__(self, parent: tk.Frame, cbitem, item: "UI_ClipboardItem"):
        super().__init__(parent, bg=COLOR_BG,
                         highlightbackground=COLOR_ACCENT, highlightthickness=1)
        self.cbitem = cbitem
        self.item = item

        self.withdraw()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.wm_attributes("-type", "splash")

        def _btn(text, cmd):
            return tk.Button(
                self, text=text, command=cmd,
                bg=COLOR_BG, fg=COLOR_TEXT,
                activebackground=COLOR_HOVER, activeforeground=COLOR_TEXT,
                relief="flat", anchor="w",
                font=("Helvetica", 9),
                padx=12, pady=5,
                borderwidth=0, highlightthickness=0,
                cursor="hand2",
            )

        pin_text = "Unpin" if cbitem.pinned else "Pin"
        self.pin_btn    = _btn(pin_text,  self._on_pin)
        self.save_btn   = _btn("Save",    self._on_save)
        self.delete_btn = _btn("Delete",  self._on_delete)

        self.pin_btn.pack(fill=tk.X)
        tk.Frame(self, bg=COLOR_ACCENT, height=1, highlightbackground=COLOR_TEXT,).pack(fill=tk.X)
        self.save_btn.pack(fill=tk.X)
        tk.Frame(self, bg=COLOR_ACCENT, height=1, highlightbackground=COLOR_TEXT).pack(fill=tk.X)
        self.delete_btn.configure(fg=COLOR_PIN)
        self.delete_btn.pack(fill=tk.X)

        # Position relative to the options button
        options_btn = item.options
        x = options_btn.winfo_rootx() + options_btn.winfo_width() + 5
        y = options_btn.winfo_rooty()
        self.geometry(f"+{x}+{y}")

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Destroy>", lambda e: setattr(item, "_options_menu", None) if e.widget is self else None)

        self.deiconify()
        self.update_idletasks()
        self.grab_set()
        self.focus_set()

        def _on_click(e):
            wx, wy = self.winfo_rootx(), self.winfo_rooty()
            ww, wh = self.winfo_width(), self.winfo_height()
            if not (wx <= e.x_root < wx + ww and wy <= e.y_root < wy + wh):
                self.destroy()

        self.bind("<ButtonPress-1>", _on_click, add=True)
    
    def _on_pin(self):
        self.item._on_pin_click()
        self.destroy()
    
    def _on_save(self):
        self.destroy()
        TkSavePopup(self.cbitem)
    
    def _on_delete(self):
        # Remove from UI
        self.item._cb.remove(self.item)
        # Remove from clipboard
        clipboard.remove(self.cbitem)
        offloader.cleanup_remnants(clipboard, clear_unpinned=False)

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

        def _togglepin():
            if not self.cbitem: return
            clipboard.togglepin(self.cbitem)
            self.cbitem.timestamp = api.get_timestamp()
            if self.cbitem.pinned:
                offloader.persist(self.cbitem)
            else:
                offloader.evict(self.cbitem)
        self.on_pin_clicked = _togglepin

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
        self._update_accent()

    def _on_pin_click(self):
        """Toggle pin state: pin moves to top (full opacity), unpin moves to bottom (25% opacity)."""
        if self._pinned:
            # Unpin: move to top of unpinned section
            self._pinned = False
            self.pin.set_opacity(0.25)
            self._update_accent()
            self._cb.items.remove(self)
            # Find first unpinned item and insert before it
            insert_idx = len(self._cb.items)
            for i, item in enumerate(self._cb.items):
                if not item._pinned:
                    insert_idx = i
                    break
            self._cb.items.insert(insert_idx, self)
        else:
            # Pin: move to top of pinned section (top if no other pinned items)
            self._pinned = True
            self.pin.set_opacity(1.0)
            self._update_accent()
            self._cb.items.remove(self)
            # Find first pinned item and insert before it
            self._cb.items.insert(0, self)
        self._cb._repack_items()
        self._cb._update_status()
        self.on_pin_clicked()
        self.lift()

    def _on_click(self):
        """Set the clipboard selection to this item."""
        if self.cbitem and self.cbitem._ready.is_set():
            cbitem = clipboard.getByHash(self.cbitem.hash)
            if cbitem:
                clipboard.focus(cbitem)
                offloader.load(cbitem) # loads into memory if not already
                server.set(cbitem)
                # Update UI selection
                self._cb._set_selection(self)
            else:
                # Reset or ignore
                pass
            root.withdraw()
        # If not ready, ignore

    def _on_options_click(self):
        """Toggle the options menu."""
        if not self.cbitem:
            return
        menu = getattr(self, "_options_menu", None)
        if menu and menu.winfo_exists():
            menu.destroy()
            self._options_menu = None
            return
        self._options_menu = UI_OptionsMenu(self, self.cbitem, self)

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
                bg=UI_ClipboardItem._bg,
                fg=COLOR_TEXT,
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
    def __init__(self, root: tk.Tk, w: int = int(300), h: int = int(360)):
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
        self.status_frame = tk.Frame(self, bg=COLOR_STATUS, height=20,
                                     highlightbackground=COLOR_TEXT, highlightthickness=1)
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_frame.pack_propagate(False)

        self.status_left = tk.Label(
            self.status_frame,
            text="",
            bg=COLOR_STATUS,
            fg=COLOR_TEXT,
            font=("Helvetica", 8),
            anchor="w"
        )
        self.status_left.pack(side=tk.LEFT, padx=5)

        self.status_right = tk.Label(
            self.status_frame,
            text="",
            bg=COLOR_STATUS,
            fg=COLOR_TEXT,
            font=("Helvetica", 8),
            anchor="e"
        )
        self.status_right.pack(side=tk.RIGHT, padx=5)

        # Scrollbar
        self._scrollbar = tk.Scrollbar(self, orient=tk.VERTICAL,
                                       bg=COLOR_ITEM, troughcolor=COLOR_BG,
                                       activebackground=COLOR_ACCENT,
                                       highlightthickness=0, borderwidth=0)
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
            fg=COLOR_TEXT,
            font=("Helvetica", 12),
        )
        self._no_history_window = None  # placeholder for canvas window ID

        # Ensure header is on top
        self.header_frame.lift()

        self._update_no_history()
        self._update_status()  # Initial update
        self.after(500, self._schedule_status_update)  # Start scheduling after 500ms

    def _set_selection(self, item: "UI_ClipboardItem"):
        """Set the selected item and update accent colors."""
        # Reset previous selection
        last = self.selected_item
        self.selected_item = item
        
        # Set new selection
        item._update_accent()
        if last: last._update_accent()

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
            # if cbitem and cbitem.hash == clipboard.selection.hash:
            #     self._set_selection(item)
        else:
            item.update_with_cbitem(cbitem)
            # Update accent in case pin state changed
            item._update_accent()
            # Check if this updated item should be selected
            # if cbitem and cbitem.hash == clipboard.selection.hash:
            #     self._set_selection(item)

            #assuming a new item added = something else was copied
            if self.selected_item:
                item = self.selected_item
                self.selected_item = None
                clipboard.focus(None)
                item._update_accent()
            #
        self._repack_items()
        self._update_no_history()
        self._update_status()
        return item

    def remove(self, item: "UI_ClipboardItem"):
        if item in self.items:
            self.items.remove(item)
            if item is self.selected_item:
                self.selected_item = None
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
        total_memory = sum(item.cbitem.total_size for item in self.items if hasattr(item, 'cbitem'))
        # Calculate cached memory size by summing each cached representation
        a = sum(i.cbitem.total_size - i.cbitem.get_cached_size() for i in self.items)
        # Show only non-cached memory
        used_memory = total_memory - a
        z = _format_bytes(used_memory, symbols=True)
        max_memory_mb = config.MEM_THRESHOLD_MB
        memory_use_percent = int(used_memory / (max_memory_mb*1e6) * 100)
        a_formatted = _format_bytes(a)
        y = sum(1 for item in self.items if item._pinned)

        self.status_left.configure(text=f"{x}/{max_items}")# / {y} Pins")
        self.status_right.configure(text=f"{z} / {memory_use_percent}% ({a_formatted} disk)")
    def _schedule_status_update(self):
        self._update_status()
        self.after(500, self._schedule_status_update)  # Reschedule every 500ms
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


root = tk.Tk()
root.configure(bg=COLOR_BG,
               highlightbackground=COLOR_TEXT, highlightcolor=COLOR_TEXT, highlightthickness=1)
root.wm_attributes("-type", "splash")
root.attributes("-topmost", True)

errpopup = TkPopup("Clipboard is full of pinned items, which do not auto-remove. Please unpin stuff.", "Ok")
errpopup.withdraw()  # hidden until needed

ui_clipboard = UI_ClipboardWidget(root)
root.withdraw()

items:CBItem = offloader.generate_persistent()
for i in sorted(items, key=lambda x: x.timestamp):
    i.pinned = False # so we can use the ui toggle
    success, value = clipboard.append(i)
    if not success:
        if value: pass #alr exist
        else: break # too many pinned. better to just not delete in case...
    #
    ui_item = ui_clipboard.add(i)
    item_dict[i.hash] = ui_item
    ui_clipboard.add(i, ui_item)
    ui_item._on_pin_click()
#
offloader.cleanup_remnants(clipboard, clear_unpinned=False)

# Start watcher with alerting
def start_threads():
    watcher.start(clipboard, alerting)
    offloader.start(clipboard, offloading)
    ipc.start(root, ui_clipboard)

    if not (offloader.rwpath / "tutorial").exists():
        TkPopup("You can change these settings in src/config.py", "Got it")
        TkPopup("Memory is automatically freed (saved to disk), with a default of 150 MB space before offloading.", "Thanks")
        TkPopup("Pin items to save them on-reboot!", "Alright")
        TkPopup("This tutorial only shows once...", "Continue")
        (offloader.rwpath / "tutorial").touch(exist_ok=True)

    TkPopup(
        "Dynamic Clipboard has started successfully. Activate with 'dynamic-clipboard-toggle' or assign to a keybind!",
        "Cool"
    )

# schedule after event loop starts
root.after(3000, start_threads)

root.mainloop()

