# `HIP_COMPILER`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata の HIP エンジンをソースからビルドするとき、setup.py がビルド用プロセス環境に `HIP_COMPILER=clang` を設定します。これは利用者が値を指定して Strata の実行時動作を切り替える設定ではありません。調査対象の Strata ソースに、既存の `HIP_COMPILER` 値を読み取る箇所はありません。

## 値と判定

| 経路 | unset・空文字・その他の既存値 | Strata が設定する値 |
|---|---|---|
| HIP エンジンのローカルビルド | 区別せず、`os.environ.update` で上書き | `clang` |
| GPU 用 HIP 画像 reader のビルド | `hipconfig` が見つからず、かつ `ROCM_PATH` も未設定の場合に上書き。それ以外は既存値を変更しない | 上書きする場合は `clang` |
| `packaging/build_hip_linux.sh` | シェル内の既存値にかかわらず `export` で上書き | `clang` |

Strata は `HIP_COMPILER` の文字列比較、数値変換、空文字判定、無効値の警告や fallback を行いません。setup.py が環境を更新するのはビルド関数が実際に進むときで、エンジンが既に最新でビルド関数が早期 return する場合はそのエンジン経路で更新されません。CLI 引数との優先順位もありません。画像生成器の HIP 経路や `tools/image/qimage.py` は `HIP_COMPILER` を設定せず、CMake に `CMAKE_HIP_COMPILER` を明示して渡します。

## 有効になる条件

- `build_engine_hip()` がキャッシュ済みエンジンの早期 return をせず、HIP エンジンのビルドへ進むと、選択された ROCm root に基づく環境設定の一部として `HIP_COMPILER` を `clang` にします。
- `build_vision_hip()` では、GPU 用 reader を求め、かつ `hipconfig` が見つからず `ROCM_PATH` も未設定のときだけ、この変数を含む HIP 環境一式を設定します。その後の CMake 呼び出しには別途 `CMAKE_HIP_COMPILER` が渡されます。
- `packaging/build_hip_linux.sh` はビルド処理の開始時に `HIP_COMPILER=clang` を export します。
- Strata の通常のエンジン実行時にこの変数を読む分岐は見つかりません。実行時、サーバーモード、モデル状態による有効化条件はありません。

## 実行時の詳細

setup.py の `run()` は `env` を省略すると `os.environ` のコピーを子プロセス環境に使います。`cmake_build()` は configure と build の各コマンドを `run()` で起動します。このため、前述の setup.py 経路で設定された値はその後のビルド子プロセスへ渡されます。`build_engine_hip()` では同時に `HIP_PLATFORM=amd`、`HIP_RUNTIME=rocclr`、`ROCM_PATH`、`HIP_PATH` なども設定します。ここではそれら外部ツール側の解釈や効果は扱いません。

setup.py が `HIP_COMPILER` の値に応じて出す専用ログ、警告、終了・失敗経路はありません。ビルド全体には通常の CMake コマンド失敗処理がありますが、Strata のコードは失敗を `HIP_COMPILER` の値に結び付けていません。`packaging/build_hip_linux.sh` では CMake の終了コードを `chk` が確認し、失敗時は build status に記録して終了します。

## 根拠

- 候補一覧: `docs/envvars/000_envvers.md:413`。
- HIP エンジンのキャッシュ判定と環境設定: `setup.py:4797-4803,4809-4816`。
- GPU 画像 reader の条件付き環境設定と CMake 呼び出し: `setup.py:4876-4885,4890-4900`。
- 子プロセスへの環境継承と CMake 実行: `setup.py:959-978,5800-5824`。
- 画像生成器は env 設定ではなく `CMAKE_HIP_COMPILER` を渡す: `setup.py:5032-5037`, `tools/image/qimage.py:124-135`。
- 同梱 Linux HIP ビルドスクリプトでの固定 export と失敗確認: `packaging/build_hip_linux.sh:52-56,60-65`。
- 全参照検索では、上記以外に候補名の参照は文書・コメント・CMake 引数例に限られ、Strata コードによる既存値の読み取りは確認できませんでした。
