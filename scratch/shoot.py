"""The widget in set states, with test to-dos, for the README's screenshots and the showcase video's clip.

python scratch\\shoot.py .github\\readme [scale]   -> one PNG per state (scale 2 by default), rounded, with a soft
                                                  shadow on a clear ground
python scratch\\shoot.py hold <state>             -> just shows that state at the screen's scale, for the showcase's
                                                  capture_window.py

It runs a copy of the widget in a temporary folder, with its own data folder, and takes no mutex, so it runs beside
Jack's own widget without touching his list.
"""
import ctypes
import math
import shutil
import struct
import sys
import tempfile
import zlib
from ctypes import wintypes
from pathlib import Path

# A copy, not the files here: todos.load() and save() fix data\todos.json as their default when defined, so patching
# todos.TODO_FILE afterwards still writes Jack's real list.
HERE = Path(__file__).resolve().parent.parent
TEMP = Path(tempfile.mkdtemp(prefix="todo-shoot-"))
for name in ("widget.py", "todos.py"):
    shutil.copy(HERE / name, TEMP)
shutil.copytree(HERE / "fonts", TEMP / "fonts")
sys.path.insert(0, str(TEMP))
import tkinter as tk  # noqa: E402

HOLD = sys.argv[1] == "hold"
SCALE = None if HOLD else float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
if SCALE:
    def fpixels(self, what):
        # Draw at SCALE instead of the screen's own, fonts too (their sizes are in points).
        self.tk.call("tk", "scaling", SCALE * 96 / 72)
        return SCALE * 96

    tk.Misc.winfo_fpixels = fpixels

import todos  # noqa: E402
import widget  # noqa: E402

assert todos.TODO_FILE.parent.parent == TEMP, "the copy must read and write only its own data"

OPEN = [
    ("jacks-space", "Write up the Yunnan trip", "Photos picked; the story is next"),
    ("jacks-space", "Try the music player on Safari", ""),
    ("media-studio", "Export the Kunming clips", "Use the warm look from the last trip"),
    ("claude-usage-widget", "Recheck the weekly factor", "Wait for a reading over 20%"),
]
TICKED = [
    ("media-studio", "Pick the keepers from Lijiang", ""),
    ("claude-usage-widget", "Screenshots for the README", ""),
    ("jacks-space", "Add a Chinese README", ""),
]


def test_items():
    items = []
    for project, text, notes in OPEN + TICKED:
        todos.add(items, text, project, notes)
    for item in items[len(OPEN):]:
        todos.set_done(item, True)
    return items


class Shot(widget.Widget):
    def saved_position(self):
        return 60, 60

    def stay_on_desktop(self):
        pass

    def show_state(self, name):
        """Each state starts from the grouped list, ticked items hidden."""
        self.close_editor()
        self.hide_undo()
        self.filter.set(widget.ALL)
        self.grouped, self.expanded = name != "list", name == "ticked"
        self.render()
        if name == "ticked":
            self.root.update()
            self.canvas.yview_moveto(1)
        if name == "adding":
            self.open_editor()
            self.text_var.set("Add a dark theme to the brief")
            self.project_box.set("jacks-space")
            self.notes_box.insert("1.0", "Match the site's night sky")
        if name == "undo":
            self.offer_undo(todos.find(self.items, self.items[-1]["id"]))
        self.root.update()


STATES = ("grouped", "list", "ticked", "adding", "undo")


def grab(hwnd):
    r = wintypes.RECT()
    widget.user32.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    gdi32.CreateCompatibleBitmap.restype = wintypes.HANDLE
    gdi32.CreateCompatibleDC.restype = wintypes.HANDLE
    user32.GetWindowDC.restype = wintypes.HANDLE
    wdc = user32.GetWindowDC(wintypes.HWND(hwnd))
    mdc = gdi32.CreateCompatibleDC(wintypes.HANDLE(wdc))
    bmp = gdi32.CreateCompatibleBitmap(wintypes.HANDLE(wdc), w, h)
    gdi32.SelectObject(wintypes.HANDLE(mdc), wintypes.HANDLE(bmp))
    user32.PrintWindow(wintypes.HWND(hwnd), wintypes.HANDLE(mdc), 2)
    header = struct.pack("<IiiHHIIiiII", 40, w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    info = ctypes.create_string_buffer(header, 44)
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(wintypes.HANDLE(mdc), wintypes.HANDLE(bmp), 0, h, buf, info, 0)
    gdi32.DeleteObject(wintypes.HANDLE(bmp))
    gdi32.DeleteDC(wintypes.HANDLE(mdc))
    user32.ReleaseDC(wintypes.HWND(hwnd), wintypes.HANDLE(wdc))
    return w, h, buf.raw


def rounded_distance(x, y, w, h, r):
    """Signed distance from a pixel centre to a w x h rectangle with corner radius r (negative inside)."""
    qx = abs(x - w / 2) - (w / 2 - r)
    qy = abs(y - h / 2) - (h / 2 - r)
    return math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - r


def framed(w, h, bgra, scale):
    """The card with Windows 11's rounded corners, on a clear ground with a soft shadow below it."""
    m, radius, drop, spread = round(28 * scale), 8 * scale, 10 * scale, 26 * scale
    W, H = w + 2 * m, h + 2 * m
    rows = []
    for Y in range(H):
        row = bytearray([0])
        for X in range(W):
            x, y = X - m + 0.5, Y - m + 0.5
            shadow = rounded_distance(x, y - drop, w, h, radius)
            sa = 0.32 * (1 - min(1, max(0, shadow) / spread)) ** 2.4
            d = rounded_distance(x, y, w, h, radius)
            ca = min(1, max(0, 0.5 - d))
            if ca > 0:
                i = (min(h - 1, max(0, int(y))) * w + min(w - 1, max(0, int(x)))) * 4
                b, g, r = bgra[i], bgra[i + 1], bgra[i + 2]
            else:
                r = g = b = 0
            a = ca + sa * (1 - ca)
            if a > 0:  # card over its black shadow, un-premultiplied
                r, g, b = (round(c * ca / a) for c in (r, g, b))
            row += bytes((r, g, b, round(a * 255)))
        rows.append(bytes(row))
    return W, H, b"".join(rows)


def png(path, w, h, raw):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


if __name__ == "__main__":
    todos.save(test_items())
    shot = Shot()
    shot.root.after(300)
    shot.root.update()
    if HOLD:
        shot.show_state(sys.argv[2])
        shot.root.mainloop()
    else:
        for name in STATES:
            shot.show_state(name)
            shot.root.after(300)
            shot.root.update()
            w, h, bgra = grab(shot.hwnd)
            png(Path(sys.argv[1]) / f"{name}.png", *framed(w, h, bgra, SCALE))
            print(name, w, h)
        shot.root.destroy()
