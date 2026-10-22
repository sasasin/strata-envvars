# `STRATA_ROCM_KEEP`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

Windows HIP 用のビルドスクリプト `tools/hip/build_windows.bat` が、既存の ROCm Python 仮想環境をそのまま使うかを決めます。設定値が文字列 `1` の場合、仮想環境に記録された ROCm バージョンや device アーキテクチャ構成が今回の要求と違っても、スクリプトは ROCm の pip install と `rocm-sdk.exe init` を実行しません。これはビルド時の制御であり、生成される Strata エンジンの実行時設定ではありません。

## 値と判定

| 環境変数 | 動作 |
|---|---|
| 未設定または空文字 | `"1"` と一致しないため、後述の stamp が要求値と異なる場合は ROCm をインストール・初期化する |
| 文字列 `1` | stamp が要求値と異なってもインストール・初期化を飛ばす |
| その他の文字列（例: `0`, `true`, `01`） | `"1"` と一致しないため、stamp が要求値と異なる場合はインストール・初期化する |

比較はバッチの `if not "%STRATA_ROCM_KEEP%"=="1"` による文字列比較です。数値変換や真偽値 parse はありません。変数はビルドバッチ起動時の環境から分岐で参照され、処理中に値を再評価する箇所はありません。

## 有効になる条件

`%ROCM_VENV%\strata-rocm.txt` に保存された `WANT`（`STRATA_ROCM_VERSION` と、`STRATA_HIP_ARCHS` から組み立てた ROCm extras）が現在の要求値と異なる場合にのみ、この変数の差が現れます。stamp が一致している場合、`STRATA_ROCM_KEEP` の値にかかわらず install/init は省略されます。

また、仮想環境内の `Scripts\python.exe` が存在しない場合は、変数の分岐より前に venv 自体を作成します。`STRATA_ROCM_KEEP=1` で新規作成した空の venvを使おうとすると、後続の `rocm-sdk.exe path --root` と ROCm clang の確認へ進み、利用可能な SDK/compiler がなければビルドは中断します。既存環境を再利用する指定なので、必要な ROCm SDK と今回のビルドに必要な device パッケージがその環境にあることは利用者側の前提です。

## 実行時の詳細

バッチはまず `STRATA_HIP_ARCHS`（未設定なら既定リスト）と `STRATA_ROCM_VERSION`（未設定なら既定版）から `EXTRAS` と `WANT` を作り、仮想環境の stamp の1行目を `HAVE` に読みます。`HAVE != WANT` かつ `STRATA_ROCM_KEEP` が `1` 以外なら、指定 index から `rocm[EXTRAS]==VERSION` を pip install し、`rocm-sdk.exe init` を実行して stamp を更新します。install または init が失敗すると `exit /b 1` で終了します。

その後は、どちらの分岐でも `rocm-sdk.exe path --root` から ROCm root を得て、`lib\llvm\bin\clang++.exe` の存在を確認してからビルドとパッケージ作成へ進みます。環境の再利用に失敗した場合、バッチは `ROCm has no compiler in ...` を表示して終了します。`STRATA_ROCM_KEEP` 自体について、エンジン側の読み取り箇所はありません。

## 根拠

- `tools/hip/build_windows.bat:13-23`: このバッチの設定変数として説明。`STRATA_ROCM_KEEP=1` は ROCM_VENV をそのまま使用する指定。
- `tools/hip/build_windows.bat:26-31`: ROCm version、architecture、venv などの既定値。
- `tools/hip/build_windows.bat:40-54`: venv 作成、extras と stamp の比較、KEEP 判定、install/init、stamp 更新、SDK/compiler 確認。
- `tools/hip/build_windows.bat:69-85,113-115`: 分岐後の engine build と package 作成。
- `docs/AMD_HIP.md:195-200`: Windows HIP のビルド手順と `STRATA_HIP_ARCHS` の説明。`STRATA_ROCM_KEEP` 固有の追加説明はありません。
