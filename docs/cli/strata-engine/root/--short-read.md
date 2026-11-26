# `--short-read`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ engine のトップレベル。`--serve` で server 入力を処理） |
| オプション | `--short-read N` |
| 別名 | なし |
| 値 | 整数。parser は `atoll` で変換して 0 未満を 0 に丸める |

## 役割

`--serve` の各リクエストで、短いテキスト区間を通常の batched prompt path ではなく decode verify windows で読む上限を指定します。区間ごとに判定されるため、長い prompt 全体が batched path に回っても、短い末尾メッセージや assistant header は window path になる場合があります。`--short-read 0` はこの振り分けを無効にし、batched path を選びます（`engine/src/program/generate.cpp:1139-1143,20223-20229,20238-20243`）。

## 使い方

```sh
strata --pack /path/to/model.pack --serve --short-read 24
```

`--serve` を使う engine 起動時に指定します。`--serve` 以外の生成経路に対する用途は parser help でも `--serve` 専用として説明されています（`engine/src/program/generate.cpp:1338-1340`）。

## 値と既定値

- 値は必須です。parser は `std::atoll` の結果を `std::max(0LL, ...)` で下限 0 に丸めます。明示した場合は `short_read_set` も true にし、環境・モデルに応じた class default を適用しないようにします（`engine/src/program/generate.cpp:1142-1143,4117`）。
- CUDA/HIP の主要 engine 経路では、未指定時の基底値は 64 です。expert layout が native で形式情報を持つ場合に限り、測定クラス、全層 fused-only か、staged fused entry の有効状態、folded trellis の有無、CUDA sm_120 条件などから既定値を選びます。通常は 64、該当する Windows gfx1151 の条件では 24、CUDA sm_120 の条件では 16 となり得ます。CLI で値を明示するとこの問い合わせ自体を行いません（`engine/src/program/generate.cpp:13831-13833`、`engine/src/prefill/prefill.cpp:3563-3579`、`engine/include/strata/prefill/staged_fo_rule.hpp:32-52`）。
- SYCL の parser は同じく 0 未満を 0 に丸めますが、`short_read_set` による適応既定値の切替はなく、構造体既定値 64 を使います（`engine/sycl/src/program/generate.cpp:759,2095`）。
- parser に数値形式の検査や上限値検査はありません。`atoll` が整数として読めない値をどう扱うかは C ライブラリ変換に委ねられています。値の範囲や重複指定時の専用エラーは定義されていません（`engine/src/program/generate.cpp:4117`）。

## 実行時の動作

通常の serve 経路では、リクエスト内の各候補区間について、区間長が `req_short_read` 以下であることを確認します。0 のときは長さが正の区間が条件を通らず、window path は使われません。`STRATA_CKPT_REREAD` が設定されていると長さに関わらず batched path を選びます。候補に埋め込み行（画像など）が含まれる区間も window path から除外されます（`engine/src/program/generate.cpp:20230-20243,21551-21571`）。

window path を選んだ後は、verify window の容量 `S` ごとに区間を分けて prompt token を処理します。`--short-read` が定めるのは window 1回あたりの token 数ではなく、batched path と window path のどちらへ渡すかの区間長上限です（`engine/src/program/generate.cpp:20414-20431`）。CUDA/HIP の serve では、非有限 logits が prompt window で検出された後の再試行に限り、次のリクエスト1件を batched path のみにし、stderr に理由を出します（`engine/src/program/generate.cpp:13826-13833,19243-19251,20231-20243`）。

## 適用条件と副作用

- 文書化された適用範囲は `--serve` です。CUDA/HIP と SYCL で既定値決定の実装が異なるため、24/16 への自動変更は全 backend 共通ではありません（`engine/src/program/generate.cpp:1338-1340,13831-13833`、`engine/sycl/src/program/generate.cpp:759,2095`）。
- `--prefill-head-alias` を使う場合、同オプションの条件検査は `--short-read 0` を要求します。既定の正値のまま併用すると「it needs --short-read 0」を stderr に表示して終了コード 2 になります（`engine/src/program/generate.cpp:8443-8455`）。
- この値で選択される read path は GPU/CPU prefill 処理に関わりますが、このオプション自体がファイルを書き換えたり、別プロセスを起動したりする処理は確認できません。特定値による性能優位は機器・モデル条件に依存し、ここでは推奨値として断定しません。

## 出力とエラー

通常、`--short-read` 自身の値検査に由来する警告や専用エラー出力はありません。serve の prompt window で非有限 logits が発生した後、次のリクエストでは一時的に window read を止める旨が stderr に出ます（`engine/src/program/generate.cpp:20231-20237`）。`--prefill-head-alias` と不整合な正値の場合のエラー・終了コードは前節のとおりです。

## 根拠

- `engine/src/program/generate.cpp:1139-1143,1338-1340,4117` — 値の保持、help の説明、CUDA/HIP parser。
- `engine/src/program/generate.cpp:13831-13833` — 指定有無を見た適応既定値の適用。
- `engine/src/prefill/prefill.cpp:3563-3579`、`engine/include/strata/prefill/staged_fo_rule.hpp:32-52` — native layout、GPU 条件による既定値の決定。
- `engine/src/program/generate.cpp:20223-20243,20414-20431,21551-21571` — request ごとの path 判定と verify window 処理。
- `engine/src/program/generate.cpp:19243-19251,20231-20237,8443-8455` — 非有限 logits 後の一時無効化、および `--prefill-head-alias` との条件。
- `engine/sycl/src/program/generate.cpp:759,915-916,2095` — SYCL 側の値既定、help、parser。
