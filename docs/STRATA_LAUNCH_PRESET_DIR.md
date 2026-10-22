# `STRATA_LAUNCH_PRESET_DIR`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

`strata launch` が保存する起動プリセット JSON の保存先ディレクトリを指定します。プリセットはモデル、起動設定、API key などを含む `LaunchSettings` を名前ごとに保存するファイルです。環境変数を指定してもプリセットの形式や名前の扱いは変わりません。

## 値と判定

| 値 | 保存先 |
|---|---|
| unset または空文字 | `strata_control.profiles.profile_dir()` が返すプロファイルディレクトリの親にある `launch-presets/` |
| 空でない文字列 | `Path(value).expanduser()` が返すパス |

値は文字列として扱い、空白除去、存在確認、絶対パス化、環境変数展開はしません。したがって空白だけの値は有効なパスとして扱われ、相対パスはプロセスの現在の作業ディレクトリからの相対パスになります。`~` は `expanduser()` によりホームディレクトリへ展開されます。

既定の profile directory は、Windows では `%APPDATA%\\Strata\\profiles`（`APPDATA` が未設定ならホーム下の `AppData/Roaming/Strata/profiles`）、それ以外では `$XDG_CONFIG_HOME/strata/profiles`（`XDG_CONFIG_HOME` が未設定なら `~/.config/strata/profiles`）です。`STRATA_PROFILE_DIR` が空でない場合はそのディレクトリを使います。このため `STRATA_LAUNCH_PRESET_DIR` が unset/空なら、`STRATA_PROFILE_DIR` も既定のプリセット位置に間接的に影響します。

根拠: `strata_cli/launch/store.py:27-32`; `strata_control/profiles.py:38-45`。

## 有効になる条件

この変数は `strata_cli.launch.store` のプリセット格納先に適用されます。CLI の `strata launch --list-presets`、`--delete-preset`、`--preset`、`--save-preset` と、起動 TUI のプリセット一覧・保存・削除がこの store を利用します。モデルや engine のデータディレクトリを指定する変数ではありません。

値のパスが存在しない場合、一覧では空の一覧になります。保存時は親ディレクトリを作成しますが、読込・削除で見つからなければ `PresetError` になります。読み取り可能な JSON でないファイルは一覧では飛ばされ、個別読込では破損・読取エラーとして扱われます。

根拠: `strata_cli/launch/cmd.py:556-585`; `strata_cli/launch/screens.py:239,303,1516`; `strata_cli/launch/store.py:39-60,81-129`。

## 実行時の詳細

`preset_dir()` は `os.environ.get("STRATA_LAUNCH_PRESET_DIR")` を呼び出しごとに評価し、その結果を module-level や関数内の cache に保存しません。プロセス内で環境を書き換えた場合も、次に呼ばれるプリセット操作では新しい値が参照されます。通常の CLI 実行では、起動時の環境から操作ごとに保存先が決まります。

保存先は `_path()` から個別プリセットの `{slug}.json` を決めるほか、一覧処理でも直接参照されます。保存はディレクトリを作成し、一時ファイルを書いて flush/fsync した後に atomic replace します。一時ファイルの mode を `0600` にする処理はベストエフォートで、Windows では現在ユーザーに限定する処理も試みます。保存処理が失敗した場合に使う代替ディレクトリはありません。

根拠: `strata_cli/launch/store.py:27-37,39-60,68-77,81-121`。

## 根拠

- 環境変数の読み取りと既定位置: `strata_cli/launch/store.py:27-32`。
- プリセットの JSON パス決定と保存処理: `strata_cli/launch/store.py:35-60,68-77`。
- 読込・一覧・削除: `strata_cli/launch/store.py:81-129`。
- 既定プロフィール保存先: `strata_control/profiles.py:38-45`。
- CLI の一覧・削除・保存呼び出し: `strata_cli/launch/cmd.py:569-585,704-708`。
- TUI の一覧・削除・保存呼び出し: `strata_cli/launch/screens.py:239,303,1516`。
- 利用者向け文書は、プリセットを profiles フォルダーの隣の `launch-presets/` に置くと説明しています（`docs/TERMINAL_LAUNCH.md:72`）。
