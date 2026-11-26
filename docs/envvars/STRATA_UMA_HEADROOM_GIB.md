# `STRATA_UMA_HEADROOM_GIB`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-26 時点）。

## 役割

Linux の統合 GPU（CPU と GPU がシステム RAM を共有するデバイス）について、Strata がモデル用メモリを見積もる際にシステム用として差し引く GiB 数を指定する。既定値は 6 GiB。GPU の空き容量を元に expert cache などを計画する値であり、割り当てをこの量に固定する設定ではない。通常のデバイス空き容量見積もりは CUDA runtime 系（CUDA/HIP 互換実装を含む）では `device_free_bytes()`、SYCL では `uma_free_bytes()` が行う（`engine/src/core/expert_cache.cpp:99-100,115-150`; `engine/sycl/src/core/expert_cache.cpp:120-148`）。

## 値と判定

両実装とも `std::getenv` で取得し、`std::strtol(..., 10)` で 10 進整数に変換する。変換後に少なくとも 1 文字を消費し、文字列末尾まで読み切り、値が `0..1024` の場合だけ採用する。したがって先頭・末尾の空白は `strtol` の規則上、先頭空白は許されても末尾空白は不許可。`+` 符号と先頭ゼロは許され、`-0` は数値 0 として許される。負の値、1024 を超える値、空文字、数字の後ろに文字がある値（例 `0anything`）、数値として読み取れない値は無効。桁あふれも範囲判定により無効になる。無効値では 6 GiB に戻し、stderr に警告する（`engine/src/core/expert_cache.cpp:137-146`; `engine/sycl/src/core/expert_cache.cpp:88-100`）。

| 条件 | 未設定 | 有効値の例 | 無効値の例 |
| --- | --- | --- | --- |
| 両実装で読み取りに到達 | 6 GiB、警告なし | `0`, `+6`, `001`, `1024` | ``, `-1`, `1025`, `0anything`, `6 ` |

空文字は「設定あり」だけでは有効にならず、変換に失敗して既定値になります。無効値の警告は `strata: STRATA_UMA_HEADROOM_GIB=%s is not a whole number of GiB (0-1024): using 6`。読み取り箇所で `static` に保存されるため、最初の評価後にプロセス環境を変更しても反映されない。CUDA/HIP 系は Linux 上で統合デバイスと判定され、`/proc/meminfo` を開けたときに初めて評価する。SYCL 系は Linux 上で統合デバイスのメモリ見積もりが呼ばれ、`/proc/meminfo` を読めたときに評価する（同上）。

## 有効になる条件

- Linux であること。通常の CUDA/HIP 系実装は `__linux__` 条件内にあり、`STRATA_HIP_GFX906` では統合判定部分を除外する（`engine/src/core/expert_cache.cpp:115-152`）。
- CUDA/HIP 系では現在選択中のデバイスが `cudaDevAttrIntegrated` により統合 GPU と判定されること。そこでは `/proc/meminfo` の `MemAvailable` から headroom を差し引き、結果が `cudaMemGetInfo` の空き値より大きい場合だけその値を採用する（`engine/src/core/expert_cache.cpp:115-150`）。この経路は `STRATA_UMA` による上書きを参照しない。
- SYCL 系では `device_unified_memory()` が統合 GPU と判定すること。`STRATA_UMA=1` はこの判定を強制でき、`STRATA_UMA=0` はカード扱いにする。未設定または空の `STRATA_UMA` はデバイス判定に委ねる（`engine/sycl/src/core/expert_cache.cpp:67-85`; `engine/sycl/include/strata/core/uma.hpp:28-29`）。
- 統合 GPU の値見積もりには `/proc/meminfo` の `MemAvailable` が必要。SYCL は読めない場合に `uma_free_bytes()` から 0 を返し、headroom 値の読み取り・ログも行わない（`engine/sycl/src/core/expert_cache.cpp:107-117,124-128`）。CUDA/HIP 系は読めない場合に `MemAvailable` に基づく差し替えをせず、先に得た `cudaMemGetInfo` 値を返す（`engine/src/core/expert_cache.cpp:130-150`）。
- `--expert-cache auto` の容量計画では空き値が slot 数の算出に使われる。明示した `--expert-cache N` も ExpertCache の割り当て前チェックが `device_free_bytes()` を比較に使うため、統合 GPU では見積もりに影響する（CUDA/HIP: `engine/src/program/generate.cpp:9077-9085,9224-9249`; SYCL: `engine/sycl/src/program/generate.cpp:4823-4853`; `engine/src/core/expert_cache.cpp:617-638`; `engine/sycl/src/core/expert_cache.cpp:653-680`）。CLI 引数が環境変数の数値を上書きする処理はない。
- SYCL では `--expert-cache auto`、単一 GPU、`--stream-experts`、GGUF source、`STRATA_VERIFY_NO_HOST` 有効、明示的な非ゼロ `STRATA_MIRROR_MIB` なし、かつ cache が全 expert を保持できない場合、起動を refusal する。診断に headroom の値も表示される（`engine/sycl/src/program/generate.cpp:5205-5226`）。

