import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import todos


class TodosTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.path = self.root / "data" / "todos.json"

    def write(self, text):
        self.path.parent.mkdir(exist_ok=True)
        self.path.write_text(text, encoding="utf-8")

    def test_first_run_is_an_empty_list(self):
        self.assertEqual(todos.load(self.path), [])

    def test_broken_file_is_refused_and_left_alone(self):
        broken = '[{"id": "a1", "project": "lan-drop", "text": "Pick a po'
        self.write(broken)
        with self.assertRaisesRegex(ValueError, "todos.json can't be read"):
            todos.load(self.path)
        with self.assertRaises(SystemExit):
            todos.main(["add", "lan-drop", "Another"], self.path)
        self.assertEqual(self.path.read_text(encoding="utf-8"), broken)

    def test_file_that_is_not_a_list_of_todos_is_refused(self):
        for text in ('{"id": "a1"}', "[1]", '[{"id": "a1", "project": "", "text": "No done field", "notes": ""}]'):
            self.write(text)
            with self.assertRaisesRegex(ValueError, "isn't a list of to-dos"):
                todos.load(self.path)

    def test_add_edit_tick_delete(self):
        items = []
        plan = todos.add(items, "  Write the plan  ", "lan-drop", "Stopped at step 3\n")
        cable = todos.add(items, "Buy a cable")
        self.assertNotEqual(plan["id"], cable["id"])
        self.assertEqual({k: plan[k] for k in ("project", "text", "notes", "done")},
                         {"project": "lan-drop", "text": "Write the plan", "notes": "Stopped at step 3", "done": False})
        todos.save(items, self.path)

        items = todos.load(self.path)
        todos.toggle(items, plan["id"])
        todos.edit(items, cable["id"], "Buy a USB-C cable", "jacks-space", "")
        todos.save(items, self.path)
        items = todos.load(self.path)
        self.assertTrue(todos.find(items, plan["id"])["done"])
        self.assertEqual(todos.find(items, cable["id"])["text"], "Buy a USB-C cable")
        self.assertEqual(todos.find(items, cable["id"])["project"], "jacks-space")

        todos.toggle(items, plan["id"])
        todos.delete(items, cable["id"])
        self.assertEqual([(i["text"], i["done"]) for i in items], [("Write the plan", False)])

    def test_to_do_needs_text(self):
        items = []
        with self.assertRaisesRegex(ValueError, "Type the to-do first"):
            todos.add(items, "   ")
        item = todos.add(items, "Keep me")
        with self.assertRaises(ValueError):
            todos.edit(items, item["id"], "", "lan-drop", "")
        self.assertEqual(item["text"], "Keep me")

    def test_non_english_text_and_emoji_survive_saving(self):
        items = []
        todos.add(items, "Bayar bil RM12.50 — 记得 ✅ 🚀", "jack-jarvis", "Nota: langkah seterusnya 下一步")
        todos.save(items, self.path)
        self.assertEqual(todos.load(self.path), items)

    def test_save_replaces_the_file_and_leaves_no_temp_files(self):
        todos.save([], self.path)
        items = []
        todos.add(items, "Second save")
        todos.save(items, self.path)
        self.assertEqual(todos.load(self.path), items)
        self.assertEqual([p.name for p in self.path.parent.iterdir()], ["todos.json"])

    def test_grouped_sorts_projects_and_puts_ticked_items_last(self):
        items = []
        for text, project in [("Old", "lan-drop"), ("Errand", ""), ("Post", "jacks-space"), ("New", "lan-drop"),
                              ("Named general", "General")]:
            todos.add(items, text, project)
        todos.toggle(items, items[0]["id"])
        self.assertEqual([(name, [i["text"] for i in group]) for name, group in todos.grouped(items)],
                         [("jacks-space", ["Post"]), ("lan-drop", ["New", "Old"]), ("General", ["Errand", "Named general"])])
        self.assertEqual([name for name, _ in todos.grouped(items, "lan-drop")], ["lan-drop"])
        self.assertEqual([i["text"] for _, group in todos.grouped(items, "General") for i in group], ["Errand", "Named general"])
        self.assertEqual(todos.grouped(items, "gone"), [])

    def test_listed_keeps_the_order_added_and_puts_ticked_items_last(self):
        items = []
        for text, project in [("Old", "lan-drop"), ("Errand", ""), ("Post", "jacks-space"), ("New", "lan-drop")]:
            todos.add(items, text, project)
        todos.toggle(items, items[0]["id"])
        self.assertEqual([i["text"] for i in todos.listed(items)], ["Errand", "Post", "New", "Old"])
        self.assertEqual([i["text"] for i in todos.listed(items, "lan-drop")], ["New", "Old"])
        self.assertEqual([i["text"] for i in todos.listed(items, "General")], ["Errand"])
        self.assertEqual(todos.listed(items, "gone"), [])

    def test_project_suggestions_are_project_folders_and_used_names(self):
        repos = self.root / "repos"
        for folder, marker in [("lan-drop", "CLAUDE.md"), ("Claude-usage-widget", "README.md"), ("jack-jarvis", "TESTING.md"),
                               ("template", None), ("old-site.git", None)]:
            (repos / folder).mkdir(parents=True)
            if marker:
                (repos / folder / marker).write_text("x", encoding="utf-8")
        (repos / "template" / "node-app").mkdir()
        (repos / "notes.md").write_text("x", encoding="utf-8")
        items = []
        todos.add(items, "One", "lan-drop")
        todos.add(items, "Two", "errands")
        todos.add(items, "Three")
        self.assertEqual(todos.project_suggestions(items, repos), ["Claude-usage-widget", "errands", "jack-jarvis", "lan-drop"])

    def test_add_command_appends_and_keeps_other_items(self):
        items = []
        todos.add(items, "Already here", "jacks-space", "Draft saved")
        todos.save(items, self.path)
        output = io.StringIO()
        with redirect_stdout(output):
            todos.main(["add", "lan-drop", "Pick a port", "--notes", "8080 is taken"], self.path)
        saved = todos.load(self.path)
        self.assertEqual(saved[0], items[0])
        self.assertEqual({k: saved[1][k] for k in ("project", "text", "notes", "done")},
                         {"project": "lan-drop", "text": "Pick a port", "notes": "8080 is taken", "done": False})
        self.assertEqual(output.getvalue(), "Added to lan-drop: Pick a port\n")

    def test_done_command_ticks_the_one_open_match_and_keeps_other_items(self):
        items = []
        for text, project in [("Plan: 2048 Bot", "jacks-space"), ("Plan: 2048 Bot", "lan-drop"), ("Other", "jacks-space")]:
            todos.add(items, text, project, "a note")
        todos.save(items, self.path)
        output = io.StringIO()
        with redirect_stdout(output):
            todos.main(["done", "jacks-space", " Plan: 2048 Bot "], self.path)
        self.assertEqual([i["done"] for i in todos.load(self.path)], [True, False, False])
        self.assertEqual(todos.load(self.path)[0]["notes"], "a note")
        self.assertEqual(output.getvalue(), "Ticked in jacks-space: Plan: 2048 Bot\n")

    def test_done_command_refuses_no_match_or_several_and_changes_nothing(self):
        items = []
        todos.add(items, "Twice", "jacks-space")
        todos.add(items, "Twice", "jacks-space")
        todos.add(items, "Ticked already", "jacks-space")
        todos.toggle(items, items[2]["id"])
        todos.save(items, self.path)
        before = self.path.read_text(encoding="utf-8")
        for text, reason in [("Twice", '2 open to-dos "Twice"'), ("Ticked already", 'no open to-do "Ticked already"'),
                             ("Missing", 'no open to-do "Missing"')]:
            with self.assertRaises(SystemExit) as stop:
                todos.main(["done", "jacks-space", text], self.path)
            self.assertEqual(str(stop.exception.code), f"Not ticked: {reason} in jacks-space.")
        self.assertEqual(self.path.read_text(encoding="utf-8"), before)

    def test_add_command_starts_the_file_on_first_use(self):
        with redirect_stdout(io.StringIO()):
            todos.main(["add", "lan-drop", "First one"], self.path)
        self.assertEqual([i["text"] for i in todos.load(self.path)], ["First one"])


if __name__ == "__main__":
    unittest.main()
