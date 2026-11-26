# `STRATA_TOPK_SPLIT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

CUDA の QSA block top-k 選択で、既定の wide kernel の代わりに、候補ブロックを複数の CTA に分ける split kernel 経路を選ぶスイッチです。これは QSA が選ぶ cell ID の計算経路を切り替えます。分割版は 2,048 block 単位で 4 回の radix histogram、threshold 上下の個数集計、ID 出力を行い、ソースコメントは既定の `block_topk_kernel` と同じ ID を出力すると説明しています（`engine/src/kernels/cuda/qsa_select.cu:2545-2556,2590-2629,2631-2668,2670-2758`）。

読み取り箇所は `topk_split_device()` の 1 箇所です。split dispatch と kernel は `#if !defined(__HIPCC__)` の内側にあり、HIP ビルドではこの変数を使った経路自体がコンパイルされません（`engine/src/kernels/cuda/qsa_select.cu:2545,2761-2797,3022-3041`）。QSA layer の fast-select 経路は block scores を計算したあとに top-k を呼び、選ばれた ID を KV resolve / attention に渡します（`engine/src/core/layer.cpp:1273-1289`）。

## 値と判定

`std::getenv` で設定有無を見て、設定されていれば `std::atoi(v) != 0` を評価します。文字列全体の妥当性検査はありません。`atoi` が先頭の数値部分を変換するため、空文字・数値で始まらない文字列・`0anything` は 0、`1anything`・`-1`・`true` は 0 以外にはなりません（`true` は数値接頭辞がなく 0）。先頭空白の後の数値は変換されます。未設定だけが `-1`（自動判定）です。判定値は関数内 `static const` に初回呼び出し時保存され、以後の環境変更は反映されません（`engine/src/kernels/cuda/qsa_select.cu:2761-2773`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| CUDA。値が設定済み | 該当なし | `1`, `2`, `-1`, `1junk`（`atoi` が非 0） | ``, `0`, `-0`, `0junk`, `junk`, `true`（`atoi` が 0） |
| CUDA。未設定 | Turing compute capability 7.5 で、`STRATA_SM75_PERF` が `atoi` で非 0 の場合だけ有効 | `STRATA_SM75_PERF=1`（同 helper も初回値を cache） | それ以外のデバイスまたは unset / 0 相当 |
| HIP ビルド | split 経路なし | 該当なし | 値にかかわらずこの分岐では使用されない |

設定済みの非ゼロ値は `STRATA_SM75_PERF` や GPU 世代の自動判定を上書きし、CUDA device で split 候補を有効にします。`0` 相当は自動判定にも進まず無効です（`engine/src/kernels/cuda/qsa_select.cu:2763-2773`、`engine/include/strata/core/sm75_series.hpp:24-37`）。

## 有効になる条件

値判定を通過しても、次の条件がすべて必要です。

- CUDA ビルドであること。HIP では分割コードが除外されます（`engine/src/kernels/cuda/qsa_select.cu:2545,3022-3041`）。
- `qsa_block_topk()` まで到達すること。`nq <= 0` は即時 return です。`STRATA_TOPK_OLD` は値ではなく設定有無を見ており、空文字でも有効になって後続の旧経路選択を行い、split 判定を通りません（`engine/src/kernels/cuda/qsa_select.cu:3016-3021,3073-3076`）。
- 先行する cluster 経路が成功して return していないこと。`STRATA_QSA_CLUSTER` は unset なら既定で有効、設定時は `atoi != 0` で判定されます。cluster kernel が利用可能なら split より先に選択されます（`engine/src/kernels/cuda/qsa_select.cu:3022-3031`）。
- 呼び出しが decode 型で `active_blocks <= 0`、`max_blocks >= 16384`、`s.idx_block == R`、`cap >= qsa_selection_width(kTopkMaxCells, s)` であること（`engine/src/kernels/cuda/qsa_select.cu:3032-3036`）。prompt など `active_blocks > 0` の選択ではこの split 分岐に入りません。
- `topk_split_device()` の CUDA device 判定を通ること。`cudaGetDevice` が失敗するか device index が 0..63 の外なら false になり、CUDA error state を clear して通常経路へ戻ります。未設定時は device compute capability と `STRATA_SM75_PERF` を見て Turing のみを許可します。設定済み非ゼロなら device ごとの判定 cache が有効になります（`engine/src/kernels/cuda/qsa_select.cu:2761-2773`）。
- 分割実装の上限に収まること。`nq` は 1..16、`ceil(max_blocks / 2048)` は最大 512 chunk です。超過、device 取得・symbol address・histogram 初期化の失敗は `false` を返して通常の選択 kernel に fallback します（`engine/src/kernels/cuda/qsa_select.cu:2776-2788`）。
- `qsa_block_topk_long()` 経由では、実験 macro `STRATA_EXPERIMENTAL_SM60` が有効で、`STRATA_TOPK_MULTI` の mode と scratch 条件を満たすと、その multi-CTA kernel が先に使われて split 判定に進みません。それ以外は `qsa_block_topk()` に委譲します（`engine/src/kernels/cuda/qsa_select.cu:3174-3196,3230-3245`）。

