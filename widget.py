"""Desktop to-do list for Jack's personal projects. Claude adds to it with `python todos.py add`.

Start it with `pythonw widget.py` so no console window opens. Right-click the header to exit.
"""
import ctypes
import json
import math
import os
import tkinter as tk
import tkinter.font
from ctypes import wintypes
from datetime import date, datetime
from pathlib import Path
from tkinter import ttk

import todos

POSITION_FILE = Path(__file__).resolve().parent / "data" / "position.json"
VIEW_FILE = Path(__file__).resolve().parent / "data" / "view.json"
POLL_MS = 2_000
UNDO_MS = 5_000
WIDTH, HEIGHT, PAD = 320, 440, 14
# The usage widget's colours, so the two cards match.
BG, FIELD, TEXT, MUTED, TRACK = "#171717", "#2a2a2a", "#ededed", "#a3a3a3", "#3a3a3a"
# Each to-do sits on a card one shade lighter than the widget, so items are told apart without lines.
CARD, CARD_R, CARD_GAP = "#222222", 8, 8
BOX, BOX_R = 16, 5
# The accent takes one colour a day, round the rainbow from Monday's red to Sunday's violet, like the usage widget.
RAINBOW = ("#ff453a", "#ff9f0a", "#ffd60a", "#30d158", "#0a84ff", "#5e5ce6", "#bf5af2")
FONT_DIR = Path(__file__).resolve().parent / "fonts"
FR_PRIVATE = 0x10


def load_font():
    """Hanken Grotesk for this process only, so nothing is installed in Windows; Segoe UI if the files are missing."""
    add = ctypes.windll.gdi32.AddFontResourceExW
    add.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p]
    loaded = [add(str(FONT_DIR / f"HankenGrotesk-{weight}.ttf"), FR_PRIVATE, None) for weight in ("Regular", "Bold")]
    return "Hanken Grotesk" if all(loaded) else "Segoe UI Variable Text"


FONT = load_font()
BODY, DONE, SMALL, GROUP = (FONT, 10), (FONT, 10, "overstrike"), (FONT, 8), (FONT, 8, "bold")
ALL = "All projects"
DESKTOP_CLASSES = ("Progman", "WorkerW")

user32 = ctypes.windll.user32
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
# Handles are 64-bit; without these declarations ctypes would cut them to 32 bits.
user32.FindWindowW.restype = wintypes.HWND
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowExW.restype = wintypes.HWND
user32.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.GetWindow.restype = wintypes.HWND
user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetForegroundWindow.restype = wintypes.HWND
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND] + [ctypes.c_int] * 4 + [wintypes.UINT]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.MonitorFromPoint.restype = wintypes.HMONITOR
user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
kernel32.CreateMutexW.restype = wintypes.HANDLE
kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
GWL_EXSTYLE, WS_EX_TOOLWINDOW = -20, 0x00000080
HWND_TOPMOST, HWND_NOTOPMOST, GW_HWNDPREV = -1, -2, 3
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x0001, 0x0002, 0x0010
MONITOR_DEFAULTTONULL = 0
ERROR_ALREADY_EXISTS = 183
DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND, DWMWA_BORDER_COLOR, DWMWA_COLOR_NONE = 33, 2, 34, 0xFFFFFFFE


def day_colour(day):
    return RAINBOW[day.weekday()]


