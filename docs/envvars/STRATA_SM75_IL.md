# `STRATA_SM75_IL`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。作業開始時の Strata の状態は `## main...origin/main` で、`git status --short --branch` に未コミット変更は表示されなかった。

## 役割

CUDA の interleaved small-batch matrix-vector（`native_mmvq_il`）経路を、compute capability 7.5（Turing）で使えるようにするスイッチです。Turing 用行数テーブル `kIlRows_75` を選択可能にします。既定では無効で、明示的に有効にするか、別変数 `STRATA_SM75_PERF` を有効にした場合に限り、後述の形状・形式条件を満たす呼び出しで使われます。Strata の設計資料は Turing の候補カーネルについて RTX 2080 Ti で測定したことと、置き換え元と bitwise equal であることを記載しています。これは資料上の説明であり、この調査では実行・測定していません（`src/kernels/cuda/native_mmvq.cu:3704-3713`, `docs/DETAILS.md:1069-1076`, `docs/MMVQ_IL_TABLE.md:3-7`）。

## 値と判定

読み取りは `strata::sm75_switch()` が行います。compute capability が 7.5 でないときは環境変数を読む前に `false` を返します。7.5 の場合、`STRATA_SM75_IL` が設定されていれば `std::atoi(value) != 0`、未設定なら `STRATA_SM75_PERF` の判定に従います（`include/strata/core/sm75_series.hpp:24-44`）。

| `STRATA_SM75_IL` | Turing での判定 |
|---|---|
| 未設定 | `STRATA_SM75_PERF` が設定され、`atoi` の結果が 0 以外なら有効。それ以外は無効 |
| 空文字 | 設定済みとして `atoi("") == 0` となり無効。`STRATA_SM75_PERF` にはフォールバックしない |
| `0`、`00`、`0abc`、非数値文字列（例: `true`） | `atoi` の結果が 0 となり無効 |
| 数値変換の結果が 0 以外（例: `1`、`-1`、`2tail`） | 有効。先頭の空白・符号と整数部分を `atoi` が解釈し、後続の非数値部分は判定に使われない |

文字列全体の厳密な検証、範囲チェック、警告出力はありません。明示値は `STRATA_SM75_PERF` より優先され、`0` 相当値で親スイッチを無効化でき、非ゼロ値で親スイッチが未設定または無効でも個別に有効化できます。Turing 以外では値にかかわらず無効です（`include/strata/core/sm75_series.hpp:36-44`）。

## 有効になる条件

- CUDA 実装であること。HIP 側は `native_mmvq_il_supported()` が常に `false` を返し、呼び出しも通常の `native_mmvq()` へ転送します（`src/kernels/cuda/native_mmvq.cu:3930-3940,3960-3976`）。
- デバイスが compute capability 7.5 と判定されること。`STRATA_EMULATE_CC=75` による compute capability の emulation も helper の判定上は対象です。デバイス属性と環境判定の結果は ordinal ごとの `il_arch_ok()` 配列に保存されます（`include/strata/core/sm75_series.hpp:33-44`, `src/kernels/cuda/native_mmvq.cu:3914-3927`）。
- `STRATA_MMVQ_IL` が無効化していないこと。Verifier の `g_mmvq_il()` は未設定なら有効、設定時は先頭文字が `0` でなければ有効です（`src/core/verify.cpp:173-175`）。これは `STRATA_SM75_IL` とは別の上位ゲートです。
- `g_multi_exact` が有効で、列数が 1〜8、形式が IQ4_XS / Q4_K / Q5_K / Q6_K / Q3_K のいずれかであり、該当するテーブル行数が 0 でないこと。Turing 用テーブルには 2〜4 列の行があり、1 列用行はありません。5〜8 列では該当アーキテクチャの wide table がなければ通常経路になります（`src/kernels/cuda/native_mmvq.cu:3704-3714,3829-3860,3930-3934`）。
- これらの条件を満たさない場合、Verifier は通常の `native_mmvq()` を選択します。カーネル関数に直接渡された場合も、サポート判定が false なら同じ経路に fallback します（`src/core/verify.cpp:1508-1517`, `src/kernels/cuda/native_mmvq.cu:3936-3940`）。

## 実行時の詳細

`native_mmvq_il()` のアーキテクチャ判定は、デバイスごとに最初に評価した結果を `il_arch_ok()` が cache します。そのため、同じプロセス内でそのデバイスの最初の判定後に環境を書き換えても、この判定には反映されません。`sm75_switch()` 自体は値を static cache しませんが、通常の実行では上記のデバイス別 cache を介して使われます。未設定時に参照する `STRATA_SM75_PERF` は `sm75_series()` 内で最初の評価結果を `static const bool` に cache します（`src/kernels/cuda/native_mmvq.cu:3914-3927`, `include/strata/core/sm75_series.hpp:24-44`）。

有効な場合、対応する dense projection や head の呼び出しが interleaved 経路を選びます。2 列以上で interleaved activation がまだ用意されていなければ、そのコピーを作ってから専用カーネルを起動します。通常の verifier 経路では、判定に通らないと `native_mmvq()` を呼びます（`src/core/verify.cpp:1491-1517,1551-1561,1791-1798,2452-2460`）。関連する `STRATA_QIL` は activation の量子化と interleave をまとめる別設定であり、これが無効でも MMVQ 側が対応すれば必要な interleave を後から作れます（同 `1493-1506,1508-1517`）。

この変数を読むログ、警告、または専用の終了経路は見つかりませんでした。非対応条件での観測可能な処理は通常カーネルへの fallback です。対応経路で発生し得る検証・カーネルエラーは通常の MMVQ 呼び出しの処理であり、この環境変数固有の失敗処理ではありません（`src/kernels/cuda/native_mmvq.cu:3936-3957`）。

## 根拠

- 読み取りと master switch の既定: `include/strata/core/sm75_series.hpp:24-44`。
- 直接参照と Turing の呼び出し条件・cache: `src/kernels/cuda/native_mmvq.cu:3901-3927`。
- Turing 行数テーブルと形式: `src/kernels/cuda/native_mmvq.cu:3704-3714,3778-3791,3829-3860`。
- Verifier の上位ゲート、interleave、fallback: `src/core/verify.cpp:173-175,1491-1517,1551-1561,1791-1798,2452-2460`。
- HIP stub: `src/kernels/cuda/native_mmvq.cu:3960-3976`。
- 設計資料: `docs/DETAILS.md:1069-1079`, `docs/MMVQ_IL_TABLE.md:3-10`。
