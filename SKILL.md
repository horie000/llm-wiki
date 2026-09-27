---
name: llm-wiki
description: Maintain this Obsidian LLM wiki by ingesting raw sources, answering from the compiled wiki, and running health checks. Use for requests involving ingest, wiki updates, queries, indexing, or linting in this vault.
metadata:
  short-description: Operate the local LLM wiki
---

# LLM Wiki Skill

このファイルは、この vault で定常作業を実行するための手順です。構造上の規約・所有権・ページ形式は [AGENTS.md](AGENTS.md) を正とし、作業前に必ず読む。`AGENTS.md` とこのファイルが衝突する場合は `AGENTS.md` に従う。

## 共通の開始手順

1. vault のルートを確認し、`AGENTS.md`、`wiki/index.md`、`wiki/log.md` を読む。
2. 依頼のモードを `ingest`、`query`、`lint`、または `maintain` として判断する。指定が曖昧なら、最も小さい安全な操作を選ぶ。
3. 既存ページを検索して重複・関連ページ・リンク先を確認する。
4. `raw/` は原典の所有者が人間であるため、読み取り専用として扱う。変更、移動、改名、削除をしない。
5. 書き込み後は、変更したページが索引・相互リンク・ログに反映されているか確認する。

### Session history access (explicit opt-in only)

- `sessions/` と Codex の外部履歴（`%USERPROFILE%\.codex\sessions`、`CODEX_HOME/sessions`、`archived_sessions`、`history.jsonl`）は、ユーザーが特定のセッション履歴を参照・書き出すよう明示した場合だけ検索・閲覧・読み込む。
- 通常の ingest/query/lint/maintain、vault の全文検索、索引・ログ更新にはセッション履歴を含めない。セッションの書き出しツールはスケジュールや他の自動処理から起動せず、明示依頼に応じて手動で実行する。
- この規則は運用上の制限であり、OS レベルのアクセス制御ではない。`sessions/` は Obsidian で通常どおり閲覧できる。

## Ingest: 原典を wiki に統合する

対象は依頼で指定されたファイル、または `raw/inbox/` の未処理ファイル。画像や添付は本文と別に必要な範囲だけ確認する。

1. 原典を最後まで読み、タイトル、日付、著者、主張、根拠、限界、未解決点を抽出する。
2. `wiki/index.md` と関連する `wiki/sources/`、`wiki/topics/`、`wiki/entities/` を読み、既存の要約・矛盾・更新候補を把握する。
3. 対象原典に対応する `wiki/sources/<slug>.md` を作成または更新する。原典を要約し、原典へのリンクを `sources` と本文に残す。
4. 原典が変更した概念や固有名詞について、既存の topic/entity ページを更新する。重要概念に専用ページがなければ作成を提案し、作成する場合は source ページからリンクする。
5. 内容が過去の主張を置き換える場合、旧内容を黙って消さず、`status: superseded` と後継ページへのリンクで履歴を残す。相反する根拠は両方を示す。
6. `wiki/index.md` の該当カテゴリへ、各変更ページの wikilink と一行要約を追加または修正する。件数などのコピーされた可変値は書かない。
7. `wiki/log.md` の概要説明の直後（既存の最新エントリより前）に `## [YYYY-MM-DD] ingest | タイトル` のエントリを挿入する。日付は実行時の現在日付を使い、過去エントリを編集しない。
8. 完了時に、読んだ原典、作成・更新したページ、未解決の矛盾・判断を短く報告する。

ユーザーが `preview`、`提案のみ`、`確認してから` と指定した場合は、手順 1–2 まで行い、予定する変更を提示して停止する。明示的な取り込み依頼では、対象が明確な限り手順 3 以降まで実行してよい。

## Query: wiki から回答する

1. まず `wiki/index.md` から関連ページを絞り込む。
2. 必要な source/topic/entity/analysis ページを読み、ページ内 wikilink をたどって根拠を確認する。
3. 回答では、確定した記述、推論、不確実性、相反する記述を区別する。主張の直後に `[[wiki/...]]` で根拠を示す。
4. wiki に根拠がない場合は、知識を補って断定せず「未収録」と明示する。外部検索が必要なら、ユーザーに確認するか、依頼された検索だけを行う。
5. 比較や分析に再利用価値がある場合、依頼または了承があれば `wiki/analyses/` に保存し、index と log も更新する。

## Lint: wiki の健全性を点検する

次の観点を確認し、各問題にファイルと具体的な修正案を付ける。

- ページ間の矛盾、古い主張、根拠のない断定
- 壊れた wikilink、索引から漏れたページ、孤立ページ
- raw にある未処理原典と対応する source ページの欠落
- 重要概念・固有名詞の言及はあるが専用ページがない状態
- frontmatter の型・status・日付・source リンクの不整合
- `wiki/index.md` と実ファイルの不一致、`wiki/log.md` の先頭への記録漏れ

lint では、問題を勝手に大量修正する前に一覧を示す。単純なリンク切れ・索引漏れなど、依頼の範囲で安全に直せるものだけ修正し、矛盾の解消や内容の再解釈はユーザー判断を求める。実行結果を `wiki/log.md` に `lint` として記録する場合は、検査範囲と未解決件数を残す。

## Maintain: 索引・リンク・形式を整える

- 新規・更新ページは `wiki/index.md` の適切なカテゴリに登録する。
- 既存の canonical page を優先し、同義語のページを増やさずにリンクを追加する。
- frontmatter の `updated` は実際に内容を変更した日だけ更新する。
- 可変の件数、SHA、最終実行時刻などを本文に固定値として埋め込まない。
- 操作後に `git diff` または差分相当を確認し、意図しない raw の変更がないことを確認する。

## 完了条件

作業は、(1) requested pages の内容が更新され、(2) wikilink と index が整い、(3) log が必要なら最新エントリとして先頭に挿入され、(4) raw が変更されていないことを確認して完了とする。確認できない項目は未完了として報告する。
