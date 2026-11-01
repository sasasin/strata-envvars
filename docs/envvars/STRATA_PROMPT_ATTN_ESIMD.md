# `STRATA_PROMPT_ATTN_ESIMD`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

SYCL backend の int8 KV 用 QSA prompt attention で、Battlemage 向け ESIMD / int8 DPAS kernel を選べるようにします。既定では有効です。無効時やこの kernel の対応条件を満たさないときも、呼び出し元は XMX kernel、その次に従来の decode attention を試します。このため、この変数は prompt attention 全体を有効・無効にする設定ではありません。

## 値と判定

値は `std::atoi` で整数に変換され、変換結果が **0 のときだけ** ESIMD kernel を止めます。文字列全体の妥当性確認や範囲制限はありません。

| 環境値 | `mode` | この kernel の値判定 |
|---|---:|---|
| 未設定 | 1 | 有効 |
| 空文字 | 0 | 無効 |
| `0`、`00`、`-0` | 0 | 無効 |
| `1`、`-1`、`2` | 非 0 | 有効 |
| 数字で始まり後ろに文字が続く値（例: `1x`） | `atoi` が読む先頭の整数 | 変換結果が非 0 なら有効 |
| 数字として変換できない値（例: `true`, `x`） | 0 | 無効 |

`atoi` の変換結果に対する明示的な下限・上限チェックはありません。値が非 0 でも、下記の device / 入力条件を満たさない場合は kernel は実行されません。

## 有効になる条件

この分岐は SYCL の `qsa_prompt_attn_batch()` から呼ばれます。ESIMD 実装は `STRATA_I8_NO_ESIMD` が定義されていない build に限られ、実行時には次の条件が必要です。

- 現在のデバイス世代が Intel Battlemage。
- `n_q > 0`。
- K/V の int8 pool と scale、page table、`ids`、`steps` があり、Q4 pool はない。
- `head_dim == 256`、`n_head == 12 * n_head_kv`、`cap > 0`。
- `page_size` が正の 2 の冪。

これらを満たさない場合、関数は `false` を返します。呼び出し元はまず XMX prompt attention を試し、それも未対応なら `false` を返して prefill 側が `qsa_decode_attn_batch()` による fallback を実行します。`STRATA_PROMPT_ATTN_OLD` が設定されている場合は、ESIMD 判定を呼ぶ前に従来経路が選ばれます。

CMake の `STRATA_SYCL_I8_ESIMD=OFF` は `STRATA_I8_NO_ESIMD` を定義して ESIMD 関数を stub（常に `false`）にします。同設定の `AUTO` も、AOT build が `bmg` / `lnl` 以外のとき stub にします。`STRATA_SYCL_I8_ESIMD=ON` はその stub 化を避けます。したがって環境変数を有効値にしても、stub build や Battlemage 以外ではこの kernel は使われません。

## 実行時の詳細

`mode` は `qsa_prompt_attn_esimd()` 内の function-local `static const` です。最初の呼び出しで一度だけ読み取られ、その後プロセス内で環境を変更しても再評価されません。優先順位を変える CLI 引数はこの判定箇所にはありません。

条件を満たして kernel を起動する最初の呼び出しでは stderr に `strata: prompt attention on the int8 DPAS (ESIMD)` を一度出します。値が 0 の場合や条件不成立時に、この関数から専用の無効化警告は出ません。build が stub の場合も関数は何も出力せず `false` を返します。

ESIMD 関数は `STRATA_ESIMD_LV` も初回に読み、`atoi` の結果が `3`, `32`, `23` のとき対応する `launch` template を選び、それ以外は既定 template を使います。この別変数は `STRATA_PROMPT_ATTN_ESIMD` の有効判定を上書きしません。

## 根拠

- `sycl/src/kernels/cuda/qsa_prompt_attn_esimd.dp.cpp:405-418` — `getenv` / `atoi`、既定値 1、ゼロ判定、Battlemage 世代判定、有効時の stderr ログ。
- `sycl/src/kernels/cuda/qsa_prompt_attn_esimd.dp.cpp:409-416` — 入力 pool、shape、page size 条件と不一致時の `false`。
- `sycl/src/kernels/cuda/qsa_prompt_attn_esimd.dp.cpp:419-435` — `STRATA_ESIMD_LV` による launch variant。
- `sycl/src/kernels/cuda/qsa_prompt_attn_esimd.dp.cpp:440-443` — `STRATA_I8_NO_ESIMD` build の stub。
- `sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:2011-2015` — ESIMD、XMX の順の呼び出しと未対応時の戻り値。
- `sycl/src/prefill/prefill.cpp:3446-3450,3470-3477` — `STRATA_PROMPT_ATTN_OLD` と従来 decode fallback。
- `sycl/CMakeLists.txt:45-63,247-249` — ESIMD build option、stub compile definition、kernel source の登録。
