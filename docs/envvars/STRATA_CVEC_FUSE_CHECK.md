# `STRATA_CVEC_FUSE_CHECK`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

制御ベクトルを適用する fused prefill write が実行されるとき、通常の3カーネル処理を一時コピー上でも実行し、fused 経路との値の一致を診断ログに出すための検査回数です。設定値は fused 経路を有効化せず、計算結果の選択にも使われません。正の値では検査用の追加 GPU メモリ、コピー、同期が発生します。CUDA/HIP 実装と SYCL 実装の両方に読み取りがあります（`engine/src/prefill/prefill.cpp:7676-7711`、`engine/sycl/src/prefill/prefill.cpp:5406-5496`）。

## 値と判定

両 backend とも `std::getenv` の結果を関数内 `static int` の初期化で `std::atoi` に渡します。未設定は `0`、空文字も `0` となり、どちらも検査しません。`atoi` のため文字列全体の妥当性検査はなく、先頭の空白と符号を許し、数値部分以降は無視します。たとえば `2`、`+2`、` 2tail` は `2` になり、`0anything`、`true`、空文字、数値に変換できない文字列は `0` になります。変換結果が正のときだけ検査し、`0` と負数は検査しません。値の clamp や独自の範囲チェックはありません（`engine/src/prefill/prefill.cpp:7679-7681`、`engine/sycl/src/prefill/prefill.cpp:5409-5411`）。

`atoi` が `int` で表せない値を受け取った場合の結果はこのコードで規定されていません。範囲外の値を検査回数として使う保証はありません。

| backend | 未設定・空文字 | 正の変換結果 | 0・負の変換結果 |
|---|---|---|---|
| CUDA/HIP | `0`、検査なし | 最初の N 回の対象 fused write を検査 | 検査なし |
| SYCL | `0`、検査なし | 最初の N 回の対象 fused write を検査 | 検査なし |

CLI 引数からこの変数を設定・上書きする処理はありません。CLI の制御ベクトル指定は別途 `--control-vector` / `--control-vector-scaled` などで行います（`engine/src/program/generate.cpp:4164-4188`、SYCL 側 `engine/sycl/src/program/generate.cpp:2128-2152`）。

## 有効になる条件

- prefill の対象箇所で、制御ベクトルが現在の層をカバーする必要があります。判定は `half == 1` かつ `cvec().covers(l)` です（`engine/src/prefill/prefill.cpp:7662-7668`、`engine/sycl/src/prefill/prefill.cpp:5392-5398`）。制御ベクトルのファイル、層範囲、モードは別の CLI 設定です（`engine/src/program/generate.cpp:4164-4188`）。
- fused 経路の有効化には別環境変数 `STRATA_CVEC_FUSE` が真であること、`STRATA_GR_UNFUSED` が有効でないこと、次の層が `LE` 未満であること、`nl == 1 && ple_on` でないこと、制御ベクトルの `n_embd` と `hc` が実行中の `N` と `HC` に一致すること、現在の device に制御ベクトルの table があることが必要です。これらを満たさなければこの検査分岐に入りません（`engine/src/prefill/prefill.cpp:7666-7676`、`engine/sycl/src/prefill/prefill.cpp:5396-5406`）。
- `STRATA_CVEC_FUSE` は gfx12 / gfx1151 向けの arch default に含まれ、arch defaults 適用時は同名の利用者設定があれば保持されます。ただしこれは検査変数の既定値ではなく、検査を実行する fused 経路側の条件です（`engine/src/core/arch_defaults.cpp:28-50`、`engine/src/core/arch_defaults.cpp:64-75`、`engine/src/core/arch_defaults.cpp:302-310`）。
- 対象変数に OS、CLI、サーバーモード、モデル状態による独自の値判定や fallback はありません。いずれの実行形態でも、上記の prefill 条件に到達しなければ値は使われません。

## 実行時の詳細

環境変数はプロセス起動時ではなく、各 backend の fused write 分岐に初めて到達した時に読み取られます。関数内 `static` に整数を保持するため、その後の環境変更は反映されず、同一プロセスの後続 prefill 呼び出しでも残り回数を共有します（`engine/src/prefill/prefill.cpp:7676-7681`、`engine/sycl/src/prefill/prefill.cpp:5406-5411`）。

残り回数が正なら1減らし、CUDA/HIP では `R` の device copy に `gr_write`、`cvec_apply`、`gr_norm_rs` を実行し、その一方で本来の `R` に fused `gr_write_cvec_norm_rs` を実行します。SYCL も同じ処理を行います。両方の結果を host にコピーして stream/queue を同期し、一時領域を解放した後に比較します。比較対象は `R`、row scale (`rs`、`grs`)、BF16 image (`xn16`) の各バッファです。CUDA/HIP 側で fused kernel に渡す `xn16_lo` は比較配列に含まれていません（`engine/src/prefill/prefill.cpp:7682-7707`、`engine/sycl/src/prefill/prefill.cpp:5412-5492`）。

検査用の3カーネル経路はコピー上で動作し、本来の `R` には fused 経路を実行します。残り回数が0以下なら追加のコピー・比較をせず、fused kernel を通常実行します（`engine/src/prefill/prefill.cpp:7708-7719`、`engine/sycl/src/prefill/prefill.cpp:5493-5516`）。

## ログと測定値

検査1回ごとに stderr へ次の形式で出力します。各項目は `memcmp` によるバイト単位の比較で、`identical` または `DIFFERS` です。

```text
strata: STRATA_CVEC_FUSE_CHECK layer <層> T <トークン数>: R <結果>, rs <結果>, xn16 <結果>
```

未設定・空文字・0・負数の場合や、対象の fused write に到達しない場合、この変数由来のログはありません（`engine/src/prefill/prefill.cpp:7703-7707`、`engine/sycl/src/prefill/prefill.cpp:5488-5492`）。この変数による測定値や速度の報告はありません。値の不正を警告する専用ログもありません。検査時は追加 device allocation と同期を行いますが、対象コードに環境値に応じた allocation 失敗時の fallback はありません（`engine/src/prefill/prefill.cpp:7682-7702`、`engine/sycl/src/prefill/prefill.cpp:5412-5487`）。

## 根拠

- 全参照と読み取り: `engine/src/prefill/prefill.cpp:7677-7679,7703-7707`、`engine/sycl/src/prefill/prefill.cpp:5407-5409,5488-5492`。
- fused 経路の条件と fallback: `engine/src/prefill/prefill.cpp:7662-7676,7708-7721`、`engine/sycl/src/prefill/prefill.cpp:5392-5406,5493-5516`。
- CLI の制御ベクトル指定: `engine/src/program/generate.cpp:4164-4188`、`engine/sycl/src/program/generate.cpp:2128-2152`。
- arch default と利用者値の保持: `engine/src/core/arch_defaults.cpp:28-50,64-75,302-310`。
