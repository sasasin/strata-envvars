# `STRATA_STAGER_THREADS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA/HIP 系の `engine/src/prefill/prefill.cpp` と SYCL 系の `engine/sycl/src/prefill/prefill.cpp` で、Prefill の Stager が unpinned な expert blob を host staging buffer にコピーする worker thread 数を決める。Stager は DMA で直接使えない expert を先行コピーし、呼び出し側が staging buffer から GPU の stage buffer へ転送する。従ってこの値は expert staging の並列度を変えるもので、GPU 側の計算 thread 数を指定するものではない（`engine/src/prefill/prefill.cpp:1121-1125,2523-2555,4724-4745`、`engine/sycl/src/prefill/prefill.cpp:469-478,1491-1503,4600-4624,4660-4685`）。

Metal の `engine/src/prefill/prefill.cpp` 実装は `STRATA_GPU_METAL` 分岐で `Prefill::init` から戻るため、この設定を読まない（`engine/src/prefill/prefill.cpp:2443-2454`）。SYCL server wrapper `engine/sycl/serve/strata-sycl.sh` は値が指定されなければ `12` を engine に渡し、環境に同名変数があればその値で置き換える（同ファイル `13-16,31-43`）。

## 値と判定

両 C++ 実装とも `std::getenv` で取得し、null でなければ `std::atoi` の結果を `std::clamp(..., 1, 32)` で制限する。整数文字列全体の検証はない。`atoi` が読む先頭部分が数値ならその値を使い、先頭に空白や符号があっても変換される。変換できない文字列や空文字は `atoi` が返す `0` となり、worker 数は下限の `1` になる。負値も `1`、`1` から `32` はその値、`32` より大きい値は `32`。例えば `4tail` は `4`、`0anything`・`true`・空文字は `1` になる。大文字小文字を比較する処理はない。数値変換範囲を超えた入力に対する `atoi` の結果はコードで保証されない（`engine/src/prefill/prefill.cpp:2523-2526,2545`、`engine/sycl/src/prefill/prefill.cpp:1491-1501`）。

| 実装・条件 | unset | 設定時に有効になる値 | 設定時に無効になる値・例 |
|---|---:|---|---|
| CUDA/HIP 系、通常の source | `max(2, min(4, hardware_concurrency / 4))` | `1`〜`32`（例: `4`） | 独立した無効値判定なし。空文字、`true`、`0`、負値は `1` に clamp |
| CUDA/HIP 系、expert source が transient で SSD profile が選ばれる場合 | `32` | 同上 | 同上 |
| SYCL | source に transient expert があれば `32`、それ以外は CUDA/HIP 系と同じ hardware concurrency 式 | `1`〜`32`（例: `4`） | 独立した無効値判定なし。空文字、`true`、`0`、負値は `1` に clamp |
| SYCL server の `strata-sycl.sh` 経由 | wrapper が `12` を設定して渡す（明示値があればそちら） | engine 到達後は上記 SYCL の変換規則 | 明示した空文字は wrapper が container に渡さず、engine では unset として扱われる |

通常 source の既定値は `std::thread::hardware_concurrency()` を整数除算で 4 分の 1 にし、2〜4 に clamp した値（取得値が 0 の場合も 2）。CUDA/HIP 系では `files` と呼ぶ transient expert の有無に加え、`STRATA_STAGER_SSD` と page-cache probe が unset 時の profile 選択に関係する。`STRATA_STAGER_THREADS` が設定されるとその値が thread 数に使われ、`STRATA_STAGER_SSD` の profile 強制と cache probe の分岐は通らない。SYCL 実装にはこの `STRATA_STAGER_SSD` 分岐がない（`engine/src/prefill/prefill.cpp:2525-2545`、`engine/sycl/src/prefill/prefill.cpp:1493-1501`）。

## 有効になる条件

- `Prefill::init` が Stager を初期化する CUDA/HIP 系または SYCL 系の engine であること。Metal の早期 return 経路では読み取り自体がない（`engine/src/prefill/prefill.cpp:2443-2455`）。
- 各 `Prefill` instance の Stager がまだ作られていないこと。値は `if (!m.stager)` 内の初期化で読み取られ、同じ instance に既に Stager があれば再読み込みされない（`engine/src/prefill/prefill.cpp:2523-2526`、`engine/sycl/src/prefill/prefill.cpp:1491-1494`）。
- Staging の対象となる unpinned / 非 resident expert があること。resident cache にある expert や `dma_direct` が直接扱える pinned blob は Stager job の対象から除かれ、job がなければ worker 数を使ったコピーは発生しない（CUDA/HIP 系: `engine/src/prefill/prefill.cpp:4670-4724`、SYCL: `engine/sycl/src/prefill/prefill.cpp:4605-4624,4660-4685`）。
- SYCL の serve 経路では `strata-sycl.sh` の初期値 `12` が優先される。起動環境から同名変数が渡れば wrapper の連想配列値を置き換える。明示した空文字は `envs` に追加されず engine には渡らないため、engine 側の unset 既定値に戻る（`engine/sycl/serve/strata-sycl.sh:31-43`）。
- CUDA/HIP 系では未設定時に限り `STRATA_STAGER_SSD` が transient source の profile 判定に関与する。非空なら先頭文字が `'0'` 以外かどうかで profile を選び、空または unset の場合は Linux の `cached_share(256)` が `0.9` 以上なら RAM profile に切り替えて理由を stderr に出す。`STRATA_STAGER_THREADS` が設定済みならこの分岐を飛ばす（`engine/src/prefill/prefill.cpp:2530-2545`、`engine/src/core/expert_source.cpp:3832-3844`）。
- CUDA/HIP 系では transient source の profile が選ばれると、`STRATA_STAGER_THREADS` を設定していても `STRATA_STAGER_RING` 未設定時の ring 深さは `4 * threads` になる。`STRATA_STAGER_RING` が設定されていれば `Stager::init` が `atoi` 値を `2`〜`256` に clamp する。SYCL も transient source では同じ `4 * threads` の既定 ring を使う（`engine/src/prefill/prefill.cpp:2545-2546,1156-1158`、`engine/sycl/src/prefill/prefill.cpp:1501-1503,502-505`）。この変数は ring 深さ自体を指定しない。
- CUDA/HIP 系では `files` profile のままなら `STRATA_STAGER_BATCH` 未設定時の batch 既定値は `8`、それ以外は `1`。thread 数を明示しても `files` の判定は保持されるため、この batch 既定値には影響しない（`engine/src/prefill/prefill.cpp:2530-2532,2537-2555`）。

