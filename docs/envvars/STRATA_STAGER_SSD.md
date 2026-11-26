# `STRATA_STAGER_SSD`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

GGUF を in-place で読むモデルの prompt prefill で、短命な expert blob を pinned host buffer へコピーする `Stager` の profile 判定を強制する。`1` 側は file/SSD profile（既定 32 threads、通常 128 ring slots）、`0` 側は RAM profile（既定 2〜4 threads、ring は既定16 slots）に相当する。これはコピー元やモデルの読み方を切り替える設定ではなく、stager の並列度と関連する既定 batching を選ぶための profile である（`engine/src/prefill/prefill.cpp:2523-2555`）。

変数を読むのは `Prefill::init` の stager 初期化時で、`src` のいずれかの layer/expert が `transient()` なら file profile 候補になる。prompt path の初期化は通常の generate 経路から呼ばれる（`engine/src/prefill/prefill.cpp:2443-2446,2523-2545`; `engine/src/program/generate.cpp:24117-24123`）。

## 値と判定

`std::getenv` で取得し、値が null または空文字なら強制指定をせず自動判定へ進む。空でない値は先頭バイトだけを調べ、`'0'` なら RAM profile、それ以外なら file/SSD profile とする。文字列全体の数値 parse、真偽語の認識、大文字小文字変換、空白除去はしない。したがって `0` と `0anything` は RAM、`1`・`true`・`2`・` 0` は file/SSD profile になる。未設定と空文字は、profile を強制しない点で同じである（`engine/src/prefill/prefill.cpp:2537-2544`）。

| 条件 | unset / 空文字 | 有効になる値 | RAM profile になる値 |
|---|---|---|---|
| file profile 候補 (`files == true`) で `STRATA_STAGER_THREADS` が未設定 | Linux では `cached_share(256)` による自動判定。それ以外、または判定不能なら file profile | 先頭バイトが `0` 以外の非空文字列 | 先頭バイトが `0` の非空文字列。自動判定で cache resident share が `0.9` 以上の場合も RAM profile |
| `STRATA_STAGER_THREADS` が設定済み、または `files == false` | この変数は読まれず、profile を変更しない | 該当なし | 該当なし |

`files == false` は `src` が null、または走査した全 layer/expert が `transient()` でない場合。`STRATA_STAGER_THREADS` は空文字を含め `getenv` が非 null なら設定済みと扱われ、この変数の読み取り自体を飛ばす。threads は `atoi` 後に 1〜32 へ clamp される（空文字や非数値は `atoi` で 0 となり 1）。これは profile 文字列の parse とは別の処理である（`engine/src/prefill/prefill.cpp:2526-2545`）。

## 有効になる条件

- CUDA/HIP 系の prompt prefill、および共通 `Prefill::init` を使う SYCL 経路で stager が初期化され、`src` に transient expert があること。Metal も同じソースを build に含むが、Metal 分岐は `Prefill::init` の冒頭で戻るため、この読み取りへ到達しない（`engine/src/prefill/prefill.cpp:2443-2455`; `engine/cmake/strata_gpu_engine.cmake:482`; `engine/sycl/CMakeLists.txt:304`; `engine/metal/CMakeLists.txt:143`）。
- transient 判定は in-place GGUF の一時 blob を対象にする。`FileExpertSource::transient` は file-backed expert の条件を確認し、resident blob が使える場合は false を返す（`engine/src/core/expert_source.cpp:3822-3830`; interface の説明 `engine/include/strata/core/expert_source.hpp:247-256`）。
- `STRATA_STAGER_THREADS` が設定されていれば thread 数の明示設定が優先し、この変数による profile 選択を行わない。ただし `files` はその後の既定 batch 数や ring の計算には残る（`engine/src/prefill/prefill.cpp:2526-2555`）。
- `STRATA_STAGER_RING` が設定されていれば、file profile に応じた `4 * threads` の ring 設定より優先される。`Stager::init` は設定値を `atoi` して 2〜256 に clamp する（`engine/src/prefill/prefill.cpp:1126-1131,1156-1160,2545-2547`）。
- `STRATA_STAGER_BATCH` が設定されていれば既定 batch を上書きする。未設定時は file profile で 8、RAM profile で 1、値は 1〜`Stager::kMaxBatch`（32）へ clamp され、さらに ring slot 数以下に制限される（`engine/src/prefill/prefill.cpp:2547-2555`）。
- CLI 引数による `STRATA_STAGER_SSD` 相当の優先設定はこの実装にはない。モデル/source の状態が transient expert を生まない場合は変数を読まず、profile 切替も起きない。

