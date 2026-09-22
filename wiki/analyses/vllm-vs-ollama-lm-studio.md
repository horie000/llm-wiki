---
type: analysis
status: active
created: 2026-09-22
updated: 2026-09-22
sources:
  - '[[wiki/sources/vllm-official-docs|vLLM 公式文書 調査メモ]]'
  - '[[wiki/sources/ollama-official-docs|Ollama 公式文書 調査メモ]]'
  - '[[wiki/sources/lm-studio-official-docs|LM Studio 公式文書 調査メモ]]'
tags: [vllm, ollama, lm-studio, comparison, load-balancing]
---

# vLLM・Ollama・LM Studio の比較

## 質問

vLLM は Ollama、LM Studio と何が違い、何ができるのか。特に「負荷分散」は何を意味するのか。

## 結論

3つは重なる機能を持つが、最適化している利用場面が違う。

- **vLLM** — 多数の request を効率よく捌く inference engine/API backend。GPU server、複数 GPU/node、replica 構成を設計したいときに強い。
- **Ollama** — model の取得、実行、custom 化、CLI/app、local API を一体化した runtime。個人 PC や開発環境で開始しやすい。
- **LM Studio** — GUI での model 探索、chat、文書 RAG、設定、local API をまとめ、headless daemon も備える local AI application。

vLLM の「負荷分散」は、主に model を複製した Data Parallel rank へ request を振り分ける機能である。TP/PP の model 分割、continuous batching、MoE の EPLB は、広い意味では仕事を分けるが HTTP request load balancing ではない。

## 比較

| 観点 | vLLM | Ollama | LM Studio |
|---|---|---|---|
| 中心用途 | high-throughput inference / API serving | local model runtime と model 管理 | GUI 中心の local AI 利用と local server |
| 主な操作面 | Python、CLI、HTTP API | desktop app、CLI、native/OpenAI互換 API | GUI、lms CLI、llmster、native/OpenAI/Anthropic互換 API |
| model 入手・管理 | 主に model repository/path を指定して engine が load | pull/run/create/import を一体化 | GUI 検索/download、load/unload、JIT、GGUF import |
| local chat / RAG UX | 別 UI・framework を組み合わせる | app/CLI と統合先を利用 | chat と文書 RAG を GUI に内蔵 |
| 1 server 内の同時要求 | continuous batching と KV cache 管理を serving の中核にする | model ごとの parallel 数と queue を管理 | llama.cpp で continuous batching |
| 1 model の multi-GPU 分割 | TP/PP/CP、multi-node も対象 | 単一 host で、1 GPU に収まらなければ複数 GPU へ配置 | 単一 host の GPU offload/allocation controls |
| replica 間 request LB | DP の internal/hybrid/external topology を公式に定義 | 組み込み multi-node LB は確認できず、外部 proxy 構成 | 組み込み replica LB は確認できず。LM Link は preferred device routing |
| 向く規模 | 単一 GPU から multi-node serving cluster | 個人 PC、開発用 local server、単一 host | 個人利用、GUI、workstation、headless 単一 server |

比較の根拠は [[wiki/sources/vllm-official-docs|vLLM 公式文書 調査メモ]]、[[wiki/sources/ollama-official-docs|Ollama 公式文書 調査メモ]]、[[wiki/sources/lm-studio-official-docs|LM Studio 公式文書 調査メモ]] に分離した。

## 負荷分散の読み分け

### 1. 同時 request を1つの engine でまとめる

continuous batching は、複数 request の token generation を動的 batch にまとめる方式である。vLLM と LM Studio の llama.cpp engine に確認できる。server 台数は増えず、request を replica 間に配る仕組みではない。

Ollama も同一 model の parallel request と FIFO queue を持つが、公式 FAQ の説明は parallel 上限・memory・queue に基づく単一 instance の scheduling である。

### 2. 1つの model を複数 GPU へ分ける

vLLM の TP/PP/CP、Ollama の multi-GPU placement、LM Studio の multi-GPU controls はこの層に属する。1 request の計算や model weights を分けるための scale-up であり、複数 replica から空いた server を選ぶ処理ではない。

### 3. model replica へ request を配る

ここが通常いう serving load balancing である。vLLM は DP rank を対象に internal、hybrid、external の構成を公式に定義する。小さな構成なら単一 endpoint の internal LB、大きな multi-node 構成なら node 間を外部 LB に任せる hybrid、独立 replica 群なら external router が候補になる。

Dense model を独立 replica として外部分散する場合、data-parallel option を使うのではなく、独立した vLLM instance を複数起動して外部 router へ接続する。external DP CLI option は MoE deployment 向けである。

Ollama は複数 instance の前段へ外部 proxy を置く案が公式 repository で示されている。LM Studio の LM Link は remote device を使えるが、同じ model が複数 device にある場合の公式選択規則は preferred device であり、負荷量に応じた動的分散とは確認できない。

### 4. MoE expert の偏りを直す

vLLM の EPLB は、token が集中する hot expert を EP rank 間で再配置する。HTTP request の入口を選ぶ機能ではない。名称に load balancer が入るため、DP request LB と混同しやすい。MoE の DP rank は forward を同期するため完全には独立せず、idle rank の dummy forward が必要になる場合がある。また redundant expert は GPU memory を消費し、KV cache の余地を減らす。

## 選定の目安

- **まず手元で model を試す** — Ollama。model pull、CLI、API を短い手順で使いたい場合。
- **GUI で model を探し、chat/RAG/設定も扱う** — LM Studio。必要なら llmster で headless 化する。
- **同一 model を多数 request へ提供し、GPU 利用率と aggregate throughput を詰める** — vLLM。
- **複数 node、replica、MoE、routing を設計する** — vLLM を engine とし、必要に応じて Kubernetes/Ray Serve/外部 router と組み合わせる。

これは機能と設計目標からの選定目安であり、実測性能の順位ではない。

## 根拠

- vLLM の API、PagedAttention、並列方式、DP load balancing: [[wiki/sources/vllm-official-docs|vLLM 公式文書 調査メモ]]
- Ollama の API、model scheduler、queue、multi-GPU と外部 proxy の断定範囲: [[wiki/sources/ollama-official-docs|Ollama 公式文書 調査メモ]]
- LM Studio の GUI/headless、continuous batching、LM Link: [[wiki/sources/lm-studio-official-docs|LM Studio 公式文書 調査メモ]]

## 限界

- 3製品を同一条件で benchmark していないため、性能を倍率で比較する結論は出していない。
- model compatibility、量子化、API compatibility は version ごとに変わるため、採用時点で再確認する。
- Ollama/LM Studio の cluster 機能に関する記述は、調査した現行公式文書で確認できた範囲を示す。将来も存在しないという主張ではない。

## 関連リンク

- [[wiki/topics/vllm|vLLM]]
