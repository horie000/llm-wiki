import json
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from codex_session_exporter.cli import Session, find_sessions, main, render, session_id, write_session


def make_session(root: Path, project: Path, sid: str, prompt: str, date: str) -> Path:
    path = root / "2026" / f"rollout-{sid}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    records = [
        {"type": "session_meta", "payload": {"id": sid, "cwd": str(project), "timestamp": date}},
        {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": prompt}]}},
        {"type": "response_item", "payload": {"type": "function_call", "name": "exec_command", "call_id": "c1", "arguments": json.dumps({"cmd": "echo safe", "cwd": str(project)})}},
        {"type": "response_item", "payload": {"type": "function_call_output", "call_id": "c1", "output": {"exit_code": 0, "text": "PRIVATE TOOL OUTPUT"}}},
    ]
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    return path


class ExporterTests(unittest.TestCase):
    def test_rejects_path_like_session_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            project = base / "project"
            source = base / "source"
            path = make_session(source, project, "unsafe", "unsafe", "2026-01-01T00:00:00Z")
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            rows[0]["payload"]["id"] = "../escape"
            path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            self.assertEqual(find_sessions(source, project), [])
            with self.assertRaises(ValueError):
                session_id(Session(source / "2026/rollout-unsafe.jsonl", {"id": "..\\outside"}))

    def test_output_dir_must_be_inside_vault_and_links_are_vault_relative(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            vault = base / "vault"
            output = vault / "exports" / "sessions"
            markdown = '---\nsession_id: "safe-id"\n---\n# Synthetic\n'
            saved = write_session(markdown, "2026-01-01", "Synthetic", "safe-id", output, vault)
            self.assertTrue(saved.is_file())
            index = (output / "index.md").read_text(encoding="utf-8")
            self.assertIn("[[exports/sessions/2026-01-01-Synthetic-safe-id|Synthetic]]", index)
            with self.assertRaises(RuntimeError):
                write_session(markdown, "2026-01-01", "Synthetic", "safe-id", base / "outside", vault)
            self.assertFalse((base / "outside").exists())

    def test_cli_explicit_source_and_codex_home_select_expected_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            project = base / "project"
            source = base / "selected-source"
            codex_home = base / "custom-codex-home"
            make_session(source, project, "source-id", "from source", "2026-03-01T00:00:00Z")
            make_session(codex_home / "sessions", project, "home-id", "from home", "2026-03-02T00:00:00Z")
            make_session(base / "other-source", project, "other-id", "other root", "2026-03-03T00:00:00Z")

            for source_args, expected_id in ((["--source", str(source)], "source-id"), (["--codex-home", str(codex_home)], "home-id")):
                output = io.StringIO()
                with redirect_stdout(output):
                    result = main(["--vault", str(base / "vault"), "--project", str(project), *source_args, "--list"])
                self.assertEqual(result, 0)
                self.assertIn(expected_id, output.getvalue())
                self.assertNotIn("other-id", output.getvalue())

    def test_filters_project_and_redacts_without_tool_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            project_a, project_b = base / "project-a", base / "project-b"
            root = base / "source"
            make_session(root, project_a, "aaa", "hello password=hunter2", "2026-01-01T12:00:00Z")
            make_session(root, project_b, "bbb", "other", "2026-01-02T12:00:00Z")
            found = find_sessions(root, project_a)
            self.assertEqual([session_id(item) for item in found], ["aaa"])
            markdown, _, _ = render(found[0])
            self.assertIn("password=[REDACTED]", markdown)
            self.assertNotIn("hunter2", markdown)
            self.assertNotIn("PRIVATE TOOL OUTPUT", markdown)
            self.assertIn("終了コード 0", markdown)

    def test_two_vaults_and_upsert_rename_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source_one, source_two = base / "source-one", base / "source-two"
            project = base / "project"
            first = make_session(source_one, project, "same-id", "First title", "2026-02-01T12:00:00Z")
            second = make_session(source_two, project, "same-id", "Renamed title", "2026-02-02T12:00:00Z")
            vault_one, vault_two = base / "vault-one", base / "vault-two"
            for vault, session in ((vault_one, find_sessions(source_one, project)[0]), (vault_two, find_sessions(source_two, project)[0])):
                markdown, day, title = render(session)
                result = write_session(markdown, day, title, session_id(session), vault / "sessions")
                self.assertTrue(result.is_file())
                self.assertIn(f"[[sessions/{result.stem}|{title}]]", (vault / "sessions/index.md").read_text(encoding="utf-8"))
            self.assertTrue((vault_one / "sessions/2026-02-01-First-title-same-id.md").exists())
            # Re-export the same ID with a changed title into vault one.
            renamed = find_sessions(source_two, project)[0]
            markdown, day, title = render(renamed)
            write_session(markdown, day, title, session_id(renamed), vault_one / "sessions")
            self.assertFalse((vault_one / "sessions/2026-02-01-First-title-same-id.md").exists())
            index = (vault_one / "sessions/index.md").read_text(encoding="utf-8")
            self.assertEqual(index.count("same-id"), 1)
            self.assertIn("Renamed-title-same-id", index)
            self.assertTrue(second.is_file())

    def test_strips_injected_user_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            project = base / "project"
            path = make_session(base / "source", project, "ctx", "placeholder", "2026-01-01T00:00:00Z")
            raw = path.read_text(encoding="utf-8")
            injected = "# AGENTS.md instructions for C:\\vault\nsecret policy\n<INSTRUCTIONS>hidden</INSTRUCTIONS>\n<environment_context>hidden env</environment_context>\nvisible"
            record = {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": injected}]}}
            path.write_text(raw + json.dumps(record) + "\n", encoding="utf-8")
            output, _, _ = render(find_sessions(base / "source", project)[0])
            self.assertIn("visible", output)
            self.assertNotIn("hidden env", output)
            self.assertNotIn("hidden</INSTRUCTIONS>", output)


if __name__ == "__main__":
    unittest.main()
