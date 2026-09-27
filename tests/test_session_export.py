import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "codex-session-exporter"))
from codex_session_exporter.cli import Session, clean_user_prompt, find_existing_output, redact, render, tool_summary, update_index, write_session


def render_markdown(session):
    return render(session)[0]


class SessionExportTests(unittest.TestCase):
    def test_clean_user_prompt_removes_codex_injected_blocks_but_keeps_user_text(self):
        injected = (
            "# AGENTS.md instructions for C:/vault\n<INSTRUCTIONS>private rules</INSTRUCTIONS>\n"
            "<environment_context>private environment</environment_context>\n"
            "私の入力したプロンプトと操作を記録してください"
        )
        result = clean_user_prompt(injected)
        self.assertEqual(result, "私の入力したプロンプトと操作を記録してください")
        self.assertEqual(clean_user_prompt("# AGENTS.md instructions for C:/vault\n<INSTRUCTIONS>rules</INSTRUCTIONS>"), "")

    def test_render_ignores_injected_messages_for_history_and_title(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rollout-test.jsonl"
            rows = [
                {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "# AGENTS.md instructions for C:/vault\n<INSTRUCTIONS>injected policy</INSTRUCTIONS>"}]}},
                {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "<environment_context>injected context</environment_context>"}]}},
                {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "私の入力したプロンプトと操作を記録してください"}]}},
            ]
            path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            result = render_markdown(Session(path, {"id": "injected-test", "timestamp": "2026-09-27T10:00:00Z"}))
            self.assertIn("# 私の入力したプロンプトと操作を記録してください", result)
            self.assertEqual(result.count("## プロンプト"), 1)
            self.assertNotIn("injected policy", result)
            self.assertNotIn("injected context", result)

    def test_redacts_common_credentials(self):
        value = "api_key=examplesecret Bearer abcdefghijklmnopqrstuvwxyz sk-1234567890abcdefghijkl"
        result = redact(value)
        self.assertNotIn("examplesecret", result)
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz", result)
        self.assertNotIn("sk-1234567890abcdefghijkl", result)

    def test_render_keeps_chat_and_summarizes_tools_without_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rollout-test.jsonl"
            rows = [
                {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Please inspect file"}]}},
                {"type": "response_item", "payload": {"type": "custom_tool_call", "call_id": "c1", "name": "shell", "input": "{}"}},
                {"type": "response_item", "payload": {"type": "custom_tool_call_output", "call_id": "c1", "output": "sensitive tool output that must not appear"}},
                {"type": "response_item", "payload": {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Done."}]}},
            ]
            path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            result = render_markdown(Session(path, {"id": "abcd1234", "timestamp": "2026-09-27T10:00:00Z"}))
            self.assertIn("Please inspect file", result)
            self.assertIn("Done.", result)
            self.assertIn("結果: 結果を受信（成否未判定）", result)
            self.assertIn("出力 42 文字", result)
            self.assertNotIn("sensitive tool output", result)

    def test_exit_codes_are_reported_and_zero_is_not_inferred_from_text(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rollout-test.jsonl"
            for code, expected in ((0, "終了コード 0"), (17, "終了コード 17")):
                rows = [
                    {"type": "response_item", "payload": {"type": "custom_tool_call", "call_id": "c1", "name": "shell", "input": "{}"}},
                    {"type": "response_item", "payload": {"type": "custom_tool_call_output", "call_id": "c1", "output": "finished successfully", "exitCode": code}},
                ]
                path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
                result = render_markdown(Session(path, {"id": "code-test", "timestamp": "2026-09-27T10:00:00Z"}))
                self.assertIn(f"結果: {expected}", result)

    def test_repeated_identical_turns_are_preserved_and_event_fallback_is_not_duplicated(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rollout-test.jsonl"
            rows = []
            for _ in range(2):
                rows.extend([
                    {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Repeat this"}]}},
                    {"type": "event_msg", "payload": {"type": "user_message", "message": "Repeat this"}},
                    {"type": "response_item", "payload": {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Same answer"}]}},
                ])
            path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            result = render_markdown(Session(path, {"id": "repeat-id", "timestamp": "2026-09-27T10:00:00Z"}))
            self.assertEqual(result.count("## プロンプト"), 2)
            self.assertEqual(result.count("## 回答"), 2)

    def test_event_message_is_fallback_when_response_user_is_absent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rollout-test.jsonl"
            rows = [
                {"type": "event_msg", "payload": {"type": "user_message", "message": "<environment_context>injected environment</environment_context>"}},
                {"type": "event_msg", "payload": {"type": "user_message", "message": "Old format prompt"}},
            ]
            path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            result = render_markdown(Session(path, {"id": "old-id", "timestamp": "2026-09-27T10:00:00Z"}))
            self.assertIn("Old format prompt", result)
            self.assertNotIn("injected environment", result)

    def test_tool_summary_includes_limited_command_and_paths_with_redaction(self):
        row = {"payload": {"type": "function_call", "name": "shell", "arguments": json.dumps({
            "command": "python inspect.py --api-key=sk-1234567890abcdefghijkl --password top-secret",
            "workdir": "C:/vault/project",
            "private_argument": "must not appear",
        })}}
        summary = tool_summary(row)
        self.assertIn("python inspect.py", summary)
        self.assertIn("C:/vault/project", summary)
        self.assertIn("[REDACTED]", summary)
        self.assertNotIn("must not appear", summary)
        self.assertNotIn("top-secret", summary)

    def test_same_session_id_reuses_existing_path_and_replaces_index_row(self):
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory)
            sessions = vault / "sessions"
            sessions.mkdir()
            sid = "id-123456"
            old = sessions / "2026-09-20-old-title-id-123456.md"
            old.write_text(f'---\nsession_id: "{sid}"\n---\n', encoding="utf-8")
            self.assertEqual(find_existing_output(sessions, sid), old)
            index = sessions / "index.md"
            index.write_text("# Sessions\n\n- 2026-09-20 — [[sessions/2026-09-20-old-title-id-123456|Old title]]\n", encoding="utf-8")
            newer = sessions / old.name
            update_index(newer, "2026-09-27", "New title", sid, sessions)
            contents = index.read_text(encoding="utf-8")
            self.assertEqual(contents.count("id-123456"), 1)
            self.assertIn("New title", contents)
            self.assertNotIn("Old title", contents)

    def test_same_id_wrong_title_file_is_renamed_to_canonical_path(self):
        with tempfile.TemporaryDirectory() as directory:
            sessions = Path(directory) / "sessions"
            sessions.mkdir()
            sid = "same-session-id"
            old = sessions / "2026-09-27-injected-title-same-session-id.md"
            new = sessions / "2026-09-27-real-prompt-same-session-id.md"
            old.write_text(f'---\nsession_id: "{sid}"\n---\n', encoding="utf-8")
            written = write_session(f'---\nsession_id: "{sid}"\n---\n# Real prompt\n', "2026-09-27", "real prompt", sid, sessions)
            self.assertFalse(old.exists())
            self.assertEqual(written, new)
            self.assertTrue(new.exists())
            self.assertEqual(find_existing_output(sessions, sid), new)
            pages = [path for path in sessions.glob("*.md") if path.name != "index.md"]
            self.assertEqual(len(pages), 1)

    def test_index_keeps_newest_date_first(self):
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory)
            sessions = vault / "sessions"
            sessions.mkdir()
            (sessions / "index.md").write_text("# Sessions\n\n- 2026-09-20 — [[sessions/older|Older]]\n", encoding="utf-8")
            target = sessions / "newer.md"
            target.write_text('---\nsession_id: "new"\n---\n', encoding="utf-8")
            update_index(target, "2026-09-27", "Newer", "new", sessions)
            lines = [line for line in (sessions / "index.md").read_text(encoding="utf-8").splitlines() if line.startswith("- ")]
            self.assertIn("2026-09-27", lines[0])
            self.assertIn("2026-09-20", lines[1])


if __name__ == "__main__":
    unittest.main()
