# `STRATA_CONNECTION_DIR`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

Strata CLI と portable monitor bundle が共有する、保存済み接続情報（接続名ごとの JSON ファイル）のディレクトリを指定します。保存レコードには接続先 URL、proxy prefix、credential の環境変数名が入ります。credential の値そのものは保存しません。この変数はサーバー接続先を直接指定するものではありません。

## 値と判定

| 値 | 動作 |
|---|---|
| 未設定または空文字 | OS ごとの既定ディレクトリを使う。 |
| 空でない絶対パス | `Path(...).expanduser()` で `~` を展開したパスを使う。 |
| 空でない相対パス | `ConnectionError("STRATA_CONNECTION_DIR must be absolute")`。 |

文字列の trim、環境変数展開、パス存在確認を値の解釈時には行いません。空白だけの値も空文字ではないため相対パスとして拒否されます。`~` は展開されますが、`$HOME` のような文字列は展開されません。

## 既定値と適用条件

- Windows (`os.name == "nt"`): `%APPDATA%/Strata/connections`。`APPDATA` が未設定または空なら `~/AppData/Roaming/Strata/connections`。
- Windows 以外: `$XDG_CONFIG_HOME/strata/connections`。`XDG_CONFIG_HOME` が未設定または空なら `~/.config/strata/connections`。
- `XDG_CONFIG_HOME` の相対パスはこの関数では拒否されず、相対ディレクトリとして使われます。

## 実行時の詳細

環境変数は `connection_dir()` の呼び出しごとに `os.environ.get()` で読み直され、値を static cache しません。接続の一覧・読み込み・作成・保存処理がこの関数を通るため、実行中のプロセスで環境を変更した場合、以降の呼び出しは新しい値を使います。作成時や保存時の lock 取得では `connection_dir(create=True)` を通り、ディレクトリがなければ親を含めて作成します。読み取り時はディレクトリを新規作成しません。

既存パスは `lstat()` で調べ、ディレクトリでなければ `ConnectionError("connection directory must be owner-only")`（exit code 5）になります。POSIX では所有者と mode も確認し、現在ユーザー所有のディレクトリで group/other 権限がある場合は `0700` への変更を試みます。別ユーザー所有の場合はエラーになります。ファイルシステムが mode 変更を保持できない場合は stderr に一度警告して処理を続けます。この箇所は Windows の既存ディレクトリ ACL を検査しません。

相対パスが指定されたときのエラーは `ConnectionError` で、既定 exit code は 2 です。`connection_dir()` 自身はログを出しません。

## 根拠

- `strata_cli/connections.py:72-90` — 値の取得、空値判定、OS 別既定値、相対パス拒否、既存ディレクトリ検査。
- `strata_cli/connections.py:93-94,128-150,190-198,221-242,256-270` — 接続 JSON、一覧、lock、作成・保存からディレクトリ関数を使う箇所。
- `strata_cli/monitor_commands.py:132-160` — `strata connection` コマンドが一覧・読込・作成・保存 API を呼ぶ箇所。
- `strata_cli/connections.py:47-50` — `ConnectionError` の既定 exit code。
- `strata_control/private_files.py:320-346` — 作成時の POSIX `0700` ディレクトリ作成と Windows の新規ディレクトリ処理。
- `strata_control/posix_owner.py:26-54` — POSIX の owner/mode 検査、権限修正、mode を保持できない filesystem での警告。
- `docs/TERMINAL.md:30-44` — CLI と portable monitor bundle が接続ファイルを共有する説明、および設定先の概要。
