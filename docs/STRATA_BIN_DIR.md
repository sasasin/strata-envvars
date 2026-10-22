# `STRATA_BIN_DIR`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

Linux/macOS 向けのシェルインストーラ `packaging/install.sh` が、`strata` コマンドへのシンボリックリンクを置くディレクトリを指定します。実行時の Strata Terminal やエンジンが読む設定ではありません。Windows 用 `packaging/install.ps1` はこの変数を参照しません。

## 値と判定

| 値 | 使用される `BIN_DIR` |
|---|---|
| 未設定 | `$HOME/.local/bin` |
| 空文字 | `$HOME/.local/bin` |
| 空でない値 | 指定された文字列をそのまま使用 |

シェルの `${STRATA_BIN_DIR:-$HOME/.local/bin}` 展開で決まり、数値やパスの妥当性は検査されません。値は引用符付きでディレクトリ作成とリンク作成に渡されるため、空白を含むパスも一つの引数として扱われます。相対パスも拒否されず、インストーラの作業ディレクトリからの相対パスとして使われます。

## 有効になる条件

この変数を読むのは Linux/macOS の `packaging/install.sh` だけです。通常の `strata` コマンド実行、Windows の PowerShell インストール、インストール済みアプリの動作には影響しません。

## 実行時の詳細

インストーラの開始時に一度 `BIN_DIR` に代入されます。展開済み Terminal は別の `STRATA_DATA_DIR` の下（既定では `${XDG_DATA_HOME:-$HOME/.local/share}/strata`）に配置されます。署名確認後、スクリプトは `mkdir -p "$BIN_DIR"` を実行し、`$BIN_DIR/strata` に `$DATA_DIR/terminal/current/bin/strata` を指すシンボリックリンクを作成します。

完了メッセージを選ぶ際、`:$PATH:` の中に `:$BIN_DIR:` が完全一致で含まれるか確認します。含まれる場合は `Installed. Run: strata launch`、含まれない場合は `$BIN_DIR/strata launch` を案内し、PATH に `$BIN_DIR` を追加するシェル設定例を表示します。スクリプト自身は PATH を変更しません。ディレクトリ作成やリンク作成に失敗した場合、`set -e` により通常はそのコマンドの失敗でスクリプトが終了します。

## 根拠

- `packaging/install.sh:20-27` — 変数の説明と既定値を含む初期化。
- `packaging/install.sh:90-102` — Terminal の展開先と `BIN_DIR` の作成、アーカイブ検証。
- `packaging/install.sh:117-125` — symlink 作成、PATH の完全一致判定、完了案内。
- `packaging/install.ps1:17-18,29-46` — Windows インストーラの設定一覧と初期化。`STRATA_BIN_DIR` の参照はありません。
- `docs/TERMINAL_LAUNCH.md:14-18`, `docs/INSTALL.md:99-103` — インストーラが Terminal をホーム配下へ配置して PATH に追加するという概要。`STRATA_BIN_DIR` の詳細な仕様は説明していません。
