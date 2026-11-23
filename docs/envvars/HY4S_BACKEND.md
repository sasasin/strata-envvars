# `HY4S_BACKEND`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

SYCL 版 Hy4-Flash runner `strata-hy4-sycl` が優先する GPU backend を選ぶ。値が小文字の `opencl` と完全一致すると Strata は `ONEAPI_DEVICE_SELECTOR` に `opencl:gpu` を設定し、GPU 列挙でも OpenCL device を優先する。それ以外は `level_zero:gpu` を設定し、Level Zero device を優先する。GPU の列挙結果には希望 backend がなければ列挙先頭 device の backend へ fallback するため、変数は常にその backend の使用を保証するものではない。実装は `sy_main.cpp` の起動処理と `sy_common.h` の device 列挙にある（`engine/src/hy4flash/sycl/sy_main.cpp:79-92`、`engine/src/hy4flash/sycl/sy_common.h:94-112`）。

この変数を読む実装は SYCL 版に限られる。ビルドスクリプトは `sy_main.cpp` を含む `strata-hy4-sycl` を Intel oneAPI `icpx` で作る（`engine/src/hy4flash/sycl/build_hy4_sycl.sh:1-3,62-68`）。

## 値と判定

起動時と `enum_gpu_devices()` の各呼び出しで `std::getenv` を行い、値全体を大文字小文字の区別ありで文字列比較する。trim、数値変換、真偽値 parse、無効値の警告はない。`opencl` 以外はすべて Level Zero 希望として扱う（`engine/src/hy4flash/sycl/sy_main.cpp:87-92`、`engine/src/hy4flash/sycl/sy_common.h:96-101`）。

| 条件 | 未設定 | OpenCL 希望になる値 | Level Zero 希望になる値 |
|---|---|---|---|
| SYCL runner の起動・GPU 列挙 | Level Zero | `opencl` | 空文字、`OpenCL`、`level_zero`、`0`、その他すべて |

Level Zero が存在しない場合など、希望 backend で絞った結果が空なら、`enum_gpu_devices()` は最初に列挙された GPU と同じ backend の device 群を返す。GPU 自体が列挙されなければ空のまま返す（`engine/src/hy4flash/sycl/sy_common.h:96-112`）。

## 有効になる条件

- `strata-hy4-sycl` の SYCL 実行経路で使われる。CUDA/HIP の Hy4 runner にはこの読み取り箇所はない（`engine/src/hy4flash/sycl/build_hy4_sycl.sh:1-3,62-68`）。
- プロセス起動時に `ONEAPI_DEVICE_SELECTOR` が未設定の場合、Strata は `HY4S_BACKEND=opencl` なら `opencl:gpu`、それ以外なら `level_zero:gpu` を設定する。`ONEAPI_DEVICE_SELECTOR` は値が空でも設定済みと判定され、その場合 Strata はこの起動時設定を行わない（`engine/src/hy4flash/sycl/sy_main.cpp:87-92`）。
- `ONEAPI_DEVICE_SELECTOR` が起動時から設定済みなら、`HY4S_BACKEND` による起動時の selector 設定は抑止される。ただし `enum_gpu_devices()` は引き続き `HY4S_BACKEND` を読み、希望 backend で列挙結果を絞る（同 `sy_main.cpp:87-92`、`engine/src/hy4flash/sycl/sy_common.h:96-112`）。
- `--gpu N` は明示 selector がないとき、`HY4S_BACKEND` に応じた `opencl:gpu:N` または `level_zero:gpu:N` を `ONEAPI_DEVICE_SELECTOR` に設定する。既存 selector がある場合はそれを書き換えず、primary GPU index に `N` を使う（`engine/src/hy4flash/sycl/sy_main.cpp:199-214`）。
- `--gpus` / `--devices` または `HY4_GPUS` による複数 GPU 指定は `enum_gpu_devices()` の結果を使って index を解決するため、この変数の backend 選択の影響を受ける（同 `sy_main.cpp:94,199-205`、`engine/src/hy4flash/sycl/sy_common.h:96-112`）。
- `HY4S_CPU_DEVICE` の先頭文字が `1` の場合、`Q()` は GPU 列挙より先に CPU selector の queue を作るため、その queue の device 選択では `enum_gpu_devices()` を通らない（`engine/src/hy4flash/sycl/sy_common.h:154-175`）。ただし `--gpus` / `--devices` の指定があると、main は queue 作成より前に GPU を列挙する（`engine/src/hy4flash/sycl/sy_main.cpp:199-205`）。
- `--version`、`--info`、`--export-tokenizer` は起動時の環境読み取り・selector 設定後に早期 return するため、その実行では通常のモデル用 GPU queue へ到達しない（`engine/src/hy4flash/sycl/sy_main.cpp:79-92,117-127`）。