## 実行時の詳細

`qsa_block_topk()` は、通常の QSA 選択のうち `active_blocks <= 0` の decode 呼び出しで、まず cluster 経路を試し、その後 split 条件を評価します。split 関数は capacity から chunk 数を決め、共有 histogram を stream 上で初期化して、histogram 4 pass、count、emit の 6 kernel を同じ stream に launch します。呼び出し元が `cudaGetLastError()` を確認し、launch error があれば `qsa_block_topk (split): <CUDA error string>` を stderr に出して `exit(1)` します。split helper が前提条件や準備処理で false を返した場合はこのエラー経路でなく、後続の通常 dispatch が行われます（`engine/src/kernels/cuda/qsa_select.cu:2776-2797,3032-3040`）。

選ばれた ID は QSA の後続 KV resolve と attention に使われます。実装コメントとコードは split と既定 top-k の ID 同一性を示していますが、この調査では実行比較・GPU 測定はしていません（`engine/src/kernels/cuda/qsa_select.cu:2550-2553,2670-2673`; `engine/src/core/layer.cpp:1280-1289`）。値の読み取りは環境変数用 `static` の初回評価時、device 可否は `ok[64]` に device ごと保存されます。プロセス起動後に値を変えても、これらの cache が再初期化される経路はありません（`engine/src/kernels/cuda/qsa_select.cu:2761-2773`）。

## ログと測定値

有効化を示す成功ログはありません。split の launch error は stderr に `qsa_block_topk (split): %s\n` を出してプロセスを終了します。split の準備条件が満たせず helper が false を返す場合は明示ログなしで通常経路へ進みます（`engine/src/kernels/cuda/qsa_select.cu:2780-2797,3037-3039`）。

`docs/DETAILS.md` は当変数を Turing 向け bitwise kernel の一つとして列挙し、Turing kernel 群について置換前と bitwise equal と述べますが、この変数固有の測定値や実行環境は記載されていません（`docs/DETAILS.md:1336-1344`）。設定一覧 `docs/SETTINGS.md:480` は対象を「NVIDIA and AMD」としていますが、現行実装は HIP で除外される CUDA 専用経路です。

## 根拠

- `engine/src/kernels/cuda/qsa_select.cu:2545-2556,2761-2797,3016-3041` — CUDA 限定実装、値・device 判定、dispatch と fallback / failure。
- `engine/src/kernels/cuda/qsa_select.cu:2590-2758` — split の histogram、count、emit。
- `engine/include/strata/core/sm75_series.hpp:24-37` — 未設定時の Turing default と `STRATA_SM75_PERF` の読み取り。
- `engine/src/kernels/cuda/qsa_select.cu:3174-3215,3230-3245` — long top-k からの先行 multi-CTA 経路。
- `engine/src/core/layer.cpp:1273-1289` — fast-select 呼び出しと選択 ID の後続利用。
- `docs/DETAILS.md:1336-1344`, `docs/SETTINGS.md:480` — ソース説明との照合（現行挙動の根拠ではない）。
