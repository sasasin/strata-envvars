# `STRATA_BIN_DIR`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Linux と macOS 用の `tools/packaging/install.sh` が、インストール先の `strata` シンボリックリンクを置くディレクトリを指定する。値は `BIN_DIR` に設定され、インストーラはそこを作成し、署名確認済み Terminal の `bin/strata` を指すリンクを配置する。Strata Terminal の実行時設定ではなく、Windows 用 `install.ps1` にも参照はない。`tools/packaging/install.sh:1-2,20-27,149-151,176-185`、`tools/packaging/install.ps1:1-19`。

## 値と判定

POSIX shell の `${STRATA_BIN_DIR:-$HOME/.local/bin}` で読み取る。未設定または空文字なら `$HOME/.local/bin` が使われ、非空なら文字列全体が `BIN_DIR` に入る。パスとしての存在確認、絶対パス化、`~` 展開、空白除去、文字種やディレクトリ形式の検証は行わない。したがって `0`、`false`、`~/bin`、空白を含む値も、空文字でない限りそのままパス値として使われる。`tools/packaging/install.sh:22-27,151,180`。

| 実行経路 | 未設定 | 設定時に使われる値 | 既定値に戻る値 |
|---|---|---|---|
| Linux / macOS の `install.sh` | `$HOME/.local/bin` | 空文字以外の任意の値（例: `/opt/strata-bin`、`0`、`~/bin`） | 空文字 `''` |
| Windows の `install.ps1` | この変数を読まない | この変数を読まない | 該当なし。インストーラは別の場所を使う |

この変数に対応する CLI 引数や別設定との優先順位はない。`install.sh` は引数を `main` に渡すだけで、`BIN_DIR` の設定を引数から変更しない。`STRATA_DATA_DIR` は Terminal のデータ配置先として別に使われ、バイナリリンク先の指定を上書きしない。`tools/packaging/install.sh:24-27,34-35,188`。

## 有効になる条件

- `install.sh` を使う Linux または Apple silicon 搭載 Mac のインストール経路で有効。対応プラットフォームの選択は `tools/packaging/install.sh:59-67` にある。
- インストーラがアーカイブのダウンロード、チェックサム検証、展開、署名済み feed の確認を通過し、配置段階に進んだときにディレクトリ作成とリンク作成に使われる。途中で失敗すればリンク作成には到達しない。`tools/packaging/install.sh:132-174,176-180`。
- Windows では `install.ps1` が `%LOCALAPPDATA%\Strata\terminal\current\bin` をユーザー PATH に登録する独自の経路であり、`STRATA_BIN_DIR` を参照しない。この環境変数は Windows インストールには適用されない。`tools/packaging/install.ps1:5-11,18-19`。
- `PATH` に `BIN_DIR` が含まれるかどうかは配置先を変えず、完了時に表示する起動方法だけを変える。`PATH` に含まれなければ、指定値を使った起動コマンドと PATH 追加用の行を表示する。`tools/packaging/install.sh:180-185`。

## 実行時の詳細

シェル起動時に環境変数を一度展開して `BIN_DIR` に代入し、後続処理ではそのシェル変数を使う。スクリプトの途中で環境変数を読み直す処理や cache はない。値を代入した後の処理で環境側の値が変化しても、`BIN_DIR` は再評価されない。`tools/packaging/install.sh:22-27,34-35`。

インストーラは検証済みアーカイブを展開する段階で `mkdir -p "$BIN_DIR"` を実行する。配置段階では `ln -sf "$DATA_DIR/terminal/current/bin/strata" "$BIN_DIR/strata"` により、指定ディレクトリに `strata` リンクを作り、続けて `:$PATH:` に `:$BIN_DIR:` が含まれるかを調べる。含まれれば `Installed. Run: strata launch`、含まれなければ `$BIN_DIR/strata launch` と PATH に追加する `export` 行を表示する。PATH 自体は書き換えない。`tools/packaging/install.sh:149-151,176-185`。

`mkdir` またはリンク作成が失敗した場合、`set -e` により失敗したコマンドでスクリプトが終了する。これらのコマンド固有の `die` メッセージはなく、配置完了メッセージにも到達しない。`tools/packaging/install.sh:22,151,176-185`。

## ログと測定値

独自の「`STRATA_BIN_DIR` が設定された」というログや値の妥当性警告はない。PATH の状態に応じて完了時の案内が異なる（実装文字列: `Installed. Run: strata launch`、または `Installed. Run: $BIN_DIR/strata launch` と `(To type just 'strata', add this line to your shell profile: export PATH="$BIN_DIR:\$PATH")`）。`tools/packaging/install.sh:181-185`。

## 根拠

- `tools/packaging/install.sh:20-27` — 対象変数の設定説明と unset / empty 用既定値。
- `tools/packaging/install.sh:149-161` — データ先とバイナリ先のディレクトリ作成、アーカイブ展開。
- `tools/packaging/install.sh:163-185` — 署名確認後の配置、リンク作成、PATH に応じた結果表示。
- `tools/packaging/install.ps1:1-19` — Windows インストーラの別経路と設定一覧（`STRATA_BIN_DIR` の記載なし）。
