# `STRATA_CVEC_FUSE`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

prompt 処理で、hyper-connection の residual write、制御ベクトル適用、次の half の norm と BF16 画像生成を一つの kernel にまとめるかを選びます。通常の三段階（write、制御ベクトル、norm）を `gr_write_cvec_norm_rs` に置き換える最適化スイッチです。制御ベクトルの読み込みやリクエストごとの有効・無効は、この変数ではなく別の設定が決めます。

CUDA/HIP 実装（`src/prefill/prefill.cpp`）と SYCL 実装（`sycl/src/prefill/prefill.cpp`）に同じ判定と適用条件があります。decode の経路ではなく prompt の prefill 経路で使われます。

## 値と判定

prefill 実装は `getenv()` の結果を static 変数に一度保存し、文字列全体ではなく先頭文字が `'1'` かだけを調べます。

| 状態 | 判定 |
|---|---|
| 未設定 | 無効（通常の既定値） |
| 空文字 | 無効。設定済みだが先頭文字は `\0` |
| 先頭が `1`（例: `1`, `10`, `1xyz`） | 有効 |
| その他（例: `0`, `true`, `2`, 空白で始まる値） | 無効 |

数値変換、空白除去、大文字小文字変換はしません。判定は初回の `cvec_fuse()` 呼び出し時に行われ、同一プロセスで環境を変更しても再評価されません。

## 有効になる条件

スイッチの判定が有効でも、各 layer で次の条件を満たしたときだけ fused kernel が選ばれます。

- 該当する hyper-connection half が layer の FFN write 側（`half == 1`）で、ロード済み制御ベクトルがその layer をカバーしている。
- `STRATA_GR_UNFUSED` が有効でない。
- 次の layer が存在し（`nl < LE`）、layer 1 の PLE block 前にあたる例外経路ではない。
- 制御ベクトルの埋め込み次元と hyper-connection 数がモデルと一致し、現在の device に制御ベクトルの表がある。

制御ベクトルは `--control-vector-scaled` などで別途ロードされます。リクエストでそのベクトルが無効でも fused kernel 自体は選ばれ得ますが、kernel 内の device flag が 0 ならベクトル変換をせず、write と norm を行います。条件を満たさない steered layer では、通常の write/norm と `cvec_apply()` に戻ります。ベクトルがない場合はこの変数だけを設定しても fused cvec 経路は使われません。

## AMD GPU での既定値と実行時の詳細

HIP build の `generate` は device の architecture を取得できた場合、engine が各スイッチを初めて読む前に `apply_arch_defaults()` を呼びます。この関数は gfx1151、gfx1200、gfx1201 に対して `STRATA_CVEC_FUSE=1` を既定表に含めます。したがって、これらの GPU では候補表の通常既定（unset は off）と異なり、環境変数が未設定なら起動時に `1` が設定されます。gfx1151 では `STRATA_GFX1151_DEFAULTS`、gfx1200/1201 では `STRATA_GFX12_DEFAULTS` の先頭文字が `0` の場合、当該 architecture の既定表は適用されません。

既に `STRATA_CVEC_FUSE` が設定済みなら、空文字を含めてユーザー設定が保持され、その値が先頭文字判定に使われます。たとえば gfx1151 で `STRATA_CVEC_FUSE=` とすると、既定値の `1` は注入されず無効になります。gfx1151/gfx12 の既定表が何かを設定した場合、stderr に `strata: gfx1151 (Strix Halo): ... exact speed switches on by default ...` または gfx12 の同形式の一覧ログが出ます。これは複数スイッチをまとめたログで、cvec 専用の有効ログはありません。

この既定表は HIP build に限られます。CUDA build と SYCL build ではこの `#if defined(STRATA_USE_HIP)` の適用箇所を通らず、別の Strata 所有コードが値を設定しない限り unset は無効です。

## ソースと文書の照合

`docs/DETAILS.md` は control vector / experimental speed projection をロード・有効化する利用者向け手順を説明しています。一方、`STRATA_CVEC_FUSE` はそのベクトル処理を prompt kernel 内にまとめるスイッチです。DETAILS の「既定で off」は実験的な制御ベクトル機能についての説明であり、HIP gfx1151/gfx12 でこの kernel 統合スイッチを既定設定する実装とは対象が異なります。資料にはこのスイッチ単独の測定条件や性能値は確認できないため、ここでは性能効果を数値で述べません。

## 根拠

- 値判定、layer 条件、fallback: `src/prefill/prefill.cpp:345-348,3933-3988`、`sycl/src/prefill/prefill.cpp:280-283,4302-4409`。
- fused kernel が write、制御ベクトル、次 half の norm を行う処理: `src/prefill/kernels.cu:175-235,1879-1884`、SYCL 相当実装 `sycl/src/prefill/kernels.dp.cpp:255-323,2386-2412`。
- 制御ベクトルがロード済みか、layer をカバーするか、device 表を持つか: `include/strata/kernels/cvec.hpp:25-57`。ロード処理: `src/program/generate.cpp:1476-1543`。
- HIP build での architecture 判定と既定値適用時点: `src/program/generate.cpp:2152-2158`、architecture ごとの値と無効化条件: `src/core/arch_defaults.cpp:12-58`、設定済み値を保持する処理とログ: `src/core/arch_defaults.cpp:61-80`。
- 対象 architecture 名の一致規則: `include/strata/kernels/gfx_arch.hpp:15-19,32-36`。
- 制御ベクトル機能と利用方法の説明: `docs/DETAILS.md:1752-1783`。
