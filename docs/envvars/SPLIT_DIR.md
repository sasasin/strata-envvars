# `SPLIT_DIR`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`SPLIT_DIR` は、HIP/Linux 用エンジンのパッケージ作成スクリプト `tools/packaging/build_hip_linux.sh` が、指定フォルダー内の `strata-split-*-amd` を stage フォルダーへコピーするための環境変数です。Strata エンジンの実行時設定ではなく、通常のモデル処理や GPU 選択を直接変えるものではありません。stage は後続の `package_engine.py --tree` に渡され、通常のパッケージ作成経路ではその中のファイルがパッケージ対象になります（`tools/packaging/build_hip_linux.sh:121-122,131-135`; `tools/packaging/package_engine.py:16-20,316,367-370`）。

## 値と判定

このスクリプトは `set -u` で実行し、`${SPLIT_DIR:-}` の結果が空でないかを `-n` で判定します。変数が未設定または空文字ならコピーを行いません。空でない場合はその値をディレクトリ部分として二重引用符で渡し、シェルの `*` に一致するファイルをコピーします。値の文字列比較、数値変換、空白除去、ディレクトリの事前検証はありません（`tools/packaging/build_hip_linux.sh:21,122`）。

| 条件 | unset | 設定時に有効になる値 | 設定時にコピーされない値・失敗例 |
|---|---|---|---|
| 通常の HIP/Linux パッケージ経路 | コピーなし | 空でない任意のパス。例: `/tmp/split`、`./split binaries` | 空文字、または一致ファイルがない・参照できないパス。後者では `cp` が失敗する |

`0`、`false`、`true`、空白だけの値も空文字でなければ「設定あり」となり、ディレクトリとして使われます。値は完全一致で判定されず、大小文字や数値としての妥当性も調べません。空白を含むパスは値部分が引用されますが、末尾のファイル名パターン `strata-split-*-amd` はシェルで展開されます。該当ファイルが一つもない場合、通常の bash では未展開パターンが `cp` に渡り、`cp` がエラーになります（`tools/packaging/build_hip_linux.sh:1,122`）。

## 有効になる条件

- `tools/packaging/build_hip_linux.sh` を Linux 上の HIP/AMD パッケージ作成経路として実行し、stage 作成まで到達する必要があります。このスクリプトは `VARIANT` と `HP` を必須入力として扱います（`tools/packaging/build_hip_linux.sh:1-2,21-29,86,121-122`）。
- `VISION_ONLY` が空でない場合は reader のビルド後に `VISION-DONE` で終了するため、`SPLIT_DIR` のコピー箇所には到達しません（`tools/packaging/build_hip_linux.sh:60,85`）。
- `NO_PACKAGE` はコピー後の判定なので、空でなければ stage へのコピーは実行されますが、エンジン component のパッケージ作成には進みません（`tools/packaging/build_hip_linux.sh:121-135`）。
- 対象の `strata-split-*-amd` が指定フォルダー直下にあり、`cp` がそれらを読み取り stage に書き込める必要があります。パターンに合うファイルがない場合を含め、ここに明示的な入力検証や `chk` による失敗確認はありません（`tools/packaging/build_hip_linux.sh:46-47,121-122`）。
- 通常のパッケージ作成では `package_engine.py` が `--tree` で stage 配下の通常ファイル全体を対象にします。ここから split バイナリが実行時にロード・選択されるかどうかは、この変数の読み取り箇所からは確認できません（`tools/packaging/build_hip_linux.sh:134-135`; `tools/packaging/package_engine.py:16-20,316,367-370`）。

## 実行時の詳細

スクリプトは stage を作った後、基幹バイナリをコピーした直後の一箇所で `SPLIT_DIR` を評価します。これはスクリプト内のパッケージ作成時の読み取りであり、Strata エンジンの起動時やリクエストごとの読み取りではありません。別プロセスへの `SPLIT_DIR` の転送・上書きもこの箇所では行いません（`tools/packaging/build_hip_linux.sh:86,120-122`）。

一致する split バイナリがあれば stage 直下へコピーされ、通常経路では後続の `package_engine.py --tree` が stage 内の通常ファイルをパッケージに含めます。コピー元に一致ファイルがなく `cp` が失敗した場合でも、このスクリプトは `set -e` を有効にしておらず、この `cp` の終了状態を `chk` で確認しないため、その場での明示的な中断処理はありません。シェルの `cp` エラーは stderr に出ますが、後続処理は続行します（`tools/packaging/build_hip_linux.sh:21,46-47,121-136`）。

## 根拠

- 全参照と値判定、コピー対象: `tools/packaging/build_hip_linux.sh:14,21,121-122`。コード上の読み取りはコピー行一箇所です。
- stage 作成、`VISION_ONLY` と `NO_PACKAGE` の分岐、パッケージ作成: `tools/packaging/build_hip_linux.sh:60,85-86,120-135`。
- `--tree` が `--src` 配下の通常ファイルを再帰的に対象にする定義: `tools/packaging/package_engine.py:16-20,316,367-370`。
