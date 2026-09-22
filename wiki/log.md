# LLM Wiki Log

このログは過去エントリを再編集せず、概要説明の直後に新しいエントリを挿入します。取り込み、保存した分析、lint を新しい順に記録します。

## [2026-09-22] ingest | vLLM の機能と Ollama・LM Studio との比較

- 原典: [vLLM 公式文書](https://docs.vllm.ai/en/latest/)、[Ollama 公式文書](https://docs.ollama.com/)、[LM Studio 公式文書](https://lmstudio.ai/docs/)
- 作成・更新: [[wiki/sources/vllm-official-docs|vLLM 公式文書 調査メモ]], [[wiki/sources/ollama-official-docs|Ollama 公式文書 調査メモ]], [[wiki/sources/lm-studio-official-docs|LM Studio 公式文書 調査メモ]], [[wiki/topics/vllm|vLLM]], [[wiki/analyses/vllm-vs-ollama-lm-studio|vLLM・Ollama・LM Studio の比較]], [[wiki/index|索引]]
- 注記: raw/ は変更していない。3製品の同一条件 benchmark は未実施で、cluster 機能の不在は調査した現行公式文書の範囲に限定した。

## [2026-09-22] analysis | Codex マルチエージェント・モデルルーティング・ハーネス設計

- 作成: [[wiki/analyses/codex-multi-agent-model-routing-harness]]
- 注記: 公式資料に基づく調査。同一 subagent tree での provider 混在は未保証のためプロセス分離を推奨し、ローカル環境の性能値は未検証。

## [2026-09-12] setup | 初期化

- 作成: [[wiki/index]], [[wiki/log]]
- 注記: raw と wiki の三層構成、および AGENTS.md の運用規約を初期化。
