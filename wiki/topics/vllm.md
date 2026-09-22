---
type: topic
status: active
created: 2026-09-22
updated: 2026-09-22
sources:
  - '[[wiki/sources/vllm-official-docs|vLLM 公式文書 調査メモ]]'
  - '[[wiki/sources/ollama-official-docs|Ollama 公式文書 調査メモ]]'
  - '[[wiki/sources/lm-studio-official-docs|LM Studio 公式文書 調査メモ]]'
tags: [vllm, llm-serving, distributed-inference]
---

# vLLM

## 統合した見解

vLLM は、LLM を「手元で簡単に chat する」ための desktop application ではなく、GPU を中心とする accelerator や CPU 上で多数の推論要求を効率よく処理し、application へ API として提供するための inference engine である。主戦場は high-throughput serving、offline batch inference、multi-GPU/multi-node 配信である。根拠は [[wiki/sources/vllm-official-docs|vLLM 公式文書 調査メモ]] を参照。

Ollama や LM Studio も API server と同時実行機能を持つため、単純な「server 対 app」の二分ではない。違いは、vLLM が request batching、KV cache 管理、複数の分散 parallelism、replica への load balancing を中心機能として深く扱うのに対し、Ollama と LM Studio は model の取得・管理や local UX まで含む一体型の入口を重視する点にある。詳細は [[wiki/analyses/vllm-vs-ollama-lm-studio|vLLM・Ollama・LM Studio の比較]] を参照。

## できること

- **online serving** — OpenAI 互換 HTTP server として text generation/chat、Responses、embedding、対応 model の音声処理などを配信する。
- **offline inference** — Python の LLM class から batch generation、chat、embedding、classification、score/rerank を実行する。
- **生成制御** — streaming、structured outputs、tool calling、reasoning parser、各種 sampling を使う。
- **model 実行の最適化** — PagedAttention、continuous batching、chunked prefill、prefix caching、quantization、speculative decoding、LoRA などを使う。
- **scale up / scale out** — tensor、pipeline、data、expert、context parallelism を構成し、単一 GPU から複数 node まで展開する。
- **運用観測** — metrics、logging、tracing を外部監視基盤と組み合わせる。

実際の対応範囲は model、hardware、attention backend、quantization の組み合わせに依存する。「vLLM が機能名を持つ」ことと「任意の model で同じように使える」ことは分けて確認する。

## 高スループット化の中心

1. **PagedAttention** が、要求ごとに長さの違う KV cache を block 単位で割り当て、断片化や未使用予約を抑える。
2. **continuous batching** が、生成を終えた sequence を iteration ごとに外し、待っている request を batch へ追加する。
3. 空いた GPU memory と計算 slot を、単発 request の最短 latency だけでなく、複数 request 全体の throughput に使う。

この設計目標から、vLLM は同時 request が継続的に到着する API backend と相性がよい。ただし低並行度や小型量子化 model も含めて常に最速という意味ではなく、採用時には対象 workload で測定する。

## 「負荷分散」の整理

| レベル | 何を分けるか | vLLM での代表機能 | HTTP request load balancing か |
|---|---|---|---|
| batch scheduling | 1 engine 内の複数 sequence | continuous batching | いいえ |
| model parallel | 1 replica の tensor/layer/context | TP / PP / CP | いいえ |
| replica parallel | 複製した model への request | DP + internal/hybrid/external LB | はい |
| MoE internal | token が向かう expert | EP / EPLB | いいえ |

### DP の3構成

- **Internal LB** — client からは単一 endpoint。vLLM の API server が各 DP engine の実行中/待機 queue を基に振り分ける。小～中規模で構成が簡単だが、head node の API process が bottleneck になり得る。
- **Hybrid LB** — node ごとに endpoint と local rank を置く。外部 LB が node を選び、node 内は vLLM が選ぶ。大きな multi-node 構成で単一 head への集中を避ける。
- **External LB** — replica/rank ごとに endpoint を持たせ、外部 router、Kubernetes ingress、serving platform 等が振り分ける。autoscaling、health check、failover、より高度な routing はこの層で扱う。

Dense model の external 構成は、data-parallel option ではなく独立した vLLM instance 群を外部 router へ接続する。external DP CLI option は MoE deployment 向けである。MoE で DP と EP/TP を組み合わせる場合は rank 間の forward 同期が必要で、idle rank の dummy forward や EPLB の redundant expert による追加 memory 消費も考慮する。

DP engine ごとに KV cache は独立する。同じ prefix を持つ要求を同じ replica へ寄せると cache reuse の余地があるため、大規模構成では単純 round-robin だけでなく cache affinity や queue telemetry が設計点になる。

## 選び方

- 個人 PC で model を download してすぐ対話したい、Windows/macOS の GUI が欲しいなら、まず Ollama または LM Studio が自然である。
- application 開発用に local API が1つ欲しいだけなら、3製品とも候補になる。API の対応範囲と対象 model を確認する。
- 多数利用者、複数 GPU、同一 model の高い aggregate throughput、replica 構成を重視するなら vLLM が有力である。
- vLLM は chat UI、RAG pipeline、認証境界、autoscaler の完成品ではない。それらは別 component と組み合わせて system を作る。

## 根拠となる source ページ

- [[wiki/sources/vllm-official-docs|vLLM 公式文書 調査メモ]]
- [[wiki/sources/ollama-official-docs|Ollama 公式文書 調査メモ]]
- [[wiki/sources/lm-studio-official-docs|LM Studio 公式文書 調査メモ]]

## 未解決点

- 想定 workload に対する実測 benchmark は未実施。
- 必要な同時 request 数、対象 model、GPU/node 構成が未指定のため、具体的な topology と製品選定までは確定していない。
