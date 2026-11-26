# `STRATA_GDN_PP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

HIP の GDN（gated-delta-net）再帰で、`STRATA_GDN_HEAD` により選ばれた quad recurrence のカーネル形状を切り替える。値 `2` は 1 lane あたり 2 列を処理する `gdn_rec_quad2c_kernel`、その他の非ゼロ値は `gdn_rec_quad_pp_kernel`、ゼロは標準の `gdn_rec_quad_kernel` を選ぶ。対象は再帰の計算経路であり、環境変数自体を読むだけのログ設定ではない（`engine/src/prefill/kernels.cu:3122-3130`）。

## 値と判定

`std::getenv` の結果を `std::atoi` に渡す。未設定なら 0。空文字、数値に変換できない文字列、先頭の数値が 0 の文字列も 0 になり、標準の quad kernel を選ぶ。`atoi` は先頭の空白と符号を受け付け、数字列の後ろは無視するため、`"2x"` は 2、`"1anything"` は 1、`"0anything"` は 0 と判定される。大文字小文字による比較はなく、`true` / `false` は数値として解釈されず 0 になる。整数として表現できない値の動作はコードで検査・制限されていない。

| 条件 | unset | 値による選択 | 0 と判定される例 |
|---|---|---|---|
| HIP、quad recurrence の `variant == 1`、`T > 0` | 0（標準 quad） | `2` → 2-column kernel。`0` 以外で `2` ではない整数 → PP kernel | `0`、`-0`、空文字、`true`、`0anything` |

`1`, `-1`, `3`, `-2` はいずれも非ゼロで `2` ではないため PP kernel を選ぶ。`2x` や `2.0` は `atoi` が先頭の整数部分を読むため 2 として扱われる（`engine/src/prefill/kernels.cu:3122-3130`）。

## 有効になる条件

- `STRATA_GDN_HEAD` が数値として非ゼロで、`STRATA_GDN_REC_HEADS` が未設定であること。標準の GDN 呼び出しはこの条件で `variant == 1` を渡す。`STRATA_GDN_REC_HEADS` は値が空でも設定されていれば serial 経路を選ぶ（`engine/src/prefill/kernels.cu:3286-3293`, `3309-3314`）。
- GDN 再帰が呼ばれ、`T > 0` であること。別のモデル経路、`T <= 0`、または別 variant ではこの値を読まない（`engine/src/prefill/kernels.cu:3122-3124`）。
- HIP の AMD kernel 経路であること。quad kernels と `STRATA_GDN_PP` の分岐は `__HIPCC__` 条件内にある。CUDA ではこの変数を読まず、SYCL の Intel 向け CMake build も `icpx` を使い、`.dp.cpp` の AMD-only `__HIPCC__` 節を有効にしない（`engine/src/prefill/kernels.cu:3088-3090`, `engine/src/prefill/kernels.cu:3122-3144`, `engine/sycl/CMakeLists.txt:1-11`, `engine/sycl/src/prefill/kernels.dp.cpp:2821-2863`）。
- `STRATA_GDN_CHUNKED` が有効で、`gdn_rec_wmma(...)` がその呼び出しを処理できた場合は、PP 分岐より前に chunked kernel を起動して戻るため `STRATA_GDN_PP` は参照されない。chunked 側が処理しない場合は後続の variant 分岐に進む（`engine/src/prefill/kernels.cu:3088-3099`, `3122-3140`）。

起動時の HIP arch defaults は、未設定の場合に `STRATA_GDN_PP=2` を設定する。対象は gfx12（`STRATA_GFX12_DEFAULTS` が `0` で始まらない場合）、gfx1151（`STRATA_GFX1151_DEFAULTS` が `0` で始まらない場合）、および discrete RDNA3 gfx1100/1101/1102（`STRATA_GFX11_DEFAULTS` が `0` で始まらず、`STRATA_DEFAULTS` が `026` / `0.2.6` / `v0.2.6` のいずれでもない場合）。既に設定済みなら空文字や `0` を含めその値を維持する。`apply_arch_defaults` は HIP の起動時に GPU 情報を得た後で呼ばれる（`engine/src/core/arch_defaults.cpp:28-50`, `64-73`, `engine/include/strata/core/gfx11_extra.hpp:27-50`, `engine/include/strata/core/defaults_026.hpp:21-29`, `engine/src/core/arch_defaults.cpp:302-323`, `engine/src/program/generate.cpp:4287-4320`）。この既定値も、`STRATA_GDN_HEAD` が有効であることや chunked 経路が先に成功しないことを上書きしない。

## 実行時の詳細

`variant == 1` の GDN 再帰で最初に `T > 0` となったとき、関数内 `static const int pp` を初期化する。この値はプロセス内でキャッシュされ、同じ実行中に環境を変更しても反映されない。環境変数が初期化前に未設定なら 0 が固定される（`engine/src/prefill/kernels.cu:3122-3130`）。

値 `2` は 2 列処理の kernel を起動し、それ以外の非ゼロ値は PP kernel を起動する。0 の場合は標準 quad kernel に戻る。通常の `gdn_recurrence` と state-only 呼び出しの双方が `variant == 1` になり得るため、後者でも `T > 0` なら同じ選択が適用される（`engine/src/prefill/kernels.cu:3122-3130`, `3286-3293`, `3309-3314`）。

起動時 defaults は `getenv` で設定の有無を確認し、未設定時のみ値を入れる。従って CLI 引数による `STRATA_GDN_PP` の上書き経路はなく、環境変数の明示値が arch default より優先される（`engine/src/core/arch_defaults.cpp:218-224`, `307-310`）。

## ログと測定値

この値の parse 結果や選択 kernel を直接表示するログはない。GPU 別 defaults が適用されたとき、gfx11 discrete では `apply_arch_defaults` が「exact speed switches on by default」の一覧を stderr に出し、名前を `GDN_PP` として含めることがある。gfx12 / gfx1151 の `STRATA_GDN_PP` 設定には、この関数からの個別表示はない（`engine/src/core/arch_defaults.cpp:318-332`, `engine/src/program/generate.cpp:4320`）。起動後の kernel check は `gdn_recurrence (quad)` のラベルを使うが、これは PP 値の診断ログではない（`engine/src/prefill/kernels.cu:3138-3140`）。

Strix Halo / Radeon 780M 資料は `STRATA_GDN_PP=2` を GDN prompt switch 群に列挙しているが、この変数単独の測定条件・測定値は示していないため、本書では性能値を記載しない（`docs/STRIX_HALO.md:109-113`, `docs/RADEON_780M.md:82-87`）。

## 根拠

- `engine/src/prefill/kernels.cu:3122-3140` — HIP variant 1 における読み取り、値の分岐、fallback、kernel check。
- `engine/src/prefill/kernels.cu:3286-3293`, `3309-3314` — 通常再帰と state-only 呼び出しが variant 1 を選ぶ条件。
- `engine/src/core/arch_defaults.cpp:28-50`, `64-73`, `302-323` — 対象 GPU 世代、既定値、ユーザー設定の保持。
- `engine/src/program/generate.cpp:4287-4320` — HIP 起動時に GPU defaults を適用する箇所。
- `engine/sycl/CMakeLists.txt:1-11`, `engine/sycl/src/prefill/kernels.dp.cpp:2821-2863` — SYCL Intel build と AMD-only guard。