## 実行時の詳細

`main()` は引数解析より前に `ONEAPI_DEVICE_SELECTOR` の有無を調べ、`HY4S_BACKEND` を読み、selector が未設定なら `hy4s_setenv` で設定する。`hy4s_setenv` は Windows では `_putenv_s`、それ以外では `setenv` を呼ぶ（`engine/src/hy4flash/sycl/sy_main.cpp:79-92`、`engine/src/hy4flash/sycl/sy_common.h:31-40`）。その後、必要に応じて `--gpu` の selector 設定または複数 GPU index の解決を行う（`engine/src/hy4flash/sycl/sy_main.cpp:199-214`）。

`HY4S_BACKEND` は `enum_gpu_devices()` の呼び出しごとにも再読込される。呼び出し元は、複数 GPU 指定の解決、`Q()` による最初の GPU queue 選択、peer GPU 初期化時の列挙である（`engine/src/hy4flash/sycl/sy_main.cpp:199-205`、`engine/src/hy4flash/sycl/sy_common.h:154-175`、`engine/src/hy4flash/sycl/sy_peer.h:182-193`）。`Q()` の queue は関数内 `static` で一度作成され、以後同じ queue を返す。そのため queue 作成後にプロセス内の環境値を変えても既存 queue の device は切り替わらない。一方、後続の `enum_gpu_devices()` はその時点の値を再読込する（`engine/src/hy4flash/sycl/sy_common.h:154-177`）。

希望 backend の device がなければ列挙先頭の GPU backend へ fallback する。GPU 列挙が空なら `Q()` は `gpu_selector_v` を使う。`--gpus` / `--devices` 指定時の列挙は main の `try` より前で実行されるため、その箇所で発生した SYCL 例外を main の `catch` は捕捉しない。通常の queue 作成など `try` 内で発生した SYCL 例外は stderr に `SYCL exception: %s\n` を出して終了コード 4 を返す（`engine/src/hy4flash/sycl/sy_main.cpp:199-205,255-256,612-615`、`engine/src/hy4flash/sycl/sy_common.h:169-175`）。

## ログと測定値

`HY4S_BACKEND` の値や、希望 backend が存在しないため fallback したことを知らせる専用ログはない。GPU queue 初期化が成功した場合は選択された device 名・platform などを stderr の `[gpu] ...` 行に出す（`engine/src/hy4flash/sycl/sy_main.cpp:255-259`）。SYCL 例外の観測経路は「実行時の詳細」に記載したとおり（同 `sy_main.cpp:612-615`）。コメント中の性能比較値は実行コードの測定結果としては扱わず、本書には記載しない。

## 根拠

- 起動時の環境読み取り、selector 設定: `engine/src/hy4flash/sycl/sy_main.cpp:79-92`
- 環境変数設定 helper: `engine/src/hy4flash/sycl/sy_common.h:31-40`
- backend 判定、列挙と fallback: `engine/src/hy4flash/sycl/sy_common.h:94-112`
- `--gpu` / `--gpus` / `--devices` と `HY4_GPUS`: `engine/src/hy4flash/sycl/sy_main.cpp:94,133-136,199-214`
- CPU queue、GPU queue の static cache: `engine/src/hy4flash/sycl/sy_common.h:154-177`
- peer GPU の再列挙: `engine/src/hy4flash/sycl/sy_peer.h:182-193`
- runner のビルド入口: `engine/src/hy4flash/sycl/build_hy4_sycl.sh:1-3,62-68`
- GPU 情報ログと SYCL 例外: `engine/src/hy4flash/sycl/sy_main.cpp:255-259,612-615`
