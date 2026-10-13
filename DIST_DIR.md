# `DIST_DIR`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

Windows 向け HIP エンジンをビルドして zip に梱包する `tools/hip/build_windows.bat` 専用の出力先です。通常の Strata 実行時設定ではありません。このバッチが `tools/hip/package_windows.py` に出力先を `--out` 引数として渡し、同スクリプトが `strata-windows-x64-hip.zip` を作成します。

## 値と判定

| 状態 | バッチの動作 |
|---|---|
| `DIST_DIR` が未設定または空 | `%SRC%\dist` を設定する。`SRC` はバッチファイル位置から求めた Strata リポジトリの絶対パス。 |
| 空でない値を設定 | 値を出力先としてそのまま使う。バッチ内でパスの正規化や値の検証はしない。 |

値の数値変換や真偽値判定はありません。空でない値は引用符付きで `--out` に渡されるため、空白を含むパスも引数として渡されます。相対パスはバッチが実行されたときのカレントディレクトリ基準です。バッチは `setlocal` を使うため、既定値や途中で設定する環境変数はこのバッチと子プロセスの実行中に限られます。

## 有効になる条件

`DIST_DIR` が使われるのは Windows の HIP ビルドバッチを実行した場合だけです。通常のビルド、エンジン実行、Python セットアップの実行時には読み取られません。バッチは `cmake --build` の後、`package_windows.py --out "%DIST_DIR%"` として値を渡します。

## 実行時の詳細

パッケージスクリプトは出力先の下に `strata-windows-x64-hip` というステージングディレクトリを作ります。同名の既存ステージングディレクトリは先に削除し、その後、エンジン実行ファイル、依存 DLL、カーネル、ライセンスなどを格納します。最後に出力先直下の `strata-windows-x64-hip.zip` が既にあれば削除してから、ステージング内容を圧縮して同名 zip を作成します。完了時、バッチは `Done: %DIST_DIR%\strata-windows-x64-hip.zip` を表示します。処理失敗時は各コマンドの `|| exit /b 1` により、バッチはエラーコード 1 で終了します。

`docs/AMD_HIP.md` も、ビルド手順の既定出力を `dist\strata-windows-x64-hip.zip` と記載しています。設定値を指定すると、このディレクトリが置き換わります。

## 根拠

- `tools/hip/build_windows.bat:13-18` — 環境変数設定一覧と `DIST_DIR` の既定値の説明。
- `tools/hip/build_windows.bat:19-27` — `setlocal`、リポジトリ位置からの `SRC` 算出、未設定時の `%SRC%\dist` 設定。
- `tools/hip/build_windows.bat:76-86` — ビルド後に `%DIST_DIR%` を `--out` に渡し、zip の場所を表示。
- `tools/hip/package_windows.py:68-81, 152-169` — `--out` の `Path` 引数、ステージングディレクトリの再作成、zip の削除・生成・出力。
- `docs/AMD_HIP.md:118-122` — Windows HIP ビルドの説明と既定出力先。
