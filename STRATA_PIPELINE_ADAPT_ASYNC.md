# `STRATA_PIPELINE_ADAPT_ASYNC`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

`--adapt-async 1` と `--pipeline-windows 2` を同時に使うとき、適応層（adaptive tier）を非同期のまま動かすか、通常のブロッキング方式へ戻すかを選びます。値が `atoi` で 0 になる場合はこの組み合わせで非同期適応層を無効にし、ブロッキング適応層を使います。それ以外の場合と未設定時は、他の条件を満たせば非同期適応層を保ちます。

対象コードは `src/program/generate.cpp` の非 SYCL 実装です。`sycl/src/program/generate.cpp` にはこの変数の読み取りがなく、同ファイルでは `--pipeline-windows` が有効なら `--adapt-async` を無効にします。

## 値と判定

環境変数の文字列全体ではなく、C の `std::atoi` の結果が 0 かどうかで判定します。`atoi` は先頭の空白と符号を許し、先頭の整数部分を変換し、数字以外の後続文字は変換に含めません。整数として読み取れない文字列と空文字は 0 になります。

| 環境変数の値 | 判定 | `--pipeline-windows 2` との組み合わせ |
|---|---|---|
| 未設定 | 既定で有効（`pl_async = true`） | 他の条件を満たせば非同期適応層を維持 |
| `0`、`00`、`0xyz`、空文字、`false`、整数に変換できない文字列 | `atoi` が 0 | `--adapt-async 1` を無効化し、ブロッキング適応層へ切り替え |
| `1`、`2`、`-1`、`1xyz`、` 1` | `atoi` が 0 以外 | 他の条件を満たせば非同期適応層を維持 |

`STRATA_PIPELINE_ADAPT_ASYNC=0` は `--pipeline-windows 2` が指定または有効な場合にだけ意味を持ちます。`--pipeline-windows` が 0 または 1 なら、この値によって `--adapt-async` は無効になりません。

## 有効になる条件

この環境変数が効くのは、非 SYCL 実装で `--adapt-async` が有効なときです。値は `static const bool` の初期化で一度読み取られるため、最初の評価後に同じプロセス内で環境を変更しても再評価されません。初期化は `--adapt-async` が有効な経路で遅延実行されます。

`atoi` が 0 で、かつ `--pipeline-windows >= 2` のときは、他の適応層の前提条件より先に `--adapt-async` を 0 にします。その後、残るブロッキング適応層は `--serve`、正の `--adapt-every` と `--adapt-swaps`、`--resident-experts` など従来の条件に従います。これらが満たされなければ適応層自体も無効です。

## 実行時の詳細

ほかの不成立条件が先に該当せず、この環境変数が無効理由になると、stderr に `strata generate: --adapt-async 1 is off (not with --pipeline-windows 2 (STRATA_PIPELINE_ADAPT_ASYNC=0)): the blocking adaptive tier` と出します。パイプラインのデコードループは `pl_adapt` を使い、適応処理を別スレッドで進めます。入れ替え処理は、処理中の窓が上書き対象を読み終わり、保留中の交換や交換待ちがなくなった後に開始されます。ループは適応スレッドの完了を確認しながらパイプライン窓を処理します。

環境変数が未設定または `atoi` で 0 以外となり、ほかの条件も満たす場合は非同期適応層を維持します。これは補助スレッド上で適応ラウンドを進め、GPU コピーはパイプラインの各カードに実行中の窓がない時間帯に投入する経路です。したがって変数は適応の有無やパイプライン自体ではなく、両者を組み合わせた際の適応方式を切り替えます。

## 根拠

- `src/program/generate.cpp:6682-6700`: 変数の唯一の実装読み取り、`atoi` 判定、未設定時の既定値、他の適応層条件と無効化ログ。
- `src/program/generate.cpp:11386-11394,11520-11536`: パイプライン実行中の非同期方式とブロッキング適応方式のスレッド処理。
- `sycl/src/program/generate.cpp:6396-6414`: SYCL 側では環境変数を読まず、`--pipeline-windows` が有効な場合に非同期適応層を無効化。
- `docs/DETAILS.md:170-179`: resident RAM モードの適応層とパイプラインの説明。非同期方式は窓の進行に応じてコピーするため、実行タイミング次第で同じ入力でも厳密一致しない場合があると記載。
- `docs/MULTI_GPU.md:311-315`: `STRATA_PIPELINE_ADAPT_ASYNC=0` のときに限り、`--pipeline-windows 2` と `--adapt-async 1` の組み合わせから非同期適応層を外す旨の記載。
