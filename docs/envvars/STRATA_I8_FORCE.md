# `STRATA_I8_FORCE`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

SYCL の ESIMD int8 expert kernel が、現在のデバイスで実行可能かを判定するときに、そのデバイスを明示的に除外するための変数です。値を設定しても ESIMD や int8 DPAS をデバイスに追加するわけではありません。実際の int8 prompt 経路には、別途 `STRATA_PREFILL_MMQ`（未設定時は `STRATA_PF_I8`）のモード、expert の形式・形状、および kernel の利用可能性が関係します。

## 値と判定

`sycl/src/prefill/esimd_moe.dp.cpp` の `available()` は文字列を数値変換せず、環境変数の有無と先頭文字だけを調べます。

| 値 | `available()` による扱い |
|---|---|
| 未設定 | デバイス機能を検査する |
| 空文字 | デバイス機能を検査する（設定値は null ではなく、先頭文字は `\0`） |
| 先頭文字が `0` | そのデバイスを利用不可として返す。例: `0`, `0abc` |
| それ以外 | デバイス機能を検査する。例: `1`, `false`, ` 0` |

大文字小文字、数値としての妥当性、文字列全体は検査しません。したがって `false` は除外にならず、空白の後に `0` がある値も除外になりません。

## 有効になる条件

- この読み取りは `STRATA_I8_NO_ESIMD` が定義されていない `esimd_moe.dp.cpp` の実装で行われます。同 macro が定義されたビルドでは `available()` は常に `false` を返す stub であり、この環境変数を読まず、int8 kernel もありません（`sycl/src/prefill/esimd_moe.dp.cpp:40-60`）。
- 通常実装では、先頭文字 `0` による除外の後、デバイスが `sycl::aspect::ext_intel_esimd` を持つことと、int8 × int8、`nsize == 16`、`ksize == 32` の matrix combination があることを確認します。条件を満たさなければ `available()` は `false` です（同 `:835-853`）。
- この判定は Battlemage だけに限定されません。ただし `STRATA_PREFILL_MMQ` が未設定のときの既定モードは、`battlemage()` と `available()` の両方が true のデバイスでのみ int8 の auto mode になります。`STRATA_I8_FORCE` は Battlemage 判定を変えません（`sycl/src/prefill/prefill.cpp:282-287`, `sycl/include/strata/prefill/esimd_moe.hpp:30-50`）。
- `STRATA_PREFILL_MMQ`（または alias `STRATA_PF_I8`）が明示されて int8/auto モードになっても、kernel の呼び出し箇所は `available()` を要求します。対応する native expert 形式・形状でない場合や利用可能性が false の場合、対象 group はこの int8 経路に入りません（`sycl/src/prefill/prefill.cpp:4230-4236`）。

## 実行時の詳細

`available()` はデバイスごとの `unordered_map` に結果を保存し、mutex で保護します。各デバイスについて最初に呼ばれたときにだけ `STRATA_I8_FORCE` とデバイス機能を確認します。その後プロセス内で環境を書き換えても、同じデバイスのキャッシュ済み結果は更新されません（`sycl/src/prefill/esimd_moe.dp.cpp:835-853`）。

int8 経路のモードが有効な場合、初期化時に stderr へ `strata: int8 prompt experts are on (...)` が出ます。各 expert format/shape で int8 経路を使ったかどうかは、必要な場合に `... -> int8 path yes/no` と出ます。`STRATA_I8_FORCE` 自体を示す専用ログはありません（`sycl/src/prefill/prefill.cpp:1205-1210,4237-4242`）。

## 根拠

- `sycl/src/prefill/esimd_moe.dp.cpp:40-60,835-853` — ESIMD なしの stub、先頭文字判定、SYCL feature / DPAS combination の検査、デバイス単位の結果キャッシュ。
- `sycl/src/prefill/prefill.cpp:282-287,4230-4242` — 既定モードと明示モード、利用可能性を含む実際の prompt kernel 選択、stderr ログ。
- `sycl/include/strata/prefill/esimd_moe.hpp:30-50` — `available()` と Battlemage 既定選択の区別。
- `docs/INTEL_INT8_EXPERTS.md:25,40-45` — Strata の設計資料も `STRATA_I8_FORCE=0` を kernel からのデバイス除外として説明し、非対応時の FP16 fallback を記載しています。値の細かな判定規則は上記ソースに基づきます。
