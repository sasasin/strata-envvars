# `HIP_PLATFORM`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリや GPU ドライバーが読む値の意味は対象外。

## 役割

Strata の setup.py と同梱 HIP ビルドスクリプトが、HIP 関連のビルド子プロセス向けに `HIP_PLATFORM=amd` を設定します。これは Strata engine の実行時設定ではありません。調査対象の Strata ソースで、利用者が設定した `HIP_PLATFORM` の読み取り、値の検証、実行時分岐は見つかりませんでした。

## 値と判定

| 経路 | 入力時の未設定・空文字・その他の値 | Strata が行う設定 |
|---|---|---|
| setup.py の HIP engine ビルド | 区別せず `os.environ.update` で上書き | `amd` |
| setup.py の GPU HIP 画像 reader ビルド | `vision == "gpu"` で、かつ `hipconfig` が見つからず `ROCM_PATH` も未設定の場合に上書き。それ以外は既存値を変更しない | 上書きする場合は `amd` |
| setup.py の HIP 画像生成器ビルド | `backend == "hip"` の分岐で上書き | `amd` |
| 同梱 Linux/Windows HIP ビルドスクリプト | シェルまたはバッチ内で既存値にかかわらず固定値を設定 | `amd` |

Strata は既存値の空文字判定、文字列比較、数値変換、無効値の警告や fallback を行いません。CLI 引数との優先順位もありません。HIP engine が既に最新で setup.py がビルド関数から早期 return する場合、engine の経路では環境変数を更新しません。画像 reader のビルドでも、上表の条件を満たさなければ既存値をそのままにします。

## 有効になる条件

- 初回の HIP engine 構築、または既存 HIP engine のソース更新で `build_engine_hip()` がコンパイルへ進む場合、ROCm root の選択後に `HIP_PLATFORM=amd` を設定します。選択 root を用いる HIP engine 経路は `setup.py` の HIP 分岐から呼ばれます。
- GPU HIP 画像 reader の構築では、`build_vision_hip()` が `vision == "gpu"` かつ `hipconfig` と `ROCM_PATH` の両方が未検出のときだけ、HIP 関連環境とともにこの変数を設定します。
- HIP backend の画像生成器では `build_image_engine()` が `backend == "hip"` の分岐へ入る場合に設定します。画像生成器の利用自体は `--images` の設定に依存します。
- `packaging/build_hip_linux.sh`、`packaging/build_hip_gfx1103.sh`、`tools/hip/build_windows.bat`、`tools/dsv41/win/build_hip_win.bat` は、それぞれ HIP 用 CMake configure/build より前に固定値を設定します。
- Strata engine の通常起動、サーバーモード、モデルや GPU の状態で `HIP_PLATFORM` を読む分岐はありません。

## 実行時の詳細

HIP engine の setup 経路では `HIP_PLATFORM` を含む環境設定の後、`cmake_build()` が configure と build を `run()` で起動します。`run()` は明示的な別環境がなければ `os.environ` のコピーを `subprocess.run()` に渡すため、設定値はそのビルド子プロセスに継承されます。HIP 画像 reader と画像生成器のビルドも同じ `run()` / `cmake_build()` 経路を使います。設定は setup.py プロセス内で行い、Strata engine の起動時には行いません。

Strata は `HIP_PLATFORM` に専用のログや警告を出しません。ビルドコマンドは通常 `  > ...` と表示され、コマンドが失敗した場合は `command failed (exit N): ...` の経路で失敗しますが、Strata はその失敗を `HIP_PLATFORM` の値に結び付けません。Linux の HIP ビルドスクリプトも CMake の終了コードを確認し、失敗時は build status に記録して終了します。

`__HIP_PLATFORM_AMD__` は CMake や C++ のコンパイル時 macro として現れますが、`HIP_PLATFORM` 環境変数を Strata が読み取った箇所ではありません。ここではその macro や外部ビルドツール・ライブラリ側の動作を説明しません。

## 文書との照合

`docs/STRIX_HALO.md` は ROCm SDK の利用例で `HIP_PLATFORM=amd` を他の環境変数とともに export するよう案内しています。同梱ビルドスクリプトと setup.py にも同じ値を設定する実装があります。これはビルド環境の設定であり、Strata engine が利用者指定の値を読むという説明ではありません。

## 根拠

- 候補一覧: `docs/envvars/000_envvers.md:417`。
- setup.py の HIP engine 判定、ROCm root 後の環境設定、CMake 起動: `setup.py:4797-4827,7798`。
- 既存 HIP engine の更新経路: `setup.py:5550-5562`。
- GPU HIP 画像 reader の条件付き設定とビルド: `setup.py:4876-4900`。
- HIP 画像生成器の環境設定と CMake 起動: `setup.py:5032-5037,5800-5824`。
- setup.py の子プロセス環境継承と失敗報告: `setup.py:959-978`。
- 同梱 HIP ビルドスクリプトの設定: `packaging/build_hip_linux.sh:52-65`, `packaging/build_hip_gfx1103.sh:9-11`, `tools/hip/build_windows.bat:64-79`, `tools/dsv41/win/build_hip_win.bat:28-41`。
- Strix Halo 向け環境設定例: `docs/STRIX_HALO.md:120-128`。
- 全参照検索では、setup.py の上記設定とビルドスクリプトの設定以外に、候補名を環境から読む Strata 所有コードは確認できませんでした。残る `__HIP_PLATFORM_AMD__` は別のコンパイル時識別子です。
