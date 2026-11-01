# `STRATA_SAMPLER_ONE_BLOCK`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

非 greedy sampling の実装経路を選びます。有効なら top-k selection に、1 block で各 token row を処理する `sampler_one_block_kernel` を選択します。無効なら既定の split top-k 経路を選びますが、split 経路の実行条件を満たさない場合も one-block kernel に fallback します。旧 sampler を選ぶ `STRATA_OLD_SAMPLER` が有効なら、そちらが優先されます。

## 値と判定

CUDA/HIP と SYCL の sampler 実装にある `env_flag()` は `getenv()` の結果を次のように判定します。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| 文字列がちょうど `0` | 無効 |
| その他の空でない文字列 | 有効。例: `1`, `00`, `false`, ` 0` |

数値変換は行わず、文字列全体を `strcmp(e, "0")` で比較します。前後の空白、大文字小文字、数値としての妥当性は検査しません。したがって `00` は無効ではなく有効です。`STRATA_OLD_SAMPLER` も同じ helper で判定され、両方が有効なら旧 sampler が選ばれます。CLI 引数による上書きはありません。

判定結果は `sampled_path()` 内の `static const` に保存されます。プロセス内の最初の `sampled_path()` 呼び出しで一度だけ環境を読み、その後の環境変更は反映されません。

## 有効になる条件

- `sample_tokens()` が greedy (`p.greedy`) でなく、temperature が `0` 以下でもない sampled 経路で使われるときに、sampled path の選択が行われます。greedy または temperature `<= 0` の場合は greedy kernel 分岐へ進み、この変数は path 選択に使われません。
- `STRATA_OLD_SAMPLER` が有効なら、`STRATA_SAMPLER_ONE_BLOCK` の値にかかわらず旧 `sampler_kernel` が選ばれます。
- split path が選ばれた場合でも、語彙幅が split の merge 上限を超える、token row 数が `kSplitMaxRows` を超える、stream が capture 中、または scratch 確保に失敗する場合は one-block kernel に fallback します。よって変数が無効でも one-block kernel が実行されることがあります。
- CUDA/HIP では `src/kernels/cuda/sampler.cu`、SYCL では `sycl/src/kernels/cuda/sampler.dp.cpp` に同じ選択処理があります。これらは GPU kernel の実装であり、CPU-only 経路についてこの変数の読み取りは見つかりませんでした。

## 実行時の詳細

通常の sampled 経路では、有効値かつ旧 sampler が無効なら split scratch を使わず one-block kernel を起動します。選択するのは実装方法であり、top-k 以降の sampling chain を切り替える設定ではありません。CUDA ソースの説明では one-block と split の新 sampler は同じ token を bit-for-bit で選ぶ設計とされていますが、この調査では build や実行による検証はしていません。

verify 用の `sample_tokens_spec()` / `sample_tokens_proposal()` は split path を使える場合に限って専用 kernel を実行します。`STRATA_SAMPLER_ONE_BLOCK` により one-block path が選ばれた場合、この専用処理は `false` を返します。通常の verify sampling は `sample_tokens()` に fallback します。一方 `measure` による proposal sampler 経路では fallback せず、`verify.cpp` が `verify: proposal sampler unavailable or allocation/copy/launch failed` を返して失敗します。

この変数固有の有効・無効ログや警告はありません。kernel launch error は CUDA では `sample_tokens launch: <runtime error>` を stderr に出して `exit(1)` します。verify 側では上記の error string が `err` に設定されます。SYCL 実装の kernel launch 後の同期は、null stream の場合 `queues_wait_and_throw()` です。

## 根拠

- `src/kernels/cuda/sampler.cu:1123-1141` — `SampledPath`、`env_flag()` の変換、旧 sampler 優先順位、static cache。
- `src/kernels/cuda/sampler.cu:1260-1318` — greedy 経路、sampled path に応じた kernel 選択、split の実行条件と one-block fallback、launch error。
- `src/kernels/cuda/sampler.cu:555-563` — one-block kernel の実装位置と役割。
- `src/kernels/cuda/sampler.cu:1368-1411` — verify 用 sampler は split path が選ばれない場合に専用経路を使えない。
- `sycl/src/kernels/cuda/sampler.dp.cpp:1290-1303,1472-1490,1534-1652` — SYCL 側の同等判定、greedy 除外、split/one-block 選択と fallback。
- `src/core/verify.cpp:3363-3398` — verify の proposal / spec 専用経路、fallback、および `measure` 時の失敗処理。
- `CMakeLists.txt:456-465`、`sycl/CMakeLists.txt:237-246` — CUDA/HIP kernel と SYCL kernel source の build target への登録。
- `src/kernels/sampler_parity.cpp:473-479`、`sycl/src/kernels/sampler_parity.cpp:535-540` は parity 用実行ファイルが選択経路を表示する箇所です。`CMakeLists.txt:1419-1440` は test ごとに環境値を設定します。これらは runtime 設定の根拠ではなく、parity/test 用参照です。
