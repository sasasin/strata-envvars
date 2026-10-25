# `--save-preset`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--save-preset` |
| 別名 | なし |
| 値 | 必須の `NAME`。parser では任意の文字列を受け取る |

## 役割

起動設定に名前を付け、次回以降 `strata launch --preset NAME` で使える launch preset として保存します。`--preset` から読み込んだ設定にほかの起動フラグを重ねた場合も、その値を指定名で保存できます。

## 使い方

```sh
strata launch --model iq3_xxs --context 128k --access lan --port 8080 --save-preset "Office" --no-tui
```

この例では `Office` の設定で起動し、成功した起動設定を preset に保存します。対話画面を使う場合は `--no-tui` を外します。既存 preset を元にする場合は、たとえば `strata launch --preset Office --context 64k --save-preset "Office 64K"` のように指定します。

## 値と既定値

- `NAME` は位置値として必須です。`argparse` parser に選択肢や長さ制限はありません（`strata_cli/launch/cmd.py:127-128`）。
- 保存時に前後の空白を除きます。空文字相当の名前は `A preset needs a name.` で拒否されます。名前は小文字化し、英数字・`-`・`_` 以外を `-` に置き換え、先頭を英字にし、48文字までに切り詰めた slug がファイル名に使われます（`strata_cli/launch/store.py:68-85`、`strata_cli/launch/settings.py:310-315`）。
- parser 自体に既定値はありません。省略すると保存処理は行われません。`--save-preset ""` も空文字が偽として扱われるため保存指定になりません。一方、空白だけの値は起動設定名に入り、保存時に空名として拒否されます（`strata_cli/launch/cmd.py:279-280,788-790`、`strata_cli/launch/store.py:75-80`）。
- 保存先ファイル名は slug から作られるため、異なる名前でも同じ slug になれば同じ JSON ファイルを指します。保存は既存ファイルを置き換えます。以前の `created` 時刻は保持し、ファイル内容は今回の設定で更新します（`strata_cli/launch/store.py:35-36,75-85`）。

## 実行時の動作

`--preset` があればその preset を読み込み、他の指定フラグで設定を上書きした後、`--save-preset` の値を設定名にします（`strata_cli/launch/cmd.py:197-203,252-280`）。`--preset` と `--save-preset` の名前が異なる場合、元 preset ではなく指定した保存名の preset が作られます。`--preset` だけで起動した場合は設定変更を保存せず、使用時刻だけを更新します（`strata_cli/launch/cmd.py:788-792`）。

- 通常の非対話経路では `runner.run()` が成功してから保存し、続けて `last_used` を記録します。起動失敗時はこの保存分岐に到達しません（`strata_cli/launch/cmd.py:784-792`）。
- 端末上で対話画面が使えるフラグ起動では、`save=True` として画面へ渡し、画面初期化時に起動前の設定を保存します（`strata_cli/launch/cmd.py:780-783`、`strata_cli/launch/app.py:438-455`）。そのため、この経路では後続の起動が失敗しても保存済み preset が残る場合があります。
- `--plan` は計画表示後に終了するため保存しません（`strata_cli/launch/cmd.py:733-760`）。管理操作も起動処理より先に分岐し、`--save-preset` による保存処理を通りません（同 `:643-677`）。
- preset は profiles フォルダーの隣にある `launch-presets/` 内の JSON です。`STRATA_LAUNCH_PRESET_DIR` が設定されていればそのディレクトリを使います（`strata_cli/launch/store.py:27-36`）。書き込み時は一時ファイルに書いて fsync し、可能な環境では Unix mode `0600` を設定してから atomic replace します。Windows では現在のユーザーに限定する処理も試みます（同 `:39-60`）。
- preset は API key を含むことがあります。設定全体が JSON に保存されるため、保存ファイルを資格情報として扱ってください（`strata_cli/launch/settings.py:99-101,114-118`、`strata_cli/launch/store.py:3-7,75-85`）。

## 適用条件と副作用

- オプションは `strata launch` の起動設定に作用します。通常起動では起動成功後に保存しますが、対話画面付き経路では画面開始前に保存します。
- 既存 slug の preset を置き換えるため、同じ preset を更新する意図がない場合は別名を使ってください。slug の正規化や48文字制限による名前の衝突もあり得ます（`strata_cli/launch/settings.py:310-315`、`strata_cli/launch/store.py:35-36,75-85`）。
- `--plan` は保存しません。保存先ディレクトリの作成とファイル書き込みは保存処理時に発生します（`strata_cli/launch/store.py:39-52`）。

## 出力とエラー

- 保存名が空なら `PresetError` となり、通常経路では stderr に `strata: A preset needs a name.` を出して終了コード 2 を返します。`--output json` の通常経路では同じ失敗を `ok: false` の JSON として stdout に出します（`strata_cli/launch/store.py:68-80`、`strata_cli/launch/cmd.py:636-641,832-835`）。
- 対話画面付き経路で画面初期化中に保存例外が起きると、`_tui` が stderr に画面の予期しない問題として表示し、終了コード 1 を返します（`strata_cli/launch/app.py:449-455`、`strata_cli/launch/cmd.py:554-564`）。
- ファイルシステムの書き込み失敗など、`PresetError` 以外の例外について、通常経路での表示・終了コードはこのオプションの呼び出し箇所だけからは確定できません。

## 根拠

- `strata_cli/launch/cmd.py:75-82,127-128` — `launch` parser とオプション定義。
- `strata_cli/launch/cmd.py:197-203,252-280` — preset 読み込み、他フラグの適用、保存名の設定。
- `strata_cli/launch/cmd.py:630-641,679-735,733-760,780-835` — 実行モード、計画の早期終了、保存位置、出力・エラー処理。
- `strata_cli/launch/store.py:27-60,68-85,139-144` — 保存場所、書き込み方式、名前処理、既存 preset の更新。
- `strata_cli/launch/settings.py:99-118,310-315` — 保存される API key を含む設定と slug 規則。
- `strata_cli/launch/app.py:438-455` — 対話画面付き起動での保存タイミング。
- `docs/TERMINAL_LAUNCH.md:59-75` — 利用例と、preset の保存・再利用に関する利用者向け説明。ソース確認の補助として参照。
