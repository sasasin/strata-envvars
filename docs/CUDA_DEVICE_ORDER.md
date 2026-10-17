# `CUDA_DEVICE_ORDER`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリや GPU driver 自身がこの変数をどう解釈するかは対象外。

## 役割

Strata は `CUDA_DEVICE_ORDER` を CUDA のデバイス番号を指定する起動経路で `PCI_BUS_ID` に設定し、GPU 番号が nvidia-smi/PCI 番号と対応する前提で `CUDA_VISIBLE_DEVICES` を組み立てます。C++エンジンでは `--gpu` が指定されたとき、Python サーバーでは GPU 指定を CUDA 子プロセスへ渡すときに設定します。Strata ソースにこの変数の値を読み取って分岐する箇所はありません。

## 値と判定

| 経路 | 条件 | 設定値と既存値の扱い |
|---|---|---|
| `strata generate` エンジン | 引数列に `--gpu LIST` がある | `CUDA_DEVICE_ORDER` を `PCI_BUS_ID` に設定し、上書きする。`--gpu` がなければこの処理では変更しない。 |
| `serve` のエンジン子プロセス | HIP backend ではなく、設定から GPU リストが得られる | 子プロセス用環境を親環境から複製した後、`PCI_BUS_ID` を設定し、`CUDA_VISIBLE_DEVICES` も設定する。その後 `cfg["env"]` の各値を適用するため、そこに `CUDA_DEVICE_ORDER` があれば上書きできる。 |
| `serve` の vision 子プロセス | `vision.cuda_device` があり、HIP backend ではない | コピーした環境に `PCI_BUS_ID` と指定 GPU を設定する。`vision_env()` 自体では `cfg["env"]` の適用はしない。 |
| `serve` の画像生成子プロセス | `gpu` があり、backend が `cuda` | `PCI_BUS_ID` と `CUDA_VISIBLE_DEVICES` を設定する。その後画像設定の `env` を適用するので、`env` に同名キーがあれば上書きできる。 |
| GPU 速度スコア取得用 Python 子プロセス | `gpu_speed_scores()` の計測処理 | 親環境を複製して `CUDA_DEVICE_ORDER=PCI_BUS_ID` を明示し、`CUDA_VISIBLE_DEVICES` を除去してから子 Python を起動する。 |

いずれも値の parse、大小文字比較、空文字の特別扱いはありません。Strata が設定する値は固定文字列 `PCI_BUS_ID` です。親環境に別の値があっても、表に記した設定経路ではその値を読み取って判断せず、代入で置き換えます。未設定時に Strata が自動で設定するのは、上記の条件を満たした場合だけです。

## 有効になる条件

- `strata generate` では `--gpu` が必要です。変数を先に設定して起動しただけでは、C++側はそれを参照も変更もしません。`--gpu` の処理は CUDA の最初の呼び出しより前に行われます。
- `serve` の `child_env()` は、設定に GPU リストがあり、HIP backend ではない場合に CUDA 用の可視 GPU と順序変数を設定します。HIP backend の分岐では `HIP_VISIBLE_DEVICES` を設定し、この箇所では `CUDA_DEVICE_ORDER` を設定しません。
- `serve` の `vision_env()` は `vision.cuda_device` が未指定なら環境をそのまま返します。指定時は backend に応じて CUDA または HIP の可視 GPU 変数を設定します。
- 画像生成では `gpu` と `backend: cuda` の組み合わせで CUDA 用設定を作ります。Vulkan/HIP の GPU 指定では `CUDA_DEVICE_ORDER` は設定されません。
- サーバーの `cfg["env"]` または画像生成設定の `env` は、各関数が既定の CUDA 設定を作った後に適用されます。同名キーがあれば設定値を上書きできます。

## 実行時の詳細

C++エンジンは起動時に引数列を走査し、最初に見つけた `--gpu` の値を使います。既存の `CUDA_VISIBLE_DEVICES` が空でなく、引数値と異なる場合は stderr に `warning: --gpu %s overrides %s=%s from the environment` を出します。`CUDA_DEVICE_ORDER` の既存値については警告せず、Windows では `_putenv_s`、それ以外では `setenv(..., 1)` で固定値を書き込みます。その後に実行される CUDA 初期化とオプション処理に先立つ設定です。

Python サーバー側は子プロセス用の環境辞書を作り、値を設定してから起動処理へ渡します。`gpu_speed_scores()` では独立した Python subprocess にも値を渡します。これらは環境変数の値を Strata が読み取る処理ではなく、Strata が子プロセス環境を構成する処理です。Strata 所有ソース内に、変数の値に応じたログやエラーはありません。

## 根拠

- `src/program/generate.cpp:791-793` は `--gpu` の説明、`src/program/generate.cpp:2229-2250` は CUDA 初期化前の引数走査、既存 `CUDA_VISIBLE_DEVICES` への警告、OS別の設定処理。
- `serve/server.py:2754-2782` は速度スコア用 subprocess の環境設定、`serve/server.py:2858-2875` はエンジン子プロセス環境の設定と `cfg["env"]` による後続上書き、`serve/server.py:2919-2932` は vision 子プロセス環境。
- `serve/images.py:131-149` は画像生成環境の CUDA 設定と画像設定 `env` の後続適用。
- `docs/SECOND_GPU.md:225` に `CUDA_DEVICE_ORDER=PCI_BUS_ID` の説明があります。ここでは性能値や driver 内部の採番仕様は根拠にせず、現行ソースで確認できた Strata の設定動作だけを記載しました。
