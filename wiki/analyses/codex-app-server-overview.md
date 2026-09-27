---
type: analysis
status: active
created: 2026-09-27
updated: 2026-09-27
tags:
  - codex
  - app-server
  - integration
---

# Codex app-server の概要と使いどころ

## 質問

Codex app-server は何を提供し、どのような場合に使うべきか。調査時点は 2026-09-27。

## 結論

Codex app-server は、Codex のエージェント機能を製品に組み込むための、ローカルで動く常駐プロセスとクライアント向けプロトコルである。会話履歴、承認、作業中のイベントを自前の UI で扱いたい場合に向く。Codex の VS Code 拡張も、このインターフェースを使うクライアントの例として公式文書に挙げられている。[Codex App Server](https://learn.chatgpt.com/docs/app-server)

単発のスクリプトや CI には `codex exec`、アプリケーションコードから一般的なタスク実行を制御する場合には Codex SDK、会話・イベント・承認を製品体験として細かく制御する場合には app-server、という使い分けが公式資料に示されている。[Codex as a platform](https://developers.openai.com/blog/codex-as-a-platform)

## 根拠と仕組み

1. `codex app-server` を起動する。標準の通信方法は stdio 上の改行区切り JSON（JSONL）。プロトコルは JSON-RPC 2.0 を基にするが、通信上のメッセージでは `jsonrpc` ヘッダーを省く。[Protocol](https://learn.chatgpt.com/docs/app-server#protocol)
2. クライアントは `initialize` を送り、続けて `initialized` 通知を送る。その後 `thread/start` で会話を作り、`turn/start` で依頼を送る。[Getting started](https://learn.chatgpt.com/docs/app-server#getting-started)
3. `item/*` や `turn/*` の通知から進捗を受け取る。`turn/steer` で進行中の作業に指示を追加し、`turn/interrupt` で中断できる。コマンド実行やファイル変更の承認が必要な場合、サーバーからの要求にクライアントが応答する。[Lifecycle overview](https://learn.chatgpt.com/docs/app-server#lifecycle-overview)、[Approvals](https://learn.chatgpt.com/docs/app-server#approvals)

`thread` は会話、`turn` は一回の依頼とそれに続く作業、`item` はメッセージ・コマンド実行・ファイル変更などの入出力単位である。[Core primitives](https://learn.chatgpt.com/docs/app-server#core-primitives)

## 導入上の注意

- WebSocket 通信は公式文書で実験的・本番運用非対応とされている。外部から接続させる場合には認証と TLS が必要で、認証なしの非 loopback リスナーを公開しない。[Protocol](https://learn.chatgpt.com/docs/app-server#protocol)
- TypeScript または JSON Schema は CLI から生成でき、生成物は実行した Codex のバージョンに対応する。クライアント実装では Codex の版とスキーマを対応させる。[Message schema](https://learn.chatgpt.com/docs/app-server#message-schema)
- `turn/steer` ではモデルや作業ディレクトリなどの turn 単位の設定を変更できない。モデル切り替えを設計する場合は turn の境界で扱う。これは公式仕様からの設計上の推論であり、[[wiki/analyses/codex-multi-agent-model-routing-harness|モデルルーティングの分析]]にも関連する。[Steer an active turn](https://learn.chatgpt.com/docs/app-server#steer-an-active-turn)

## 限界

このページは公式文書に基づく概観であり、実機での接続・認証・負荷試験は行っていない。通信方法や API の実験的な部分は、導入時に利用する Codex バージョンの文書と生成スキーマで再確認する。

## 関連リンク

- [[wiki/analyses/codex-multi-agent-model-routing-harness|Codex マルチエージェントとモデル切り替えのハーネス設計]]
- [[wiki/index|LLM Wiki Index]]
