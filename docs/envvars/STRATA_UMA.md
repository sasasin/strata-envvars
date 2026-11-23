# `STRATA_UMA`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

SYCL エンジンで、現在の GPU をシステム RAM と一つのメモリプールを共有する統合 GPU（UMA）として扱うか、カードとして扱うかを上書きする。設定すると検出結果をすべてのデバイスに対して上書きするが、GPU の物理的なメモリ構成自体は変更しない。統合 GPU 扱いの場合、空きメモリの計算に Linux の `/proc/meminfo` を使い、キャッシュ予算や関連する分岐に反映する（`engine/sycl/include/strata/core/uma.hpp:13-15,25-29`、`engine/sycl/src/core/expert_cache.cpp:67-85,120-138,145-148`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Linux かつ `STRATA_HIP_GFX906` 未定義の SYCL エンジン | デバイス属性による判定 | 空でない値で先頭文字が `0` 以外なら UMA 扱い（例: `1`, `true`, `off`, ` 0`） | 空でない値で先頭文字が `0` ならカード扱い（例: `0`, `0anything`, `00`） |
| Linux 以外、または `STRATA_HIP_GFX906` 定義時 | カード扱い | 上書きは読まれず、カード扱い | 上書きは読まれず、カード扱い |

実装は `getenv` が返す文字列の先頭一文字だけを検査する。未設定（null）と空文字はどちらもデバイス判定に委ねる。空白除去、数値変換、文字列全体の比較、大文字小文字の検査はない。このため `false` や `off` も UMA 扱い、`0.5` はカード扱いとなる（`engine/sycl/include/strata/core/uma.hpp:28-29`）。

## 値と判定

| ビルド・実行条件 | unset / 空文字 | 有効になる値 | 無効になる値 |
|---|---|---|---|
| Linux、SYCL、`STRATA_HIP_GFX906` 未定義 | 現在のデバイス属性を使う | 先頭文字が `0` 以外の任意の非空文字列。例: `1`, `true`, `false`, ` 0` | 先頭文字が `0` の任意の非空文字列。例: `0`, `0anything`, `00` |
| それ以外 | 常にカード扱い | 該当なし（この分岐では環境変数を参照しない） | 該当なし |

判定は `uma_override()` の `v[0] != '0'` のみで行うため、たとえば `1abc` も UMA 扱い、`0anything` もカード扱いである。値の境界は文字列の先頭一文字であり、数値の範囲はない（`engine/sycl/include/strata/core/uma.hpp:28-29`）。

## 有効になる条件

- この実装は `engine/sycl/` の SYCL エンジンにある。通常の CUDA/HIP エンジンの同名変数読み取りは見つからなかった。SYCL は独立したビルド経路で、`STRATA_ENABLE_SYCL` 時に `engine/sycl` を追加し、その後通常の CUDA/HIP ビルド設定を通らない（`engine/CMakeLists.txt:23-33`、`engine/sycl/CMakeLists.txt:290-301`）。
- 上書き値を使うのは Linux かつ `STRATA_HIP_GFX906` が未定義のときだけ。それ以外は関数が `false` を返し、環境変数は読み取られない（`engine/sycl/src/core/expert_cache.cpp:70-85`）。
- 統合 GPU 扱いの効果を利用するのは、モデル開始処理などから `device_unified_memory()` / `device_free_bytes()` を通るとき。自動 expert cache（`--expert-cache auto`、または expert profile 指定時の `--expert-cache 0`）では空き量を使って slot 数を算出する。固定 slot 数はこの変数で変更されないが、割当可能量の検査・サイズ調整に影響する経路がある（`engine/sycl/src/program/generate.cpp:3787-3790,4829-4853,4875-4882,4969-4985`）。CLI の cache 設定が変数値を直接上書きする処理はない。
- UMA 扱いでも `/proc/meminfo` を開けない場合、`uma_free_bytes()` は `0` を返す。その場合、自動 cache の空き量計算も 0 から始まる（`engine/sycl/src/core/expert_cache.cpp:107-117,124-128`）。
- `STRATA_UMA_HEADROOM_GIB` は UMA 扱い時のメモリ見積もりから差し引く余白を変える別変数である。`STRATA_VERIFY_NO_HOST`、`--stream-experts`、モデル入力形式などの組み合わせは、cache がモデル全体を収容できない場合の拒否経路を左右する（`engine/sycl/src/core/expert_cache.cpp:124-138`、`engine/sycl/src/program/generate.cpp:5201-5214`）。

