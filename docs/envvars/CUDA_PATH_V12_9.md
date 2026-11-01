# `CUDA_PATH_V12_9`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Windows の vision reader パッケージ用ビルドスクリプトで、CUDA 12.9 toolkit の場所を `CUDA_PATH` に設定する候補として読みます。Strata の実行時エンジンがこの変数を読む箇所は見つかりませんでした。対象は `packaging/build_vision_windows.bat` の `cuda12` variant です。

## 値と判定

| 状態 | スクリプトの処理 |
|---|---|
| `CUDA_PATH_V12_9` が未設定または空 | `CUDA_PATH` を変更せず、既存の `CUDA_PATH` を使う。これも未設定なら `CUDA_PATH is not set: install the cuda12 toolkit` を表示して終了コード 1。 |
| `CUDA_PATH_V12_9` が設定済み | その値をそのまま `CUDA_PATH` に代入し、元からある `CUDA_PATH` を上書きする。 |
| 値が不正なパス、または `bin\\nvcc.exe` がない | `no nvcc.exe in %CUDA_PATH%\\bin` を表示して終了コード 1。 |
| 値が指す場所に `bin\\nvcc.exe` がある | パス文字列や toolkit のバージョン番号を追加 parse せず、そのパスを後続の CMake 引数に渡す。 |

ここでの判定は Windows バッチの `if defined` です。数値・真偽値としては変換せず、許可範囲や clamp もありません。明示的な空値は `if defined` を満たさず、`CUDA_PATH` の既定候補として採用されません。

## 有効になる条件

- Windows 上で `packaging\\build_vision_windows.bat cuda12 <stage folder>` を呼び出した場合に限り、この変数の分岐に入ります。`cuda13` variant は `CUDA_PATH_V13_0` を見ます。
- `CUDA_PATH_V12_9` が定義されていれば既存の `CUDA_PATH` より優先されます。未定義なら既存の `CUDA_PATH` が fallback です。
- どちらの値も toolkit の版を検証しません。最初に `CUDA_PATH\\bin\\nvcc.exe` の存在だけを確認します。
- stage 引数が欠けている場合など、先行する引数検査で usage に進むと変数処理には到達しません。

## 実行時の詳細

これはバッチ起動時に一度評価されるビルド用設定で、エンジンの実行中に読む設定ではありません。選択後、スクリプトは `CUDA_PATH\\bin\\nvcc.exe` と `CUDAToolkit_ROOT` を CMake に渡して vision target を構成し、ビルド・配置・パッケージ metadata 更新へ進みます。CMake 構成、ビルド、コピー、metadata 更新の各コマンドが失敗すると、スクリプトは終了コード 1 を返します。この変数自体に関するログはなく、パス検査の失敗時に上記のエラー文が出ます。

## 根拠

- `packaging/build_vision_windows.bat:20-32`: 引数と `cuda12` variant の選択、および `CUDA_PATH_V12_9` が定義されている場合の `CUDA_PATH` 上書き。
- `packaging/build_vision_windows.bat:33-39`: `VISION_ARCHS` / toolkit path / `nvcc.exe` / llama.cpp の検査と失敗時のメッセージ・終了コード。
- `packaging/build_vision_windows.bat:57-64`: 選ばれた toolkit path を CMake に渡し、vision target のビルド、配置、metadata 更新を行う流れ。
- `packaging/ENGINE-COMPONENT.md:105-106`: Windows `cuda12` variant が CUDA 12.9 と当該バッチを使うことの補足。`docs/DETAILS.md` にこの変数の追加説明は見つかりませんでした。
