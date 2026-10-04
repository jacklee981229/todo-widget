# Test steps

Run these in PowerShell from this folder:

```powershell
cd C:\repos\Jack\todo-widget
```

## Task 1. To-do widget

### 1. Unit tests

```powershell
python -m unittest discover -s tests
```

Expected: a line of dots, then `Ran 14 tests in 0.XXXs` and `OK` (11 before Task 2, 13 before Task 3). PowerShell may print the dots as a red `NativeCommandError`; that's only because unittest writes to stderr.

### 2. Start the widget

```powershell
pythonw widget.py
```

Expected: no console window opens, and the window you were typing in keeps focus. Press Win+D: the widget is at the top right, under where the usage widget starts. It shows `To-do`, `0 open`, `All projects`, an orange `+`, and "Nothing to do yet." Leave it running for the next steps.

### 3. Add, tick, edit, delete

Click **+**, type `Try the to-do widget`, pick `todo-widget` in Project, type a note, and press Enter.

Expected: the item shows under a `todo-widget` heading with the note in grey below it, and the header count goes up by one. Click its box: the box turns orange with a tick, the text is struck through, and the count goes down. Click the text, change it, and click Save: the new text shows. Click it again, click Delete, then `Click again to delete`: it's gone.

### 4. Add with the command

```powershell
python todos.py add todo-widget 'Added with the command' --notes 'shows up by itself'
```

Expected: it prints `Added to todo-widget: Added with the command`, and within 2 seconds the item appears in the widget (Win+D to look). Delete it in the widget afterwards.

### 5. Claude adds when you ask

In a Claude app session in one of your projects, for example lan-drop, say "add to my to-do: check the to-do widget".

Expected: Claude runs the add command with `lan-drop` as the project, and the item appears under `lan-drop` in the widget. Delete it afterwards.

### 6. Stays behind your windows; move, one copy, exit

Click an app window that covers the widget, then drag the widget's header somewhere else. Run `pythonw widget.py` again, then right-click the header and choose Exit.

Expected: the widget stays behind the app window and is in neither the taskbar nor Alt+Tab. The second start adds no second widget, Exit closes it, and starting it again (step 2) reopens it where you dropped it.

### 7. Starts with Windows

Press Win+R and type `shell:startup`, then sign out and back in (or restart).

Expected: the Startup folder has a shortcut named `To-do widget`, and after you sign in the widget is running (Win+D to see it). If you ever move this folder, make the shortcut again with the command in the README's "Start with Windows" section.

## Task 2. Tick off with the command

### 1. Unit tests

Run Task 1's step 1. Expected: `OK`.

### 2. Add, then tick off

With the widget running:

```powershell
python todos.py add todo-widget 'Tick me with the command'
```

```powershell
python todos.py done todo-widget 'Tick me with the command'
```

Expected: the first prints `Added to todo-widget: Tick me with the command`, the second `Ticked in todo-widget: Tick me with the command`. Within 2 seconds the item shows ticked and struck through in the widget (Win+D to look).

### 3. Nothing to tick

Run the `done` command from step 2 again.

Expected: it prints `Not ticked: no open to-do "Tick me with the command" in todo-widget.` and the list doesn't change. Delete the item in the widget afterwards.

## Task 3. Grouped or one list

### 1. Unit tests

Run Task 1's step 1. Expected: `Ran 14 tests` and `OK`.

### 2. Restart the widget

Right-click the widget's header and choose Exit, then:

```powershell
pythonw widget.py
```

Expected: the widget comes back where it was, with a **Group** word in orange left of the project box, grouped under project headings as before.

### 3. One list

Press Win+D, then click **Group**.

Expected: **Group** turns grey, the headings go, and all items form one list: open ones first, oldest at the top, ticked ones at the bottom. Each item has a small grey tag with its project (`jacks-space`, `Jack` …) between its text and its note.

### 4. One project

Pick `jacks-space` in the project box.

Expected: only jacks-space items, and no tags. Pick `All projects` again: the tags come back.

### 5. Remembers

Exit and start the widget again (step 2).

Expected: it opens as one list, with **Group** grey. Click **Group** to go back to grouped if you prefer; that's remembered too.
