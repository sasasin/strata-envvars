# `CUDA_PATH_V13_0`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Windows 用 vision reader (`strata-vision.exe`) を CUDA 13 variant としてビルドするときに、CUDA 13.0 toolkit の場所を指定するための環境変数です。`packaging/build_vision_windows.bat cuda13 <stage folder>` の経路だけで参照されます。Strata engine の通常起動時に読む設定ではありません。

このバッチは変数が定義されていれば、その値をバッチ内の `CUDA_PATH` にコピーし、後続の検査と CMake 引数に使います。値自体を数値や真偽値として parse せず、パス文字列として扱います。

## 値と判定

| 状態 | バッチの処理 |
|---|---|
| `cuda13` variant で未定義 | 既存の `CUDA_PATH` をそのまま使う。`CUDA_PATH` も未定義なら `CUDA_PATH is not set: install the cuda13 toolkit` を表示して終了コード 1。 |
| `cuda13` variant で定義済み | 値を `CUDA_PATH` に代入する。値が空または無効なパスであっても、バッチ側に別の parse や fallback はない。 |
| `cuda12` variant | `CUDA_PATH_V13_0` は参照しない。`CUDA_PATH_V12_9` が定義されていれば、そちらを `CUDA_PATH` に代入する。 |

定義済みの `CUDA_PATH_V13_0` は既存の `CUDA_PATH` より優先されます。未定義なら既存の `CUDA_PATH` が fallback です。バッチは `setlocal` を使うため、代入された `CUDA_PATH` はこのバッチとその子プロセスの範囲に限られ、呼び出し元の環境には残りません。空文字が Windows の環境で定義済みとして扱われる場合も値の検証はなく、次の `CUDA_PATH` 未定義チェックまたは `nvcc.exe` 検査で失敗します。

## 有効になる条件

- Windows 上で `packaging\\build_vision_windows.bat cuda13 <stage folder>` を実行すること。variant の比較は大文字小文字を区別しません。
- `CUDA_PATH_V13_0` が未定義なら、代わりに `CUDA_PATH` が利用可能であること。
- 選ばれた toolkit root の下に `bin\\nvcc.exe` が存在すること。存在しなければ `no nvcc.exe in %CUDA_PATH%\\bin` を表示して終了コード 1。
- Visual Studio の `cl.exe`、CMake、Ninja など後続のビルド要件も満たすこと。

この環境変数は CUDA 13 variant の architecture list (`75;86;89;120`) や他のビルド設定を変更しません。`VISION_ARCHS` が定義されていれば architecture list はそちらで上書きされます。`CUDA_PATH_V13_0` は CUDA toolkit の選択に使われ、architecture の選択とは別です。

## 実行時の詳細

バッチ開始時に `setlocal EnableDelayedExpansion` を実行し、引数から variant と stage folder を取得します。`cuda13` 分岐で `CUDA_PATH_V13_0` が定義されていれば `CUDA_PATH` を設定し、その後 `CUDA_PATH` と `%CUDA_PATH%\\bin\\nvcc.exe` を検査します。CMake configure には `-DCMAKE_CUDA_COMPILER=%CUDA_PATH%/bin/nvcc.exe` と `-DCUDAToolkit_ROOT=%CUDA_PATH%` を渡し、続けて `strata-vision` target を build します。したがってこの変数が影響するのは、このパッケージング用 vision executable のビルド設定です。

必須引数の不足または未知の variant は usage を表示して終了コード 2 です。toolkit path / `nvcc.exe` の確認失敗、CMake configure/build、成果物コピー、package stamp の失敗は終了コード 1 になります。成功時は `built: ... (cuda13, archs ...)` を表示します。環境変数値の独自ログや警告はありません。読み取りはバッチ実行中の variant 分岐時で、プロセス内 cache はありません。

## 根拠

- `packaging/build_vision_windows.bat:20-35` — `setlocal`、variant 分岐、`CUDA_PATH_V13_0` から `CUDA_PATH` への代入、未設定・`nvcc.exe` 検査。
- `packaging/build_vision_windows.bat:57-64` — CMake に compiler/toolkit root を渡す処理、build、成果物コピー、成功ログ。
- `packaging/build_vision_windows.bat:67-69` — usage と終了コード 2。
- `packaging/build_vision_windows.bat:4-5,28-32` — variant ごとの toolkit / architecture の説明と CUDA 12 側の別変数。

リポジトリ全体の `CUDA_PATH_V13_0` 完全一致検索では、このバッチのコメントと `cuda13` 分岐以外に参照はありませんでした。Strata の engine 起動時の読み取り、子 engine への転送、または実行時動作を変えるコードは確認できませんでした。