def luminance(colour):
    """Relative luminance, as WCAG defines it for contrast."""
    def channel(value):
        value /= 255
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(int(colour[i:i + 2], 16)) for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    light, dark = sorted((luminance(a), luminance(b)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def ink(colour):
    """Text and ticks on an accent fill: light on the dark days, dark on yellow, green and the like."""
    # Pure white, not TEXT: TEXT on Saturday's indigo falls just short of 4.5:1 for small text.
    return "#ffffff" if contrast("#ffffff", colour) >= contrast(BG, colour) else BG


def rgb(colour):
    return tuple(int(colour[i:i + 2], 16) for i in (1, 3, 5))


def hex_colour(channels):
    return "#%02x%02x%02x" % channels


def mix(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def lighten(colour, t):
    return hex_colour(mix(rgb(colour), (255, 255, 255), t))


def coverage(distance):
    """How much of a pixel a shape covers, from the pixel centre's distance to the shape's edge (negative inside)."""
    return min(1.0, max(0.0, 0.5 - distance))


def photo_rows(width, height, colour_at):
    """Pixels for PhotoImage.put: one {…} group of #rrggbb per row."""
    return " ".join("{" + " ".join(hex_colour(colour_at(x + 0.5, y + 0.5)) for x in range(width)) + "}"
                    for y in range(height))


def rounded_box(x, y, cx, cy, half_w, half_h, radius):
    """Distance from a point to a rounded rectangle's edge, negative inside."""
    qx, qy = abs(x - cx) - (half_w - radius), abs(y - cy) - (half_h - radius)
    return math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - radius


def segment(x, y, a, b):
    (ax, ay), (bx, by) = a, b
    t = max(0.0, min(1.0, ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / ((bx - ax) ** 2 + (by - ay) ** 2)))
    return math.hypot(x - ax - t * (bx - ax), y - ay - t * (by - ay))


# Tk's canvas draws shapes with jagged edges, so the rounded parts are painted pixel by pixel, as in the usage widget.
def pill_rows(width, height, fill, bg):
    fill, bg = rgb(fill), rgb(bg)
    return photo_rows(width, height, lambda x, y: mix(bg, fill, coverage(
        rounded_box(x, y, width / 2, height / 2, width / 2, height / 2, height / 2))))


def corner_rows(radius, right, bottom, card, bg):
    """One rounded corner of a card: the card's colour inside the curve, the widget's outside."""
    card, bg = rgb(card), rgb(bg)

    def colour_at(x, y):
        x, y = (radius - x if right else x), (radius - y if bottom else y)
        return mix(bg, card, coverage(math.hypot(max(radius - x, 0), max(radius - y, 0)) - radius))

    return photo_rows(radius, radius, colour_at)


def box_rows(size, side, radius, fill, accent, outline, bg):
    """The tick box: a rounded outline, and over it the accent fill with a tick, grown to `fill` (1 = the box)."""
    accent, outline, bg, tick = rgb(accent), rgb(outline), rgb(bg), rgb(ink(accent))
    centre, stroke = size / 2, side / 11
    unit = side / 16 * fill
    points = [(centre + unit * x, centre + unit * y) for x, y in ((-3.6, 0.2), (-1.1, 2.8), (3.8, -2.6))]

    def colour_at(x, y):
        # The outline sits just inside the box, so a full fill hides it.
        ring = abs(rounded_box(x, y, centre, centre, side / 2 - stroke / 2, side / 2 - stroke / 2, radius)) - stroke / 2
        colour = mix(bg, outline, coverage(ring))
        if fill <= 0:
            return colour
        inside = coverage(rounded_box(x, y, centre, centre, side / 2 * fill, side / 2 * fill, radius * fill))
        colour = mix(colour, accent, inside)
        mark = min(segment(x, y, points[0], points[1]), segment(x, y, points[1], points[2])) - unit * 0.95
        return mix(colour, tick, coverage(mark) * inside)

    return photo_rows(size, size, colour_at)


def spring_frames(start, target, stiffness, damping, duration_ms, frame_ms=16):
    """Positions of a spring (mass 1) sampled once a frame, from rest at `start` towards `target`."""
    x, v, frames = start, 0.0, []
    for ms in range(duration_ms):
        v += (-stiffness * (x - target) - damping * v) / 1000
        x += v / 1000
        if ms % frame_ms == frame_ms - 1:
            frames.append(x)
    return frames + [target]


def ease_frames(start, target, duration_ms, frame_ms=16):
    """An ease-in-out from `start` to `target`, for things going away."""
    steps = max(1, round(duration_ms / frame_ms))
    return [start + (target - start) * t * t * (3 - 2 * t) for t in (n / steps for n in range(1, steps + 1))]


def desktop_window():
    """The top-level window showing the desktop icons."""
    progman = user32.FindWindowW("Progman", None)
    if user32.FindWindowExW(progman, None, "SHELLDLL_DefView", None):
        return progman
    # Wallpaper apps can move the icons into a separate WorkerW window.
    found = []

    def check(hwnd, _):
        if user32.FindWindowExW(hwnd, None, "SHELLDLL_DefView", None):
            found.append(hwnd)
        return True

    user32.EnumWindows(WNDENUMPROC(check), 0)
    return found[0] if found else progman


def class_name(hwnd):
    buffer = ctypes.create_unicode_buffer(64)
    user32.GetClassNameW(hwnd, buffer, 64)
    return buffer.value


def ours(hwnd):
    """True for any window of this process, such as the project box's drop-down list."""
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value == os.getpid()


def on_screen(x, y):
    return bool(user32.MonitorFromPoint(wintypes.POINT(x, y), MONITOR_DEFAULTTONULL))


def cursor():
    point = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y


def file_key():
    try:
        stat = todos.TODO_FILE.stat()
    except OSError:
        return None
    return stat.st_mtime_ns, stat.st_size


class Widget:
    def __init__(self):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except OSError:
            pass
        previous = user32.GetForegroundWindow()
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.configure(bg=BG)
        self.scale = self.root.winfo_fpixels("1i") / 96
        self.grouped = self.saved_view()
        self.accent = day_colour(date.today())
        self.pictures = {}
        self.style()
        self.build()
        self.root.geometry("%dx%d+%d+%d" % (self.px(WIDTH), self.px(HEIGHT), *self.saved_position()))
        self.root.update()
        self.hwnd = int(self.root.wm_frame(), 16)
        # A tool window stays out of the taskbar and Alt+Tab. Unlike the usage widget it can become the active
        # window, or its fields couldn't take typing.
        ex_style = user32.GetWindowLongPtrW(self.hwnd, GWL_EXSTYLE) & 0xFFFFFFFF
        user32.SetWindowLongPtrW(self.hwnd, GWL_EXSTYLE, ex_style | WS_EX_TOOLWINDOW)
        # Windows 11 rounds the card's corners, like the usage widget's, and drops the grey frame it adds to them;
        # older Windows keeps a plain square card.
        try:
            for attribute, value in ((DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND), (DWMWA_BORDER_COLOR, DWMWA_COLOR_NONE)):
                ctypes.windll.dwmapi.DwmSetWindowAttribute(wintypes.HWND(self.hwnd), attribute, ctypes.byref(ctypes.c_uint(value)), 4)
        except (OSError, AttributeError):
            pass
        # Appearing made the widget the active window; hand focus back to where it was.
        if previous:
            user32.SetForegroundWindow(previous)
        self.raised = False
        # Ticked items start hidden every time; unlike Group this isn't saved, so the list always opens short.
        self.expanded = False
        self.items, self.problem, self.editing, self.delete_armed = [], None, None, False
        self.seen = "unread"
        self.poll()
        self.stay_on_desktop()

    def px(self, value):
        return round(value * self.scale)

    def style(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        field = dict(fieldbackground=FIELD, background=FIELD, foreground=TEXT, insertcolor=TEXT, arrowcolor=MUTED,
                     bordercolor=TRACK, lightcolor=FIELD, darkcolor=FIELD, selectbackground=self.accent,
                     selectforeground=ink(self.accent), padding=self.px(4))
        for name in ("TEntry", "TCombobox"):
            style.configure(name, **field)
            style.map(name, bordercolor=[("focus", self.accent)])
        # A read-only box (the filter) shouldn't look selected after a pick.
        style.map("TCombobox", fieldbackground=[("readonly", FIELD)], selectbackground=[("readonly", FIELD)],
                  selectforeground=[("readonly", TEXT)], background=[("active", TRACK)])
        style.layout("Slim.Vertical.TScrollbar", [("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
            ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
        style.configure("Slim.Vertical.TScrollbar", troughcolor=BG, background=TRACK, bordercolor=BG,
                        lightcolor=TRACK, darkcolor=TRACK, gripcount=0, arrowsize=self.px(6))
        style.map("Slim.Vertical.TScrollbar", background=[("active", MUTED)])
        # shortcut: a drop-down list already opened keeps the day it was opened on until restart; fine for a
        # selection colour, recolour the open lists if it ever shows.
        for option, value in (("background", FIELD), ("foreground", TEXT), ("selectBackground", self.accent),
                              ("selectForeground", ink(self.accent)), ("font", BODY)):
            self.root.option_add(f"*TCombobox*Listbox.{option}", value)

    def build(self):
        p = self.px
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=p(PAD), pady=(p(8), p(8)))
        title = tk.Label(header, text="TO-DO", bg=BG, fg=TEXT, font=(FONT, 10, "bold"))
        title.pack(side="left")
        self.count = tk.Label(header, bg=BG, fg=MUTED, font=SMALL)
        self.count.pack(side="left", padx=(p(6), 0))
        # Anything clickable is a filled pill; plain words, such as the count and project names, have no fill.
        self.plus = self.button(header, "+", self.open_editor, self.accent, font=(FONT, 12, "bold"), width=24, height=24)
        self.plus.pack(side="right")
        self.filter = ttk.Combobox(header, state="readonly", width=12, font=SMALL, values=[ALL])
        self.filter.set(ALL)
        self.filter.pack(side="right", padx=(0, p(8)))
        self.filter.bind("<<ComboboxSelected>>", lambda e: self.render())
        self.group_toggle = self.button(header, "Group", self.toggle_grouped, FIELD)
        self.group_toggle.pack(side="right", padx=(0, p(8)))
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Exit", command=self.root.destroy)
        for part in (header, title, self.count):
            part.bind("<Button-1>", self.start_drag)
            part.bind("<B1-Motion>", self.drag)
            part.bind("<ButtonRelease-1>", self.save_position)
            part.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))
        tk.Frame(self.root, bg=TRACK, height=1).pack(fill="x", padx=p(PAD))
        self.body = tk.Frame(self.root, bg=BG)
        self.body.pack(fill="both", expand=True, padx=p(PAD), pady=p(10))
        self.status = tk.Label(self.root, bg=BG, fg=self.accent, font=SMALL, wraplength=p(WIDTH - 2 * PAD),
                               justify="left", anchor="w")
        # After a tick, the item has gone from the open list; this bar brings it back for a few seconds.
        self.undo_bar = tk.Frame(self.root, bg=BG)
        self.undo_text = tk.Label(self.undo_bar, bg=BG, fg=MUTED, font=SMALL, anchor="w")
        self.undo_text.pack(side="left", fill="x", expand=True)
        self.undo_button = self.button(self.undo_bar, "Undo", self.undo, self.accent)
        self.undo_button.pack(side="right", padx=(p(8), 0))
        self.undo_id = self.undo_token = None
        self.build_list()
        self.build_editor()

    def build_list(self):
        p = self.px
        self.list_area = tk.Frame(self.body, bg=BG)
        self.list_area.pack(fill="both", expand=True)
        self.list_area.rowconfigure(0, weight=1)
        self.list_area.columnconfigure(0, weight=1)
        # Room for the scroll bar is kept even while it's hidden, so text doesn't re-wrap when it appears.
        self.list_area.columnconfigure(1, minsize=p(10))
        self.canvas = tk.Canvas(self.list_area, bg=BG, highlightthickness=0, bd=0, yscrollincrement=p(12))
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar = ttk.Scrollbar(self.list_area, orient="vertical", style="Slim.Vertical.TScrollbar",
                                       command=self.canvas.yview)
        self.scrollbar.grid(row=0, column=1, sticky="nse")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.list = tk.Frame(self.canvas, bg=BG)
        window = self.canvas.create_window(0, 0, window=self.list, anchor="nw")

        def canvas_resized(event):
            self.canvas.itemconfigure(window, width=event.width)
            self.fit_list()

        self.canvas.bind("<Configure>", canvas_resized)
        self.list.bind("<Configure>", lambda e: self.fit_list())
        self.root.bind_all("<MouseWheel>", self.wheel)

    def build_editor(self):
        p = self.px
        self.editor = tk.Frame(self.body, bg=BG)
        self.text_var = tk.StringVar()
        self.label("To-do")
        self.text_entry = ttk.Entry(self.editor, textvariable=self.text_var, font=BODY)
        self.text_entry.pack(fill="x", pady=(p(2), p(10)))
        self.label("Project")
        self.project_box = ttk.Combobox(self.editor, font=BODY)
        self.project_box.pack(fill="x", pady=(p(2), p(10)))
        self.label("Notes")
        self.notes_box = tk.Text(self.editor, height=5, wrap="word", font=BODY, bg=FIELD, fg=TEXT, insertbackground=TEXT,
                                 selectbackground=self.accent, selectforeground=ink(self.accent), relief="flat",
                                 padx=p(6), pady=p(4), highlightthickness=1, highlightbackground=TRACK,
                                 highlightcolor=self.accent)
        self.notes_box.pack(fill="both", expand=True, pady=(p(2), p(10)))
        buttons = tk.Frame(self.editor, bg=BG)
        buttons.pack(fill="x")
        self.save_button = self.button(buttons, "Save", self.save_editor, self.accent, height=28)
        self.save_button.pack(side="left")
        self.button(buttons, "Cancel", self.close_editor, FIELD, height=28).pack(side="left", padx=(p(8), 0))
        self.delete_button = self.button(buttons, "Delete", self.delete_item, FIELD, height=28)
        self.text_entry.bind("<Return>", lambda e: self.save_editor())
        self.notes_box.bind("<Control-Return>", lambda e: self.save_editor() or "break")
        for field in (self.text_entry, self.project_box, self.notes_box):
            field.bind("<Escape>", lambda e: self.close_editor())

    def label(self, text):
        tk.Label(self.editor, text=text, bg=BG, fg=MUTED, font=SMALL).pack(anchor="w")

    def picture(self, width, height, key, rows):
        """A painted picture, made once; the cache also keeps it alive, or Tk would show an empty space."""
        key = (width, height, *key)
        if key not in self.pictures:
            self.pictures[key] = tk.PhotoImage(width=width, height=height)
            self.pictures[key].put(rows())
        return self.pictures[key]

    def button(self, parent, text, command, fill, fg=None, font=SMALL, width=None, height=24, bg=BG):
        """A pill-shaped button that lightens under the mouse. `width` is fixed, else it fits the text."""
        label = tk.Label(parent, bd=0, padx=0, pady=0, bg=bg, font=font, compound="center", cursor="hand2")
        label.pill_text, label.pill_fill, label.pill_fg, label.pill_bg = text, fill, fg, bg
        label.pill_width, label.pill_height, label.pill_hover = width, height, False
        label.bind("<Button-1>", lambda e: command())

        def hover(on):
            label.pill_hover = on
            self.paint_button(label)

        label.bind("<Enter>", lambda e: hover(True))
        label.bind("<Leave>", lambda e: hover(False))
        self.paint_button(label)
        return label

    def set_button(self, label, text=None, fill=None, fg=None):
        """Change a button's text, or its fill and text colour (None for the colour that reads best on the fill)."""
        if text is not None:
            label.pill_text = text
        if fill is not None:
            label.pill_fill, label.pill_fg = fill, fg
        self.paint_button(label)

    def paint_button(self, label):
        p = self.px
        text, bg = label.pill_text, label.pill_bg
        width = p(label.pill_width) if label.pill_width else tkinter.font.Font(font=label.cget("font")).measure(text) + p(22)
        height = p(label.pill_height)
        fill = lighten(label.pill_fill, 0.1) if label.pill_hover else label.pill_fill
        image = self.picture(width, height, ("pill", fill, bg), lambda: pill_rows(width, height, fill, bg))
        label.configure(image=image, text=text, fg=label.pill_fg or ink(label.pill_fill))

    def saved_position(self):
        try:
            saved = json.loads(POSITION_FILE.read_text(encoding="utf-8"))
            # A spot on a monitor that's since been unplugged would leave the widget out of reach.
            if on_screen(saved["x"] + self.px(20), saved["y"] + self.px(10)):
                return saved["x"], saved["y"]
        except (OSError, ValueError, KeyError, TypeError):
            pass
        # Top right, under where the usage widget starts.
        return self.root.winfo_screenwidth() - self.px(WIDTH) - self.px(40), self.px(194)

    def saved_view(self):
        """Grouped by project, unless the list was last switched to one plain list."""
        try:
            return json.loads(VIEW_FILE.read_text(encoding="utf-8"))["grouped"] is not False
        except (OSError, ValueError, KeyError, TypeError):
            return True

    def toggle_grouped(self):
        self.grouped = not self.grouped
        try:
            VIEW_FILE.parent.mkdir(exist_ok=True)
            VIEW_FILE.write_text(json.dumps({"grouped": self.grouped}), encoding="utf-8")
        except OSError:
            pass  # The view still changes; it just starts grouped next time.
        self.render()

    def start_drag(self, _):
        self.drag_from = (*cursor(), self.root.winfo_x(), self.root.winfo_y())

    def drag(self, _):
        x0, y0, left, top = self.drag_from
        x, y = cursor()
        self.root.geometry(f"+{left + x - x0}+{top + y - y0}")

    def save_position(self, _):
        rect = wintypes.RECT()
        user32.GetWindowRect(self.hwnd, ctypes.byref(rect))
        POSITION_FILE.parent.mkdir(exist_ok=True)
        POSITION_FILE.write_text(json.dumps({"x": rect.left, "y": rect.top}), encoding="utf-8")

    def stay_on_desktop(self):
        """Sit just above the desktop, under every app window; come to the top while the desktop or the widget is
        the active window (Win+D, or a click on it)."""
        flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
        foreground = user32.GetForegroundWindow()
        if ours(foreground) or class_name(foreground) in DESKTOP_CLASSES:
            if not self.raised:
                user32.SetWindowPos(self.hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags)
                self.raised = True
        else:
            if self.raised:
                user32.SetWindowPos(self.hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, flags)
                self.raised = False
            above_desktop = user32.GetWindow(desktop_window(), GW_HWNDPREV)
            if above_desktop and above_desktop != self.hwnd:
                user32.SetWindowPos(self.hwnd, above_desktop, 0, 0, 0, 0, flags)
        self.root.after(500, self.stay_on_desktop)

    def poll(self):
        """Pick up changes made outside the widget, such as items Claude adds, and the new day's colour."""
        if day_colour(date.today()) != self.accent:
            self.recolour()
        key = file_key()
        if key != self.seen or self.problem:
            self.seen = key
            try:
                items = todos.load()
            except (OSError, ValueError) as error:
                self.problem = str(error)
            else:
                self.items, self.problem = items, None
                self.render()
            self.show()
        try:
            stale = not self.problem and todos.stale(self.items, datetime.now())
        except ValueError:
            stale = False  # A hand-edited tick time that can't be read; that item just stays.
        if stale:
            self.change(lambda items: todos.tidy(items, datetime.now()))
        self.root.after(POLL_MS, self.poll)

    def recolour(self):
        self.accent = day_colour(date.today())
        self.style()
        self.set_button(self.plus, fill=self.accent)
        self.set_button(self.save_button, fill=self.accent)
        self.set_button(self.undo_button, fill=self.accent)
        self.status.configure(fg=self.accent)
        self.notes_box.configure(selectbackground=self.accent, selectforeground=ink(self.accent),
                                 highlightcolor=self.accent)
        self.render()

    def change(self, update):
        """Apply an edit to the file as it is now, so items Claude added meanwhile are kept."""
        try:
            items = todos.load()
        except (OSError, ValueError) as error:
            self.problem = str(error)
            self.show()
            return False
        try:
            update(items)
            todos.save(items)
        except (OSError, ValueError) as error:
            self.show(str(error))
            return False
        self.items, self.seen, self.problem = items, file_key(), None
        self.show()
        self.render()
        return True

    def show(self, message=""):
        """Show a message under the list; a file that can't be read keeps its message until it's fixed."""
        text = message or self.problem or ""
        self.status.configure(text=text)
        if text:
            self.status.pack(side="bottom", fill="x", padx=self.px(PAD), pady=(0, self.px(10)), before=self.body)
        else:
            self.status.pack_forget()

    def render(self):
        p = self.px
        names = [name for name, _ in todos.grouped(self.items)]
        self.filter.configure(values=[ALL, *names])
        if self.filter.get() not in names:
            self.filter.set(ALL)
        view = None if self.filter.get() == ALL else self.filter.get()
        open_groups = self.layout([i for i in self.items if not i["done"]], view)
        done_groups = self.layout([i for i in self.items if i["done"]], view)
        self.set_button(self.group_toggle, fill=self.accent if self.grouped else FIELD, fg=None if self.grouped else MUTED)
        self.count.configure(text=f"{sum(len(group) for _, group in open_groups)} open")
        # Keep the view where it was in pixels, so the Expand line stays put when clicked; the same fraction of a
        # list that just grew would land far below it.
        top = self.canvas.canvasy(0)
        for child in self.list.winfo_children():
            child.destroy()
        if not open_groups and not done_groups:
            tk.Label(self.list, text="Nothing to do yet.\nClick + to add a to-do, or ask Claude in any project to add one.",
                     bg=BG, fg=MUTED, font=SMALL, justify="left", anchor="w",
                     wraplength=p(WIDTH - 2 * PAD - 14)).pack(fill="x")
        self.show_groups(open_groups, view)
        if done_groups:
            self.divider()
            if self.expanded:
                self.show_groups(done_groups, view)
        self.list.update_idletasks()
        self.fit_list()
        self.canvas.yview_moveto(top / max(self.list.winfo_reqheight(), self.canvas.winfo_height(), 1))

    def layout(self, items, view):
        # A plain list is one group with no heading; its items carry their project as a tag instead.
        groups = todos.grouped(items, view) if self.grouped else [(None, todos.listed(items, view))]
        return [(name, group) for name, group in groups if group]

    def show_groups(self, groups, view):
        p = self.px
        for n, (name, group) in enumerate(groups):
            if view is None and name:
                tk.Label(self.list, text=name, bg=BG, fg=MUTED, font=GROUP, anchor="w").pack(
                    fill="x", pady=(p(8) if n else 0, p(4)))
            for item in group:
                self.row(item, tag=item["project"] if view is None and not name else "")

    def divider(self):
        """The line between open and ticked items; a click anywhere on it shows or hides the ticked ones."""
        p = self.px
        line = tk.Frame(self.list, bg=BG, cursor="hand2")
        line.pack(fill="x", pady=(p(4), p(12)))
        self.button(line, "Collapse" if self.expanded else "Expand", self.toggle_expanded, FIELD, fg=MUTED).grid(
            row=0, column=1, padx=p(8))
        parts = [line]
        for column in (0, 2):
            line.columnconfigure(column, weight=1)
            rule = tk.Frame(line, bg=TRACK, height=1, cursor="hand2")
            rule.grid(row=0, column=column, sticky="ew")
            parts.append(rule)
        for part in parts:
            part.bind("<Button-1>", lambda e: self.toggle_expanded())

    def toggle_expanded(self):
        self.expanded = not self.expanded
        self.render()

    def row(self, item, tag=""):
        p = self.px
        card = tk.Frame(self.list, bg=CARD, cursor="hand2")
        card.pack(fill="x", pady=(0, p(CARD_GAP)))
        card.columnconfigure(1, weight=1)
        box = tk.Label(card, image=self.box_image(1 if item["done"] else 0), bg=CARD, bd=0, cursor="hand2")
        box.grid(row=0, column=0, sticky="n", padx=(p(8), p(6)), pady=(p(8), 0))
        box.animating = False
        box.bind("<Button-1>", lambda e: self.tick(item, box))
        wrap = p(WIDTH - 2 * PAD - 10 - 8 - BOX * 1.25 - 6 - 18)
        parts = [tk.Label(card, text=item["text"], bg=CARD, fg=MUTED if item["done"] else TEXT,
                          font=DONE if item["done"] else BODY, wraplength=wrap, justify="left", anchor="w")]
        if tag:
            parts.append(tk.Label(card, text=tag, bg=CARD, fg=MUTED, font=GROUP, anchor="w"))
        if item["notes"]:
            parts.append(tk.Label(card, text=item["notes"], bg=CARD, fg=MUTED, font=SMALL, wraplength=wrap,
                                  justify="left", anchor="w"))
        for line, part in enumerate(parts):
            part.grid(row=line, column=1, sticky="w", padx=(0, p(12)),
                      pady=(p(9) if line == 0 else p(2), p(10) if line == len(parts) - 1 else 0))
            part.configure(cursor="hand2")
        corners = []
        for right in (False, True):
            for bottom in (False, True):
                r = p(CARD_R)
                corner = tk.Label(card, bd=0, bg=CARD, cursor="hand2", image=self.picture(
                    r, r, ("corner", right, bottom), lambda: corner_rows(r, right, bottom, CARD, BG)))
                corner.place(relx=float(right), rely=float(bottom), anchor=("s" if bottom else "n") + ("e" if right else "w"))
                corners.append(corner)
        for part in (card, *parts, *corners):
            part.bind("<Button-1>", lambda e: self.open_editor(item))

    def box_image(self, fill, keep=True):
        """The tick box at `fill` (0 empty, 1 ticked); frames of the animation aren't kept."""
        size, side, radius = self.px(BOX * 1.25), self.px(BOX), self.px(BOX_R)

        def rows():
            return box_rows(size, side, radius, fill, self.accent, MUTED, CARD)

        if keep:
            return self.picture(size, size, ("box", fill, self.accent), rows)
        image = tk.PhotoImage(width=size, height=size)
        image.put(rows())
        return image

    def tick(self, item, box):
        """Ticking springs the fill in from 70% with a small bounce; unticking shrinks it away. Then the item moves."""
        if box.animating:
            return
        box.animating = True
        frames = ease_frames(1, 0, 140) if item["done"] else spring_frames(0.7, 1, 520, 12, 420)

        def show(fill):
            try:
                box.frame = self.box_image(fill, keep=False)
                box.configure(image=box.frame)
            except tk.TclError:
                pass  # The list was redrawn meanwhile; the change below still happens.

        for n, fill in enumerate(frames):
            self.root.after(16 * n, show, fill)
        def commit():
            if self.change(lambda items: todos.toggle(items, item["id"])) and not item["done"]:
                self.offer_undo(item)

        self.root.after(16 * len(frames) + 80, commit)

    def offer_undo(self, item):
        p = self.px
        font = tkinter.font.Font(font=SMALL)
        room = p(WIDTH - 2 * PAD) - self.undo_button.winfo_reqwidth() - p(8)
        text = f"Ticked: {item['text']}"
        if font.measure(text) > room:
            while text and font.measure(text + "…") > room:
                text = text[:-1]
            text += "…"
        self.undo_text.configure(text=text)
        self.undo_id = item["id"]
        token = self.undo_token = object()
        self.undo_bar.pack(side="bottom", fill="x", padx=p(PAD), pady=(0, p(10)), before=self.body)
        self.root.after(UNDO_MS, lambda: self.hide_undo(token))

    def hide_undo(self, token=None):
        """Hide the bar; given a token, only if no later tick has taken the bar over since."""
        if token is None or token is self.undo_token:
            self.undo_bar.pack_forget()
            self.undo_token = None

    def undo(self):
        item_id = self.undo_id
        self.hide_undo()

        def untick(items):
            item = todos.find(items, item_id)
            if item and item["done"]:
                todos.set_done(item, False)

        self.change(untick)

    def fit_list(self):
        height, visible = self.list.winfo_reqheight(), self.canvas.winfo_height()
        self.canvas.configure(scrollregion=(0, 0, self.canvas.winfo_width(), max(height, visible)))
        if height > visible:
            self.scrollbar.grid()
        else:
            self.scrollbar.grid_remove()

    def wheel(self, event):
        # Ask Tk directly: tkinter can't name the drop-down list's widgets and would raise.
        under = str(self.root.tk.call("winfo", "containing", "-displayof", self.root, event.x_root, event.y_root))
        inside = under == str(self.canvas) or under.startswith(f"{self.canvas}.")
        if inside and self.list.winfo_reqheight() > self.canvas.winfo_height():
            self.canvas.yview_scroll(-round(event.delta / 120) * 3, "units")

    def open_editor(self, item=None):
        self.editing = item["id"] if item else None
        view = self.filter.get()
        self.text_var.set(item["text"] if item else "")
        self.project_box.configure(values=todos.project_suggestions(self.items))
        self.project_box.set(item["project"] if item else ("" if view in (ALL, todos.GENERAL) else view))
        self.notes_box.delete("1.0", "end")
        self.notes_box.insert("1.0", item["notes"] if item else "")
        self.delete_armed = False
        self.set_button(self.delete_button, text="Delete")
        if item:
            self.delete_button.pack(side="right")
        else:
            self.delete_button.pack_forget()
        self.list_area.pack_forget()
        self.editor.pack(fill="both", expand=True)
        self.text_entry.focus_set()
        self.text_entry.icursor("end")

    def close_editor(self):
        self.editing = None
        self.editor.pack_forget()
        self.list_area.pack(fill="both", expand=True)
        self.show()

    def save_editor(self):
        text, project, notes = self.text_var.get(), self.project_box.get(), self.notes_box.get("1.0", "end")
        if self.editing:
            saved = self.change(lambda items: todos.edit(items, self.editing, text, project, notes))
        else:
            saved = self.change(lambda items: todos.add(items, text, project, notes))
        if saved:
            # Show the item even when it moved out of the project being viewed.
            if self.filter.get() not in (ALL, project.strip() or todos.GENERAL):
                self.filter.set(ALL)
                self.render()
            self.close_editor()

    def delete_item(self):
        if not self.delete_armed:
            self.delete_armed = True
            self.set_button(self.delete_button, text="Click again to delete")
        elif self.change(lambda items: todos.delete(items, self.editing)):
            self.close_editor()


if __name__ == "__main__":
    # One widget at a time: starting a second copy just exits.
    mutex = kernel32.CreateMutexW(None, False, "JackTodoWidget")
    if ctypes.get_last_error() != ERROR_ALREADY_EXISTS:
        Widget().root.mainloop()
