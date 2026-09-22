---
type: source
status: active
created: 2026-09-22
updated: 2026-09-22
tags: [ollama, local-llm, inference]
---

# Ollama 公式文書 調査メモ

2026-09-22 時点の Ollama 公式文書を、vLLM との比較に必要な範囲で確認したメモ。

## 要点

- Ollama は macOS、Windows、Linux で model の取得・実行・管理を短い CLI 操作と desktop app から行え、local HTTP server も提供する。現在は local model に加え、任意の Ollama Cloud も扱う。
- native API と OpenAI 互換 API、公式 Python/JavaScript library を持つ。OpenAI API は subset であり、完全互換ではない。
- 1 instance 内では、複数 model の同時常駐、同一 model の parallel request、待ち行列、単一 host 内の multi-GPU 配置を管理する。
- 調査した公式製品文書では multi-node replica 群への組み込み request load balancing は確認できない。複数 instance を使う場合は外部 proxy/router を置く構成として区別する。

## 主張と根拠

### 導入と model 管理

- 公式 Quickstart は macOS/Windows/Linux 向け download、ollama pull、ollama run、local server の API 利用を案内する。local model の実行に API key は不要である。([Quickstart](https://docs.ollama.com/quickstart))
- CLI は run、pull、rm、ls、create、ps、stop、serve を提供する。Modelfile で base model、parameter、prompt template、system message などをまとめた custom model を作れる。([CLI Reference](https://docs.ollama.com/cli)、[Modelfile Reference](https://docs.ollama.com/modelfile))
- Safetensors と GGUF の import にも対応する。([Importing a Model](https://docs.ollama.com/import))

### API と推論機能

- local native API は http://localhost:11434/api、OpenAI 互換 API は http://localhost:11434/v1 を使う。([API Introduction](https://docs.ollama.com/api/introduction))
- OpenAI 互換 API は Chat Completions、Completions、Models、Embeddings、Responses などの subset を実装する。Responses の会話 state など非対応機能もある。([OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility))
- streaming、JSON/JSON Schema の structured outputs、vision、embeddings、tool calling、thinking model を扱える。([Capabilities](https://docs.ollama.com/capabilities))

### 同時実行、queue、GPU

公式 FAQ は1 server 内の scheduling を次のように説明する。([FAQ](https://docs.ollama.com/faq))

- memory/VRAM が足りれば複数 model を同時に常駐させられる。
- 同一 model も memory が足りれば parallel request を処理する。OLLAMA_NUM_PARALLEL が model ごとの同時 request 上限を決める。
- 新しい model を載せる memory がない場合は request を queue し、idle model を unload して順番に処理する。OLLAMA_MAX_QUEUE を超えると 503 を返す。
- model が1枚の GPU に収まればその GPU に置き、収まらなければ利用可能な複数 GPU に広げる。これは1つの model の配置・分割であり、replica 間の request load balancing ではない。

### cluster 機能の断定範囲

- 公式 FAQ は Nginx reverse proxy と network 公開を説明するが、複数 Ollama server の状態を見て要求を配る組み込み cluster scheduler は説明していない。([FAQ](https://docs.ollama.com/faq))
- 公式 repository の data-parallel feature request では、Ollama collaborator が GPU ごとに server を分け、LiteLLM、ollama_proxy、Nginx 等を前段に置く案を示している。これは製品内蔵機能ではなく外部 proxy 構成である。([Issue #8947](https://github.com/ollama/ollama/issues/8947))
- 複数 machine に1つの model を分散する要望も、調査時点では open feature request である。([Issue #4643](https://github.com/ollama/ollama/issues/4643))

したがって、安全な表現は「Ollama は単一 instance 内の model scheduling、parallel request、queue、同一 host の multi-GPU 利用を持つ。複数 replica/node への要求分散は外部 proxy/orchestrator の領域」である。将来の全 version で非対応とまでは断定しない。

## 他ページへの影響

- vLLM との比較: [[wiki/analyses/vllm-vs-ollama-lm-studio|vLLM・Ollama・LM Studio の比較]]
- 関連する中心概念: [[wiki/topics/vllm|vLLM]]

## 未解決点

- Ollama と vLLM の性能差は model、quantization、backend、同時 request 数に依存し、公式機能表だけでは決められない。
- 外部 proxy を含む Ollama cluster の設計・耐障害性は、Ollama 単体の仕様ではなく採用する proxy/orchestrator ごとに評価が必要。
- 原典は外部公式文書へのリンクで、raw/ に snapshot はない。恒久保存が必要なら、人間が URL manifest または snapshot を raw/inbox/ へ追加する必要がある。
