# `DS4_MM_ASGU`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Metal backend の expert 行列積テスト用フックです。`iq_set_dn()` から呼ばれる `mm_set(false, ...)` の down dispatch で、この変数が設定されていると down 用 pipeline と引数を gate/up 用に差し替えます。値が整数として `1` と変換される場合に限り、dispatch grid の X も gate/up の幅に変更します。ソースコメントも「the gate/up kernel on the down's buffers」と記しています。通常の設定機能ではなく、結果を変え得る内部テスト経路です（`metal/src/engine/ds4_finish.cpp:2476-2479,2596-2605,2637-2643`）。

## 値と判定

コードは同じ `mm_set()` 呼び出し中に `getenv()` を2回実行します。最初の判定は値の内容ではなく、環境変数が未設定かどうかです。2回目は `std::atoi()` の戻り値が `1` かを調べます（`metal/src/engine/ds4_finish.cpp:2598-2605`）。

| 値 | pipeline / 引数の差し替え | grid X の変更 |
|---|---|---|
| 未設定 | なし。通常の down dispatch | なし。`n_embd / COLS` |
| 空文字 | あり（`getenv()` は非 null） | なし（`atoi("")` は 0） |
| `1` に変換される文字列（例: `1`, `01`, `+1`, ` 1`, `1abc`） | あり | あり。`n_ff / COLS` にする |
| 設定済みで `atoi()` が 1 以外を返す文字列（例: `0`, `2`, `true`, `0x1`） | あり | なし |

`atoi()` は文字列全体の厳密な数値検証ではなく、先頭の空白と符号の後の10進整数部分を変換します。後続文字は判定に使われないため、たとえば `1abc` は 1 になります。エラーや範囲外を検査するコードはありません。値を `1` に限定した入力チェック、fallback、clamp はありません。

## 有効になる条件

- このコードは `metal/src/engine/ds4_finish.cpp` にあり、Metal backend の `iq_set_dn()` が `mm_set(false, ...)` を通る場合にだけ評価されます。CUDA/HIP/SYCL 側で同名変数を読む参照は見つかりませんでした。
- `mm_set()` は `n_exp <= 0` または `total_rows <= 0` なら先に成功 return するため、その呼び出しでは変数を読みません。また量子化 type、shape、stride 条件を満たし、`mm_prepare()` が成功して dispatch 構築へ進む必要があります（`metal/src/engine/ds4_finish.cpp:2476-2485`）。
- down 側では `g_mm_hs_ok` が false なら先に失敗 return します。これは先行する gate/up 側が scratch を準備して `g_mm_hs_ok = true` にした状態を要求します（`metal/src/engine/ds4_finish.cpp:2559-2564,2575-2583`）。
- `iq_set_dn()` wrapper は `mm_set(false, ...)` を呼びますが、調査対象 commit の tracked source では `iq_set_dn()` / `iq_set_gu()` の呼び出し元を確認できませんでした。そのため、この dispatch 経路が通常の実行で到達可能かは確定できません（定義・宣言: `metal/src/engine/ds4_finish.cpp:2637-2643`, `metal/include/metal_compat/ds4_metal_host.h:56-57`）。
- CLI 引数や別環境変数による優先順位の設定はありません。後続処理では `DS4_MM_DROP` が引数を差し替える場合があり、`DS4_MM_ONE` が grid Y を 1 にし、`DS4_MM_NODN` が kernel dispatch 自体を省略します（`metal/src/engine/ds4_finish.cpp:2606-2617`）。

## 実行時の詳細

変数は `mm_set()` の down dispatch ごとに読み直され、`static` cache はありません。プロセス開始時の一括評価ではないため、dispatch 前に環境が変更された場合はその呼び出しの判定に使われます（`metal/src/engine/ds4_finish.cpp:2598-2605`）。

未設定なら down 用 pipeline と通常の down 引数・grid のままです。設定されている場合、コードは `ds4_mm_gu_<tg>` pipeline を取得し、引数1・2を `g_mm_xs`・`g_mm_ys` に差し替えます。値が `atoi(...) == 1` の場合は grid X を `(uint32_t)(n_ff / COLS)` にします。それ以外の設定値では pipeline と引数は gate/up 用に変わりますが grid X は down 用の `(uint32_t)(n_embd / COLS)` のままです。`COLS` は 128 です（`metal/src/engine/ds4_finish.cpp:2485-2487,2596-2605`）。

環境変数専用のログや警告はありません。Metal library の準備に失敗した場合は `dsv41 metal: compiling ds4_mm.metal failed` が stderr に出て `mm_set()` は false を返します（`metal/src/engine/ds4_finish.cpp:2466-2472`）。この変数による pipeline 取得は局所的な例外処理に包まれていません。dispatch が成功した場合、down 経路は続けて結果を `ds4_copy4` で engine 側の行へコピーします（`metal/src/engine/ds4_finish.cpp:2616-2634`）。対象関数より上の呼び出し元での失敗表示・終了処理は、この調査で辿れた同リポジトリ内の参照からは確定できません。

## 根拠

- `metal/src/engine/ds4_finish.cpp:2476-2487` — `mm_set()` の早期 return、入力条件、tile 定数。
- `metal/src/engine/ds4_finish.cpp:2559-2588` — gate/up scratch の準備状態と down 側の前提条件。
- `metal/src/engine/ds4_finish.cpp:2596-2617` — 通常の down grid、環境変数判定、gate/up pipeline/引数への差し替え、後続の相互作用。
- `metal/src/engine/ds4_finish.cpp:2619-2643` — down 結果のコピーと gate/up/down wrapper。

対象名の全参照をリポジトリ内で検索した結果、読み取りは上記の2箇所だけでした。`docs/DETAILS.md` にこの変数の説明や測定条件は見つからず、性能・正確性への影響は評価していません。また、wrapper の呼び出し元が見つからないため、通常実行経路からこのフックに到達するかは確認できていません。
