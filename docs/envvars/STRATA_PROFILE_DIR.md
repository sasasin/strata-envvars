# `STRATA_PROFILE_DIR`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。Strata 所有の Python 実装を調査。外部ライブラリの環境変数は対象外。

## 役割

Terminal の保存プロファイルと、その履歴・関連データを置くディレクトリを指定します。`strata profile` 系コマンドのほか、プロファイルを使うレシピ、ベンチマーク、プリセットなどもこのディレクトリを参照します。Windows のアクセス権修復処理では、この環境変数の値がユーザー所有データのルート候補にもなります。

## 値と判定

プロファイル保存先を決める `profile_dir()` は `os.environ.get("STRATA_PROFILE_DIR")` の返り値を真偽値で判定します。文字列全体の trim、検証、絶対パス化はしません。

| 値 | プロファイル保存先 |
|---|---|
| 未設定 | OS ごとの既定先 |
| 空文字 | 未設定と同じく OS ごとの既定先 |
| 非空文字列 | `Path(value).expanduser()` の結果 |

非空の相対パスは相対パスのまま返され、`~` で始まる部分は `expanduser()` で展開されます。空白だけの値も非空なので、その空白を含むパスが指定先になります。`resolve()` はこの関数内では呼びません。

既定先は Windows (`os.name == "nt"`) では `%APPDATA%/Strata/profiles`、ただし `APPDATA` が未設定または空なら `~/AppData/Roaming/Strata/profiles` です。Windows 以外では `$XDG_CONFIG_HOME/strata/profiles` で、`XDG_CONFIG_HOME` が未設定なら `~/.config/strata/profiles` です。後者は `os.environ.get(key, default)` のため、`XDG_CONFIG_HOME` が明示的な空文字ならホーム既定にはならず、相対パス `strata/profiles` になります。

## 有効になる条件

プロファイル管理など `profile_dir()` を呼ぶ Strata Control の経路で使用されます。環境変数を使った OS/backend の制限はありません。`profile_dir()` は呼び出しごとに環境を読み、結果をキャッシュしません。したがって同一プロセス内で環境を書き換えた後の呼び出しは、新しい値を参照します（保存先と読み出し先を途中で切り替える可能性もあります）。

保存先ディレクトリが必要な書き込み経路では `_private_mkdir(..., parents=True, exist_ok=True)` により作成されます。プロファイルの一覧取得は、ディレクトリが存在しない場合に空の一覧を返します。

## 実行時の詳細

プロファイルファイルは指定ディレクトリ直下の `<profile-id>.json` です。編集履歴は `.history/<profile-id>/`、編集時の一時 JSON も同ディレクトリに作成されます。プロファイルロックも同じ場所に置かれます。レシピは `.ops/<profile-id>/`、較正レポートの既定ディレクトリは `.reports/` です。既定のプリセットディレクトリはプロファイルディレクトリの親にある `presets/` です。ベンチマークもプロファイルディレクトリをリース等の保存先として使います。

`private_files.user_roots()` と `known_roots()` も非空の `STRATA_PROFILE_DIR` を読みます。前者は値を `Path` 化してルート候補に加えた後 `resolve()` し、Windows で修復対象パスがそのルート内にあるかを判定します。後者は `Path` 化した値を既知ルート候補に加え、存在するルートだけを返します。これらの箇所では `expanduser()` を行いません。プロファイル保存先を選択する `profile_dir()` とは別の用途・パス処理です。

## 根拠

- `strata_control/profiles.py:38-45` — 値の読み取り、空値判定、Windows / 非 Windows の既定先、`expanduser()`。
- `strata_control/profiles.py:54-55,169-182,185-190,286-295,312-346,349-357` — プロファイル名ファイル、一覧、ロック、履歴、ロールバック、編集一時ファイルとディレクトリ作成。
- `strata_control/recipes.py:38-42,117-127` — レシピ保存ディレクトリと較正レポートの既定パス。
- `strata_control/presets.py:45-50` — 個別指定がない場合のプリセット保存先。
- `strata_control/benchmarking.py:27-35` — ベンチマークのプロファイルディレクトリ利用。
- `strata_control/private_files.py:415-439,506-524` — Windows のユーザー所有判定・既知ルート列挙における参照。ここでは `expanduser()` なし。
- `docs/TERMINAL.md:156` — 保存プロファイルの機能説明と OS ごとの保存先の概要。これは利用者向け説明であり、値の判定の根拠は実装箇所。
