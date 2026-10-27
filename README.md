# To-do widget

A small to-do list on your desktop for your personal projects. You add to it, and so does Claude when you ask it to; Claude also ticks items off when their work is committed and pushed.

- Each to-do has a project and can have notes, such as where you left off. The box at the top shows all projects or just one.
- It sits just above the desktop, behind all your windows, like the usage widget. Win+D (or a click on the desktop) brings it to the front, and you can click it to type. It stays out of the taskbar and Alt+Tab.
- It starts when you sign in to Windows.
- It matches the usage widget: the same dark card, and an accent (the **+**, ticks, Save) that changes colour each day, round the rainbow from red on Monday to violet on Sunday.
- Both widgets use Hanken Grotesk, under the SIL Open Font License, from `fonts\`. Only the widget loads it, so nothing is installed in Windows; without the files it falls back to Segoe UI.
- Every change is saved in `data\todos.json`. The widget checks that file every 2 seconds, so items Claude adds appear on their own.

## Use it

- **Add:** click **+**, type the to-do, pick or type a project, and add notes if you like. Enter saves, Esc cancels. In a one-project view, the project is filled in for you.
- **Tick:** click the box. For 5 seconds after a tick, **Undo** at the bottom brings the item back. Ticked items move below a line under the open ones, struck through, the latest ticked first. A week after its tick, an item moves to `data\archive.json`, which keeps it; ask Claude to bring one back. The line hides them: click **Expand** to show them and **Collapse** to hide them again. The widget always starts with them hidden.
- **Edit or delete:** click the item. Delete asks for a second click.
- **Grouped or one list:** click **Group** in the header. Coloured means grouped under project headings; grey means one list, oldest first, with each item's project in small grey letters under it (hidden when the box shows one project). The widget starts the way you left it.
- **Move or exit:** drag the header to move it; it reopens where you left it. Right-click the header and choose Exit.

The Project box suggests your project folders (any folder in `C:\repos\Jack` with a CLAUDE.md, README.md or TESTING.md) and the names you've already used. Any name works.

## Commands

Run these in PowerShell from this folder:

| Command | Does |
|---|---|
| `pythonw widget.py` | Start the widget, without a console window |
| `python todos.py add <project> "<text>" --notes "<notes>"` | Add a to-do (`--notes` is optional) |
| `python todos.py done <project> "<text>"` | Tick off the open to-do with exactly this project and text |
| `python -m unittest discover -s tests` | Run the tests |

## Adding or ticking a to-do from a Claude session

Run the add command with the full path, so it works from any folder. Use the session's project folder name as the project:

```powershell
python C:\repos\Jack\todo-widget\todos.py add lan-drop 'Pick a port for the server' --notes 'Tried 8080; Trae uses it'
```

It prints `Added to lan-drop: Pick a port for the server`. In PowerShell, wrap the text in single quotes and double any single quote inside it (`'Jack''s list'`). If `todos.json` can't be read, it prints `Not added: …` and changes nothing.

To tick one off, give the same project and the item's exact text:

```powershell
python C:\repos\Jack\todo-widget\todos.py done jacks-space 'Plan: 2048 Bot'
```

It prints `Ticked in jacks-space: Plan: 2048 Bot`. If no open item has that text, or more than one does, it prints `Not ticked: …` and changes nothing.

## Start with Windows

A shortcut named `To-do widget` in your Startup folder starts the widget when you sign in (press Win+R and type `shell:startup` to see it). Delete the shortcut to stop that.

The shortcut runs `To-do.exe`, a copy of Python's `pythonw.exe` beside it in the Python folder, renamed so Task Manager lists the widget as "To-do" instead of Python. It still runs `widget.py` from this folder, so a code change needs only a restart. Reinstalling Python or moving this folder breaks the shortcut; close the widget (right-click, Exit), then run this from this folder to make both again:

```powershell
python startup.py
```
