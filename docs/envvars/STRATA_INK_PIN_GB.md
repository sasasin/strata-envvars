# `STRATA_INK_PIN_GB`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

Inkling 2 Mini の CUDA 実装で、RAM 上に確保する host expert arena を CUDA の page-locked memory にするサイズ上限（GiB）を指定します。正の値は OS ごとの通常の pin 判定を置き換えて上限を設定し、`0` 相当の値は arena の pin を無効にします。これは host arena の確保方法だけを決め、expert を RAM / SSD に置く計画そのものは決めません。対象の読み取りは `InkHybridEngine::alloc_host_arena` のみです（`engine/src/inkling2/cuda/ink_hybrid.cuh:1524-1541`）。

CUDA 実装では arena が pin されると `cudaHostAlloc` を試み、成功時は `sec4_is_pinned` を立ててその領域を返します。後続の exact staging は pinned arena を必要とし、pageable の場合はその経路を使わず bounce buffer 経路になります（`engine/src/inkling2/cuda/ink_hybrid.cuh:1380-1382,1542-1547,2022-2038`）。この変数が生成 token や expert 選択を変更する処理は確認できません。

## 値と判定

値は `std::getenv` で読み、helper が未設定と空文字を通常の OS 別判定として扱います。空でない文字列は `std::atof` に渡され、変換結果が `n > 0.0` かどうかだけを判定します。文字列全体の数値検証はなく、`atof` が読める数値接頭辞を使います。その後 `n * 2^30` を `uint64_t` にキャストして GiB 上限にします（`engine/src/inkling2/cuda/ink_hybrid.cuh:1541`; `engine/include/strata/core/ink_pin_rule.hpp:22-34`）。

| 条件 | unset / 空文字 | pin を許可する値 | pin を許可しない値 |
|---|---|---|---|
| Windows、正の値を設定 | 該当なし | 変換値が正で、arena が `n GiB` 以下、かつ空き RAM が既知なら pin 後に 8 GiB 以上残る場合 | `0`、負数、数値に変換できない文字列、arena が上限を超える場合、または既知の空き RAM が 8 GiB の残量条件を満たさない場合 |
| Linux、正の値を設定 | 該当なし | 変換値が正で、arena が `n GiB` 以下の場合 | `0`、負数、数値に変換できない文字列、arena が上限を超える場合 |
| Windows、unset / 空文字 | 上限は `min(16 GiB, 空き RAM の 35%)`。空き RAM が不明（0）なら 8 GiB。加えて空き RAM が既知なら pin 後に 8 GiB 以上残す | arena が上限以下で、残量条件も満たす | arena が上限より大きい、または残量条件を満たさない |
| Linux、unset / 空文字 | 空き RAM が不明（0）、または arena が空き RAM の 45% 未満なら pin | 上記条件を満たす | 空き RAM が既知で arena が 45% 以上 |

比較はいずれも上限に対して `bytes > cap` で拒否し、Linux の既定値は `bytes < 0.45 * avail` なので等しい場合は pin しません。`atof("1.5GiB")` のように正の数値接頭辞がある文字列はその接頭辞で判定されます。`"1tail"` は 1 GiB、`"0anything"`、`"true"`、空白だけの文字列は pin 無効相当です。空文字だけは `atof` には渡らず unset と同じ規則です。大文字小文字を比較するフラグ判定ではありません。クランプや明示的な上限値の検証はありません（`engine/include/strata/core/ink_pin_rule.hpp:26-45`）。

## 有効になる条件

- CUDA backend の Inkling 2 Mini 経路で host expert arena のサイズが正であること。runner は `host_used > 0` または `uh > 0` の場合に `alloc_host_arena` を呼びます（`engine/src/inkling2/cuda/ink_runner.cuh:524-530,1420-1428`）。そのため arena が不要なモデル配置では読み取りません。
- Windows または Linux の CUDA ビルドであること。ビルド設定は NVIDIA CUDA backend plugin を定義しています（`engine/src/inkling2/cuda/CMakeLists.txt:1-7,56-65`）。この名前を読むのは CUDA ソースだけで、HIP / SYCL の読み取りはありません。Strata の `docs/SETTINGS.md:403` は適用先を「NVIDIA and AMD」としていますが、調査対象 commit の実装で確認できるのは CUDA 経路です。
- 別の CLI 引数や環境変数で pin 上限を上書きする処理は、この読み取り経路にはありません。正の値を設定しても `cudaHostAlloc` が失敗すれば pageable memory に切り替わります。

## 実行時の詳細

`alloc_host_arena` が呼ばれるたびに `std::getenv` を評価して helper に値を渡します。関数内 static などへのキャッシュはなく、環境変数を変更した後に新しい arena 確保が行われれば新しい値を読みます。リクエストごとの読み取りではありません（`engine/src/inkling2/cuda/ink_hybrid.cuh:1524-1541`）。

正の値が受理されると `cudaHostAlloc` を試し、成功時に pinned arena を返します。失敗時は CUDA error を `cudaGetLastError` で取得して捨て、`pinning failed (cudaHostAlloc), using pageable memory` を stderr に出して pageable allocation に進みます。判定で pin しない場合も理由付きの stderr 行を出し、Windows では `VirtualAlloc`、それ以外では `mmap` で pageable memory を確保します。pageable allocation が失敗すると null が返り、runner は `cannot allocate host expert arena` をエラーとして返します（`engine/src/inkling2/cuda/ink_hybrid.cuh:1542-1573`; `engine/src/inkling2/cuda/ink_runner.cuh:528-530,1427-1428`）。

この変数は SSD 専用 expert の pinned DMA ring など、`alloc_host_arena` 以外の pinned allocation を制御しません。SSD 用 ring は別途 `cudaHostAlloc` されます（`engine/src/inkling2/cuda/ink_runner.cuh:547-562`）。

## ログと測定値

判定で pageable に進む場合、stderr に `[InkHybrid] host expert arena %.2f GB not pinned (%s; available RAM %.1f GB): pageable memory with a pinned bounce ring` を出します。pin に成功すると `[InkHybrid] host expert arena %.2f GB pinned (%s; available RAM %.1f GB): the card reads the cold experts itself`、pin allocation に失敗すると `[InkHybrid] host expert arena %.2f GB: pinning failed (cudaHostAlloc), using pageable memory` を出します。続けて pageable allocation の試行を示す `[InkHybrid] host expert arena %.2f GB allocated as pageable RAM + pinned bounce ring (avail=%.1f GB)` も出ます。ソースにこの変数による性能測定値はありません（`engine/src/inkling2/cuda/ink_hybrid.cuh:1543-1554,1571-1572`）。

## 根拠

- `engine/include/strata/core/ink_pin_rule.hpp:22-45` — 値の変換、既定値、Windows / Linux の境界。
- `engine/src/inkling2/cuda/ink_hybrid.cuh:1524-1573` — 環境変数の読み取り、pin / pageable 分岐、ログ、確保失敗時の戻り値。
- `engine/src/inkling2/cuda/ink_runner.cuh:524-530,547-562,1420-1428` — arena を呼び出す条件、SSD ring との区別、呼び出し元の失敗処理。
- `engine/src/inkling2/cuda/ink_hybrid.cuh:1380-1382,2022-2038` — pinned arena を必要とする exact staging と pageable bounce 経路。
- `engine/src/inkling2/cuda/CMakeLists.txt:1-7,56-65` — CUDA backend plugin の範囲。
