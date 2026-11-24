# `INK_BC_SOLO_CHUNK`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

`strata-inkling --batch-check` の比較で、単独実行側（solo）の prompt prefill を何 token ずつ `forward_batch` に渡すかを指定する診断用変数です。環境変数が変えるのは solo 側の分割だけで、比較相手の batched 側は `--chunk` と slot 数から作る scheduler のままです。serve や通常の生成で使う設定ではありません（`engine/src/inkling2/ink_main.cpp:445-449, 466-490, 512-530`）。

## 値と判定

`cmd_batch_check` が `std::getenv` で読み、値が存在して `std::atoi` の結果が正数ならその整数を採用します。それ以外は `chunk = max(1, bo.chunk)` に戻ります。`atoi` は先頭の空白と符号を許し、先頭の十進整数部分を変換するため、文字列全体の検証はありません。たとえば `"4tail"` は 4 として採用され、`"tail4"`、`"0"`、`"0anything"`、`"-2"`、`"true"`、`"false"`、空文字は 0 以下となり fallback します。`"1"` は 1 として採用されます。大文字小文字の判定はありません。正数に対する明示的な上限 clamp もありません（`engine/src/inkling2/ink_main.cpp:466-468`）。

| 条件 | 未設定 | 有効になる値の例 | fallback になる値の例 |
|---|---|---|---|
| `--batch-check N` が実行され `N > 0` | `--chunk` の値（未指定時 512） | `1`, `+4`, ` 4`, `4tail` | 空文字、`0`, `-2`, `tail4` |
| それ以外の実行経路 | 読み取られない | 該当なし | 該当なし |

`--chunk` は CLI 解析時に `max(1, atoi(argument))` として `cfg.bopts.chunk` に入り、`BackendOpts` の初期値は 512 です。`INK_BC_SOLO_CHUNK` の正数はこの値を solo 側だけで置き換えます。`--chunk` は batched 側の chunk と scheduler に引き続き使われます（`engine/src/inkling2/ink_main.cpp:879-881, 466-468, 512-530`; `engine/src/inkling2/ink_backend.h:17-21`）。

## 有効になる条件

- `strata-inkling` がビルドされている必要があります。CMake の `STRATA_BUILD_INKLING` と `STRATA_BUILD_INKLING2` がともに有効で、`engine/src/inkling2/CMakeLists.txt` が存在するときに Inkling-2 ターゲットを追加します（`engine/CMakeLists.txt:1000-1005`）。
- `--batch-check` に正数を渡し、`--prompt-ids` に ID リストまたは `@file` を渡して prompt ID の解析を通る必要があります。ID が未指定または解析できない場合は `--batch-check needs --prompt-ids (a list or @file)` を stderr に出して戻り値 2 となります。`--batch-check` が 0 以下ならこの関数は呼ばれず、環境変数も読みません（`engine/src/inkling2/ink_main.cpp:964-965, 1053-1060`）。
- 環境変数の読み取りは `cmd_batch_check` 内でモデルを開き、backend を初期化し、slot を割り当てた後です。それらの処理が失敗すれば環境変数を読む前に終了します（`engine/src/inkling2/ink_main.cpp:452-468`）。
- OS や CUDA/HIP/Metal/SYCL/CPU backend ごとの値判定分岐はありません。選択 backend に対する solo 側の `forward_batch` 呼び出しに chunk 分割が渡されます（`engine/src/inkling2/ink_main.cpp:471-490`）。
- 他の環境変数による上書きは見つかりません。`--chunk` は fallback 値と batched 側の chunk を決めますが、環境変数が有効な場合は solo 側 chunk を環境変数の値が置き換えます（`engine/src/inkling2/ink_main.cpp:466-468, 512-530`）。

## 実行時の詳細

環境変数は `cmd_batch_check` の実行ごとに一度読み取られ、関数内の `solo_chunk` に保存されます。prompt の solo prefill ループでは残り token 数との小さい方を一度の `forward_batch` に渡し、最後の chunk で logits を取得します。その後の solo decode は 1 token ずつ行い、この値を使いません。solo 結果を保存して slot を reset した後、別の batched scheduler が `max(chunk, K)` の budget で比較実行します（`engine/src/inkling2/ink_main.cpp:466-490, 494-530`）。

この関数内での読み取りは一回限りで、プロセス実行中に環境を変更しても既に決めた `solo_chunk` には反映されません。子プロセスへの転送はありません。prompt より大きい正数も受け付けますが、各 prefill 呼び出しの長さは残り prompt token 数までです（`engine/src/inkling2/ink_main.cpp:467-480`）。

## ログと測定値

環境変数の値や採用結果を表示する専用ログはありません。batch-check は各 step の KL と top-1 の一致状況を条件付きで stdout に出し、最後に集計を表示します。`KL > 1.0` が一つでもあれば戻り値 1 です（`engine/src/inkling2/ink_main.cpp:573-580`）。モデル open / backend init / slot allocation / solo prefill / solo decode / batched forward の失敗時はそれぞれ `open: ...`, `init: ...`, `alloc_slot: ...`, `solo prefill: ...`, `solo decode: ...`, `batched: ...` を stderr に出して戻り値 1 とします。また scheduler が完了しない場合は `batch-check: scheduler did not finish` を stderr に出して戻り値 1 です（`engine/src/inkling2/ink_main.cpp:454, 460, 463, 481, 490, 538, 553`）。

`docs/DETAILS.md` にこの変数または batch-check の説明は見つかりませんでした。ソースから性能・正確性の測定値は確認できないため記載していません。

## 根拠

- 候補名は `engine/src/inkling2/ink_main.cpp:467` の直接参照 1 箇所だけです。リポジトリ全体の完全一致検索で、その他の Strata 読み取り箇所は見つかりませんでした。
- 読み取り、fallback、solo prefill での使用: `engine/src/inkling2/ink_main.cpp:466-490`。
- `--chunk` と `--batch-check` の解析・dispatch: `engine/src/inkling2/ink_main.cpp:879-881, 964-965, 1053-1060`。
- chunk の初期値: `engine/src/inkling2/ink_backend.h:17-21`。
- CMake ターゲット条件: `engine/CMakeLists.txt:1000-1005`。
- 出力と終了結果: `engine/src/inkling2/ink_main.cpp:538, 553-580`。
