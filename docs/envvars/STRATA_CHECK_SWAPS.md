# `STRATA_CHECK_SWAPS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL 版の resident RAM mode で adaptive swap を行うとき、退避した expert の exchange buffer がモデルファイル上の blob と一致するかを調べる診断用スイッチです。さらに、通常の `generate` 実行の最後に resident RAM と GPU cache の所在数、および RAM blob とファイルの差異を全 expert について監査します。候補選択、swap の選択や生成結果を制御する設定ではありません。`resident_stage_swaps` の swap 処理と `generate` の終了時監査で参照されます（`engine/sycl/src/program/generate.cpp:360-364,404-428,13897-13900,14302-14325`）。

## 値と判定

両読み取り箇所とも `std::getenv` の結果を文字列全体ではなく先頭文字で判定します。未設定、空文字、先頭が `0` の文字列は無効です。それ以外は有効で、数値変換、真偽値の文字列比較、空白除去、大文字小文字の判定はありません（`engine/sycl/src/program/generate.cpp:405,14305`）。

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| SYCL の `resident_stage_swaps` 内 | 診断しない | `1`, `true`, `false`, ` 0`, `00x` 以外で先頭が `0` でない文字列 | 空文字、`0`, `0anything` |
| SYCL `generate` の終了時監査 | 監査しない | 上と同じ | 上と同じ |

たとえば `false` も有効です。`0anything` は先頭が `0` なので無効です。値に範囲や不正値のエラー処理はありません。

## 有効になる条件

- Strata の SYCL 実装であること。コード参照は `engine/sycl/src/program/generate.cpp` にあり、他 backend の同名読み取りはありません。
- Swap 時の比較には resident RAM mode が成立して (`src.complement_ready()`)、退避対象 swap があり、exchange buffer へのコピーと stream 同期が成功する必要があります。成立しない場合、関数は診断比較を行わず戻ります（`engine/sycl/src/program/generate.cpp:360-364,370-403`）。
- 終了時の全体監査は `src.complement_ready()` の場合だけ実行され、上記値条件も満たす必要があります（`engine/sycl/src/program/generate.cpp:14302-14306`）。
- Resident RAM mode は `--resident-experts` または resident budget 系の CLI 経路で構築され、adaptive tier は `--adapt-every` と `--adapt-swaps` がともに正のときに有効です。環境変数はこれらの CLI 条件を上書きしません（`engine/sycl/src/program/generate.cpp:7056-7067,7098-7137`）。Serve の blocking adaptive 経路も共通の `resident_stage_swaps` を呼びます（`engine/sycl/src/program/generate.cpp:8851-8855,8908-8917`）。
- GPU 世代、OS、モデル形式、build macro による値判定の違いはありません。SYCL mirror adaptive の経路はこの resident swap helper を経由せず、同 helper の buffer 比較対象ではありません（`engine/sycl/src/program/generate.cpp:8878-8907`）。

## 実行時の詳細

`resident_stage_swaps` は、GPU cache から退避する expert を交換用 host buffer にコピーし、使用 stream を待った後で環境変数を読みます。有効時は各 staged blob を `copy_blob_from_file` でモデルファイルから別途読み、buffer と `memcmp` します。一致しない場合は layer/expert を stderr に出し、不一致数を累積します。一致数・不一致数の累計 atomic はプロセス内で保持されますが、環境変数自体は static cache されず、helper が呼ばれるたびに読み直されます（`engine/sycl/src/program/generate.cpp:394-423`）。

比較後も `stage_exchange` による通常の swap 処理を続けます。不一致だけを理由に swap を拒否したり、終了コードを変えたりはしません。`stage_exchange` 自体が失敗した場合は helper が失敗を返し、呼び出し元の adaptive refill エラー経路に進みます（`engine/sycl/src/program/generate.cpp:424-428,13897-13900`）。

通常の `generate` 実行の終了時は、resident RAM にある全 expert をファイルから再読込して比較し、GPU cache または RAM のどちらにもない expert 数と、ファイルと異なる RAM blob 数を集計します。ファイル読込失敗も blob の差異として数えます。ここでも不一致や未保持 expert はログに出すだけで、監査自体は exit/return を行いません。serve にはこの終了時全体監査の箇所はありませんが、blocking adaptive swap 内の buffer 比較は共通 helper 経由で行われます（`engine/sycl/src/program/generate.cpp:14304-14325,8851-8855,8917`）。

## ログと測定値

Swap 時の不一致は stderr に `strata: STRATA_CHECK_SWAPS: layer %d expert %d: the exchange buffer differs from the file`、各回の件数とプロセス累計は `strata: STRATA_CHECK_SWAPS: %zu staged, %lld differ (total %lld ok, %lld differ)` と出ます（`engine/sycl/src/program/generate.cpp:414-422`）。差異ゼロでも staged swap があれば集計行は出ます。

終了時監査では不一致の最初の最大 8 件を stderr に `strata: STRATA_CHECK_SWAPS: layer %d expert %d: the RAM copy differs from the file` と出し、stdout に `STRATA_CHECK_SWAPS audit: ...` の形式で RAM/GPU/未保持/不一致数を出します（`engine/sycl/src/program/generate.cpp:14319-14325`）。差異が見つかった場合も、この診断箇所自体は異常終了させません。

## 根拠

- `engine/sycl/src/program/generate.cpp:360-433` — resident swap の前提、exchange buffer の検査、ログ、swap 継続。
- `engine/sycl/src/program/generate.cpp:7056-7137` — resident RAM mode と adaptive swap の CLI 条件。
- `engine/sycl/src/program/generate.cpp:8851-8917` — serve adaptive 経路と helper 呼び出し。
- `engine/sycl/src/program/generate.cpp:14302-14325` — generate 終了時の全体監査。
- `engine/sycl/include/strata/core/expert_source.hpp:499-514,575-579` — resident/exchange の契約と、モデルファイルから読む `copy_blob_from_file`。
- `docs/DETAILS.md:261-282` — resident RAM mode と adaptive tier の説明。`STRATA_CHECK_SWAPS` 自体の説明はなく、上記の診断挙動はソースコードに基づきます。
