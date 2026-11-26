# `HIP_RUNTIME`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

この名前を Strata のエンジン実行時コードが読み取る箇所は見つからなかった。確認できた用途は、Strata の AMD/HIP ビルド用スクリプトが HIP のビルド環境に `HIP_RUNTIME=rocclr` を設定することに限られる。`tools/packaging/build_hip_linux.sh` と `tools/packaging/build_split_hip.sh` は CMake / Ninja を起動する前に設定し、`terminal/setup.py` はローカルの HIP エンジン、または条件を満たした GPU 画像リーダーをビルドする前に Python プロセス環境へ設定する（`tools/packaging/build_hip_linux.sh:52-68`、`tools/packaging/build_split_hip.sh:27-38`、`terminal/setup.py:5681-5701`、`terminal/setup.py:5750-5774`）。

## 値と判定

Strata は利用者から受け取った `HIP_RUNTIME` の値を判定しない。記載したビルド経路では値を固定文字列 `rocclr` に設定するため、それ以前の値は保持されない。unset、空文字、その他の値を Strata が有効・無効として parse する規則はない。

| ビルド経路 | 既存値（unset / 空 / その他） | Strata が設定する値 | 判定 |
|---|---|---|---|
| Linux HIP パッケージ (`build_hip_linux.sh`) | 問わない | `rocclr` | 引数の検証と変数設定を通過してスクリプトの 52 行目に達すると export する。`VISION_ONLY` の有無にかかわらず設定する。 |
| Linux HIP split エンジン (`build_split_hip.sh`) | 問わない | `rocclr` | 必須引数を得て 27 行目に達すると export する。 |
| `terminal/setup.py` の HIP エンジン | 問わない | `rocclr` | `build_engine_hip` がコンパイル経路へ進み、ROCm root を解決した後で `os.environ.update` が上書きする。 |
| `terminal/setup.py` の HIP 画像リーダー | 問わない | 条件成立時に `rocclr` | `vision == "gpu"` かつ `hipconfig` がなく `ROCM_PATH` も設定されていない場合に設定する。条件が偽ならこの箇所では変更しない。 |

シェルでは単純な固定値の export、Python では `os.environ.update` を使い、値文字列の比較・数値変換・大文字小文字や空白の検査はない（`tools/packaging/build_hip_linux.sh:52`、`tools/packaging/build_split_hip.sh:27`、`terminal/setup.py:5685-5686`、`terminal/setup.py:5754-5759`）。

## 有効になる条件

- Strata の Linux HIP パッケージビルドまたは split エンジンビルドを実行すると、それぞれのスクリプトが環境変数を設定してから CMake / Ninja を実行する（`tools/packaging/build_hip_linux.sh:52-68`、`tools/packaging/build_split_hip.sh:27-38`）。
- `terminal/setup.py` では、AMD/HIP エンジンのコンパイルが必要な経路で設定する。通常の準備では既製エンジンが選択されない場合、または AMD エンジンの更新・再ビルド経路が該当する（`terminal/setup.py:6492-6504`、`terminal/setup.py:9614-9625`）。
- GPU 画像リーダーのビルドでは、`vision == "gpu"` かつ `hipconfig` と `ROCM_PATH` の両方が環境にない場合にこの名前を含む ROCm 環境を設定する。すでにそのどちらかがある場合、この関数内では環境を設定し直さない（`terminal/setup.py:5750-5759`）。
- `terminal/setup.py` の `run` は、明示的な別環境が渡されなければ `os.environ` のコピーを `subprocess.run(..., env=env)` に渡す。`cmake_build` は `run(conf)` と `run(build)` を呼ぶため、この設定は CMake とビルド子プロセスへ継承される（`terminal/setup.py:1131-1152`、`terminal/setup.py:6793-6820`）。シェルの `export` も後続コマンドの環境に設定を渡す（`tools/packaging/build_hip_linux.sh:52-68`、`tools/packaging/build_split_hip.sh:27-38`）。

## 実行時の詳細

これは Strata の生成・推論時の挙動を切り替える設定ではなく、HIP のビルド子プロセスへ渡す値である。Strata 所有の通常エンジンソースに `HIP_RUNTIME` を読む箇所は見つからなかったため、起動時の読み取り、キャッシュ、CLI 引数との優先順位、生成結果への影響は該当しない。Python の環境設定はその `setup.py` プロセス内でビルドを呼ぶ直前に行い、CMake とビルド子プロセスには継承される（`terminal/setup.py:5685-5701`、`terminal/setup.py:1131-1152`、`terminal/setup.py:6793-6820`）。

Strata のビルドスクリプトは失敗時にそれぞれの一般的なビルド失敗経路へ進むが、`HIP_RUNTIME` の値に固有の警告・エラー・終了分岐はない（`tools/packaging/build_hip_linux.sh:46-47`、`tools/packaging/build_hip_linux.sh:63-68`、`tools/packaging/build_split_hip.sh:31-40`、`terminal/setup.py:1150-1156`）。この文書は、外部の HIP ツールチェーンが `HIP_RUNTIME` をどう解釈するかを説明しない。

## 根拠

- Linux HIP パッケージでの固定値設定と CMake / build 起動: `tools/packaging/build_hip_linux.sh:52-68`。
- Linux split HIP ビルドでの固定値設定と CMake / Ninja 起動: `tools/packaging/build_split_hip.sh:27-38`。
- 通常の HIP エンジンビルドでの環境更新と呼び出し: `terminal/setup.py:5681-5701`。
- GPU 画像リーダービルド用の条件付き環境更新: `terminal/setup.py:5750-5774`。
- setup の子プロセス環境継承: `terminal/setup.py:1131-1152`、`terminal/setup.py:6793-6820`。
- エンジン再ビルド経路と初期エンジン選択: `terminal/setup.py:6492-6504`、`terminal/setup.py:9614-9625`。
