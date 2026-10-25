# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile create` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると有効 |

## 役割

profile 作成が成功したときの人向け標準出力を抑制します。profile の作成処理や保存内容は変えません。

## 使い方

```sh
strata profile create example-profile --from-config /path/to/run-config.json --quiet
```

`/path/to/run-config.json` は実在する Strata の run config に置き換えてください。`name` は小文字英字で始まり、小文字英数字、`_`、`-` で構成する名前です。

## 値と既定値

値は不要です。省略時は静音にならず、成功メッセージが表示されます。明示的な既定値は parser に設定されていませんが、`store_true` のため未指定時は偽です。同じフラグを複数回指定しても真のままです。値を続けて指定する構文は受け付けません。

`strata profile create` は one-shot parser 群に含まれ、`--quiet` が共通追加されます。`--json` も同じ parser に追加されます。

## 実行時の動作

人向け出力モードでは、CLI が標準出力を一時捕捉します。profile 作成成功時の `Saved profile … at revision …` は標準出力へ出さず破棄されます。`--output json` または `--json` と併用した場合は JSON 出力モードが優先され、静音捕捉を行わず JSON を出力します。`--quiet` は profile 作成そのもの、保存される profile の内容、終了コードを変更しません。

profile 作成では `--from-config` のファイルを読み、検証後に profile ディレクトリへ新規 JSON ファイルを保存します。同名 profile が既に存在する場合は上書きせず失敗します。これらは `--quiet` なしでも同じです。

## 適用条件と副作用

このオプションは `strata profile create` の one-shot コマンドに適用されます。stdout だけを成功時に抑え、stderr はリダイレクトしません。失敗時はエラーを stderr に表示します。処理途中で stdout に人向け出力があり、コマンドが非ゼロで終了した場合、捕捉された直近 64 KiB は stderr に書き戻されます。64 KiB を超えて切り詰められた場合は、省略を示すメッセージも stderr に出ます。

## 出力とエラー

- 成功時、既定の human 出力は抑制されます。`--output json` / `--json` 指定時は JSON が stdout に出ます。
- profile 名の不正や同名 profile の存在などの `ProfileError` は `strata: …` の形式で stderr に出て、通常は終了コード 2 です。run config を開けない場合は終了コード 5 です。
- `--quiet` は失敗時のエラー表示を抑制しません。非ゼロ終了時の標準出力捕捉の書き戻しについては上記のとおりです。

## 根拠

- 索引上のコマンド階層と予定リンク: `docs/cli/README.md:57-65`。
- `create` parser の引数（`name`、必須 `--from-config`、human/json 出力）: `strata_cli/cli.py:69-74`。
- one-shot parser への `--quiet` と `--json` の追加: `strata_cli/cli.py:508-515`。
- quiet の適用条件、JSON モード時の優先、stdout 捕捉と失敗時の書き戻し: `strata_cli/cli.py:2196-2214,2217-2248`。
- 作成成功メッセージと JSON 成功出力: `strata_cli/cli.py:535-542,958-963`。
- profile 名と run config の検証、既存 profile の拒否、新規保存: `strata_control/profiles.py:25,48-55,135-147,236-249`。
- profile 保存は同じディレクトリ内の一時ファイルを経て置換する: `strata_control/profiles.py:213-233`。
- `ProfileError` の終了コードと human エラー出力: `strata_control/profiles.py:30-35`, `strata_cli/cli.py:527-532,2166-2173`。

調査時点の Strata checkout は `main...origin/main` で未コミット変更なし。CLI の実行 help は補助資料として使用せず、parser と実行経路をソースで確認しました。
