# `STRATA_UMA_HEADROOM_GIB`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。作業開始時のブランチは `main`、作業ツリーに変更はありませんでした。外部ライブラリや GPU ドライバー自身の環境変数動作は対象外です。

## 役割

Linux 上の統合 GPU（CPU と GPU がシステム RAM を共有するデバイス）で、expert cache 用に Strata が見積もる空きデバイスメモリを調整します。実装は `/proc/meminfo` の `MemAvailable` からこの値の GiB 分を差し引き、その値が CUDA/SYCL ランタイムの空き量より大きければ、空き量の見積もりを引き上げます。未設定時に差し引く量は 6 GiB です。

この見積もりは expert cache の `auto` サイズ計算などに使われ、cache の確保前チェックにも使われます。環境変数は確保量を直接指定するものではなく、固定値の `--expert-cache N` を自動で変更もしません。

## 値と判定

両実装とも `std::strtol(h, &end, 10)` で基数10の整数に変換し、変換が1文字以上あり、文字列末尾まで消費され、値が `0..1024` の場合だけ採用します。小数や単位は受け付けません。先頭の空白と符号は `strtol` の規則で受け付けますが、数字の後ろの空白を含む余分な文字は拒否します。

| 環境変数の状態・値 | 採用される headroom | 動作 |
|---|---:|---|
| 未設定 | 6 GiB | 既定値を使用。警告なし |
| `0`、`+0`、`-0` | 0 GiB | `MemAvailable` の全量を候補にする |
| `6`、` 6`、`+6`、`001` | 指定整数 GiB | 文字列全体が整数として有効で、範囲内なら採用 |
| `1024` | 1024 GiB | 上限値として採用 |
| 空文字、`-1`、`1025`、`6.0`、`6GiB`、`6 ` | 6 GiB | stderr に `strata: STRATA_UMA_HEADROOM_GIB=<値> is not a whole number of GiB (0-1024): using 6` を出して既定値に戻る |

## 有効になる条件

- Linux で、ビルド時に `STRATA_HIP_GFX906` が定義されていないこと。
- 現在のデバイスを取得でき、その番号が `0..63` の範囲で、デバイス属性が統合メモリを示すこと。デバイス属性の判定結果はデバイスごとに `static` 配列へキャッシュされます。
- `/proc/meminfo` を開けること。`MemAvailable` 行が見つからない場合、読み取った kB 値は 0 のままで、見積もりは引き上げられません。

CUDA/HIP 実装は `cudaGetDevice` と `cudaDeviceGetAttribute(..., cudaDevAttrIntegrated, ...)` で判定します。gfx906 互換ビルドではこの処理全体が除外されます。SYCL 実装も Linux 条件を使い、DPCT の現在デバイス ID と `get_integrated()` で判定します。非 Linux、統合 GPU 以外、または条件を満たさないデバイスでは、この変数は読み取られず、ランタイムの空き量がそのまま使われます。

## 実行時の詳細

設定値はプロセス起動時ではなく、対象デバイスで `device_free_bytes()` が呼ばれ、かつ `/proc/meminfo` を開けた後に初めて評価されます。値は関数内の `static const long` に保存されるため、プロセス内で一度評価されると、その後の環境変更は反映されません。無効値の警告もこの初回評価時に一度だけ出ます。

実装は `avail = MemAvailable_kB << 10`、`head = headroom_GiB << 30` として計算します。`avail > head` かつ `avail - head > runtime_free_bytes` のときだけ、返す空き量を `avail - head` に置き換えます。したがって、これはランタイム値から常に差し引く reserve ではなく、統合メモリで OS が回収可能と報告する量を使って見積もりを上方補正する処理です。`MemAvailable - headroom` がランタイムの空き量以下なら、値を変えません。

呼び出し先では `--expert-cache auto` のスロット数計算に空き量を使います。expert cache の `open()` も割り当て前に同じ関数を呼び、要求サイズが見積もりを超える場合は確保を拒否します。別途、実際のデバイス割り当ても行われるため、この見積もりだけで確保成功が保証されるわけではありません。既存の `docs/STRIX_HALO.md` も、統合 GPU では `device_free_bytes()` が `MemAvailable` から通常 6 GiB を引いて使う旨を説明しています。資料にこの変数による性能測定値はなく、ここでは性能効果を主張しません。

## 根拠

- 値の取得、変換、既定値、警告、計算式、Linux/統合 GPU 条件（CUDA/HIP）: `src/core/expert_cache.cpp:28-69`。
- 同じ処理の SYCL 実装: `sycl/src/core/expert_cache.cpp:69-132`。
- 返された空き量を expert cache の割り当て前チェックに使う箇所: `src/core/expert_cache.cpp:481-503`、`sycl/src/core/expert_cache.cpp:605-633`。
- `--expert-cache auto` が空き量からスロット数を計算する箇所: `src/program/generate.cpp:4868-4913`、`sycl/src/program/generate.cpp:4327-4348`。
- 関数の役割に関する設計コメント: `include/strata/core/expert_cache.hpp:75-79`。
- 文書との照合: `docs/STRIX_HALO.md:15-17` は Linux の統合 GPU で `MemAvailable` を使い、`STRATA_UMA_HEADROOM_GIB` が既定の 6 GiB を変更すると説明しています。
