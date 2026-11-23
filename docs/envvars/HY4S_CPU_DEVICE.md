# `HY4S_CPU_DEVICE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

SYCL 実行経路で共有 queue `hy4s::Q()` が使うデバイスを選びます。環境変数の値が `1` で始まる場合は CPU selector を指定し、それ以外の場合は GPU デバイス一覧と primary GPU index による選択、または GPU selector に進みます。これは SYCL queue のデバイス選択であり、Strata の別 backend 全般を CPU 実行に切り替える設定ではありません。実装は `engine/src/hy4flash/sycl/sy_common.h:154-175` にあります。

`sy_common.h` のコメントは CPU-only unit tests 用途を示しますが、同じ `Q()` は製品用 `strata-hy4-sycl` にも組み込まれています。ビルドスクリプトは `sy_main.cpp` をコンパイルし、サーバー起動処理は `Q().get_device()` を呼びます（`engine/src/hy4flash/sycl/build_hy4_sycl.sh:62-68`、`engine/src/hy4flash/sycl/sy_serve.h:235-240`）。

## 値と判定

`std::getenv` の戻り値が null でなく、かつ最初の1文字が文字 `'1'` かだけを調べます。文字列全体の比較・数値変換・空白除去はありません（`engine/src/hy4flash/sycl/sy_common.h:165-168`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| SYCL queue 初期化時 | CPU 分岐に入らず GPU 選択へ進む | `1`、`10`、`1anything` など先頭が `1` の値 | 空文字、`0`、`2`、`true`、` 1` など先頭が `1` でない値 |

大文字小文字を解釈する語の比較はなく、`true` や `TRUE` は有効になりません。境界判定は先頭文字だけなので、後続文字が不正・追加文字でも結果は変わりません。未設定・空文字・先頭が `1` 以外の場合に CPU を選ばないことは示されていますが、GPU 選択先が利用できない場合の結果はこの変数の判定だけでは決まりません。

## 有効になる条件

- `HY4S_CPU_DEVICE` を読む `hy4s::Q()` が実行される SYCL 経路であること。Strata の SYCL ビルドは `fat`、`bmg`、`acm` のいずれも同じ `sy_main.cpp` をコンパイルし、この判定を特定の `HY4S_*` build macro で囲っていません（`engine/src/hy4flash/sycl/build_hy4_sycl.sh:26-40,62-68`、`engine/src/hy4flash/sycl/sy_common.h:165-175`）。
- queue 初期化時に先頭文字が `1` であること。その場合、`Q()` は `sycl::cpu_selector_v` を queue に渡します。GPU 一覧、`HY4S_BACKEND` による GPU backend の絞り込み、および primary GPU index を使う通常分岐は通りません（`engine/src/hy4flash/sycl/sy_common.h:94-113,165-175`）。
- main は `ONEAPI_DEVICE_SELECTOR` が未設定なら、`HY4S_BACKEND=opencl` のとき `opencl:gpu`、それ以外は `level_zero:gpu` を設定します。これは CPU 分岐とは別の初期化処理であり、Strata のソースから SYCL runtime がこの組み合わせをどう解決するかは断定できません（`engine/src/hy4flash/sycl/sy_main.cpp:79-92`）。
- `--gpu` / `--gpus` / `--devices` の指定は通常の GPU 選択用です。CPU 分岐に入ると `Q()` は GPU index による queue 構築を行いません。ただし `--gpu` は `ONEAPI_DEVICE_SELECTOR` を設定する経路もあるため、その外部 runtime 上の影響は本調査の対象外です（`engine/src/hy4flash/sycl/sy_main.cpp:199-214`、`engine/src/hy4flash/sycl/sy_common.h:165-175`）。

## 実行時の詳細

`Q()` の関数内 static queue を初めて初期化するときに環境を読み、以後は同じ queue を返します。したがって初回 `Q()` 呼び出し前に設定した値が判定に使われ、queue 初期化後のプロセス内環境変更はこの選択をやり直しません（`engine/src/hy4flash/sycl/sy_common.h:154-176`）。CPU 分岐では `sycl::queue{sycl::cpu_selector_v, make_props()}` を構築します。通常分岐では GPU を列挙して primary index を範囲内に収めて選び、GPU 一覧が空なら `gpu_selector_v` を指定します（同 `:165-175`）。

共有 queue はカーネル・メモリー操作などで利用されます（例: `engine/src/hy4flash/sycl/sy_vision.h:31-43`、`engine/src/hy4flash/sycl/sy_common.h:264-284`）。サーバー経路は処理開始時に `Q()` からデバイス情報を取得してログに出し、その後モデルを読み込みます（`engine/src/hy4flash/sycl/sy_serve.h:235-245`）。同じ初期化はモデル処理など他の SYCL 経路でも共有されます。`--version` のように queue に触れず早期終了する経路には適用されません（`engine/src/hy4flash/sycl/sy_main.cpp:117-123`）。

## ログと測定値

この変数専用の有効・無効ログはありません。サーバー経路では選択後の device 名などを `[gpu] %s, %.2f GiB (runtime: %s)` の形式で stderr に出します。CPU 分岐でもこの書式は同じです（`engine/src/hy4flash/sycl/sy_serve.h:238-240`）。

CPU selector を含む queue 構築などで `sycl::exception` が発生した場合、通常実行では stderr に `SYCL exception: %s` を出して終了コード 4 を返し、serve 経路では stdout に `ERR sycl: %s` を出して戻り値 1 を返します。例外の発生条件や `what()` の内容は SYCL runtime に依存するため、Strata の動作としてはここまでを記載します（`engine/src/hy4flash/sycl/sy_main.cpp:612-615`、`engine/src/hy4flash/sycl/sy_serve.h:532-535`）。この変数に関する測定値は `docs/DETAILS.md` に見つかりませんでした。

## 根拠

- 候補一覧への掲載: `docs/envvars/000_envvers.md:405`。
- 文字判定・selector 分岐・queue の static cache: `engine/src/hy4flash/sycl/sy_common.h:154-176`。
- 製品 runner のビルド対象: `engine/src/hy4flash/sycl/build_hy4_sycl.sh:62-68`。
- SYCL backend と selector 環境の設定: `engine/src/hy4flash/sycl/sy_main.cpp:79-92`。
- CLI の GPU index 決定: `engine/src/hy4flash/sycl/sy_main.cpp:199-214`。
- serve 起動後の queue 利用・device ログ: `engine/src/hy4flash/sycl/sy_serve.h:235-245`。
- queue による SYCL 処理の例: `engine/src/hy4flash/sycl/sy_vision.h:31-43`、`engine/src/hy4flash/sycl/sy_common.h:264-284`。
- 例外の観測経路: `engine/src/hy4flash/sycl/sy_main.cpp:612-615`、`engine/src/hy4flash/sycl/sy_serve.h:532-535`。
