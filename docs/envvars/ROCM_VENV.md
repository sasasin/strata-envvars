# `ROCM_VENV`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。対象は Strata 所有ソースと同梱ツール。外部の ROCm SDK・Python・Windows コマンドの内部動作は対象外。

## 役割

Windows 向け HIP ビルド補助スクリプトが、ROCm Python 環境（venv）のディレクトリを決めるために使います。該当するのは `tools/hip/build_windows.bat`、`tools/dsv41/win/build_hip_win.bat`、`tools/dsv41/win/build_umaprobe.bat` です。Strata の通常実行ファイルやサーバーがこの名前を読み取るコードは見つかりませんでした。

既定値はいずれもリポジトリ内の `.rocm-win` です。`tools/hip/build_windows.bat` と `tools/dsv41/win/build_hip_win.bat` はスクリプトから求めたリポジトリルートを使い、`build_umaprobe.bat` はバッチファイルの位置から相対パスを組み立てます。設定値はパス文字列として後続コマンドに使われます。

## 値と判定

| 状態 | Strata の処理 |
|---|---|
| 未定義（または `if not defined` が未定義として扱う状態） | 各スクリプトが `.rocm-win` を設定します。 |
| 値が定義済み | その値を venv の場所として使います。数値変換、`1` 判定、パス正規化、存在確認による既定値への fallback は行いません（`build_windows.bat` は venv 内の Python 実行ファイルの有無を別途確認します）。 |
| 空文字 | `if not defined ROCM_VENV` の判定に従い既定パスを設定します。空文字専用の分岐はありません。 |
| パスとして不正、または必要なファイルがない | 一般的な値域検査はありません。後続の venv 作成、`rocm-sdk.exe` 呼び出し、または Python 実行が失敗し得ます。各スクリプトの終了処理は下記の通りです。 |

コマンドライン引数から `ROCM_VENV` を上書きする処理はありません。親プロセスの環境値が、各バッチ内の既定値設定に先行します。3 本はいずれも処理の冒頭で `if not defined` を評価し、値をキャッシュする実装ではありません。

## 有効になる条件

Windows の HIP/ROCm build 補助スクリプトを実行した場合に限って参照されます。OS/backend 条件は各スクリプトの用途上 Windows HIP であり、実行時の CUDA/HIP backend 選択や Strata サーバーモードには作用しません。

`tools/hip/build_windows.bat` では、`ROCM_VENV` が決める Python と `strata-rocm.txt` を使って環境を作成・照合します。照合文字列は `STRATA_ROCM_VERSION` と `STRATA_HIP_ARCHS` から作られます。スタンプが一致すればインストールを省き、不一致なら `STRATA_ROCM_KEEP` が文字列 `1` の場合を除きインストールします。従って `ROCM_VENV` は保存先を決めますが、インストールを省くかどうかは別条件です。

`tools/dsv41/win/build_hip_win.bat` と `tools/dsv41/win/build_umaprobe.bat` は、venv にある `rocm-sdk.exe` を直接呼んで ROCm root を得ます。これらのスクリプトに venv 作成・インストール処理はありません。

## 実行時の詳細

- `tools/hip/build_windows.bat` は `setlocal` 内で環境を設定します。`ROCM_VENV\Scripts\python.exe` がなければ Python で venv を作成し、失敗時は `exit /b 1` します。`strata-rocm.txt` の内容が必要な version/arch と異なり、`STRATA_ROCM_KEEP` が `1` でなければ pip install、`rocm-sdk.exe init` を行い、各失敗で終了コード 1 になります。最後に同じ venv の `rocm-sdk.exe path --root` で ROCm の実体パスを取得します。見つかった root に `clang++.exe` がなければメッセージ `ROCm has no compiler in ...` を出して終了コード 1 です。パッケージ作成にも同じ venv の Python を使います。根拠: `tools/hip/build_windows.bat:24-31,35-54,64-68,113-117`。
- `tools/dsv41/win/build_hip_win.bat` は venv の `rocm-sdk.exe path --root` で root を取得し、コンパイラがなければ同様のメッセージを出して終了します。その後、得た root を HIP/CMake の設定に使います。root 取得の `for` 自体には明示的な失敗時終了分岐がなく、後続のコンパイラ確認やコマンドで失敗が表面化します。根拠: `tools/dsv41/win/build_hip_win.bat:11-22,28-43`。
- `tools/dsv41/win/build_umaprobe.bat` も venv の `rocm-sdk.exe` から root を取得し、取得した ROCm の clang で `umaprobe.cpp` をビルドします。`ROCM_VENV` に対する専用エラー表示や終了分岐はなく、最後に `BUILD-EXIT` とコマンドの `%errorlevel%` を表示します。根拠: `tools/dsv41/win/build_umaprobe.bat:3-11`。

いずれも `ROCM_VENV` 自体を子プロセスに渡して Strata エンジンの挙動を変える実装ではありません。Strata 側のスクリプトが venv 内のツールを起動し、解決した ROCm root を環境変数や CMake 引数に設定するまでが確認できる動作です。

## 根拠

- `tools/hip/build_windows.bat:13-21,24-31,35-54,64-79,87-115` — 既定値、venv 作成・stamp 判定・再インストール条件、root 解決、ビルド／パッケージ。
- `tools/dsv41/win/build_hip_win.bat:6-20,28-43` — DSV41 用 HIP ビルドにおける既定値、root 解決、ビルド。
- `tools/dsv41/win/build_umaprobe.bat:2-11` — UMAP probe 用ビルドにおける既定値、root 解決、コンパイル。
- 候補一覧には `docs/envvars/000_envvers.md:547` に名前があります。全参照検索では上記3スクリプト以外に読み取りは見つからず、Strata の実行時 engine/server の環境変数としての実装は確認できませんでした。
