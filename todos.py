"""Jack's to-do list: a JSON file the widget shows and Claude adds to.

Claude adds items with `python todos.py add <project> "<text>" --notes "<notes>"` and ticks them off with
`python todos.py done <project> "<text>"`.
"""
import argparse
import json
import os
import sys
import tempfile
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
TODO_FILE = HERE / "data" / "todos.json"
ARCHIVE_FILE = HERE / "data" / "archive.json"
ARCHIVE_AFTER = timedelta(days=7)
PROJECTS_ROOT = HERE.parent
GENERAL = "General"
PROJECT_MARKERS = ("CLAUDE.md", "README.md", "TESTING.md")
FIELDS = {"id": str, "project": str, "text": str, "notes": str, "done": bool}


def load(path=TODO_FILE):
    """All items in the order added. No file yet means an empty list; a file that can't be read raises ValueError,
    so nobody saves over it."""
    try:
        items = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except ValueError as error:
        raise ValueError(f"{path.name} can't be read ({error}). Nothing is saved until it's fixed.") from error
    if not (isinstance(items, list) and all(isinstance(i, dict) and all(isinstance(i.get(k), t) for k, t in FIELDS.items()) for i in items)):
        raise ValueError(f"{path.name} isn't a list of to-dos. Nothing is saved until it's fixed.")
    return items


def save(items, path=TODO_FILE):
    """Write a temp file and swap it in, so a crash never leaves half a list."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            json.dump(items, file, ensure_ascii=False, indent=2)
        for attempt in range(20):
            try:
                os.replace(temp, path)
                return
            except PermissionError:
                # Windows refuses the swap while another process (the widget, the add command) is reading the file.
                if attempt == 19:
                    raise
                time.sleep(0.05)
    finally:
        if os.path.exists(temp):
            os.remove(temp)


def fields(text, project, notes):
    text = text.strip()
    if not text:
        raise ValueError("Type the to-do first.")
    return {"project": project.strip(), "text": text, "notes": notes.strip()}


def add(items, text, project="", notes=""):
    item = {"id": uuid.uuid4().hex, **fields(text, project, notes), "done": False}
    items.append(item)
    return item


def find(items, item_id):
    return next((i for i in items if i["id"] == item_id), None)


def edit(items, item_id, text, project, notes):
    changes = fields(text, project, notes)
    item = find(items, item_id)
    if item:
        item.update(changes)


def set_done(item, done):
    """Tick or untick, noting when it was ticked so ticked items can show the latest first."""
    item["done"] = done
    if done:
        item["done_at"] = datetime.now().isoformat(timespec="seconds")
    else:
        item.pop("done_at", None)


def toggle(items, item_id):
    item = find(items, item_id)
    if item:
        set_done(item, not item["done"])


def tick(items, project, text):
    """Ticks the one open item with this project and text. Refuses rather than guess when none or several match."""
    project, text = project.strip(), text.strip()
    matches = [i for i in items if not i["done"] and i["project"] == project and i["text"] == text]
    if len(matches) != 1:
        found = "no open to-do" if not matches else f"{len(matches)} open to-dos"
        raise ValueError(f'{found} "{text}" in {project or GENERAL}.')
    set_done(matches[0], True)
    return matches[0]


def stale(items, now):
    """Ticked items to archive (ticked over a week ago) or to start the clock on (ticked before times were kept)."""
    return [i for i in items if i["done"] and ("done_at" not in i or datetime.fromisoformat(i["done_at"]) <= now - ARCHIVE_AFTER)]


def tidy(items, now, archive_path=ARCHIVE_FILE):
    """Move items ticked over a week ago into the archive file, which keeps them, so the ticked list stays short.
    Items ticked before tick times were kept start their week now."""
    for item in items:
        if item["done"] and "done_at" not in item:
            item["done_at"] = now.isoformat(timespec="seconds")
    old = {i["id"] for i in stale(items, now)}
    if old:
        archived = load(archive_path)
        kept = {i["id"] for i in archived}
        # The archive is saved first: a crash before the list is saved leaves an item in both, never in neither.
        save(archived + [i for i in items if i["id"] in old and i["id"] not in kept], archive_path)
        items[:] = [i for i in items if i["id"] not in old]


def delete(items, item_id):
    items[:] = [i for i in items if i["id"] != item_id]


def shown_order(items):
    """Open items in the order added, then ticked ones, the latest ticked first. Items ticked before tick times were
    kept come last, in the order added."""
    ticked = sorted((i for i in items if i["done"]), key=lambda i: i.get("done_at", ""), reverse=True)
    return [i for i in items if not i["done"]] + ticked


def grouped(items, project=None):
    """(project, items) pairs to show: projects A-Z with General last, open items before ticked ones.
    Given a project, only that one."""
    groups = {}
    for item in items:
        name = item["project"] or GENERAL
        if project is None or name == project:
            groups.setdefault(name, []).append(item)
    order = sorted(groups, key=lambda name: (name == GENERAL, name.lower()))
    return [(name, shown_order(groups[name])) for name in order]


def listed(items, project=None):
    """Items to show as one list, without project headings, in shown_order. Given a project, only that one."""
    return shown_order([i for i in items if project is None or (i["project"] or GENERAL) == project])


def project_suggestions(items, root=PROJECTS_ROOT):
    """Project folders (any folder with a CLAUDE.md, README.md or TESTING.md) plus names already used."""
    names = {i["project"] for i in items if i["project"]}
    try:
        names.update(d.name for d in root.iterdir() if d.is_dir() and any((d / m).is_file() for m in PROJECT_MARKERS))
    except OSError:
        pass
    return sorted(names, key=str.lower)


def main(argv=None, path=TODO_FILE):
    parser = argparse.ArgumentParser(prog="todos.py", description="Add a to-do to Jack's list, or tick one off.")
    commands = parser.add_subparsers(dest="command", required=True)
    add_command = commands.add_parser("add", help="add a to-do")
    done_command = commands.add_parser("done", help="tick off the open to-do with exactly this text")
    for command in (add_command, done_command):
        command.add_argument("project", help="the project's folder name, e.g. lan-drop")
        command.add_argument("text", help="the to-do")
    add_command.add_argument("--notes", default="", help="a longer note, such as where you left off")
    args = parser.parse_args(argv)
    adding = args.command == "add"
    try:
        items = load(path)
        item = add(items, args.text, args.project, args.notes) if adding else tick(items, args.project, args.text)
        save(items, path)
    except (OSError, ValueError) as error:
        sys.exit(f"{'Not added' if adding else 'Not ticked'}: {error}")
    print(f"{'Added to' if adding else 'Ticked in'} {item['project'] or GENERAL}: {item['text']}")


if __name__ == "__main__":
    # Claude's shell reads the output through a pipe in the ANSI code page; escape what it can't show instead of
    # crashing after the item is already saved.
    sys.stdout.reconfigure(errors="backslashreplace")
    main()
