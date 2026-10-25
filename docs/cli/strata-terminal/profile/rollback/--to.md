# `--to`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile rollback` |
| オプション | `--to` |
| 別名 | なし |
| 値 | 必須。プロフィール履歴の16桁 revision（小文字 `0-9a-f`） |

## 役割

指定した保存済みプロフィール revision を現行プロフィールに復元します。対象プロフィール名は位置引数で指定します。revision は `strata profile history <name>` で確認できます。

## 使い方

```sh
strata profile history demo
strata profile rollback demo --to 0123456789abcdef
```

例の revision は形式を示す値です。実行時には `history` に表示された対象プロフィールの revision に置き換えてください。

## 値と既定値

- `--to` は必須で、既定値はありません。parser は値を文字列として受け取り、書式検査は rollback 実装で行います。省略すると `argparse` が usage とエラーを stderr に表示して終了コード 2 で終了します。
- 値は16文字ちょうどの小文字16進数でなければなりません。大文字、短縮 revision、空文字、その他の文字は受理されず、`ProfileError`（既定終了コード 2）になります。
- `--to` を複数回指定した場合は `argparse` の通常の単一値引数として最後の値が使われます。

## 実行時の動作

rollback はプロフィールを読み込んで現在 revision を取得し、プロフィールディレクトリ下の `.history/<name>/<revision>.json` を探します。ファイルが通常ファイルであること、内容の SHA-256 先頭16桁が指定 revision と一致すること、JSON が対象プロフィール名に対応する有効なプロフィールであることを検証します。その内容を通常のプロフィール保存処理に渡し、ロック下で現在 revision が変わっていないことを確認してから保存します（`strata_control/profiles.py:326-346`, `266-295`）。

プロフィールの revision は JSON bytes の SHA-256 先頭16桁です。通常の変更時には変更前のプロフィールが `.history/<name>/<revision>.json` に保存されます。rollback の保存も同じ経路を使うため、変更前の現行プロフィールも履歴に残ります。目標内容が既に現行内容と同じ場合、保存処理は変更せず同じ revision を返します（`strata_control/profiles.py:62-64`, `284-295`）。

## 適用条件と副作用

- 指定できるのは `.history/<name>/` に存在する履歴 revision です。現在のプロフィール JSON そのものを直接選ぶ仕組みではありません。履歴の列挙では現在 revision と保存済み revision が区別されます（`strata_control/profiles.py:312-323`, `326-346`）。
- 保存先の基点は `STRATA_PROFILE_DIR` があればその値、Windows では `APPDATA`（なければユーザーホーム）、その他の OS では `XDG_CONFIG_HOME`（なければ `~/.config`）の下の `strata/profiles` です（`strata_control/profiles.py:35-43`）。
- 履歴から復元するプロフィールが参照する run config も保存前に読み込まれます。そのファイルが利用できず、または形式が不正なら保存は失敗します（`strata_control/profiles.py:266-270`, `326-346`, `126-138`）。
- 成功時はプロフィールファイルを更新し、必要なら履歴ディレクトリを作成します。ファイルロックと一時ファイル経由の atomic replace を用います（`strata_control/profiles.py:174-206`, `266-295`）。
- 実行中のサーバーやインスタンスには適用されず、CLI の成功メッセージも running instances are unchanged と明示します。ネットワークや GPU を操作する処理は rollback 経路にありません（`strata_cli/cli.py:1011-1014`; `strata_control/profiles.py:326-346`）。
- プロフィール名は小文字英字で始まり、小文字英数字・`_`・`-` の最大64文字です。無効な名前は保存処理に入る前に拒否されます（`strata_control/profiles.py:29-45`, `326-328`）。

## 出力とエラー

- 成功時、既定の human 出力は復元前 revision から保存後 revision への遷移を表示します。`--output json` または one-shot alias の `--json` を指定すると、復元プロフィール、`previous_revision`、`revision` を含む JSON が stdout に出ます（`strata_cli/cli.py:958-959`, `1011-1014`, `508-514`, `2232-2235`）。
- 指定形式が不正、履歴 JSON のプロフィール構造・ID が不正、または `--to` が省略された場合は終了コード 2 です。対象プロフィールがない、履歴 revision が見つからない、履歴ファイルが通常ファイルでない、内容の hash が一致しない、履歴や run config を読み込めない場合は終了コード 5 です。run config の読み込み後に行う構造検証エラーは終了コード 2 です。保存中にプロフィールが同時変更された場合は終了コード 6 です（`strata_control/profiles.py:126-145`, `326-346`, `266-295`）。
- `ValueError`（`ProfileError` を含む）は通常 `strata: <message>` として stderr に出ます。JSON 出力時は `ok: false` と `error.code` / `error.message` を持つ JSON が stdout に出ます（`strata_control/profiles.py:23-27`; `strata_cli/cli.py:2166-2173`, `527-532`）。

## 根拠

- parser 定義: `strata_cli/cli.py:102-105`（必須文字列引数、出力形式）。`strata_cli/cli.py:508-514` は `--json` alias を rollback parser に追加します。
- オプション適用と成功出力: `strata_cli/cli.py:1011-1014`。profile command dispatch は `strata_cli/cli.py:2127-2128`。
- revision 形式、履歴ファイル検証、rollback 実装: `strata_control/profiles.py:62-64`, `326-346`。
- 保存時の同時更新確認、履歴作成、ファイル置換: `strata_control/profiles.py:266-295`。
- 履歴一覧と現在 revision の表示: `strata_control/profiles.py:312-323`。
- エラー処理と終了コード: `strata_control/profiles.py:23-27`, `strata_cli/cli.py:2166-2183`。

調査範囲は上記 revision の checkout 内の CLI parser とプロフィール保存実装です。同一 revision の実行 CLI help や Release 配布物は照合していません。
