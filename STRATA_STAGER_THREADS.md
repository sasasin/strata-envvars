# `STRATA_STAGER_THREADS`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

プロンプト処理で、GPU に直接 DMA できない expert blob を staging buffer へコピーする worker thread 数を指定します。CUDA 系と SYCL の Prefill 実装がそれぞれ読み取ります。値は生成処理の decode worker 数や、別機能の `STRATA_FETCH_THREADS` を変更しません。

## 値と判定

変数の設定有無を `getenv()` で判定し、設定されていれば `atoi()` の結果を 1〜32 に clamp します。文字列全体の数値検証はありません。

| 状態 | Stager worker 数 |
|---|---:|
| 未設定、通常の ExpertSource | `max(2, min(4, hardware_concurrency() / 4))` |
| 未設定、transient blob を返す source | 通常 32。CUDA 実装では Linux のファイル source の page-cache 判定により warm profile を選ぶ場合、または `STRATA_STAGER_SSD=0` の場合は通常 source と同じ式 |
| 設定あり | `clamp(atoi(値), 1, 32)` |

したがって、空文字、数値に変換できない文字列、`0`、負値は 1 thread になります。`8workers` のように先頭が数値なら `atoi()` が読む数値部分が使われ、32を超える値は32です。先頭空白や符号も `atoi()` の規則に従います。大文字小文字の比較はありません。

## 有効になる条件

- Prefill の `init()` で Stager がまだ作られていないときに読み取られます。Stager は Prefill object 内で保持され、同じ object で後から `init()` を呼んでも値を読み直しません。`Prefill::reset()` は object の実装状態を作り直すため、その後の初期化では再評価されます。
- この数は Stager の worker pool 作成数です。実際にコピー job が流れるのは、プロンプトの expert streaming 経路が Stager に job を登録した場合です。resident / pinned の blob など、Stager を通らない expert には影響しません。
- CUDA 実装では、未設定時に transient blob があると `STRATA_STAGER_SSD` が明示されていない場合に限り、`cached_share(256)` を使った page-cache 判定を行います。90%以上 resident と判定すると RAM profile を選びます。`STRATA_STAGER_THREADS` が設定されていればこの自動判定を飛ばし、指定 thread 数を使います。未設定で `STRATA_STAGER_SSD=0` の場合は通常 thread 数、`=1` の場合は32 threadになります。`STRATA_STAGER_THREADS` と同時に設定した場合、SSD 選択は worker 数を上書きしません。
- transient blob があり、`STRATA_STAGER_RING` が未設定なら、Stager ring の深さは `4 × thread 数` に設定されます（明示された ring 値があればそちらが優先）。したがって thread 数の指定は worker 数に加え、この条件下の既定 ring 深さにも影響します。
- SYCL 実装も同じ `atoi` と 1〜32 clamp、および transient source 未設定時の32 threadという規則を使います。ただし、掲載 HEAD の SYCL `Prefill::init()` には CUDA 側の `cached_share()` による RAM/SSD 自動判定はありません。

## 実行時の詳細

CUDA 実装は `Prefill::init()` の `if (!m.stager)` 節で hardware concurrency と環境値を調べ、得た数を `Stager::init()` に渡します。Stager はその数だけ `std::thread` を作成します。SYCL も同じ初期化位置で同数の thread を作り、各 worker が Stager の仕事ループを実行します。

job は GPU へ送る expert の staging copy で使われます。CUDA 実装では CUDA 系 event と pinned/pageable host buffer を用意し、SYCL 実装では対応する SYCL buffer/event を用意します。ring buffer の空き待ちや copy 完了待ちの仕組みは別の設定にも左右されますが、この変数自体は worker 数を決めます。

この変数を読み取ったこと自体を示す専用ログはありません。CUDA の自動 page-cache 判定が warm profile を選んだ場合には `prefill: the GGUF experts are ... in the page cache; the stager takes the RAM profile` が stderr に出ますが、これは `STRATA_STAGER_THREADS` が未設定で、該当するファイル source の判定を通った場合のログです。

## 根拠

- `src/prefill/prefill.cpp:1096-1133`: CUDA 実装の Stager 初期化、環境値の読み取り、transient source 判定、page-cache 判定、thread 数と ring の決定。
- `sycl/src/prefill/prefill.cpp:999-1017`: SYCL 実装の Stager 初期化と thread 数の決定。
- `src/prefill/prefill.cpp:435-461`, `sycl/src/prefill/prefill.cpp:382-419`: ring 値の clamp、buffer の初期化、指定数の worker thread 作成。
- `src/prefill/prefill.cpp:2352-2392`, `sycl/src/prefill/prefill.cpp:2529-2572`: streamed experts の job 登録と Stager への投入。
- `src/prefill/prefill.cpp:910-925`: Prefill object の生成、reset、release。Stager は `Impl` に保持される。
- `include/strata/core/expert_source.hpp:200-209`, `src/core/expert_source.cpp:2434-2473`: transient source と page-cache 共有率 API、および Linux `mincore` 判定。
- `docs/DETAILS.md:1562`: GGUF read-in-place の測定条件で32 thread・128 ringが使われた説明と、明示的な `STRATA_STAGER_THREADS` が profile 選択より優先する旨。測定値は記載された構成に限られ、一般的な速度効果を示すものではありません。
