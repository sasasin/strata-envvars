# `STRATA_UMA_HEADROOM_GIB`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-02 時点）。

## 役割

Linux の統合 GPU で、エンジンが使える GPU メモリ量を見積もる際に、`/proc/meminfo` の `MemAvailable` から差し引くシステム用 headroom（GiB）を指定します。CUDA/HIP 互換実装と SYCL 実装の `device_free_bytes()` がこの値を読みます。離散 GPU、Windows、macOS ではこの読み取り経路に入りません。

この見積もりは `--expert-cache auto` の slot 数計算に使われます。また、明示した `--expert-cache N` のサイズを実際のキャッシュ確保前に照合する検査にも使われます。変数自体が CLI 値を上書きしたり、明示サイズを自動で縮めたりはしません。

## 値と判定

値は `std::strtol(h, &end, 10)` で基数10の `long` に変換し、変換が1文字以上進み、終端まで消費され、`0 <= v <= 1024` の場合だけ採用します。未設定時は 6 GiB です。設定値が無効なら 6 GiB に戻し、stderr に次の警告を一度出します。

```text
strata: STRATA_UMA_HEADROOM_GIB=<値> is not a whole number of GiB (0-1024): using 6
```

| 入力 | 判定 |
|---|---|
| 未設定 | 6 GiB。警告なし |
| `0` ～ `1024` の整数表記 | その GiB 数を採用。`0` は差し引きなし |
| 空文字、範囲外、整数として最後まで読めない文字列 | 6 GiBへ fallback し、警告 |

変換は `strtol` のため先頭空白と符号は受け付けます（例: ` +2`）。数値の後ろに空白や文字が残る値（例: `2 `、`2GiB`）は無効です。小数、部分変換、値の丸めや clamp はありません。

## 有効になる条件

- Linux であること。
- 現在の GPU が統合 GPU と判定されること（CUDA/HIP 互換側は `cudaDevAttrIntegrated`、SYCL 側は DPCT の `get_integrated()` を使用）。CUDA/HIP 互換実装では `STRATA_HIP_GFX906` ビルドを除きます。
- `/proc/meminfo` を開けること。このファイルを開けない場合、環境変数も読みません。

GPU が統合 GPU でも、`/proc/meminfo` から得た `MemAvailable - headroom` が GPU API の空き量以下なら、返す空き量は変わりません。反対に、残量が GPU API の値を超える場合にだけ、見積もりをその残量まで引き上げます。つまり headroom を大きくすると見積もりを増やすのではなく、OS に残す分を増やして見積もりを抑えます。

Linux HIP の `--expert-cache auto` では、後段で `STRATA_UMA_RESERVE_GIB` に基づく host RAM の上限も適用されます。そちらの上限がこの変数による GPU 空き見積もりより小さければ、auto sizing ではその上限が使われます。SYCL の auto sizing にはこの HIP 固有の後段処理はありません。

## 実行時の詳細

`device_free_bytes()` は GPU API の空き量を読み、Linux で統合 GPU の場合に `/proc/meminfo` の `MemAvailable` を kB 単位で読みます。変数値を GiB から byte に直し、`MemAvailable` が headroom を上回り、差し引き後の量が GPU API の値を上回る場合に、その値で free bytes を更新します。これはカーネル側のメモリ制限を設定する処理ではなく、Strata のメモリ見積もりです。

読み取り値は関数内の `static const long` に保存されます。プロセス内で最初に統合 GPU 分岐から `/proc/meminfo` を読んだ時点で一度だけ評価され、その後に環境を変更しても再読込されません。統合 GPU 分岐に入らない実行では初期化されません。

CUDA/HIP 互換実装では `--expert-cache auto` がこの free bytes から予約領域などを引き、キャッシュ slot 数を計算します。Linux HIP の追加 RAM 制限を含む流れと auto のログは `src/program/generate.cpp:6870-6901,6942-6973` にあります。SYCL も `--expert-cache auto` の計算に同じ関数を使います（`sycl/src/program/generate.cpp:4611-4632`）。キャッシュを明示した場合は auto sizing されませんが、確保前の `ExpertCache::open()` が同じ free bytes と要求 byte 数を比較し、足りなければ `ExpertCache: ... Lower --expert-cache.` を返して生成側の開始を失敗させます（CUDA/HIP: `src/core/expert_cache.cpp:560-594`、SYCL: `sycl/src/core/expert_cache.cpp:610-646`）。

auto sizing で slot が0になる場合、生成側は `no VRAM is left for the expert cache` を stderr に出します（CUDA/HIP: `src/program/generate.cpp:6994-7003`、SYCL: `sycl/src/program/generate.cpp:4661-4681`）。通常の auto sizing ログは `expert cache auto: ... GiB free ... -> ... slots` で、headroom を適用した後の値を表示します。

## 根拠

- `src/core/expert_cache.cpp:98-138`: CUDA/HIP 互換実装の GPU 統合判定、Linux 条件、`/proc/meminfo` 読み取り、値の parse、headroom 適用。
- `sycl/src/core/expert_cache.cpp:69-145`: SYCL 実装の同等処理。
- `src/core/expert_cache.cpp:560-594`, `sycl/src/core/expert_cache.cpp:610-646`: 実際のキャッシュ確保前に free bytes を使って要求量を検査する経路。
- `src/program/generate.cpp:6870-6901,6942-6973`, `sycl/src/program/generate.cpp:4611-4632`: auto cache sizing とログ。Linux HIP の追加 RAM 上限は `include/strata/core/uma_cache.hpp:16-31` と `src/program/generate.cpp:6877-6901`。
- `include/strata/core/expert_cache.hpp:75-81` と `docs/STRIX_HALO.md:101-103` は統合 GPU での空きメモリ見積もりと既定 6 GiB を説明しています。