## 実行時の詳細

CUDA/HIP 系では Prefill 初期化時に thread 数を決め、`Stager::init` がその数だけ worker thread を生成する。SYCL も同じく `Prefill::init` で値を読み、`Stager::init` の `for (t < nthreads)` で worker を生成する（`engine/src/prefill/prefill.cpp:2523-2555,1156-1183`、`engine/sycl/src/prefill/prefill.cpp:1491-1503,502-538`）。この値を環境から読むのはこの初期化時だけで、実行中に環境を変更しても既存 Stager の thread 数は変わらない。

各 prompt の Stager job は unpinned expert blob を pinned host buffer（確保できない slot では pageable buffer）へコピーする。起動側はその buffer から GPU stage buffer へ async copy を発行し、slot の DMA 完了後に再利用する。CUDA/HIP 系では `Stager::start` と `wait`、SYCL では同様の `start` / `wait` を使う。既に resident または直接 DMA 可能な expert にはこのコピー経路を使わない（`engine/src/prefill/prefill.cpp:1133-1139,1162-1174,4724-4747`、`engine/sycl/src/prefill/prefill.cpp:476-483,514-538,4603-4624,4669-4687`）。

CUDA/HIP 系では ring buffer や event 初期化が失敗すると `Prefill::init` は `prefill: host buffers or events for a chunk of <N> tokens` をエラーにし、generate 側は `strata generate: <error>` を stderr に出して終了コード `1` で戻る。SYCL の初期化失敗でも同じ `prefill: host buffers or events for a chunk of <N> tokens` を返し、通常 generate 経路が同様に stderr 出力後 `1` で終了する（`engine/src/prefill/prefill.cpp:2554,2632`、`engine/src/program/generate.cpp:24118-24123`、`engine/sycl/src/prefill/prefill.cpp:1503,1596`、`engine/sycl/src/program/generate.cpp:13354-13359`）。

設定値そのものに対する有効・無効ログはない。CUDA/HIP 系の別設定で page-cache 比率が `90%` 以上となり RAM profile に切り替えた場合だけ、`prefill: the GGUF experts are <N>% in the page cache; the stager takes the RAM profile` が stderr に出る。このログは `STRATA_STAGER_THREADS` 未設定で `STRATA_STAGER_SSD` が空または unset の場合に限られる（`engine/src/prefill/prefill.cpp:2537-2543`）。

## ログと測定値

Strata の `docs/DETAILS.md:1216` は Linux の GGUF read-in-place に対し、page cache 上で 4 threads、SSD で 32 threads と記載し、`STRATA_STAGER_THREADS` が優先するとしている。現行コードでは thread 数の明示値が優先する点は一致する。一方、RAM profile の未設定既定値は `4` 固定ではなく hardware concurrency から 2〜4 に決まり、SSD profile は transient source と `STRATA_STAGER_SSD` / cache probe によって選ばれる（`engine/src/prefill/prefill.cpp:2530-2545`）。コードコメントには RTX 5070 / NVMe PC での 29 秒対 71 秒の記述があるが、これは調査時に再測定した結果ではない（`engine/src/prefill/prefill.cpp:2527-2529`）。

## 根拠

- CUDA/HIP 系の parse、既定値、SSD profile、ring/batch との関係: `engine/src/prefill/prefill.cpp:2523-2557`。
- SYCL の parse と既定値: `engine/sycl/src/prefill/prefill.cpp:1491-1503`。
- Worker thread の生成と staging buffer: `engine/src/prefill/prefill.cpp:1121-1183`、`engine/sycl/src/prefill/prefill.cpp:469-538`。
- SYCL wrapper の default と環境変数の転送: `engine/sycl/serve/strata-sycl.sh:13-16,31-43`。
- transient source と Linux cache probe: `engine/src/core/expert_source.cpp:3822-3850`、`engine/sycl/src/core/expert_source.cpp:1564-1585`。
