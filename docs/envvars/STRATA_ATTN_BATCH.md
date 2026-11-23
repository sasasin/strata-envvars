# `STRATA_ATTN_BATCH`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

SYCL の prompt prefill で、旧式 FP32 QSA attention 経路が一度に処理する query 数を指定する。実際の値は `min(設定値, 現在の prompt chunk の token 数)` で、最低 1。QSA attention scratch の容量と prefill の領域見積もりにも同じ値が使われる。読み取りと適用箇所は `engine/sycl/src/prefill/prefill.cpp` の `attn_batch_setting()`、`attn_batch_for()`、`Prefill::init()`、QSA 処理部にある（`engine/sycl/src/prefill/prefill.cpp:764-772, 1674-1688, 1731-1735, 3873-3895`）。

## 値と判定

`std::getenv` で値を取得し、設定されていれば `std::atoll` で数値に変換する。変換結果が 1〜1024 のときだけ採用し、それ以外は 32 にする。未設定も 32。空文字、数値に変換できない文字列、`0`、負数、1025 以上は `atoll` の結果が範囲外になるため 32 に戻る。`atoll` は文字列全体の厳密な検証ではないため、数値の後ろに文字が続く場合も数値部分が変換される（例: `12xyz` は 12）。先頭の空白や符号も変換規則に従う。範囲内の値も prompt chunk 長 `T` で上限を受ける（`engine/sycl/src/prefill/prefill.cpp:764-772`）。

| 条件 | unset | 有効になる値（例） | 無効値・fallback の例 |
|---|---:|---|---|
| SYCL `Prefill` | 32 | `1`〜`1024`（例: `1`, `32`, `1024`） | 空文字、`0`, `-1`, `1025`, `true` は 32 |
| chunk 長 `T` での適用 | 上記の 32 を使用 | `attn_batch = max(1, min(設定値, T))` | `T` より大きい設定値は `T` に制限 |

この変数を読むコードは SYCL prefill 実装にだけある。CUDA/HIP や他の backend で同名変数を読む箇所はない（`engine/sycl/src/prefill/prefill.cpp:764-767`）。

## 有効になる条件

- SYCL backend の `Prefill` が使われること。`strata_prefill` は SYCL の CMake target に `src/prefill/prefill.cpp` を含む（`engine/sycl/CMakeLists.txt:304-311`）。
- `Prefill::init()` と prefill の chunk sizing が `attn_batch_for(T)` を呼ぶため、SYCL prefill の scratch 領域確保・見積もりに反映される（`engine/sycl/src/prefill/prefill.cpp:1674-1688, 1731-1735, 2423-2475`）。
- QSA layer の prompt attention で `old_attn` が設定されているか、`qsa_prompt_attn_batch(...)` が `false` を返して旧式経路に入る場合、query を `m.attn_batch` ごとに分けるループ幅として使われる。最適化経路が `true` を返せば、その呼び出しには chunk 全体 `T` が渡され、環境変数はその経路の query 数を分割しない（`engine/sycl/src/prefill/prefill.cpp:3873-3895`）。
- `STRATA_PROMPT_ATTN_OLD` が存在すると `old_attn` が true になり、最適化経路を呼ばず分割ループへ進む。値の内容ではなく設定有無を見ており、空文字も有効（`engine/sycl/src/prefill/prefill.cpp:3853-3854, 3873-3876`）。
- `STRATA_SYCL_TLA_ATTN` の build option が有効な場合、その分割ループ内でさらに `STRATA_SYCL_TLA_ATTN` の実行時値が先頭文字 `1` かを調べる。`nb == 32` かつ `m.cap == 2051` の場合に TLA kernel が成功すると、その batch はそこで処理される。build option は `STRATA_SYCL_AOT=bmg-g31` と Level Zero などを要求する（`engine/sycl/src/prefill/prefill.cpp:3877-3882`, `engine/sycl/CMakeLists.txt:313-335`）。
- 旧式経路内で `STRATA_ATTN_PERCELL` が未設定、または先頭文字が `0` 以外なら per-cell kernel を使い、先頭文字が `0` なら `qsa_decode_attn_batch` を使う。どちらも同じ `nb` を処理する（`engine/sycl/src/prefill/prefill.cpp:3884-3895`）。

## 実行時の詳細

`attn_batch_setting()` に static cache はなく、呼び出すたびに環境を読み直す。`attn_batch_for(T)` は `Prefill::init()` の carve 前と bytes-needed の計算からも呼ばれるため、設定は scratch 見積もりと確保の双方に反映される（`engine/sycl/src/prefill/prefill.cpp:764-772, 1674-1688, 2423-2475`）。プロセス実行中に環境値を変更した場合、次の helper 呼び出しから読み直されるが、既に確保した領域は自動で再確保されない。

QSA scratch は `attn_batch * qsa_decode_attn_scratch_floats(cap, s)` 個の `float` として数えられ、同じサイズで確保される。従ってバッチ値を増やすと領域見積もりと scratch 消費量が増える。chunk より大きい値は chunk 長までに抑えられる（`engine/sycl/src/prefill/prefill.cpp:1220-1238, 1674-1688, 1731-1735, 2471-2475`）。

この値は CLI の `--prefill` chunk 長とは別で、`T` は選択済み chunk 長から渡される。`--prefill` の値をこの変数が上書きする処理はない（`engine/sycl/src/prefill/prefill.cpp:1674-1677, 3873-3876`）。

## ログと測定値

この変数の読み取りや fallback 自体を知らせるログはない。確保領域が足りず `Prefill::init()` の carve が失敗すると、`err` に `prefill: device buffers for a chunk of ... tokens do not fit (...)` を設定して false を返す。呼び出し側は `strata generate: ` を付けて stderr に出し、終了コード 1 で戻る（`engine/sycl/src/prefill/prefill.cpp:1613-1632`, `engine/sycl/src/program/generate.cpp:13329-13334`）。SYCL exception の場合は `exc.what()` とソース位置を stderr に出して `std::exit(1)` する（`engine/sycl/src/prefill/prefill.cpp:1635-1639`）。

## 根拠

- `engine/sycl/src/prefill/prefill.cpp:764-772` — 読み取り、既定値、範囲判定、chunk 長による制限。
- `engine/sycl/src/prefill/prefill.cpp:1220-1238, 1674-1688, 1731-1735, 2423-2475` — scratch の見積もりと確保。
- `engine/sycl/src/prefill/prefill.cpp:3853-3895` — QSA の最適化経路、分割、関連する環境条件。
- `engine/sycl/src/prefill/prefill.cpp:1613-1639`; `engine/sycl/src/program/generate.cpp:13329-13334` — 失敗の返却、stderr、終了経路。
- `engine/sycl/CMakeLists.txt:304-335` — SYCL prefill target と任意 TLA build option。
