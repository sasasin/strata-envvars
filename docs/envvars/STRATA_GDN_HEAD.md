# `STRATA_GDN_HEAD`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。調査対象 checkout は `main...origin/main` で、未コミット変更はなかった。

## 役割

HIP ビルドで GDN (gated-delta-net) recurrence に使う kernel variant を選ぶ。値が真なら通常の列分割 recurrence の代わりに、4 lane/column の quad recurrence と grid-stride 出力 norm を選ぶ（`engine/src/prefill/kernels.cu:1461-1475, 3122-3140, 3286-3293`）。状態だけを進める recurrence にも同じ選択を渡す（同 `:3309-3314`）。

この variant は AMD/HIP 用の `__HIPCC__` 分岐内で実装されている。CUDA の `kernels.cu` にも値の読み取りはあるが、quad variant の launch 節は HIP compile guard 内にあるため CUDA ではこの設定による kernel 切替は行われない（同 `:3122-3144, 3286-3293`）。SYCL ファイルも値を読み、variant を選ぶが、quad variant 本体は `__HIPCC__` guard 内にあり、通常の非 HIP SYCL ビルドでは variant 1 専用の launch はなく、後続の一般経路へ進む（`engine/sycl/src/prefill/kernels.dp.cpp:2821-2863, 2972-2980`）。

Strata は HIP engine の起動時に一部 AMD GPU 向けの既定値 `1` を設定する。GPU architecture defaults はユーザーが同名変数を設定済みなら値を上書きしない（`engine/src/core/arch_defaults.cpp:43-50, 64-74, 302-323`; `engine/include/strata/core/gfx11_extra.hpp:41-53`）。

## 値と判定

recurrence 関数ごとの関数内 `static` 初期化で `std::getenv` の結果を `std::atoi` に渡し、未設定でなく変換結果が 0 以外なら有効とする。文字列全体の検証や範囲チェックはない。したがって空文字、`0`、`0anything`、`true`、`false`、数字で始まらない文字列は無効、`1`、`2`、`-1`、`1tail`、先頭空白付きの ` 1` は有効になる（`atoi` が先頭の整数部分を変換）。数値変換の範囲外入力については C ライブラリの `atoi` の範囲外動作に依存し、Strata 側で定義していない（`engine/src/prefill/kernels.cu:3291-3293, 3311-3314`; SYCL 側 `engine/sycl/src/prefill/kernels.dp.cpp:2977-2980`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| HIP kernel の初回 recurrence 呼び出しで環境を直接読む場合 | `false` | `1`, `2`, `-1`, `1tail` | 空文字, `0`, `0anything`, `true`, `false`, `abc` |
| gfx1151 / gfx12 / discrete RDNA3 の HIP engine architecture defaults が適用される場合 | 原則 `1` を設定 | 未設定時の既定値 `1`、または利用者が指定した `atoi != 0` の値 | 利用者が指定した `atoi == 0` の値。該当 family defaults を無効にすれば unset のまま |
| setup が gfx1103 / gfx1150 向け run config を生成する場合 | config の `env` に `1` を含める | `1`（生成 config の値） | 設定値をユーザーが保持・変更した場合は engine の `atoi` 判定に従う |

`atoi` は大文字小文字を比較せず、真偽語として `true` / `false` を解釈しない。`1tail` は先頭の数値 `1` だけが使われ、`0anything` は `0` になる。明示的な値があると architecture defaults は `getenv(...) != nullptr` を見てスキップするため、空文字も既定値 `1` に置換されず、結果として無効のままになる（`engine/src/core/arch_defaults.cpp:307-310`; gfx11 `:318-324`）。

## 有効になる条件

