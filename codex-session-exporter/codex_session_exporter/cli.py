from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


SECRET_PATTERNS = [
    (re.compile(r"(?i)(\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|passwd|secret)\b\s*[:=]\s*)([^\s,;]+)"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(--?(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|passwd|secret)(?:=|\s+))(?:(?:\"[^\"]*\")|(?:'[^']*')|[^\s]+)"), r"\1[REDACTED]"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"), "[REDACTED_KEY]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), "[REDACTED_TOKEN]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED_AWS_KEY]"),
    (re.compile(r"(?i)(\bbearer\s+)[A-Za-z0-9._~+/=-]{12,}"), r"\1[REDACTED]"),
]
SESSION_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")


@dataclass
class Session:
    path: Path
    meta: dict[str, Any]


def redact(text: str) -> str:
    for pattern, replacement in SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def default_source_root() -> Path:
    home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    return home / "sessions"


def read_meta(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                row = json.loads(line)
                if row.get("type") == "session_meta" and isinstance(row.get("payload"), dict):
                    return row["payload"]
    except (OSError, UnicodeError, json.JSONDecodeError):
        pass
    return {}


def find_sessions(root: Path, project: Path | None = None) -> list[Session]:
    """Find top-level sessions. A project filter matches canonical cwd paths."""
    if not root.is_dir():
        return []
    target = str(project.resolve()).casefold() if project else None
    found: list[Session] = []
    for path in root.rglob("rollout-*.jsonl"):
        meta = read_meta(path)
        if not meta or (target and str(meta.get("cwd", "")).casefold() != target):
            continue
        if meta.get("parent_thread_id") or meta.get("forked_from_id") or meta.get("agent_nickname"):
            continue
        session = Session(path, meta)
        try:
            session_id(session)
        except ValueError:
            continue
        found.append(session)
    def order(item: Session) -> tuple[str, float]:
        try:
            mtime = item.path.stat().st_mtime
        except OSError:
            mtime = 0
        return str(item.meta.get("timestamp", "")), mtime
    return sorted(found, key=order, reverse=True)


def session_id(session: Session) -> str:
    value = str(session.meta.get("id") or session.meta.get("session_id") or session.path.stem.rsplit("-", 1)[-1])
    if not SESSION_ID_PATTERN.fullmatch(value):
        raise ValueError("セッション ID は英数字、ピリオド、アンダースコア、ハイフンのみ使用できます")
    return value


def extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts = [part["text"] for part in content if isinstance(part, dict) and part.get("type") in {"input_text", "output_text", "text"} and isinstance(part.get("text"), str)]
    return "\n".join(parts).strip()


def clean_user_prompt(text: str) -> str:
    text = re.sub(r"(?ms)^\s*# AGENTS\.md instructions for[^\n]*\n.*?</INSTRUCTIONS>\s*", "", text)
    text = re.sub(r"(?ms)<environment_context>.*?</environment_context>\s*", "", text)
    return text.strip()


def tool_summary(row: dict[str, Any]) -> str:
    payload = row.get("payload") or {}
    name = str(payload.get("name") or payload.get("recipient") or payload.get("type", "tool"))
    details: list[str] = []
    path_keys = ("path", "file_path", "cwd", "workdir")
    args = payload.get("arguments", payload.get("input"))
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            args = None
    for container in (payload, args if isinstance(args, dict) else {}):
        for key in path_keys:
            value = container.get(key)
            if isinstance(value, str) and value and not any(d.startswith(f"{key}:") for d in details):
                details.append(f"{key}: `{redact(value)}`")
    if isinstance(args, dict):
        command = args.get("cmd", args.get("command"))
        if isinstance(command, list):
            command = " ".join(map(str, command))
        if isinstance(command, str) and command.strip():
            compact = re.sub(r"\s+", " ", redact(command.strip()))
            details.append(f"command: `{compact[:180]}{'…' if len(compact) > 180 else ''}`")
    return f"`{redact(name)}`" + (" — " + "; ".join(details) if details else "")


def get_exit_code(output: dict[str, Any]) -> int | None:
    containers = [output] + [output[k] for k in ("output", "result", "content") if isinstance(output.get(k), dict)]
    for container in containers:
        for key in ("exit_code", "exitCode", "return_code", "returncode"):
            value = container.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                return value
            if isinstance(value, str) and re.fullmatch(r"-?\d+", value.strip()):
                return int(value.strip())
    return None


def rows(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                yield row


def parse_timestamp(value: Any) -> dt.datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=dt.timezone.utc) if parsed.tzinfo is None else parsed
    except ValueError:
        return None


def title_from(events: list[tuple[int, str, str]], fallback: str) -> str:
    first = next((body.splitlines()[0] for _, label, body in events if label == "プロンプト" and body.splitlines()), fallback)
    title = re.sub(r"\s+", " ", first).strip()
    title = re.sub(r"[\\/:*?\"<>|\[\]#^{}]", "", title)
    return title[:64].rstrip(" .-") or "Codex セッション"


def safe_filename(title: str) -> str:
    return re.sub(r"[^\wぁ-んァ-ヶ一-龠.-]+", "-", title, flags=re.UNICODE).strip(".-") or "session"


def render(session: Session) -> tuple[str, str, str]:
    events: list[tuple[int, str, str]] = []
    fallbacks: list[tuple[int, str, str]] = []
    outputs: dict[str, dict[str, Any]] = {}
    has_user = False
    source_rows = list(rows(session.path))
    for ordinal, row in enumerate(source_rows):
        payload = row.get("payload")
        if not isinstance(payload, dict):
            continue
        record, subtype = row.get("type"), payload.get("type")
        if record == "response_item":
            if subtype == "message" and payload.get("role") in {"user", "assistant"}:
                text = extract_text(payload.get("content"))
                if payload["role"] == "user":
                    text = clean_user_prompt(text)
                    has_user |= bool(text)
                if text:
                    events.append((ordinal, "プロンプト" if payload["role"] == "user" else "回答", redact(text)))
            elif subtype in {"function_call_output", "custom_tool_call_output"}:
                outputs[str(payload.get("call_id", ""))] = payload
            elif subtype in {"function_call", "custom_tool_call"}:
                events.append((ordinal, "操作", f"操作: {tool_summary(row)}"))
        elif record == "event_msg" and subtype == "user_message":
            text = payload.get("message")
            if isinstance(text, str) and (text := clean_user_prompt(text)):
                fallbacks.append((ordinal, "プロンプト", redact(text)))
    for ordinal, row in enumerate(source_rows):
        payload = row.get("payload", {})
        if row.get("type") != "response_item" or payload.get("type") not in {"function_call", "custom_tool_call"}:
            continue
        output = outputs.get(str(payload.get("call_id", "")))
        if output is None:
            continue
        result = output.get("output", output.get("content", ""))
        result_text = extract_text(result) or (result if isinstance(result, str) else "")
        exit_code = get_exit_code(output)
        status = f"終了コード {exit_code}" if exit_code is not None else "結果を受信（成否未判定）"
        pos = next((i for i, event in enumerate(events) if event[0] == ordinal and event[1] == "操作"), None)
        if pos is not None:
            old = events[pos]
            events[pos] = (old[0], old[1], f"{old[2]}\n  - 結果: {status}（出力 {len(result_text)} 文字の要約）")
    if not has_user:
        events.extend(fallbacks)
    events.sort(key=lambda event: event[0])
    timestamp = parse_timestamp(session.meta.get("timestamp"))
    if timestamp is None:
        timestamp = dt.datetime.fromtimestamp(session.path.stat().st_mtime, dt.timezone.utc)
    local = timestamp.astimezone()
    date = local.date().isoformat()
    title = title_from(events, session.path.stem)
    sid = session_id(session)
    body = ["---", "type: codex-session", f"session_id: {json.dumps(sid, ensure_ascii=False)}", f"date: {date}", "tags: [codex, session]", "---", "", f"# {title}", "", f"- 日時: {local.isoformat(timespec='minutes')}", f"- セッション ID: `{sid}`", "- 入力形式: Codex JSONL", "", "> 手動エクスポート。秘密情報らしい文字列は自動マスクし、ツール出力本文は保存せず結果の概要だけ記録。", ""]
    for _, label, text in events:
        body.extend([f"## {label}", "", text, ""])
    return "\n".join(body).rstrip() + "\n", date, title


def page_session_id(path: Path) -> str | None:
    try:
        with path.open(encoding="utf-8") as stream:
            for _ in range(12):
                line = stream.readline()
                if not line or line.startswith("# "):
                    break
                if line.startswith("session_id:"):
                    try:
                        value = json.loads(line.partition(":")[2].strip())
                    except json.JSONDecodeError:
                        return None
                    return value if isinstance(value, str) else None
    except OSError:
        return None
    return None


def find_existing_output(output_dir: Path, sid: str) -> Path | None:
    if output_dir.is_dir():
        for candidate in output_dir.glob("*.md"):
            if candidate.name != "index.md" and not candidate.is_symlink() and page_session_id(candidate) == sid:
                return candidate
    return None


def write_session(markdown: str, date: str, title: str, sid: str, output_dir: Path, vault_root: Path | None = None) -> Path:
    if not SESSION_ID_PATTERN.fullmatch(sid):
        raise ValueError("安全でないセッション ID です")
    vault = (vault_root or output_dir.parent).resolve()
    root = output_dir.resolve()
    try:
        root.relative_to(vault)
    except ValueError as exc:
        raise RuntimeError("--output-dir は --vault の配下に指定してください") from exc
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"{date}-{safe_filename(title)}-{sid}.md"
    existing = find_existing_output(output_dir, sid)
    for candidate in (target, existing):
        if candidate is not None and (candidate.is_symlink() or candidate.resolve().parent != root):
            raise RuntimeError(f"出力ファイルが指定フォルダーの直下にありません: {candidate}")
    if target.exists() and target != existing and page_session_id(target) != sid:
        raise RuntimeError(f"別セッションのファイルを上書きできません: {target}")
    if existing is not None and existing != target:
        if target.exists():
            existing.unlink()
        else:
            existing.rename(target)
    target.write_text(markdown, encoding="utf-8")
    update_index(target, date, title, sid, output_dir, vault)
    return target


def update_index(target: Path, date: str, title: str, sid: str, output_dir: Path, vault_root: Path | None = None) -> None:
    index = output_dir / "index.md"
    vault = (vault_root or output_dir.parent).resolve()
    relative = target.relative_to(vault).with_suffix("").as_posix()
    link = f"- {date} — [[{relative}|{title}]]"
    content = index.read_text(encoding="utf-8") if index.exists() else "# セッション記録\n\n"
    lines = content.splitlines()
    bullets = [line for line in lines if line.startswith("- ")]
    other = [line for line in lines if not line.startswith("- ")]
    keep = []
    for line in bullets:
        match = re.search(r"\[\[([^]|]+)", line)
        old = match.group(1) if match else ""
        old_path = vault / f"{old}.md"
        try:
            old_path.resolve().relative_to(vault)
            in_vault = True
        except ValueError:
            in_vault = False
        if old_path == target or sid in Path(old).name or (in_vault and old_path.exists() and page_session_id(old_path) == sid):
            continue
        keep.append(line)
    keep.append(link)
    keep.sort(key=lambda item: (re.search(r"- (\d{4}-\d{2}-\d{2})", item).group(1) if re.search(r"- (\d{4}-\d{2}-\d{2})", item) else "0000-00-00"), reverse=True)
    other.extend(["\n".join(keep)])
    index.write_text("\n".join(other).rstrip() + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preview or manually export Codex session JSONL to Obsidian Markdown.")
    parser.add_argument("--vault", type=Path, default=Path.cwd(), help="vault root (default: current directory)")
    parser.add_argument("--project", type=Path, help="select sessions whose recorded cwd matches this project")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--source", type=Path, help="session JSONL root")
    source.add_argument("--codex-home", type=Path, help="Codex home directory; reads its sessions/ subfolder")
    parser.add_argument("--output-dir", type=Path, help="destination (default: VAULT/sessions)")
    parser.add_argument("--session", help="select a session UUID")
    parser.add_argument("--list", action="store_true", help="list matching sessions")
    parser.add_argument("--write", action="store_true", help="write Markdown and update index; default is preview")
    args = parser.parse_args(argv)
    vault = args.vault.expanduser().resolve()
    project = (args.project or vault).expanduser().resolve()
    root = (args.source or ((args.codex_home / "sessions") if args.codex_home else default_source_root())).expanduser().resolve()
    output_dir = (args.output_dir or vault / "sessions").expanduser().resolve()
    try:
        output_dir.relative_to(vault)
    except ValueError:
        print("エラー: --output-dir は --vault の配下に指定してください。", file=sys.stderr)
        return 2
    candidates = find_sessions(root, project)
    if args.list:
        for item in candidates:
            print(f"{item.meta.get('timestamp', '日時不明')}  {session_id(item)}  {item.path.name}")
        return 0
    chosen = next((item for item in candidates if session_id(item) == args.session), None) if args.session else (candidates[0] if candidates else None)
    if chosen is None:
        print("対象セッションが見つかりません。--list で候補を確認してください。", file=sys.stderr)
        return 2
    try:
        markdown, date, title = render(chosen)
        sid = session_id(chosen)
        target = output_dir / f"{date}-{safe_filename(title)}-{sid}.md"
        if args.write:
            saved = write_session(markdown, date, title, sid, output_dir, vault)
            print(f"書き込みました: {saved}")
        else:
            print(f"プレビュー（{target}）\n")
            print(markdown)
            print("プレビュー確認後に書き込むには --write を付けてください。")
    except (OSError, RuntimeError) as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
