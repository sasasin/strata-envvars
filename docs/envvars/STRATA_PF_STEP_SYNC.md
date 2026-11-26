# `STRATA_PF_STEP_SYNC`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

プロンプトを読む CUDA/HIP または SYCL の通常の chunk-major prefill 経路で、指定された GPU 処理の後に compute stream と copy stream の完了を待ちます。GPU 処理を細かい境界で同期し、250 ms 超の step と同期エラーをログに出す診断用スイッチです。同期の追加で処理は遅くなり得ます。コードコメントはデータ量は同じとしていますが、この変数が生成結果の同一性を独立に検証するものではありません。CUDA/HIP 実装は `Prefill::run_impl`、SYCL 実装は同名の prefill 処理にあります（`engine/src/prefill/prefill.cpp:4956-4969`; `engine/sycl/src/prefill/prefill.cpp:3334-3364`）。

## 値と判定

両実装とも `std::getenv` の結果が非 null で、かつ `e[0] == '1'` の場合だけ有効です。文字列全体は parse しません。未設定・空文字・先頭が `1` 以外なら無効、先頭が `1` なら後続文字にかかわらず有効です。空白除去、大文字小文字変換、数値としての妥当性検査、範囲検査はありません（`engine/src/prefill/prefill.cpp:4959`; `engine/sycl/src/prefill/prefill.cpp:3337`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA/HIP の `engine/src` 実装、SYCL の `engine/sycl` 実装 | 無効 | `1`, `10`, `1anything` | 空文字, `0`, `0anything`, `true`, `false`, ` 1` |

CLI 引数による上書きや数値境界はありません。サーバー起動時は `child_env` が親環境を複製した後、run config の `env` を文字列化して子エンジン環境に設定するため、同じ名前を config に書けば親環境の値を置き換えます（`terminal/serve/server.py:4007-4028`）。

## 有効になる条件

- 対象バックエンドの Strata 所有 prefill 実装を使うこと。`engine/src/prefill/prefill.cpp` に CUDA/HIP 側、`engine/sycl/src/prefill/prefill.cpp` に SYCL 側の読み取りがあります。対象箇所は Metal 専用の早期 return より後にある CUDA/HIP `Prefill::run` の chunk-major 経路にあります（`engine/src/prefill/prefill.cpp:9629-9650`, `engine/src/prefill/prefill.cpp:9705-9708`）。
- CUDA/HIP では、`Prefill::run` が `STRATA_PREFILL_LAYER_MAJOR` 等の判定で layer-major 経路を選んだ場合、`run_layer_major` を実行して戻るため、この `run_impl` 内のスイッチは評価されません。layer-major が無効またはその prompt で準備できない場合に `run_impl` へ進みます（`engine/src/prefill/prefill.cpp:9657-9705`）。
- 環境値が有効でも、同期地点はループ内の該当 step に限られます。各 layer の先頭で前 layer の処理を待つ地点は `l > LB` の場合だけです。K/V の RAM staging と K/V append 後の追加待ちは、KV 状態が staged (`st.kv_mode == 1`) のときだけです（`engine/src/prefill/prefill.cpp:4994`, `engine/src/prefill/prefill.cpp:5250-5264`, `engine/src/prefill/prefill.cpp:5303-5308`; SYCL: `engine/sycl/src/prefill/prefill.cpp:3370`, `engine/sycl/src/prefill/prefill.cpp:3580-3594`, `engine/sycl/src/prefill/prefill.cpp:3633-3638`）。
- Strata の `--prefill` 等がどの prompt 経路を選ぶかは別の設定で決まります。この変数自身は経路を選択せず、選ばれた chunk-major 経路内の待ちと診断だけを変えます。

## 実行時の詳細

`step_sync` は `run_impl` 内の関数ローカル `static const bool` です。環境を読むのはその初回初期化時だけで、以後同じプロセスでは環境を変更しても値は更新されません。初回判定が false なら各 step の lambda は直ちに戻ります（`engine/src/prefill/prefill.cpp:4959-4962`; `engine/sycl/src/prefill/prefill.cpp:3337-3342`）。

有効時、各対象地点で `core::progress_at` に step 名と layer を渡してから、CUDA/HIP は `m.cs` と `m.copy` に `cudaStreamSynchronize`、SYCL は対応する `wait()` を順に実行します。通常の layer 境界では前 layer の experts と残りの処理を待ち、staged KV 経路では RAM からの KV staging と KV append もそれぞれ待ちます（`engine/src/prefill/prefill.cpp:4960-4969`, `engine/src/prefill/prefill.cpp:4994`, `engine/src/prefill/prefill.cpp:5263`, `engine/src/prefill/prefill.cpp:5308`; `engine/sycl/src/prefill/prefill.cpp:3338-3364`, `engine/sycl/src/prefill/prefill.cpp:3370`, `engine/sycl/src/prefill/prefill.cpp:3594`, `engine/sycl/src/prefill/prefill.cpp:3638`）。

CUDA/HIP はいずれかの待ちが 250 ms を超えるか同期 API がエラーを返すと、次の形式を stderr に出します: `strata pf-step: chunk from token %lld, layer %lld: %s took %.0f ms (%s / %s)`。250 ms 以下かつ両方成功ならこの行は出しません。同期 API の返り値を prefill の `err` に変換して即時終了する処理はこの lambda にはなく、主に step の特定と所要時間・エラー文字列の記録を行います（`engine/src/prefill/prefill.cpp:4964-4969`）。同期が戻らない stall では lambda 内のログ行まで到達できませんが、step 名は `progress_at` に渡されています（同 `:4962`）。

SYCL は 250 ms 超または wait のエラーコードが非ゼロのとき、同じ `strata pf-step: ...` 形式を stderr に出します。同期中に `sycl::exception` が送出されると `exc.what()` と file/line を stderr に出し、`std::exit(1)` します（`engine/sycl/src/prefill/prefill.cpp:3341-3364`）。

## 根拠

- `engine/src/prefill/prefill.cpp:4956-4969` — CUDA/HIP 側の値判定、同期、閾値ログ。
- `engine/src/prefill/prefill.cpp:4994-4995`, `engine/src/prefill/prefill.cpp:5250-5264`, `engine/src/prefill/prefill.cpp:5303-5308` — 同期を呼ぶ layer / KV staging / KV append の位置と条件。
- `engine/sycl/src/prefill/prefill.cpp:3334-3364`, `engine/sycl/src/prefill/prefill.cpp:3370`, `engine/sycl/src/prefill/prefill.cpp:3580-3594`, `engine/sycl/src/prefill/prefill.cpp:3633-3638` — SYCL 側の同等処理と例外終了。
- `engine/src/prefill/prefill.cpp:9629-9650`, `engine/src/prefill/prefill.cpp:9657-9708` — Metal の早期 return、CUDA/HIP の layer-major 選択と `run_impl` への分岐。
- `terminal/serve/server.py:4007-4028` — サーバーが run config の `env` を子エンジン環境へ反映する処理。
