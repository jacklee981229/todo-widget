"""Desktop to-do list for Jack's personal projects. Claude adds to it with `python todos.py add`.

Start it with `pythonw widget.py` so no console window opens. Right-click the header to exit.
"""
import ctypes
import json
import os
import tkinter as tk
from ctypes import wintypes
from pathlib import Path
from tkinter import ttk

import todos

POSITION_FILE = Path(__file__).resolve().parent / "data" / "position.json"
VIEW_FILE = Path(__file__).resolve().parent / "data" / "view.json"
POLL_MS = 2_000
WIDTH, HEIGHT, PAD = 320, 440, 14
BG, FIELD, TEXT, MUTED, TRACK, ACCENT = "#1f1f1f", "#2a2a2a", "#e8e6e3", "#9a9894", "#3a3a3a", "#d85a30"
BODY, DONE, SMALL, GROUP = ("Segoe UI", 10), ("Segoe UI", 10, "overstrike"), ("Segoe UI", 8), ("Segoe UI", 8, "bold")
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
        self.style()
        self.build()
        self.root.geometry("%dx%d+%d+%d" % (self.px(WIDTH), self.px(HEIGHT), *self.saved_position()))
        self.root.update()
        self.hwnd = int(self.root.wm_frame(), 16)
        # A tool window stays out of the taskbar and Alt+Tab. Unlike the usage widget it can become the active
        # window, or its fields couldn't take typing.
        ex_style = user32.GetWindowLongPtrW(self.hwnd, GWL_EXSTYLE) & 0xFFFFFFFF
        user32.SetWindowLongPtrW(self.hwnd, GWL_EXSTYLE, ex_style | WS_EX_TOOLWINDOW)
        # Appearing made the widget the active window; hand focus back to where it was.
        if previous:
            user32.SetForegroundWindow(previous)
        self.raised = False
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
                     bordercolor=TRACK, lightcolor=FIELD, darkcolor=FIELD, selectbackground=ACCENT,
                     selectforeground=TEXT, padding=self.px(4))
        for name in ("TEntry", "TCombobox"):
            style.configure(name, **field)
            style.map(name, bordercolor=[("focus", ACCENT)])
        # A read-only box (the filter) shouldn't look selected after a pick.
        style.map("TCombobox", fieldbackground=[("readonly", FIELD)], selectbackground=[("readonly", FIELD)],
                  selectforeground=[("readonly", TEXT)], background=[("active", TRACK)])
        style.layout("Slim.Vertical.TScrollbar", [("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
            ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
        style.configure("Slim.Vertical.TScrollbar", troughcolor=BG, background=TRACK, bordercolor=BG,
                        lightcolor=TRACK, darkcolor=TRACK, gripcount=0, arrowsize=self.px(6))
        style.map("Slim.Vertical.TScrollbar", background=[("active", MUTED)])
        for option, value in (("background", FIELD), ("foreground", TEXT), ("selectBackground", ACCENT),
                              ("selectForeground", TEXT), ("font", BODY)):
            self.root.option_add(f"*TCombobox*Listbox.{option}", value)

    def build(self):
        p = self.px
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=p(PAD), pady=(p(8), p(8)))
        title = tk.Label(header, text="To-do", bg=BG, fg=TEXT, font=("Segoe UI", 10, "bold"))
        title.pack(side="left")
        self.count = tk.Label(header, bg=BG, fg=MUTED, font=SMALL)
        self.count.pack(side="left", padx=(p(6), 0))
        plus = tk.Label(header, text="+", bg=BG, fg=ACCENT, font=("Segoe UI", 15), cursor="hand2")
        plus.pack(side="right")
        plus.bind("<Button-1>", lambda e: self.open_editor())
        self.filter = ttk.Combobox(header, state="readonly", width=15, font=SMALL, values=[ALL])
        self.filter.set(ALL)
        self.filter.pack(side="right", padx=(0, p(10)))
        self.filter.bind("<<ComboboxSelected>>", lambda e: self.render())
        self.group_toggle = tk.Label(header, text="Group", bg=BG, font=SMALL, cursor="hand2")
        self.group_toggle.pack(side="right", padx=(0, p(8)))
        self.group_toggle.bind("<Button-1>", lambda e: self.toggle_grouped())
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
        self.status = tk.Label(self.root, bg=BG, fg=ACCENT, font=SMALL, wraplength=p(WIDTH - 2 * PAD),
                               justify="left", anchor="w")
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
                                 selectbackground=ACCENT, relief="flat", padx=p(6), pady=p(4), highlightthickness=1,
                                 highlightbackground=TRACK, highlightcolor=ACCENT)
        self.notes_box.pack(fill="both", expand=True, pady=(p(2), p(10)))
        buttons = tk.Frame(self.editor, bg=BG)
        buttons.pack(fill="x")
        self.button(buttons, "Save", self.save_editor, ACCENT).pack(side="left")
        self.button(buttons, "Cancel", self.close_editor, FIELD).pack(side="left", padx=(p(8), 0))
        self.delete_button = self.button(buttons, "Delete", self.delete_item, FIELD)
        self.text_entry.bind("<Return>", lambda e: self.save_editor())
        self.notes_box.bind("<Control-Return>", lambda e: self.save_editor() or "break")
        for field in (self.text_entry, self.project_box, self.notes_box):
            field.bind("<Escape>", lambda e: self.close_editor())

    def label(self, text):
        tk.Label(self.editor, text=text, bg=BG, fg=MUTED, font=SMALL).pack(anchor="w")

    def button(self, parent, text, command, color):
        return tk.Button(parent, text=text, command=command, bg=color, fg=TEXT, activebackground=TRACK,
                         activeforeground=TEXT, relief="flat", bd=0, padx=self.px(12), pady=self.px(3), font=SMALL,
                         cursor="hand2")

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
        """Pick up changes made outside the widget, such as items Claude adds."""
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
        self.root.after(POLL_MS, self.poll)

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
        # A plain list is one group with no heading; its items carry their project as a tag instead.
        groups = todos.grouped(self.items, view) if self.grouped else [(None, todos.listed(self.items, view))]
        groups = [(name, group) for name, group in groups if group]
        self.group_toggle.configure(fg=ACCENT if self.grouped else MUTED)
        self.count.configure(text=f"{sum(not i['done'] for _, group in groups for i in group)} open")
        top = self.canvas.yview()[0]
        for child in self.list.winfo_children():
            child.destroy()
        if not groups:
            tk.Label(self.list, text="Nothing to do yet.\nClick + to add a to-do, or ask Claude in any project to add one.",
                     bg=BG, fg=MUTED, font=SMALL, justify="left", anchor="w",
                     wraplength=p(WIDTH - 2 * PAD - 14)).pack(fill="x")
        for n, (name, group) in enumerate(groups):
            if view is None and name:
                tk.Label(self.list, text=name, bg=BG, fg=MUTED, font=GROUP, anchor="w").pack(
                    fill="x", pady=(p(8) if n else 0, p(4)))
            for item in group:
                self.row(item, tag=item["project"] if view is None and not name else "")
        self.list.update_idletasks()
        self.fit_list()
        self.canvas.yview_moveto(top)

    def row(self, item, tag=""):
        p = self.px
        row = tk.Frame(self.list, bg=BG)
        row.pack(fill="x", pady=(0, p(6)))
        box = tk.Canvas(row, width=p(14), height=p(14), bg=BG, highlightthickness=0, cursor="hand2")
        box.grid(row=0, column=0, sticky="n", padx=(0, p(8)), pady=(p(3), 0))
        if item["done"]:
            box.create_rectangle(p(1), p(1), p(13), p(13), fill=ACCENT, outline=ACCENT)
            box.create_line(p(4), p(7), p(6), p(10), p(10.5), p(4.5), fill=TEXT, width=max(1, p(1.6)))
        else:
            box.create_rectangle(p(1), p(1), p(13), p(13), outline=MUTED, width=max(1, p(1)))
        box.bind("<Button-1>", lambda e: self.change(lambda items: todos.toggle(items, item["id"])))
        wrap = p(WIDTH - 2 * PAD - 10 - 14 - 8)
        parts = [tk.Label(row, text=item["text"], bg=BG, fg=MUTED if item["done"] else TEXT,
                          font=DONE if item["done"] else BODY, wraplength=wrap, justify="left", anchor="w")]
        tag_label = tk.Label(row, text=tag, bg=FIELD, fg=MUTED, font=SMALL, padx=p(5), pady=0) if tag else None
        if tag_label:
            parts.append(tag_label)
        if item["notes"]:
            parts.append(tk.Label(row, text=item["notes"], bg=BG, fg=MUTED, font=SMALL, wraplength=wrap,
                                  justify="left", anchor="w"))
        for line, part in enumerate(parts):
            part.grid(row=line, column=1, sticky="w", pady=(p(2), p(2)) if part is tag_label else 0)
            part.configure(cursor="hand2")
            part.bind("<Button-1>", lambda e: self.open_editor(item))

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
        self.delete_button.configure(text="Delete")
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
            self.delete_button.configure(text="Click again to delete")
        elif self.change(lambda items: todos.delete(items, self.editing)):
            self.close_editor()


if __name__ == "__main__":
    # One widget at a time: starting a second copy just exits.
    mutex = kernel32.CreateMutexW(None, False, "JackTodoWidget")
    if ctypes.get_last_error() != ERROR_ALREADY_EXISTS:
        Widget().root.mainloop()