## 実行時の詳細

CUDA/HIP 系は `device_free_bytes()` の呼び出しごとに現在の `MemAvailable` を読む。headroom の数値だけは最初の該当呼び出しで `static const long` にキャッシュする。空き値は通常 `cudaMemGetInfo` の値だが、統合 GPU かつ `/proc/meminfo` 読み取り成功時は `max(cudaMemGetInfo free, MemAvailable - headroom)` となる。ただし `MemAvailable <= headroom` の場合は RAM 側の値を作らない（`engine/src/core/expert_cache.cpp:99-150`）。この値を `--expert-cache auto` は reserve 等を差し引く slot 数計算に使い、profile があると profile 内の数を上限にする（`engine/src/program/generate.cpp:9077-9085,9202-9249`）。

SYCL は `uma_free_bytes(total_b)` ごとに `/proc/meminfo` の `MemAvailable` と `GPUReclaim` を読み、`max(available + pooled - headroom, 0)` を計算し、デバイスの global memory を上限にする。headroom の数値は最初の `uma_free_bytes()` 到達時に static cache される（`engine/sycl/src/core/expert_cache.cpp:88-100,107-138`）。この空き量は `device_free_bytes()` および ExpertCache の容量チェックに渡る（`engine/sycl/src/core/expert_cache.cpp:144-148,653-680`）。

いずれも環境変数は Strata のプロセス内で読み、子プロセスへ転送する実装はこの変数について見つからない。headroom を下げると見積もり上のモデル用余地が増え、上げると減る。これは cache 容量計画・割り当て可否の入力を変えるもので、メモリが実際に確保できることを保証しない。SYCL の `--expert-cache auto` で共有メモリにモデル全体が収まらず、上記 refusal 条件を満たす場合は終了コード 2 で refusal する（`engine/sycl/src/program/generate.cpp:5213-5226`）。

## ログと測定値

無効値を初めて評価したとき、両実装は次を stderr に出して既定の 6 GiB を使う（`engine/src/core/expert_cache.cpp:142-145`; `engine/sycl/src/core/expert_cache.cpp:94-98`）。

```text
strata: STRATA_UMA_HEADROOM_GIB=<値> is not a whole number of GiB (0-1024): using 6
```

SYCL は `uma_free_bytes()` の最初の呼び出し時、メモリ見積もり成功時に次の形式で stderr に一度表示する。値は実行時の RAM / GPUReclaim 見積もりであり、性能測定値ではない（`engine/sycl/src/core/expert_cache.cpp:124-138`）。

```text
strata: integrated GPU, one pool of memory with the system: ... GiB of RAM available..., ... GiB kept free for the system (STRATA_UMA_HEADROOM_GIB) -> ... GiB for the model
```

CUDA/HIP 系には headroom の通常値を示す専用ログはない。SYCL の上記 refusal 条件では `STRATA_UMA_HEADROOM_GIB` を含む診断が stderr に出て終了コード 2 となる（`engine/sycl/src/program/generate.cpp:5213-5226`）。

## 根拠

- `engine/src/core/expert_cache.cpp:99-152` — CUDA/HIP 系の空き値計算、Linux / 統合デバイス条件、parse と fallback。
- `engine/sycl/src/core/expert_cache.cpp:67-100,107-148` — SYCL の統合判定、parse、RAM 見積もりとログ。
- `engine/sycl/include/strata/core/uma.hpp:28-43` — `STRATA_UMA` 判定と共有メモリ余地の clamp。
- `engine/src/core/expert_cache.cpp:617-638`、`engine/sycl/src/core/expert_cache.cpp:653-680` — ExpertCache 割り当て前の容量確認。
- `engine/src/program/generate.cpp:9077-9085,9224-9249`、`engine/sycl/src/program/generate.cpp:4823-4853` — 自動 expert cache の free-memory 取得と slot 数計画。
- `engine/sycl/src/program/generate.cpp:5205-5226` — 統合 GPU でのモデル容量不足 refusal と観測可能な終了経路。
