# `STRATA_PF_STEP_SYNC`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

バッチ型 prompt 処理中に GPU の compute stream と copy stream を特定の区間ごとに同期し、遅い区間や停止した区間をログ上で絞り込む診断用フックです。CUDA/HIP 共通ソースと SYCL ソースにそれぞれ実装があります。通常の処理に同期点を加えるため、prompt 処理は遅くなります。ソースコメントでは処理する byte 数は同じとされています。

## 値と判定

| 環境変数の状態 | 動作 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（設定値の先頭文字が `\0`） |
| 先頭文字が `1` | 有効。`1`, `10`, `1anything` などを含む |
| それ以外 | 無効。`true`, `0`, `2`, 空白で始まる値など |

数値変換や文字列全体の比較は行いません。大文字小文字や後続文字も判定しません。各実装の関数内 `static const bool` に結果が保存され、初回にこの判定行へ到達した後は同じプロセス内で環境を変更しても再評価されません。判定行に到達するのは後述のバッチ型 prompt 経路です。

## 有効になる条件

`Prefill::run` のチャンク処理がバッチ型に選ばれる必要があります。CUDA/HIP ソースでは、layer split からの `hand_in_` がなく、device token buffer があり、native embedding または対応形式の token embedding を使い、チャンクに画像などの embedding row がなく、各 token id が有効な場合にバッチ型になります。条件を満たさないチャンクは per-token 経路へ切り替わります。この場合、この変数による追加同期・診断は通りません。

変数が有効でも、レイヤー間の診断同期は最初の layer では行われず、前の layer があるときだけ行われます。K/V の追加診断同期は K/V streaming の `staged` が有効なときだけです。したがって、変数を設定しただけで全 GPU 処理を同期するものではありません。

## 実行時の詳細

バッチ型チャンクの処理中、対象ステップの開始前に `core::progress_at` で進捗位置を更新し、その後 compute stream と copy stream の完了を待ちます。同期対象は次のとおりです。

- layer の先頭（最初の layer を除く）: 前 layer の expert 処理と残りの処理。
- K/V streaming が staged の場合: RAM からの K/V staging 後、および K/V append 後。

CUDA/HIP 経路は同期にかかった時間が 250 ms を超えた場合、またはいずれかの同期 API がエラーを返した場合に、stderr へ `strata pf-step: chunk from token ..., layer ...: ... took ... ms (... / ...)` を出します。API エラー時もこの箇所では戻り値をエラーにせず、ログ後に処理を続けます。SYCL 経路も 250 ms 超またはエラー状態で同じ `strata pf-step:` 形式を出しますが、wait 中に `sycl::exception` が発生すると例外内容とソース位置を stderr に出して `exit(1)` します。

`docs/TROUBLESHOOTING.md` は Windows AMD の prompt 中の GPU hang を調べる手順として、サーバー設定 JSON の `env` に `"STRATA_PF_STEP_SYNC": "1"` を加え再起動する方法を案内しています。そこで説明される「250 ms を超えた step のログ」と速度低下は実装と一致します。

## 根拠

- `src/prefill/prefill.cpp:2156-2170` — CUDA/HIP 経路でのバッチ型判定。
- `src/prefill/prefill.cpp:2484-2502` — 環境変数の判定、キャッシュ、CUDA/HIP の同期・ログ、layer 間呼び出し。
- `src/prefill/prefill.cpp:2673-2689,2727-2732` — staged K/V の前後で行う診断同期。
- `sycl/src/prefill/prefill.cpp:2708-2747,2930-2946,2985-2990` — SYCL の判定、同期・例外処理、呼び出し箇所。
- `CMakeLists.txt:585-592` — CUDA/HIP 用 `strata_prefill` に `src/prefill/prefill.cpp` を含める。
- `sycl/CMakeLists.txt:232-239` — SYCL 用 `strata_prefill` に SYCL 側 prefill ソースを含める。
- `docs/TROUBLESHOOTING.md:155-168` — 診断設定の案内と目的。
