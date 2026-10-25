# `STRATA_DATA_DIR`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。対象は Strata 同梱 Terminal インストーラー。外部ライブラリの環境変数は対象外。

## 役割

Terminal の per-user インストール先の基点ディレクトリを指定します。Linux/macOS の `packaging/install.sh` と Windows の `packaging/install.ps1` が読みます。各インストーラーはこの下に `terminal/<version>` を展開し、`terminal/current` を現在の版へ向けます。環境変数を読むのはインストーラーであり、候補名の記述だけからエンジンや通常起動時の設定変数とは判断できません。

## 値と判定

値を数値や真偽値として parse せず、パス文字列として使います。

| インストーラー | 未設定または空文字 | 非空文字列 |
|---|---|---|
| Linux/macOS (`install.sh`) | `${XDG_DATA_HOME:-$HOME/.local/share}/strata` | 指定値をそのまま `DATA_DIR` にする |
| Windows (`install.ps1`) | `%LOCALAPPDATA%\Strata`。ただし `LOCALAPPDATA` も空または未設定なら停止 | 指定値をそのまま `$data` にする |

シェル側の `${STRATA_DATA_DIR:-...}` は未設定と空文字の両方で既定値へ進みます。Windows 側も `if ($env:STRATA_DATA_DIR)` の真偽判定なので空文字は既定値になります。空白だけの文字列を trim したり、相対パスを絶対化したり、書き込み可能性を事前検証したりする処理はありません。指定値は後続のパス結合に使われます。

## 有効になる条件

- `install.sh` は Linux x86_64 と macOS Apple silicon の対応プラットフォーム確認後に展開先として使用します。Linux/macOS 以外や未対応 CPU では先に終了します。
- `install.ps1` は Windows x64 で使用します。`STRATA_DATA_DIR` と `LOCALAPPDATA` がともに空または未設定なら、例を示すエラーで停止します。
- `STRATA_DATA_DIR` の設定は `STRATA_BIN_DIR`（Unix 系のリンク配置先）や `STRATA_NO_PATH`（Windows の PATH 更新抑止）とは独立です。Windows では `STRATA_NO_PATH=1` でも `$data` はインストール先として使われます。

## 実行時の詳細

環境変数はインストーラースクリプトの実行時に一度読み取られます。Unix 系では `$DATA_DIR/terminal/$version` が展開先となり、成功後 `$DATA_DIR/terminal/current` をその版へ向けます。さらに `STRATA_BIN_DIR/strata` から `terminal/current/bin/strata` へのリンクを作ります。Windows では `$data\terminal\$version` が展開先、`$data\terminal\current` が junction（作成できない場合は小さな起動スクリプト）の場所です。したがってこの変数はインストール時に Terminal 本体の配置を変えます。

インストーラーは展開後、その展開先の `strata update --check --no-engine --feed ...` を実行します。環境変数を後から変更しても、既に作成したリンクや配置場所は移動しません。インストーラー内に値のログ出力、独自のパス正規化、既定値への書き戻しはありません。ディレクトリ作成・展開に失敗すればインストーラーのエラー処理へ進みます。

## 根拠

- `packaging/install.sh:20-27` は設定と既定値を定義し、`packaging/install.sh:90-102,117-125` は指定先への展開、`current` と実行リンクの作成を行います。
- `packaging/install.ps1:18-19,45-47` は設定、Windows の既定値と `LOCALAPPDATA` 不在時のエラーを定義します。`packaging/install.ps1:65-79,105-124` は指定先への展開と `current` の用意を行います。
- `packaging/install.ps1:125-135` は `STRATA_NO_PATH` による PATH 更新の条件を示します。
- `docs/TERMINAL_LAUNCH.md:90-94` は Terminal のモデル探索で使う既存インストール場所やアプリのデータフォルダーを説明しますが、インストーラーの `STRATA_DATA_DIR` とその各処理の根拠は上記スクリプトです。
