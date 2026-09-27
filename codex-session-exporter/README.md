# Codex Session Exporter

A small, portable Python tool that turns explicitly selected Codex session JSONL files into Obsidian Markdown notes. It uses only the Python standard library at runtime and does not run automatically.

## Requirements and installation

Python 3.10 or newer. Windows, macOS, and Linux are supported.
The package is licensed under MIT; see `LICENSE`.

From this directory, install the command:

```sh
python -m pip install .
```

For development, use `python -m pip install -e .`. The package has no runtime dependencies.

## Use

The default project is the vault directory. The default source is `$CODEX_HOME/sessions`, or `~/.codex/sessions` when `CODEX_HOME` is unset. `--project` selects sessions whose recorded working directory matches that project. `--vault` selects where Markdown notes are written.

Windows PowerShell:

```powershell
codex-session-exporter --vault "$HOME\Documents\Notes" --project "D:\work\app" --list
codex-session-exporter --vault "$HOME\Documents\Notes" --project "D:\work\app" --codex-home "$HOME\.codex" --session UUID
codex-session-exporter --vault "$HOME\Documents\Notes" --project "D:\work\app" --codex-home "$HOME\.codex" --session UUID --write
```

macOS:

```sh
codex-session-exporter --vault "$HOME/Notes" --project "$HOME/work/app" --list
codex-session-exporter --vault "$HOME/Notes" --project "$HOME/work/app" --source "$HOME/.codex/sessions" --session UUID
codex-session-exporter --vault "$HOME/Notes" --project "$HOME/work/app" --source "$HOME/.codex/sessions" --session UUID --write
```

Linux:

```sh
codex-session-exporter --vault "$HOME/notes" --project "$HOME/src/app" --list
codex-session-exporter --vault "$HOME/notes" --project "$HOME/src/app" --codex-home "$HOME/.codex" --session UUID
codex-session-exporter --vault "$HOME/notes" --project "$HOME/src/app" --codex-home "$HOME/.codex" --session UUID --write
```

Without `--write`, the command prints a preview. `--list` shows matching session IDs and dates. A manual `--write` creates or updates `VAULT/sessions/<date>-<title>-<session-id>.md` and `sessions/index.md`. Existing notes are matched by session ID; changed titles rename the note and replace its old index entry. The index uses Obsidian links such as `[[sessions/2026-01-01-Title-UUID|Title]]`. `--source PATH` selects a JSONL root directly; alternatively, `--codex-home PATH` selects its `sessions/` subfolder. These options are mutually exclusive. `--output-dir PATH` overrides the default destination.

## Privacy and manual use

Run the exporter only after an explicit request to access or export session history. It reads from the configured source root and filters sessions by the selected project `cwd`. It redacts common token/password patterns, removes injected `AGENTS.md instructions` and `environment_context` blocks from user prompts, records only limited command/path fields, and does not copy tool output bodies. Tool results show an exit code when the JSONL provides one; otherwise their outcome is marked unclassified. Redaction is heuristic and cannot detect every sensitive value, so inspect the preview and note before sharing. The tool makes no network requests.

Generated notes can contain private conversation text. The included `.gitignore` excludes `sessions/`, build output, virtual environments, and Python caches. The exporter creates no scheduled task or background process; every read, preview, and write begins with a manual command.

## Existing vault migration

Copy this `codex-session-exporter/` directory into a repository or install it independently. For an existing vault, `python scripts/session_export.py` remains a compatibility wrapper while this directory stays beside `scripts/`; alternatively run the installed `codex-session-exporter` command. Set `--vault`, `--project`, and `--source` or `--codex-home` explicitly when the vault/project/source differ. Installing the package does not read or migrate existing notes. A later explicitly requested write updates the matching ID and index entry.

## Tests

Run synthetic-data tests from this directory:

```sh
python -m unittest discover -s tests -v
```

Tests create temporary project directories, JSONL source roots, and vaults. They do not read actual Codex history.
