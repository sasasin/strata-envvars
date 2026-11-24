# `CUDA_LAUNCH_BLOCKING`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

Strata の engine はこの変数を CUDA build で読み、値が整数として非ゼロなら stderr に verify window の停止リスクを警告します。serve watchdog が停止を検出した際も、停止理由の注記に使います。Strata 自身はこの変数を設定・削除・子プロセスへ転送せず、値によって生成 token や選択結果を変える処理もありません。CUDA 環境での launch の意味そのものは外部側の動作なので、ここでは説明しません。読み取りと警告は `engine/src/program/generate.cpp:1935-1941,3777-3780,16313-16321` にあります。

Strata の verifier は graph を起動し、GPU が待つ CPU doorbell をホスト側で処理します。実装コメントは、blocking launch では graph 完了まで `cudaGraphLaunch` が戻らず最初の verify window が終わらない経路を説明しています（`engine/src/program/generate.cpp:1932-1934`）。CUDA build で `STRATA_VERIFY_ASYNC_LAUNCH=1` を有効にすると、別の `HostGraphLaunch` が graph launch を helper thread に移し、呼び出し側が doorbell を処理できる構成になります（`engine/src/core/verify.cpp:3895-3928`、`engine/include/strata/core/host_graph_launch.hpp:11-30`）。この設定があっても `CUDA_LAUNCH_BLOCKING` の起動警告は抑止されません。

## 値と判定

| ビルド条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `STRATA_USE_HIP` または `STRATA_HIP_GFX906` が定義された build | `false` | なし。環境を読み取らず `false` を返す | すべて（設定値にかかわらず） |
| 上記以外の build（CUDA engine 経路） | `false` | `std::atoi(v) != 0` となる値。例: `1`, `-1`, `1tail`, ` 1` | `std::atoi(v) == 0` となる値。例: 空文字、`0`, `0tail`, `true`, `false`, 空白だけ |

CUDA 側は文字列全体の検証をせず、`atoi` が読む先頭の整数部分だけで判定します。先頭の空白と符号は `atoi` の変換規則に従い、数値の後ろは無視されます。したがって `1tail` は有効、`0tail` は無効です。大文字小文字の比較はありません。数値部分がない文字列は 0 として無効になります。Strata は整数範囲の検査や clamp をしません。int で表現できない数値の扱いは、このコードから保証できません。値は `getenv` の有無だけでは判定されないので、空文字は「設定あり」でも有効にはなりません（`engine/src/program/generate.cpp:1935-1941`）。

## 有効になる条件

- 値の判定が true になるのは CUDA 側の build だけです。HIP build（`STRATA_USE_HIP` または `STRATA_HIP_GFX906`）では値を読まず false を返し、HIP 固有の blocking 設定も調べません（`engine/src/program/generate.cpp:1935-1941`）。
- 起動警告は `main` の通常の engine 初期化経路で判定が true のときに出ます。`--version`、`--families`、`--geometry`、`--expert-support` は同箇所より前に return するため、この警告判定を通りません（`engine/src/program/generate.cpp:3701-3740,3777-3780`）。
- serve watchdog の停止注記は、watchdog が有効で、request の進捗停止が watchdog の停止分岐に達したときに限られます。`STRATA_WATCHDOG_S=0` なら `limit` が 0 となり watchdog thread は作られません（`engine/src/program/generate.cpp:16261-16278,16311-16321`）。
- `STRATA_VERIFY_ASYNC_LAUNCH=1` は verifier の launch を helper thread に移す別設定です。CUDA build の verifier では `STRATA_VERIFY_HGL` が定義され、値の先頭文字が `'1'` のとき helper launch を選びます。これは `CUDA_LAUNCH_BLOCKING` 判定とは独立しており、起動警告を無効にしません（`engine/src/core/verify.cpp:2-5,3895-3928`）。
- `--gpu` を含む CLI 引数や別の環境変数による `CUDA_LAUNCH_BLOCKING` の上書き・優先順位処理は、この変数の読み取り箇所にはありません（`engine/src/program/generate.cpp:1935-1941,3777-3780`）。

## 実行時の詳細

`launch_blocking()` は static cache を持たず、呼び出されるたびに `getenv` と `atoi` を実行します。engine 初期化時の警告判定と、watchdog が停止行を出す時点で再評価されるため、コード上はその時点の環境値を読みます（`engine/src/program/generate.cpp:1935-1941,3777-3780,16313-16317`）。

engine 初期化時に値が非ゼロなら、次の stderr 警告を出します。これは値の設定・修正ではなく注意喚起です。

```text
warning: CUDA_LAUNCH_BLOCKING=1: the verify windows cannot run with blocking launches, so the first one after a prompt hangs until the watchdog ends the engine (#1341). Unset it; STRATA_PF_STEP_SYNC=1 narrows down a failing prompt step without it
```

serve watchdog が停止と判断した場合は、進捗停止時間と場所を示す行の末尾に `; CUDA_LAUNCH_BLOCKING=1 is set, and no verify window can finish with it (#1341)` を付けます。その後 stall report を出力し、GPU wait を解放して stderr を flush し、`std::abort()` します。watchdog のコードコメントは、その後 server が engine を再起動する経路と説明しています（`engine/src/program/generate.cpp:16261-16264,16313-16321`）。

## ログと測定値

上記の起動時警告と watchdog 停止行が Strata から観測できる出力です。該当する起動警告は値が false の場合には出ません。`docs/DETAILS.md` の環境変数表も確認しましたが、この変数の測定値は記載されていません（例として `docs/DETAILS.md:1270` は `STRATA_VERIFY_ASYNC_LAUNCH` の説明です）。

## 根拠

- `engine/src/program/generate.cpp:1932-1941` — build 条件、`getenv`、`atoi` 判定。
- `engine/src/program/generate.cpp:3701-3740,3777-3780` — 早期 return と通常初期化時の警告。
- `engine/src/program/generate.cpp:16261-16278,16311-16321` — watchdog の有効条件、注記、停止処理。
- `engine/src/core/verify.cpp:2-5,3895-3928`、`engine/include/strata/core/host_graph_launch.hpp:11-30` — verifier の build 条件と helper-thread launch。
- `docs/DETAILS.md:1260-1275` — 関連設定と測定値記載の照合。