## 実行時の詳細

`device_unified_memory()` の最初の呼び出しで `std::getenv("STRATA_UMA")` を `static const int forced` に保存する。したがって、起動後に環境変数を変更しても同一プロセス内では反映されない。空または未設定なら、現在のデバイスの `get_integrated()` 結果をデバイス ID ごとの `static std::atomic<int> uma_cache[64]` に保存する。0〜63 の device ID が対象で、取得失敗または範囲外の ID はカード扱いになる。明示した上書きはこのデバイス属性キャッシュより先に返る（`engine/sycl/src/core/expert_cache.cpp:70-85`）。

UMA と判定されると、`device_free_bytes()` は `/proc/meminfo` から `MemAvailable` と、存在すれば `GPUReclaim` を読み、`STRATA_UMA_HEADROOM_GIB` 相当の余白を差し引き、デバイスの global memory size を上限として返す。ファイルを読めない場合は 0。カード扱いなら SYCL device の memory-info を使う（`engine/sycl/src/core/expert_cache.cpp:102-117,120-148,150-179`）。この空き量は自動 cache の slot 数計算に使われ、統合メモリ判定は大きな context の KV streaming 判定や、expert の pinned host mirror の既定量・UMA 用の上限計算にも使われる（`engine/sycl/src/program/generate.cpp:4240-4253,4829-4882,5440-5473`）。

`--expert-cache auto` は CLI 値を `-1` として設定し、自動計算経路に入る。expert profile 指定時は `--expert-cache 0` も `-1` に正規化される。一方、環境変数は cache 自体を有効化せず、固定の `--expert-cache N` の値も書き換えない（`engine/sycl/src/program/generate.cpp:2002-2005,3787-3790,4829-4853`）。

## ログと測定値

UMA と判定され、`/proc/meminfo` が読めて `uma_free_bytes()` に到達すると、プロセス内で一度だけ stderr に `strata: integrated GPU, one pool of memory with the system: ...` から始まるメモリ内訳を出す。`GPUReclaim` が正なら、以前のロードから GPU driver が保持する量も表示する。カード判定、非 Linux 分岐、または `/proc/meminfo` の読み取り失敗時にはこのログは出ない（`engine/sycl/src/core/expert_cache.cpp:107-138`）。

`--expert-cache auto` の計算結果は stderr の `strata generate: expert cache auto: ... -> ... slots` に出る。UMA 扱いで `--stream-experts` と `STRATA_VERIFY_NO_HOST` などの条件を満たし、全 expert が cache に入らない場合は stderr に `strata generate: REFUSED: this model does not fit in the memory the integrated GPU shares with the system: ...` を出して終了コード 2 で拒否する（`engine/sycl/src/program/generate.cpp:4880-4882,5201-5214`）。

## 根拠

- `engine/sycl/include/strata/core/uma.hpp:13-15,25-29` — 宣言、値の判定規則。
- `engine/sycl/src/core/expert_cache.cpp:67-85` — OS / macro 条件、上書きとデバイス属性の cache。
- `engine/sycl/src/core/expert_cache.cpp:102-138,145-179` — UMA 時の RAM 空き量・余白・ログとカード側 fallback。
- `engine/sycl/src/program/generate.cpp:2002-2005,3787-3790,4829-4882` — CLI 値の正規化と自動 cache サイズ計算。
- `engine/sycl/src/program/generate.cpp:4240-4253,5201-5214,5440-5473` — KV streaming 判定、拒否条件、mirror sizing への適用。
- `engine/CMakeLists.txt:23-33`、`engine/sycl/CMakeLists.txt:290-301` — SYCL が独立したビルド経路であること。
