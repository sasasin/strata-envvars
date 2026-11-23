# `STRATA_CVEC_FUSE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

prefill の residual stream 書き戻しで、制御ベクトルが適用される層に限り、書き戻し・制御ベクトル適用・次 half の norm を `gr_write_cvec_norm_rs` の 1 パスにまとめます。CUDA/HIP と SYCL の prefill 実装に読み取りがあります（`engine/src/prefill/prefill.cpp:1030-1033,7662-7721`、`engine/sycl/src/prefill/prefill.cpp:400-403,5392-5516`）。

この変数は制御ベクトル自体をロードしたり有効化したりせず、融合経路を選ぶだけです。制御ベクトルがない層では融合条件が成立せず、既存の通常経路を通ります。融合カーネルの宣言コメントは、従来の write・cvec・norm の三カーネルと同じビット結果と説明しています（`engine/include/strata/prefill/kernels.hpp:35-40`）。

## 値と判定

どちらの prefill 実装も `std::getenv` の結果が null でなく、先頭文字が文字 `'1'` のときだけ true とし、関数内 `static const bool` に保存します。文字列全体の parse、数値検査、空白除去、大文字小文字変換はありません（`engine/src/prefill/prefill.cpp:1030-1033`、`engine/sycl/src/prefill/prefill.cpp:400-403`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| 明示値（CUDA/HIP・SYCL の読み取り箇所） | false。ただし HIP 起動時に後述の AMD 既定値が注入される場合あり | `1`、`1anything`（先頭が `'1'`） | 空文字、`0`、`0anything`、`true`、` 1` |
| AMD のアーキテクチャ既定値が適用される起動 | 対象 GPU と無効化設定に応じて `1` を注入 | 注入値 `1` | 明示値があれば値を上書きしない。明示した空文字や `0` も既定値より優先される |

## 有効になる条件

- 実行中の prefill で、層 `l` が `cvec().covers(l)` に該当する必要があります。これは制御ベクトルがロード済みで、層範囲内かつその層の方向ベクトルが非ゼロの場合です。通常は `--control-vector-scaled` で制御ベクトルをロードした経路です（`engine/include/strata/kernels/cvec.hpp:13-15,25-36`）。
- 次 half が存在し（`nl < LE`）、`STRATA_GR_UNFUSED` が有効でなく、`nl == 1 && ple_on` の除外条件に該当せず、ベクトルの `n_embd` と `hc` が現在の値に一致し、現在 device 上のベクトル表を取得できる必要があります。これらを満たさない場合は `cv_fused` が false となり、融合されません（`engine/src/prefill/prefill.cpp:7662-7669,7713-7721`、SYCL は `engine/sycl/src/prefill/prefill.cpp:5392-5399,5498-5516`）。
- HIP 起動時の自動既定値は AMD GPU アーキテクチャに限られます。gfx1151 は `STRATA_GFX1151_DEFAULTS` が先頭 `'0'` でない場合、gfx12 は `STRATA_GFX12_DEFAULTS` が先頭 `'0'` でない場合に候補となります。離散 RDNA3 gfx1100/1101/1102 は integrated でなく、`STRATA_GFX11_DEFAULTS` が先頭 `'0'` でない場合に候補です（`engine/src/core/arch_defaults.cpp:28-66`、`engine/include/strata/core/gfx11_extra.hpp:39-53`）。
- CUDA build の起動コードは HIP 専用 `#if defined(STRATA_USE_HIP)` の内側にあるため、ここで説明した AMD アーキテクチャ既定値の注入対象ではありません。明示値は prefill の読み取り箇所で判定されます（`engine/src/program/generate.cpp:4282-4315`）。

## 実行時の詳細

HIP 起動経路では `apply_arch_defaults` が prefill の switch 読み取りより前に呼ばれ、対象 GPU の既定表を調べます。対象変数が既に環境に存在すれば値を保持し、なければ `setenv(..., 0)`（Windows では `_putenv_s`）で既定値を設定します（`engine/src/program/generate.cpp:4282-4315`、`engine/src/core/arch_defaults.cpp:218-224,302-324`）。gfx1151 と gfx12 の表には `STRATA_CVEC_FUSE=1` があり、離散 gfx1100/1101/1102 の表にも含まれます（`engine/src/core/arch_defaults.cpp:64-76`、`engine/include/strata/core/gfx11_extra.hpp:41-53`）。

switch 値は `cvec_fuse()` の初回呼び出しで static cache されるため、それ以降の環境変更は同プロセス内で反映されません（`engine/src/prefill/prefill.cpp:1030-1033`、`engine/sycl/src/prefill/prefill.cpp:400-403`）。制御ベクトルがロード済みでも、要求ごとの有効フラグは別に保持され、融合カーネルにはその device flag が渡されます。したがって本変数は要求ごとのベクトル ON/OFF を変更しません（`engine/include/strata/kernels/cvec.hpp:25-35,50-57`）。

融合が成立すると、従来の `gr_write`、`cvec_apply`、`gr_norm_rs` に相当する処理に代えて `gr_write_cvec_norm_rs` を呼びます。条件が足りない steered 層では通常の norm 経路の後に `cvec_apply` を呼びます（`engine/src/prefill/prefill.cpp:7676-7721`、`engine/sycl/src/prefill/prefill.cpp:5406-5516`）。

## ログと測定値

gfx1151/gfx12 で既定値を注入した場合、stderr の format string は `strata: %s: %zu exact speed switches on by default (%s=0 turns them off; a switch you set is kept): ` で、`%s` は `gfx12 (RDNA4)` または `gfx1151 (Strix Halo)` です。スイッチ名の一覧には `CVEC_FUSE` が含まれます。離散 RDNA3 の format string は `strata: gfx11 (RDNA3): %zu exact speed switches on by default (STRATA_GFX11_DEFAULTS=0 turns them off; a switch you set is kept): ` で、こちらも一覧に `CVEC_FUSE` が含まれます。既定値を注入しない場合、この既定スイッチ一覧には追加されません（`engine/src/core/arch_defaults.cpp:312-332,397-404`）。

ソース内資料 `docs/STRIX_HALO.md:110-114` と `docs/RADEON_780M.md:82-85` は、書き戻し・制御ベクトル・次 norm を一回にまとめる説明で一致します。これらの資料に本変数単独の測定条件・性能値は記載されていないため、ここでは測定値を付しません。

## 根拠

- 値の読み取りと cache: `engine/src/prefill/prefill.cpp:1030-1033`、`engine/sycl/src/prefill/prefill.cpp:400-403`
- 融合条件・通常経路への fallback: `engine/src/prefill/prefill.cpp:7662-7721`、`engine/sycl/src/prefill/prefill.cpp:5392-5516`
- AMD 既定値の注入と保持: `engine/src/core/arch_defaults.cpp:28-76,218-224,302-332,397-404`、`engine/include/strata/core/gfx11_extra.hpp:39-53`
- 制御ベクトルのロード状態・要求単位フラグ・表取得: `engine/include/strata/kernels/cvec.hpp:13-15,25-57`
