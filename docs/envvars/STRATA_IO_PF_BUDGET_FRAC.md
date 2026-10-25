# `STRATA_IO_PF_BUDGET_FRAC`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

Linux の file tier I/O prefetch scheduler が、decode window ごとに先読みする speculative read の自動バイト予算を調整します。実測した I/O worker の読み取り速度、worker 数、decode window の時間から見積もった読み取り可能量に、この割合と未使用先読み量に応じた feedback scale を掛けます。

## 値と判定

| 状態・入力 | `io_budget_frac_` の値 |
|---|---:|
| 未設定 | 既定値 `0.5` |
| 数値として読める値が `0.01` 未満 | `0.01` に clamp |
| `0.01` 以上 `4.0` 以下 | `std::atof` が変換した値 |
| 数値として読める値が `4.0` より大きい | `4.0` に clamp |
| 空文字、または数値変換できない文字列 | `std::atof` が返す `0.0` を `0.01` に clamp |

`std::atof` を使い、文字列全体の妥当性確認はしません。先頭の数値部分を変換し、後続文字は無視します（例: `0.8tail` は `0.8`）。先頭に数値がない文字列は `0.0` として扱われます。値は `set_io_prefetch()` の呼び出し時に読み取られ、同じ `FileExpertSource` の実行中に環境を書き換えても再読込されません。

## 有効になる条件

- Linux のビルドであること。`set_io_prefetch()` の I/O worker 実装と環境変数の読み取りは `__linux__` 条件内です。
- file tier の prefetch が有効で、`set_io_prefetch(true, ...)` が呼ばれること。mapped file tier でない場合、file mapping がない場合、または unbuffered 読み取りの場合は、この prefetch を開始しません。
- 予算を使った admission は `STRATA_IO_PF_SCHED` が非ゼロに変換される場合に限ります。未設定・空文字・`atoi` の結果が 0 の値では scheduler は無効で、通常の prefetch queue 経路となるため、この割合は予算に影響しません。scheduler 有効時は `warm_scored()` が予測 expert の confidence と window budget を使って job を採否します。
- `STRATA_IO_PF_BUDGET_MB` が正の値に変換されると、その固定 MB 予算が優先され、この変数の割合は予算計算に使われません。未設定時の固定予算は 0 です。

## 実行時の詳細

`set_io_prefetch()` はこの変数を `std::atof` で読み、結果を `[0.01, 4.0]` に clamp して `io_budget_frac_` に保存します。scheduler が有効で、固定 MB 予算が 0 の場合、`io_budget_now()` は worker の EWMA 読み取り速度 `io_bw_` × worker 数 × decode window 時間 `io_win_us_` × `io_budget_frac_` × feedback scale `io_scale_` を予算 bytes とします。速度または window 時間がまだ計測されていない間は `256 MiB` を返し、計測値に基づく予算は最低 `16 MiB` です。

`warm_scored()` はこの予算を使って window 内の先読み累積量を制限し、queue の byte pressure に応じて confidence の採用しきい値も上げます。decode window の切り替わりでは、先読み bytes に対する使用 bytes の割合を計測し、`STRATA_IO_PF_TARGET` と比較して `io_scale_` を縮小または回復させます。そのため、この変数は基準予算の割合を決めますが、実際の window 予算は worker 速度・window 長・別変数の固定予算・feedback にも依存します。

起動時に scheduler が有効なら stderr に `strata generate: io prefetch scheduling ON (STRATA_IO_PF_SCHED=1): a deadline per read, confidence admission (STRATA_IO_PF_MINCONF), a per-window byte budget (STRATA_IO_PF_BUDGET_MB / _FRAC)` が出ます。このログは個別の割合値を表示しません。

## 根拠

- `include/strata/core/expert_source.hpp:1146-1166` — scheduler の既定状態、`io_budget_frac_ = 0.5`、関連する予算状態。
- `src/core/expert_source.cpp:1045-1052` — 固定予算の優先、未計測時の `256 MiB` fallback、割合を含む自動予算式と `16 MiB` 下限。
- `src/core/expert_source.cpp:1055-1075` — decode window 時間と先読み利用率 feedback による scale 更新。
- `src/core/expert_source.cpp:1081-1112` — scheduler 経路での confidence と window byte budget による admission。
- `src/core/expert_source.cpp:1114-1165` — Linux 条件、file tier prefetch の前提、設定値の読み取り、scheduler 判定。
- `src/core/expert_source.cpp:1244-1257,3276-3291` — worker の読み取り速度計測と window tick。
- `src/program/generate.cpp:5655-5690` — generate 経路での file tier prefetch 起動条件と scheduler のログ。