## 実行時の詳細

`Prefill::init` 内で `m.stager` がまだない場合に限り、まず `STRATA_STAGER_THREADS` を調べ、未設定かつ transient expert があれば `STRATA_STAGER_SSD` を評価する。未設定または空文字の自動判定では `src->cached_share(256)` を呼び、値が `0.9` 以上なら `files` を false にして RAM profile とする。それ以外（0.9 未満、または判定不能を示す負値）は file profile のままにする。`cached_share` は Linux で最大256件の transient expert の3つの領域のページ常駐率を `mincore` で標本確認し、Linux 以外は `-1.0` を返す（`engine/src/prefill/prefill.cpp:2530-2544`; `engine/src/core/expert_source.cpp:3832-3860`）。

選んだ profile から threads を決め、file profile かつ `STRATA_STAGER_RING` 未設定なら ring を `4 * threads` に設定する。その後 ring buffer、copy worker threads、CUDA event を初期化し、prefill の expert copy job を実行する。通常の `files` profile は 32 threads と 128 slots、RAM profile は hardware concurrency に応じて 2〜4 threads と既定16 slotsとなる（`engine/src/prefill/prefill.cpp:2545-2555,1126-1131,1156-1183`）。

読み取りは `Prefill` インスタンスの stager 作成時に一度だけ行う。既存 stager がある再初期化では再評価しないため、プロセス実行中に環境値を変えても初期化済み stager の設定は変わらない。複数 GPU の layer split では各 stage が別の `Prefill` を初期化するため、それぞれの stager 作成時に評価される（`engine/src/prefill/prefill.cpp:2523-2525`; `engine/src/program/generate.cpp:13008-13029`）。

## ログと測定値

この変数の値を示す専用ログはない。強制値が使われた場合も profile 選択を直接報告しない。自動判定で cache resident share が 90% 以上のときだけ、次の stderr 行を出す。

```text
prefill: the GGUF experts are <割合>% in the page cache; the stager takes the RAM profile
```

stager buffer/event の初期化に失敗すると `Prefill::init` は `prefill: host buffers or events for a chunk of <chunk> tokens` を `err` に設定し、generate 側が `strata generate: <err>` を stderr に出して終了コード 1 を返す。このエラーは当該環境変数の値不正を示すものではない（`engine/src/prefill/prefill.cpp:2632`; `engine/src/program/generate.cpp:24118-24123`）。

ソースコメントには 4K chunk の SSD profile を RTX 5070 / NVMe PC で 29 秒、4 threads / 16 slots で 71 秒とする比較があるが、モデル・OS・backend・試行回数が記されていないため、一般的な性能値としては扱わない（`engine/src/prefill/prefill.cpp:2527-2529`）。

## 根拠

- 直接の環境変数参照は `engine/src/prefill/prefill.cpp:2537-2544` の一箇所。
- transient 判定と cache resident share: `engine/src/core/expert_source.cpp:3822-3860`。
- stager thread/ring/batch の設定と作成: `engine/src/prefill/prefill.cpp:2523-2555,1126-1183`。
- generate prompt path からの初期化・失敗伝播: `engine/src/program/generate.cpp:24117-24123`。
- `docs/DETAILS.md:1216` は Linux / page-cache 検出を説明しているが、現行コードでは Linux 以外は常駐率判定不能時の file profile を維持する。また通常の RAM profile は hardware concurrency に応じて2〜4 threadsである（`engine/src/core/expert_source.cpp:3857-3860`; `engine/src/prefill/prefill.cpp:2545`）。
