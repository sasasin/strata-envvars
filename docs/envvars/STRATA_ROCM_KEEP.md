# `STRATA_ROCM_KEEP`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

この変数は Windows 用 HIP ビルドスクリプト `tools/hip/build_windows.bat` 専用です。既存の ROCm virtual environment（`ROCM_VENV`）について、記録済みの ROCm version / package extras が今回の要求と異なっていても pip install と `rocm-sdk.exe init` を省略します。Strata の実行ファイルが読む runtime 設定ではありません。

## 値と判定

スクリプトは `%STRATA_ROCM_KEEP%` を文字列 `1` と比較します。数値変換や trim はありません。

| 状況 | 結果 |
|---|---|
| `STRATA_ROCM_KEEP` 未設定、または空文字 | 値は `""` として比較され、keep 指定ではない |
| 値が厳密に `1` | keep 指定 |
| それ以外（例: `0`, `true`, `01`, `1 `） | keep 指定ではない |

ただし、インストール処理に入るのは ROCm stamp の `HAVE` と今回の `WANT` が異なる場合だけです。stamp が一致すれば、変数の値に関係なく pip install は行われません。`HAVE` は `%ROCM_VENV%\strata-rocm.txt` の先頭行、`WANT` は `STRATA_ROCM_VERSION` と `STRATA_HIP_ARCHS` から組み立てた version / extras の文字列です。`STRATA_HIP_ARCHS` は既定値を持ち、`STRATA_ROCM_VERSION` も既定値を持ちます（下記根拠）。

## 有効になる条件

- Windows の `tools/hip/build_windows.bat` を実行する場合に限ります。通常の実行時、Linux / macOS の HIP 経路、サーバーモードや CLI 引数からは参照されません。
- stamp が今回の要求と異なる場合にだけ `STRATA_ROCM_KEEP=1` が差を生みます。このとき既存 `ROCM_VENV` を使い続け、pip install、`rocm-sdk.exe init`、stamp の書き換えを省略します。
- stamp が異なり、keep 指定がない場合は pip install と SDK init を行い、成功後に `WANT` を stamp に書きます。
- keep 指定は venv や必要ファイルの妥当性を検査・修復する指定ではありません。後続で SDK root を取得し、その下に `clang++.exe` があるか検査します。古い／不完全な venv では後続処理が失敗し得ます。

## 実行時の詳細

スクリプトは `ROCM_VENV` の Python がなければまず venv を作成し、`STRATA_HIP_ARCHS` の各 architecture から ROCm package extras を作ります。その後 stamp と `WANT` を比較します。差異があり keep 指定もないとき、pip install または `rocm-sdk.exe init` が失敗すると `exit /b 1` でビルドを終了します。keep 指定による skip 時には install の進捗行は出ません。

install 分岐の後は常に `rocm-sdk.exe path --root` を実行し、root 配下に `lib\llvm\bin\clang++.exe` がない場合は `ROCm has no compiler in "..."` を表示して終了コード 1 になります。その後も CMake configure / build や package 処理の失敗は `|| exit /b 1` で終了します。したがって keep 指定は「pip install を必ず省く」条件であり、「ビルドが成功する」ことを保証しません。

## 根拠

- `tools/hip/build_windows.bat:21`: スクリプトの設定コメント。ROCM_VENV をそのまま使い、archs が異なっていても pip install しない意図を記載。
- `tools/hip/build_windows.bat:24-33`: 環境設定と引数処理。`STRATA_HIP_ARCHS` と `STRATA_ROCM_VERSION` の既定値、`ROCM_VENV` の既定パスを設定。
- `tools/hip/build_windows.bat:40-47`: venv 作成、extras と stamp 要求の生成、keep の文字列比較。stamp が違う場合にだけ `STRATA_ROCM_KEEP` を評価。
- `tools/hip/build_windows.bat:48-54`: install / init / stamp 書き込み、後続の SDK root と compiler 検査、および失敗終了経路。
- `tools/hip/build_windows.bat:72-85, 113-117`: configure/build/package の後続処理と失敗時終了。
- `docs/AMD_HIP.md:165-169`: Windows HIP ビルドスクリプトが ROCm を `.rocm-win` に install して build/package する説明。`STRATA_ROCM_KEEP` 個別の挙動説明はありません。