- GDN recurrence を呼ぶ経路であること。通常の使用箇所は GDN を含む prompt の recurrence。`T > 0` で variant 1 に入ったとき quad recurrence を launch する（`engine/src/prefill/kernels.cu:3122-3140`）。
- quad variant の実装が使われる HIP build であること。CUDA build はこの値を読み取るものの quad launch をコンパイルしない（同 `:3122-3144`）。
- `STRATA_GDN_REC_HEADS` が未設定であること。この別変数は値の内容ではなく設定有無を見て serial variant を選び、空文字や `0` でも `STRATA_GDN_HEAD` の選択を抑止する（同 `:3291-3293, 3311-3314`）。
- 自動既定値は HIP engine の `apply_arch_defaults` で GPU 0 の architecture を調べた後に設定される（`engine/src/program/generate.cpp:4287-4320`）。gfx1151 は `STRATA_GFX1151_DEFAULTS` が先頭文字 `0` なら defaults 一式が無効（`engine/src/core/arch_defaults.cpp:64-74`）。gfx1200 / gfx1201 は `STRATA_GFX12_DEFAULTS` が先頭文字 `0` なら無効（同 `:30-50`）。discrete RDNA3 gfx1100 / gfx1101 / gfx1102 は非 integrated GPU で、`STRATA_GFX11_DEFAULTS` が先頭文字 `0` でない場合に既定値候補となる（`engine/include/strata/core/gfx11_extra.hpp:27-30, 41-49`; `engine/src/core/arch_defaults.cpp:312-324`）。
- Strata setup は gfx1103 / gfx1150 向け run config の `env` にも `STRATA_GDN_HEAD=1` を含める。これは setup が作成・更新する config の値で、engine 自身の architecture defaults の対象 GPU 群とは別経路（`terminal/setup.py:4472-4485, 7544-7547`）。
- 上記 architecture defaults より前に同名変数が存在すれば、その値が優先される。特定の CLI 引数でこの変数を上書きする経路は確認できなかった。

## 実行時の詳細

`gdn_recurrence` と `gdn_recurrence_state_only` はそれぞれ別の関数内 `static` で値を一度読み、以降の呼び出しではキャッシュ値を再利用する。したがって初回読み取り後にプロセス環境を変えても、すでに初期化された側の判定には反映されない。通常の engine main は recurrence の利用より先に architecture defaults を適用し、該当 GPU では unset を `1` に設定する（`engine/src/program/generate.cpp:4287-4320`; `engine/src/prefill/kernels.cu:3291-3293, 3311-3314`）。

有効時、HIP implementation は `gdn_rec_quad_kernel` を起動し、通常の GDN path では出力 norm に `gdn_out_norm_loop_kernel` を使う。`STRATA_GDN_PP` はこの variant 内で `atoi` され、値 `2` は二列/ lane kernel、他の非ゼロ値は別の quad PP kernel、ゼロまたは unset は基本 quad kernelを選ぶ。state-only 経路では出力 norm は呼ばず recurrence variant のみを切り替える（`engine/src/prefill/kernels.cu:3122-3140, 3286-3314`）。

無効時、または `STRATA_GDN_REC_HEADS` 設定時は variant 0 側へ進み、通常の列分割 recurrence などの既存 dispatch を使う。CPU、CUDA、通常の非 HIP SYCL でこの変数による quad kernel 選択は行われない（`engine/src/prefill/kernels.cu:3185-3190, 3286-3293`; `engine/sycl/src/prefill/kernels.dp.cpp:2821-2863, 2972-2980`）。

## ログと測定値

この変数単独の有効・無効を表示するログや、失敗時専用のエラー文言は確認できなかった。自動既定値を新たに適用したときは、gfx1151 / gfx12 で `strata: gfx1151 (Strix Halo): ... exact speed switches on by default ...` または `strata: gfx12 (RDNA4): ... exact speed switches on by default ...` の行に `GDN_HEAD` が列挙される。離散 RDNA3 では `strata: gfx11 (RDNA3): ... exact speed switches on by default ...` の一覧に列挙される。利用者が明示した場合や既定値が無効の場合は、この設定名を追加した既定値適用ログは出ない（`engine/src/core/arch_defaults.cpp:307-323, 325-332, 397-404`）。

## 根拠

- `engine/src/prefill/kernels.cu:1461-1475, 3122-3144, 3286-3314`
- `engine/sycl/src/prefill/kernels.dp.cpp:2821-2863, 2972-2980`
- `engine/src/core/arch_defaults.cpp:30-50, 64-74, 302-332, 397-404`
- `engine/include/strata/core/gfx11_extra.hpp:27-30, 41-53`
- `engine/src/program/generate.cpp:4287-4320`
