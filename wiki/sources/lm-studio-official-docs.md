---
type: source
status: active
created: 2026-09-22
updated: 2026-09-22
tags: [lm-studio, local-llm, inference]
---

# LM Studio 公式文書 調査メモ

2026-09-22 時点の LM Studio 公式文書を、vLLM との比較に必要な範囲で確認したメモ。

## 要点

- LM Studio は model の検索・download、chat、文書 RAG、設定、local API server、MCP 接続をまとめた desktop GUI である。lms CLI と GUI 不要の llmster daemon も提供する。
- Mac/Windows/Linux では llama.cpp の GGUF、Apple Silicon では加えて MLX model を実行できる。download 済み model の chat、文書 RAG、local server は offline で動く。
- native REST API、OpenAI/Anthropic 互換 API、Python/TypeScript SDK を提供する。
- llama.cpp engine には continuous batching による parallel requests がある。LM Link は遠隔端末の model を使う機能だが、確認した仕様は preferred device 選択であり、replica の動的 load balancing とは異なる。

## 主張と根拠

### GUI、headless、model 管理

- desktop app は Hugging Face からの model 検索・download、chat、文書 RAG、preset、server、MCP client を一体化する。([LM Studio, llmster, and lms](https://lmstudio.ai/docs/app/basics/lmstudio-vs-llmster-vs-lms))
- llmster は GUI 不要の独立 daemon で、Linux server、cloud VM、GPU rig、CI/CD、常駐 service での利用を想定する。lms CLI は desktop app と llmster の両方を操作する。([Headless Mode](https://lmstudio.ai/docs/developer/core/headless))
- GUI、CLI、REST API、SDK から model の download/load/unload と JIT loading を管理できる。([LM Studio as a Local LLM API Server](https://lmstudio.ai/docs/developer/core/server))

### API と同時実行

- server は localhost または LAN に公開でき、native REST API、OpenAI 互換、Anthropic 互換を提供する。([Local LLM API Server](https://lmstudio.ai/docs/developer/core/server)、[OpenAI Compatibility Endpoints](https://lmstudio.ai/docs/developer/openai-compat))
- Max Concurrent Predictions を設定すると、llama.cpp engine が複数要求を continuous batching で動的に1 batch へまとめる。公式文書では MLX 対応は今後とされる。([Parallel Requests](https://lmstudio.ai/docs/app/advanced/parallel-requests))
- continuous batching は単一 server/model 内の処理効率化であり、複数 server から1台を選ぶ load balancing ではない。

### GPU と複数端末

- 単一 host の multi-GPU controls は、使用 GPU、均等または優先順の割り当て、VRAM 内への weight 制限を制御する。これは model weight の offload/allocation である。([Multi-GPU Controls](https://lmstudio.ai/blog/lmstudio-v0.3.14))
- LM Link は所有する端末を暗号化 network でつなぎ、remote machine の model を GUI、API、SDK から使う。([LM Link](https://lmstudio.ai/docs/lmlink))
- 同じ model が複数 device にある場合、LM Link は client ごとに設定した preferred device を使う。([Set a preferred device](https://lmstudio.ai/docs/lmlink/basics/preferred-device))

確認した公式文書には、複数 LM Studio replica の queue 長や KV cache 状態を見て request を動的配分する機能、health check 付き failover、複数端末にまたがる1推論の model 分割は記載されていない。したがって LM Link を cluster load balancer とみなさない。これは調査範囲に基づく記述であり、将来の非対応を断定するものではない。

## 他ページへの影響

- vLLM との比較: [[wiki/analyses/vllm-vs-ollama-lm-studio|vLLM・Ollama・LM Studio の比較]]
- 関連する中心概念: [[wiki/topics/vllm|vLLM]]

## 未解決点

- 同じ model/backend/hardware 条件での実測比較は行っていない。
- LM Link は新しい機能であり、routing と複数端末利用の仕様は更新時に再確認が必要。
- 原典は外部公式文書へのリンクで、raw/ に snapshot はない。恒久保存が必要なら、人間が URL manifest または snapshot を raw/inbox/ へ追加する必要がある。
