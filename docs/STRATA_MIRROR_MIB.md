# `STRATA_MIRROR_MIB`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。

## 役割

SYCL 版 `strata generate` の `--stream-experts` 経路で、VRAM の expert cache に入らない expert を pinned host memory（SYCL USM host allocation）へ先読みする量の上限を MiB 単位で指定します。mirror address は device-built verify plan に渡され、`STRATA_VERIFY_DEVICE_PLAN` が有効で、その plan が device 計画する miss を処理するとき GPU が PCIe 経由で読めます。プロンプト経路も、mirror にある expert は SSD から毎回読む代わりに mirror から DMA できます。

CUDA/HIP の通常経路にこの変数の読み取りはありません。これは一般的な host arena のサイズ設定ではなく、native pack の expert をストリームする場合の SYCL mirror 上限です。

## 値と判定

| 値 | cap の扱い |
|---|---|
| 未設定 | `/proc/meminfo` の `MemAvailable` から 4 GiB を引いた値。`MemAvailable` が 4 GiB 以下、または読み取りに失敗した場合は 0。 |
| 設定あり | `std::atoll(value)` の結果を `uint64_t` に変換し、20 bit 左シフトする（MiB 換算）。 |
| 空文字・数値に変換できない文字列 | `atoll` が 0 を返すため cap は 0。mirror しない。 |
| 数字の後ろに文字が続く値 | 数字の prefix だけが `atoll` で変換される。例: `512junk` は 512 MiB。文字列全体の検証はない。 |
| 負数 | 符号付き `atoll` の結果を unsigned に変換してからシフトするため、0 にはならず非常に大きな cap になる。負数を無効化手段として扱わない。 |

先頭空白と符号は `atoll` の変換規則に従います。値の読み取りは mirror 構築時の一度だけで、static cache ではありませんが、同じ起動処理で後から環境を変えて再評価する経路はありません。

cap は割り当てる上限であり、要求した MiB 数を必ず確保する指定ではありません。expert ごとのサイズを 256 byte 境界に丸め、候補の順に追加し、次の expert 全体が cap を超える時点で打ち切ります。expert の一部だけを mirror することはありません。

## 有効になる条件

この変数が参照されるのは、すべての条件を満たす場合だけです。

- `--stream-experts` が指定されている。
- expert source が GGUF source で、`--expert-cache` が正数。
- `--stream-experts` の source 初期化では native (IQ) pack と `--native SHARD1` が必要。満たさない場合、起動時にエラーを出して終了する。
- 候補 expert があり、計算された cap が正数。

`--stream-experts` なし、または expert cache が 0 の場合、この環境変数の値は読み取られません。layer split では mirror 候補を最初の GPU の layer（`split_at[0]` まで）に限ります。残りの GPU の layer の miss はこの mirror には含みません。

候補の順番は、まず profile に載った非 resident expert（profile 順）、次に profile にない非 resident expert、最後に条件を満たした prompt loan 用の cache tail の expert です。従って cap が足りないと、通常の miss を優先し、loan 用の追加分が先に省かれます。loan 用候補は `--no-prefill-borrow` がなく、`--prefill-chunk > 0` で、単一 GPU の場合に追加されます。`STRATA_LEND_MIRROR` は追加する tail slot 数を変えます。

## 実行時の詳細

起動時に `/proc/meminfo` を開き、`MemAvailable:` の kB 値を byte に換算します。未設定時の既定 cap は空きメモリ全量ではなく、その値から 4 GiB を差し引いたものです。明示値は `atoll` 後に MiB から byte へ換算されます。

`GgufExpertSource::mirror()` は候補を cap 内で選び、最大 2 GiB 単位の pinned host chunk を割り当てます。expert blob は 8 thread で GGUF から読み込まれます。割り当てまたは読み取りに失敗すると負値を返し、呼び出し側は `mirroring the experts missing from VRAM: ... (they stay on the SSD)` を stderr に出して処理を続けます。成功時は mirror した個数・容量・所要時間を stderr に出し、device-readable address の表を作って verify plan に設定します。

mirror に入らなかった expert は引き続き SSD 側に残ります。`STRATA_VERIFY_NO_HOST` は空でなく、文字列全体が `0` と異なる場合に有効です。これが有効で未 mirror の miss がある場合は、呼び出し側が `REFUSED: ... raise STRATA_MIRROR_MIB or the free RAM, or lower --max-context` を stderr に出し、終了コード 2 で生成を拒否します。未 mirror miss がない場合や `STRATA_VERIFY_NO_HOST` が有効でない場合はこの拒否分岐に入りません。有効値の扱いは `sycl/src/program/generate.cpp:4836-4843` を参照してください。

`docs/INTEL.md` は、mirror が VRAM 外 expert の GPU 読み取りに使われる構成例と、A750 で大きな単一 host allocation が失敗した測定例を記載しています。現行実装は最大 2 GiB ごとに chunk 化しています。資料の測定値は特定の Arc A750 環境での報告であり、他機種の確保可能量を示すものではありません。

## 根拠

- `sycl/src/program/generate.cpp:4767-4776` — mirror の目的、デフォルト cap の説明、起動時の適用範囲と layer split の上限。
- `sycl/src/program/generate.cpp:4777-4803` — 候補の並び、非 resident expert と prompt loan slot の選定条件。
- `sycl/src/program/generate.cpp:4805-4816` — `MemAvailable` 読み取り、4 GiB 差し引き、`atoll` と MiB 換算、mirror 呼び出し。
- `sycl/src/program/generate.cpp:4817-4852` — 失敗・成功ログ、device address 表、`STRATA_VERIFY_NO_HOST` 時の拒否と adaptive swap の停止。
- `sycl/src/program/generate.cpp:4153-4167` — `--stream-experts` 時の GGUF source 条件。
- `sycl/src/core/gguf_expert_source.cpp:118-201` — cap 内での候補選択、256 byte 丸め、chunk allocation、並列読み込み、mirror 表への登録。
- `sycl/src/core/gguf_expert_source.cpp:204-216` — mirror 登録状態と device alias の取得。
- `sycl/include/strata/core/gguf_expert_source.hpp:46-57` — mirror API と device-readable alias の説明。
- `sycl/src/program/generate.cpp:6957-6961,12056-12065` — mirror table を verify plan に設定する箇所。
- `sycl/src/core/verify.cpp:723-729` — 非 resident layer の device plan が `STRATA_VERIFY_DEVICE_PLAN` の `atoi` 結果で有効になる条件。
- `docs/INTEL.md:432-437,693-699` — 構成説明と A750 固有の測定例。測定条件は Arc A750 8 GB、64 GB RAM、Ryzen 5 5600X の記載を参照。
