# `strata` / `strata-q36` `--greedy`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata-q36`（または Qwen3.6 family に振り分けられた `strata`） |
| オプション | `--greedy` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

Qwen3.6 専用 parser で受理される互換フラグです。この parser では `--tokens` の生成が元から argmax（greedy）で行われるため、指定しても動作を変えません。Qwen3.6 専用 parser の索引上の scope は `qwen36/` です（`engine/src/qwen35/q36_engine.cu:5348-5364`、`docs/cli/README.md:1240-1258`）。

## 使い方

```sh
strata-q36 --model ./qwen36.gguf --tokens 1,2,3 --greedy
```

`--greedy` は値なしで指定します。実際のトークン列生成には `--tokens` が必要です。Qwen3.6 専用 parser の使用例であり、モデルファイルは環境に合わせて指定してください（`engine/src/qwen35/q36_engine.cu:5355-5364`）。

## 値と既定値

値は取りません。既定値というより、`--tokens` モード自体が常に greedy です。parser は引数がちょうど `--greedy` と一致したとき空の処理を行い、値の検証や内部設定の変更をしません。複数回指定しても同じ空処理が繰り返されます（`engine/src/qwen35/q36_engine.cu:5360`）。

## 実行時の動作

`--tokens` 経路は生成前にプロンプトを処理し、各生成ステップで `E.greedy()` が返す argmax token を出力用ベクトルに追加します。argmax は最大 logit を選び、同値なら小さい token ID を選ぶ実装です。そのため `--greedy` の有無で生成結果を切り替える処理はありません（`engine/src/qwen35/q36_engine.cu:919-921`, `4056-4060`, `5595-5612`, `5639-5653`）。

`--serve` でもこのフラグは sampling 設定を変更しません。serve の各 `GEN` 要求は `Sampling` を作成し、要求内の `temperature`、`top_k`、`top_p` などのキーを読み取って、`needs_logits()` に応じて greedy または sampling の経路を選びます（`engine/src/qwen35/q36_engine.cu:5025-5045`, `5177-5189`, `5219-5225`）。

## 適用条件と副作用

Qwen3.6 専用 parser がこの引数を受理します。フラグ自身は状態・環境変数・ファイル・GPU 設定を変更せず、専用出力や警告も発生させません。サンプリングへ切り替える指定としては機能しません（`engine/src/qwen35/q36_engine.cu:5360`, `5639-5653`）。

## 出力とエラー

`--greedy` 固有の出力・失敗経路はありません。parser は完全一致の `--greedy` を受理します。通常の引数解析では未知の引数に usage を stderr へ出して終了コード `2` を返し、`--model` 未指定や生成モード未指定も stderr のエラーと終了コード `2` になります（`engine/src/qwen35/q36_engine.cu:5412-5420`, `5595-5597`）。serve mode では未知の `--...` 引数は警告して読み飛ばす分岐がありますが、`--greedy` 自体は明示的に受理されるためそこには入りません（`engine/src/qwen35/q36_engine.cu:5360`, `5405-5411`）。

## 根拠

- `engine/src/qwen35/q36_engine.cu:5340-5364` — Qwen3.6 parser の初期値、`--greedy` の値なし受理、`--tokens` の登録。
- `engine/src/qwen35/q36_engine.cu:919-921`, `4056-4060` — argmax kernel の仕様と engine の greedy token 取得。
- `engine/src/qwen35/q36_engine.cu:5025-5045`, `5177-5189`, `5219-5225` — serve 要求ごとの sampling 設定と生成分岐。
- `engine/src/qwen35/q36_engine.cu:5412-5420`, `5595-5657` — parser のエラー、`--tokens` の実行と出力。
- `docs/cli/README.md:1240-1258` — Qwen3.6 parser の索引 scope と作成対象リンク。
