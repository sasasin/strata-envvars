# `STRATA_BIN_DIR`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

Linux と macOS 向けの同梱 Terminal インストーラー `packaging/install.sh` が、`strata` コマンドへのシンボリックリンクを置くディレクトリを指定します。インストール時にディレクトリを作成し、展開した Terminal の `bin/strata` を指す `$BIN_DIR/strata` を作成します。実行時エンジンやモデルの設定ではありません。

## 値と判定

| `STRATA_BIN_DIR` の状態 | `BIN_DIR` の値 |
|---|---|
| 未設定 | `$HOME/.local/bin` |
| 空文字 | `$HOME/.local/bin` |
| 空でない値 | その値をそのまま使用 |

シェルの `${STRATA_BIN_DIR:-...}` 展開を使うため、空文字も未設定と同じ既定値になります。文字列の parse、空白除去、絶対パス化、パス検証や正規化はありません。空でなければ相対パスや空白を含む文字列も引用符付きでディレクトリ作成・リンク先指定に渡されます。別の環境変数や CLI 引数による `BIN_DIR` の上書きはありません。

## 有効になる条件

この変数を読むのは `packaging/install.sh` です。同スクリプトが対象とする Linux x86_64、Linux aarch64、macOS Apple silicon のインストールで、プラットフォーム判定・ダウンロード・チェックサム検証を通過して展開処理へ進んだ場合に使われます。Windows 用の `packaging/install.ps1` にこの名前の参照はなく、Strata のエンジンやサーバーからの読み取りも確認できません。

`STRATA_BIN_DIR` はスクリプト開始時に一度 `BIN_DIR` に代入されます。シェルの実行中に環境を変更しても、この代入値は再評価されません。インストーラーはまず `mkdir -p "$DATA_DIR/terminal" "$BIN_DIR"` を実行し、最後に `ln -sf "$DATA_DIR/terminal/current/bin/strata" "$BIN_DIR/strata"` を作成します。インストール途中で失敗してこの段階に到達しない場合、値は配置先に影響しません。

## 実行時の詳細

`PATH` に `:$BIN_DIR:` が含まれるかを文字列として調べます。含まれる場合は `Installed. Run: strata launch`、含まれない場合は `Installed. Run: $BIN_DIR/strata launch` と PATH に追加するための `export PATH="$BIN_DIR:$PATH"` を案内します。空でない値が不適切な場所や書き込み不能な場所を指す場合、明示的な `STRATA_BIN_DIR` 警告はありません。`set -eu` の下で `mkdir` または `ln` が失敗するとスクリプトは失敗終了し、失敗コマンドのエラーが出力されます。

既定値と通常の配置は `docs/INSTALL.md` も「normally `~/.local/bin/strata`」として案内しています（`docs/INSTALL.md:67-80`）。

## 根拠

- `packaging/install.sh:20-27` — 対象設定の宣言と未設定・空文字時の既定値を含む代入。
- `packaging/install.sh:34-35,53-61` — 主処理の開始と対応プラットフォーム。
- `packaging/install.sh:83-109` — ダウンロード、検証を経て展開処理へ進む流れ。
- `packaging/install.sh:22,98-102,125-134` — `set -eu`、対象ディレクトリ作成、リンク配置、PATH 判定と完了案内。
- `packaging/install.ps1:18-46` — Windows スクリプトの設定一覧と `$env:STRATA_DATA_DIR` の読み取り。`STRATA_BIN_DIR` は参照しません。
- `docs/INSTALL.md:67-80` — Linux / Mac と Windows のインストール経路、および既定のリンク場所の案内。

候補一覧 `000_envvers.md:628` には名前があります。候補名の全参照検索では、実際の読み取りは `packaging/install.sh:27` のみでした。`tests/terminal/test_install_scripts_env.py:62-75` はテスト環境を組み立てる参照であり、本番の読み取り箇所ではありません。
