---
type: source
status: active
created: 2026-09-22
updated: 2026-09-22
tags: [vllm, llm-serving, distributed-inference]
---

# vLLM 公式文書 調査メモ

2026-09-22 時点の vLLM 公式文書と原論文を確認したメモ。latest 文書は更新されるため、機能名やオプションは導入時に再確認する。

## 要点

- vLLM は、ローカルチャット用の統合アプリというより、LLM を高スループットで推論・配信するためのエンジンである。Python からのオフライン推論と、HTTP によるオンライン配信の両方を扱う。
- PagedAttention、continuous batching、chunked prefill、prefix caching などにより、特に複数要求を処理するときの GPU メモリ利用とスループットを重視する。
- 生成だけでなく、embedding、分類、score/rerank、マルチモーダル入力、構造化出力、tool calling、LoRA、量子化、speculative decoding などを扱える。対応可否はモデルとバックエンドに依存する。
- 分散機能には、1つのモデルを分割する TP/PP、モデルを複製する DP、MoE 向けの EP がある。「負荷分散」は主に DP rank への要求振り分けを指し、モデル分割とは別である。

## 主張と根拠

### 推論と API 配信

- 公式 Quickstart は、LLM class による offline batched inference と vllm serve による online serving を主要な入口としている。標準 Quickstart の前提 OS は Linux であり、Apple Silicon は vLLM-Metal という別バックエンドを案内している。([Quickstart](https://docs.vllm.ai/en/latest/getting_started/quickstart/))
- オフライン API は text generation/chat に加え、classify、embed、score、各種 pooling を提供する。([Offline Inference](https://docs.vllm.ai/en/latest/serving/offline_inference/))
- OpenAI 互換サーバーは Completions、Chat Completions、Responses、Embeddings、音声 transcription/translation などを実装する。ただし完全互換ではなく、非対応または無視されるパラメータもある。([OpenAI-Compatible Server](https://docs.vllm.ai/en/latest/serving/online_serving/openai_compatible_server/))

### PagedAttention と continuous batching

- LLM serving では、各要求の過去 token に対応する KV cache が大きく、長さも動的に変わる。PagedAttention は KV cache を固定長 block に分け、論理 block と物理 block を分離して必要時に割り当てる。これにより断片化と過剰予約を抑え、同時処理へ使えるメモリを増やす。([PagedAttention 原論文](https://arxiv.org/abs/2309.06180))
- continuous batching は、固定 batch 全体の終了を待たず、推論 iteration ごとに完了要求を外して新規要求を入れるスケジューリングである。これは1エンジン内の batch 編成であり、複数 server への HTTP request load balancing ではない。([原論文 §2.3](https://arxiv.org/html/2309.06180v1#S2.SS3))
- 原論文の性能値は当時の比較対象・hardware・workload に対する結果であり、現在の Ollama や LM Studio との優劣を直接示す benchmark ではない。

### 並列化と負荷分散

- **Tensor Parallel (TP)** は1つの model の tensor 計算を複数 GPU に分ける。単一 GPU には収まらないが、単一 node に収まる場合の基本選択肢である。
- **Pipeline Parallel (PP)** は model の layer を stage に分ける。複数 node にまたがる大きな model や、GPU 数が model の attention head 数で割り切れない構成などで使う。
- **Data Parallel (DP)** は model weights を rank ごとに複製し、独立した request batch を処理する。同一 model の同時処理量を増やすとき、HTTP request の振り分け対象になる。
- **Expert Parallel (EP)** は MoE model の expert を GPU 間に分ける。Expert Parallel Load Balancer (EPLB) は token が集中する expert を再配置する機能であり、HTTP request の load balancer ではない。

TP/PP の選び方と multi-node 実行は [Parallelism and Scaling](https://docs.vllm.ai/en/latest/serving/parallelism_scaling/)、DP/EP の詳細は [Data Parallel Deployment](https://docs.vllm.ai/en/latest/serving/data_parallel_deployment/) と [Expert Parallel Deployment](https://docs.vllm.ai/en/latest/serving/expert_parallel_deployment/) に基づく。

DP の online serving には次の3形態がある。

1. **Internal load balancing** — 単一 endpoint の API server が各 DP engine の running/waiting queue を見て rank を選ぶ。大きな DP 構成では head node の API server が bottleneck になり得る。
2. **Hybrid load balancing** — node ごとに API endpoint と local DP rank を持ち、node 間は ingress 等の外部 load balancer、node 内は vLLM が振り分ける。
3. **External load balancing** — rank または独立 vLLM instance ごとに endpoint を持たせ、外部 router が telemetry を使って振り分ける。大規模 replica 群では orchestration、autoscaling、health check も外部基盤の担当になる。

Dense model の external 構成では data-parallel 系の CLI option を付けず、独立した vLLM instance を複数起動して外部 router へ接続する。external DP CLI option は MoE deployment 向けである。([Data Parallel Deployment](https://docs.vllm.ai/en/latest/serving/data_parallel_deployment/))

各 DP engine の KV cache は独立している。したがって prefix cache を活かすには同じ prefix を同じ replica へ寄せる routing が有利だが、公式文書では internal LB の KV-cache-aware routing は今後の改善余地としている。([Data Parallel Deployment](https://docs.vllm.ai/en/latest/serving/data_parallel_deployment/))

### 運用上の注意

- TP/PP/EP は主として1回の model 計算を分割する仕組みであり、replica 間の request load balancing とは目的が違う。
- multi-node TP は通信量が多い。node 間 network、GPU 間接続、全 node の model path と実行環境を揃える運用が必要になる。
- MoE で DP と EP/TP を組み合わせる場合、DP rank は完全には独立せず forward の同期が要る。request のない rank に dummy forward が必要になる場合もある。
- EPLB で redundant expert を増やすと hot expert を複製できる一方、追加の GPU memory を使って KV cache の余地を減らす。
- vLLM の API key 設定は同じ HTTP server 上のすべての endpoint を保護しない。外部公開時は reverse proxy や network policy を含む防御が必要である。([OpenAI-Compatible Server](https://docs.vllm.ai/en/latest/serving/online_serving/openai_compatible_server/))
- vLLM は inference engine/API server であり、利用者向け chat GUI、model catalog の探索、RAG application 全体、cluster autoscaling を一式で提供する製品ではない。必要に応じて別の UI、retrieval framework、router/orchestrator と組み合わせる。

## 他ページへの影響

- 統合説明: [[wiki/topics/vllm|vLLM]]
- 比較と選定: [[wiki/analyses/vllm-vs-ollama-lm-studio|vLLM・Ollama・LM Studio の比較]]

## 未解決点

- 同一 model・量子化・hardware・request 分布を揃えた3製品の実測比較は行っていない。用途ごとの latency、throughput、VRAM は benchmark が必要。
- latest 文書の機能は変化する。特に model/backend ごとの tool calling、multimodal、量子化、分散方式の対応表は導入時に確認する必要がある。
- 原典は外部公式文書へのリンクで、raw/ に snapshot はない。恒久保存が必要なら、人間が URL manifest または snapshot を raw/inbox/ へ追加する必要がある。
