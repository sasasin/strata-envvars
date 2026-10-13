# `STRATA_PIN_GUARD`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

Linux の `FileExpertSource` が resident RAM に置く expert cache complement を page-lock するとき、メモリを一度に確保するか、RAM の空きに応じて段階的に page-lock するかを選びます。通常の guarded 動作では、空き RAM が不足すると Strata 自身が読み込んだモデルファイルの cache を解放して再確認し、それでも不足する場合に段階処理へ移ります。`STRATA_PIN_GUARD=2` は段階処理を常に選びます。

この分岐は `src/core/expert_source.cpp` の `FileExpertSource::pin_cache_complement()` にあります。`--resident-experts` または `--resident-budget-gib` で resident mode を選び、`STRATA_RESIDENT_PIN=0` で pin を無効化していないときにだけ関係します。`--resident-cpu-experts` のように `pin` が false の場合、この変数は読み取られません。

## 値と判定

Linux かつ `pin` が有効で complement のサイズが正の場合、関数内の `static const int` として最初の該当呼び出し時に一度だけ読み取られます。未設定なら `1`、設定されていれば `std::atoi()` の結果を使います。文字列全体の検証はしません。

| 値 | 動作 |
|---|---|
| 未設定 | `1` として通常の guarded 動作。 |
| `atoi()` の結果が `0` | guard を無効化し、モデルファイル cache の解放判定や段階 page-lock を行わず、通常の一括 `cudaHostAlloc()` に進む。空文字、数値で始まらない文字列も通常は 0 になる。 |
| `atoi()` の結果が `2` | 空き RAM の事前判定を省いて段階処理を強制し、`FileExpertSource: STRATA_PIN_GUARD=2: page-locking the complement in steps` を stderr に出す。 |
| その他の非 0 | 通常の guarded 動作。たとえば `1`、`-1`、`3` は同じ分岐。数値の後ろは無視されるため `2extra` は 2、`1extra` は 1 として扱われる。 |

`atoi()` の結果が 0 でも page-lock 自体を無効にする設定ではありません。無効になるのはこの guard による事前処理と段階化で、一括 `cudaHostAlloc()` は引き続き試みられます。

## 有効になる条件

- `pin_cache_complement()` に渡される `pin` が true で、RAM に置く complement が存在すること。`generate.cpp` では `--resident-experts` と `--resident-budget-gib` が pin を有効にし、どちらも環境変数 `STRATA_RESIDENT_PIN=0` があれば false にします。
- OS が Linux であること。変数を読む箇所と段階化の分岐は `#if defined(__linux__)` 内です。Windows の page-lock/commit 処理にはこの分岐はありません。
- `STRATA_PIN_RESERVE_GIB` は段階処理の各 step で残す RAM の量に関係します。`atof()` が正の値なら GiB を byte に換算して使い、それ以外（未設定、空、0、負数、数値に変換できない文字列）は `max(headroom_bytes, 2 GiB)` を使います。これは guard の値判定とは別の変数です。

## 実行時の詳細

既定の `guard != 0` では、Strata は `/proc/meminfo` の `MemFree` と NUMA node ごとの `MemFree` を読み、最も厳しい空き量を使います。測定できない場合は guarded の不足判定をせず、一括 page-lock 側へ進みます。空き量が complement と reserve の合計を下回る場合、Strata が mmap したモデルファイルについて `madvise(MADV_DONTNEED)` と `posix_fadvise(POSIX_FADV_DONTNEED)` を試し、`MemFree` を再確認します。再確認後も不足する場合に段階処理を選びます。

段階処理では、通常メモリを 1 GiB ずつ page fault させる前に、cgroup の余裕も考慮した `host_available_memory` がその step と reserve の合計以上かを確認します。RAM が足りなくなるか page-lock に失敗するとそこで止め、取れた prefix を一度に CUDA に登録します。登録範囲は expert blob の境界に合わせます。残りは resident だが pageable のままとなり、stderr に `WARNING: only ... could be page-locked (...)` の行が出ます。全量を登録できた場合は段階処理で page-lock した GiB 数を出します。

`STRATA_PIN_GUARD=2` は `MemFree` による事前判定とモデルファイル cache 解放を通らず段階処理へ進みます。ただし各 step の空き RAM 確認は行います。guard を無効にした場合や guarded 判定で不足がない場合は一括 `cudaHostAlloc()` を試します。page-lock を使えない残りのコピーは pageable のままとなり、Troubleshooting 文書はその GPU コピーが CPU 経由になると説明しています。

値は関数内の static に保存されます。同じプロセスで最初の該当呼び出し後に環境変数を変更しても再評価されません。段階処理時の reserve は呼び出しごとに読み取られます。

## 根拠

- 値の読み取り、既定値、`atoi()`、Linux 条件、`guard==2` と不足時の分岐、ログ: `src/core/expert_source.cpp:2817-2858`。
- `MemFree` / NUMA node 読み取りと測定できない場合の扱い: `src/core/expert_source.cpp:437-464`。
- 1 GiB step の空き確認、登録範囲の expert 境界合わせ、部分 pin 時の警告: `src/core/expert_source.cpp:2926-2981`。
- reserve の値と fallback: `src/core/expert_source.cpp:2828-2832`。
- resident mode と `STRATA_RESIDENT_PIN=0` による pin 無効化、`pin_cache_complement()` 呼び出し: `src/program/generate.cpp:2113-2132,6723-6733`。
- Strata の説明では、`STRATA_PIN_GUARD=0` が段階 page-lock を無効化し、pageable 部分の GPU コピーは CPU 経由になります。また `STRATA_PIN_RESERVE_GIB` の既定を resident headroom（4 GiB）と記しています。コード上は reserve の下限が 2 GiB で、実際には `headroom_bytes` との大きい方です: `docs/TROUBLESHOOTING.md:113-120`, `docs/DETAILS.md:1046-1052`, `src/core/expert_source.cpp:2826-2832`。
