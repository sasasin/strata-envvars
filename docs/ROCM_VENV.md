# `ROCM_VENV`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

Windows 向け HIP ビルドスクリプト `tools/hip/build_windows.bat` が使う、TheRock の ROCm Python パッケージを入れる仮想環境の場所です。エンジンの実行時設定ではなく、このバッチを使ったビルド・パッケージ作成時だけ参照されます。

## 値と判定

| 環境の状態 | スクリプトの動作 |
|---|---|
| 未設定または空 | `%SRC%\.rocm-win` を設定する。`SRC` はバッチファイルの場所から求めた Strata リポジトリの絶対パス。 |
| 非空の値 | その値を仮想環境のルートディレクトリとして使う。文字列の形式検証や絶対パス化はしない。相対パスなら、バッチ実行時の作業ディレクトリ基準になる。 |

値を数値や真偽値として parse する処理はありません。パスはコマンドやファイル操作で二重引用符に囲まれており、通常の空白を含むパスを扱えます。設定値に対する優先順位はなく、空でない環境値が既定値より優先されます。

## 有効になる条件

この変数を読むのは Windows 用 `tools/hip/build_windows.bat` のみです。`build_windows.bat tests` でも同じ ROCm 仮想環境を使います。通常の Strata エンジン実行や、Linux の HIP ビルドには適用されません。

## 実行時の詳細

バッチ開始時に `setlocal` を実行し、`ROCM_VENV` が未定義または空の場合だけ `%SRC%\.rocm-win` を割り当てます。指定先に `Scripts\python.exe` がなければ、見つけた Python（`py -3` を優先し、なければ `python`）で仮想環境を作成します。既にその実行ファイルがあれば、仮想環境の作成はスキップします。

指定先の `strata-rocm.txt` をインストール状態の記録に使います。記録内容は `STRATA_ROCM_VERSION` と選択済み extras の組み合わせです。記録が一致しない場合は、その仮想環境の Python から `pip install` を実行して TheRock の `rocm[...]` パッケージを入れ、`rocm-sdk init` を実行して記録を書きます。一致する場合はこのインストール処理をスキップします。その後も同じ環境内の `rocm-sdk.exe`、Python を使って ROCm の場所を取得し、最後に `package_windows.py` を起動します。

インストール失敗などで明示的に `|| exit /b 1` が付いた処理が失敗すると、バッチはエラー終了します。指定パスが無効・不完全な場合の事前診断や修復は行いません。`setlocal` による環境変更はバッチ終了時に呼び出し元へ戻ります。

## 根拠

- `tools/hip/build_windows.bat:13-18` — 任意設定としての説明と既定パス。
- `tools/hip/build_windows.bat:19-28` — `SRC` の決定、未設定・空の場合の既定値設定、ビルド引数。
- `tools/hip/build_windows.bat:30-49` — 仮想環境作成、stamp によるパッケージ状態判定、ROCm インストールと SDK によるルート取得。
- `tools/hip/build_windows.bat:82-84` — 指定した仮想環境の Python でパッケージスクリプトを実行。
- `docs/AMD_HIP.md:118-122` — 手動ビルド手順が `.rocm-win` に ROCm を導入する説明。既定値と整合します。
