# `STRATA_Q2_WARP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA の Q2_0 行列ベクトル積（native MMVQ）で、従来のカーネルに代えて、出力 4 行を 1 warp で処理する `q2_0_warp_rows_kernel` を選ぶか制御する。Q2_0 以外の量子化型には作用しない。実装は `engine/src/kernels/cuda/native_mmvq.cu` の `q2_0_warp_rows_on()` と `native_q2_0_mmvq()` にある（3363-3405、3420-3445、3800-3818 行）。

## 値と判定

値全体の parse や数値検査はせず、`std::getenv` が null かどうかと、設定値の先頭 1 文字だけを見る。未設定は `-1`（自動判定）、設定値の先頭が文字 `'0'` なら無効、それ以外は有効になる。したがって空文字も有効であり、`0anything` は無効、`00` も無効、`1`・`true`・`false`・` 0`・`-0` はいずれも有効。大文字小文字や後続文字、数値としての妥当性は判定しない（`engine/src/kernels/cuda/native_mmvq.cu:3403-3406`）。

| ビルド・条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA (`__HIPCC__` 未定義) | 自動判定。compute capability 7.5 かつ `STRATA_SM75_PERF` が `atoi` で非 0 のとき有効 | 先頭文字が `0` 以外の値。GPU 世代を問わず有効判定 | 先頭文字が `0` の値。GPU 世代を問わず無効判定 |
| HIP (`__HIPCC__` 定義) | この変数による分岐なし | なし | なし |

自動判定で参照する `STRATA_SM75_PERF` は `std::atoi` で変換されるため、未設定・数値 0 相当は無効、数値として非 0 の接頭部を持つ値は有効（例: `1`, `2x`）、空文字や `true` は無効。これは同変数の実装 (`engine/include/strata/core/sm75_series.hpp:24-30`) による。`STRATA_Q2_WARP` 自体が設定されると、この既定判定を上書きする。

## 有効になる条件

- CUDA ビルドであること。新カーネルを選ぶ条件は `#if !defined(__HIPCC__)` 内にあり、HIP では従来経路が使われる（`engine/src/kernels/cuda/native_mmvq.cu:3428-3446`）。
- `native_mmvq()` に型 ID 42（Q2_0）が渡り、`native_q2_0_mmvq()` に到達すること（`engine/src/kernels/cuda/native_mmvq.cu:3800-3818`）。
- `ncols` が 1〜4 であること。1 列は常に候補となる。2〜4 列は `g_multi_exact` が true の場合だけ候補になる。これら以外では従来の単列または multi カーネルへ進む（`engine/src/kernels/cuda/native_mmvq.cu:3429-3450`）。
- 上記に加え、この変数が有効判定になるか、未設定時の自動判定が有効になること。明示値は自動判定に優先し、たとえば Turing 以外でも `STRATA_Q2_WARP=1`（または先頭が `0` 以外）なら選択対象となる。未設定時は Turing (compute capability 7.5) と `STRATA_SM75_PERF` の非 0 設定が必要（`engine/src/kernels/cuda/native_mmvq.cu:3403-3416`、`engine/include/strata/core/sm75_series.hpp:24-37`）。

CLI 引数や別の設定による `STRATA_Q2_WARP` の上書きは、この実装では確認できない。`STRATA_SM75_PERF` が関係するのは本変数が未設定の場合だけ。

## 実行時の詳細

`q2_0_warp_rows_on()` の関数内 `static const int env` が初回評価時に環境変数を読み、その結果をプロセス内で保持する。したがって初回評価後に環境を変更しても再評価されない。変数が未設定の場合は現在の CUDA device ordinal を取得し、0〜15 の device ごとに compute capability の判定結果を `on[dev]` に保存する。device 取得失敗・ordinal が範囲外・属性取得失敗の場合は無効となる（属性取得失敗時は `cudaGetLastError()` も呼ぶ）。自動判定は compute capability 7.5 と `STRATA_SM75_PERF` の読み取り済み状態を使う（`engine/src/kernels/cuda/native_mmvq.cu:3403-3416`; `engine/include/strata/core/sm75_series.hpp:24-37`）。

有効時は対象の列数に対応する `q2_0_warp_rows_kernel<1..4>` を起動し、起動チェック後に戻る。無効時または条件外では既存の Q2_0 カーネル経路に進む。どちらの経路でも形状・ポインタ・stream の検査が先に行われる（`engine/src/kernels/cuda/native_mmvq.cu:3420-3462`）。

## ログと測定値

この変数の有効・無効や自動判定を知らせる専用ログはない。選択した新カーネルの起動に CUDA エラーがある場合、`launch_check()` は `native MMVQ launch: ` に CUDA エラー文字列を続けた `std::runtime_error` を送出する（`engine/src/kernels/cuda/native_mmvq.cu:2491-2495`、3443-3444）。

ソースコメントには、RTX 2080 Ti 上で `attn_q` の形状が 2560×12288、3 列のケースについて旧経路 80 µs / 110 GB/s と、新経路で 3 列 80→31 µs、1 列 37→25 µs という記録がある。これはソースコメントに記された値であり、調査時に再測定した値ではない。コメントはモデル、量子化設定、測定回数を示していないため、一般的な性能差としては扱えない（`engine/src/kernels/cuda/native_mmvq.cu:3354-3360`）。

## 根拠

- `engine/src/kernels/cuda/native_mmvq.cu:3353-3418` — Q2_0 warp-row カーネル、環境変数の読み取り、CUDA device / Turing の自動判定。
- `engine/src/kernels/cuda/native_mmvq.cu:3420-3462` — Q2_0 関数内での有効条件、HIP 除外、カーネル選択と起動エラー確認。
- `engine/src/kernels/cuda/native_mmvq.cu:3775-3818` — `native_mmvq()` から Q2_0 型 ID 42 への dispatch。
- `engine/include/strata/core/sm75_series.hpp:24-37` — 未設定時に使う `STRATA_SM75_PERF` の読み取りと Turing 条件。
- `docs/DETAILS.md:1336-1346` — Turing 系の説明で本変数を個別 opt-in として列挙。

`docs/SETTINGS.md:451` は対応先を「NVIDIA and AMD」とするが、現行ソースの本変数によるカーネル選択は `__HIPCC__` でないビルドに限られる。ここではソース上で確認できる CUDA の挙動を記載した。
