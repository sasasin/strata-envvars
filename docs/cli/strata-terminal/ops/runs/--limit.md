# `--limit`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査時の作業ツリーは `main...origin/main` で、`git status --short --branch` に未コミット変更は表示されませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops runs` |
| オプション | `--limit` |
| 別名 | なし |
| 値 | 整数。1〜100 |

## 役割

`strata ops runs` が表示する、指定した profile の操作履歴の最大件数を指定します。このサブコマンドは記録を読むだけで、操作を実行しません。索引でも `strata ops runs` のオプションとして掲載されています（`docs/cli/README.md:585-594`）。

## 使い方

```sh
strata ops runs --profile four-gpu --limit 20
```

JSON で受け取る場合:

```sh
strata ops runs --profile four-gpu --limit 20 --output json
```

`--profile` は必須で、出力形式は `--output human|json`（既定値 `human`）です（`strata_cli/cli.py:255-269`）。

## 値と既定値

- `--limit` は `argparse` の `type=int` で整数に変換され、既定値は `20` です（`strata_cli/cli.py:268-269`）。
- `strata_control.journal.list_runs()` は `1 <= limit <= 100` を検査します。範囲外なら `operation list limit must be 1..100` の `ProfileError`（既定終了コード 2）になります（`strata_control/journal.py:254-256`、`strata_control/profiles.py:30-35`）。
- 整数に変換できない値や値の省略は `argparse` が引数エラーとして扱います。`--limit` を複数回指定した場合の独自処理はなく、標準の `store` 動作により最後の値が使われます（parser 定義: `strata_cli/cli.py:268-269`）。

## 実行時の動作

CLI は `a.limit` をそのまま `journal.list_runs(a.profile, limit=a.limit)` に渡し、その戻り値を profile 名とともに出力します（`strata_cli/cli.py:1404-1408`）。ジャーナルがない場合は空リストを返し、human 出力では `No operation runs recorded` と表示します（`strata_control/journal.py:257-259`、`strata_cli/cli.py:1406-1408`）。

記録ファイル名が 32 桁の小文字16進 ID である JSON ファイルを対象にし、ファイルの更新時刻が新しい順に並べた先頭 `limit` 件だけを読み込みます。したがって件数は「有効な記録の件数」ではなく、候補ファイルのうち調べる最大数です（`strata_control/journal.py:27`、`strata_control/journal.py:260-264`）。読み込めた各記録から一覧に載せるのは ID、recipe（直接操作なら null）、origin、kind、state、開始・終了時刻、完了未確認フラグです。詳細結果や intent は一覧には出しません（`strata_control/journal.py:265-270`）。

## 適用条件と副作用

`--limit` はこの `ops runs` parser にだけ登録されています（`strata_cli/cli.py:258-269`）。取得上限を変えるだけで、記録の作成・削除・実行はしません。確認できた処理は profile の journal directory と対象 JSON 記録の列挙・読み込みです（`strata_control/journal.py:254-273`）。

個々の記録の読み込みで `ProfileError` が起きた場合、その候補は一覧から黙って除かれず、ID とエラー文字列を持つ行として返ります。その行も上限件数を消費します（`strata_control/journal.py:263-273`）。journal directory が存在しない場合は空一覧です。ファイルシステムの `OSError` などが一覧処理全体から伝播した場合、CLI 共通経路がエラーを報告し、終了コード 6 を返します（`strata_control/journal.py:257-273`、`strata_cli/cli.py:2176-2183`）。

## 出力とエラー

- 成功時の human 出力は各行に operation ID と state（個別読込エラー時はエラー文字列）を表示します。空なら `No operation runs recorded` です（`strata_cli/cli.py:1406-1408`）。
- `--output json` では `_success` が `schema_version: 1`、`ok: true`、`profile`、`runs` を JSON に出力します（`strata_cli/cli.py:1405-1408`、`strata_cli/cli.py:535-542`）。
- 範囲外の件数は `strata: operation list limit must be 1..100`（human）またはエラー JSON となり、終了コード 2 です（`strata_control/journal.py:254-256`、`strata_cli/cli.py:527-532`、`strata_cli/cli.py:2166-2173`）。
- JSON 記録が不正・読めない場合、ファイル単位の `ProfileError` は一覧内のエラー行になります。ディレクトリ列挙などの `OSError` は CLI 全体のエラーになり、human では stderr、JSON 指定時はエラー JSON、終了コード 6 です（`strata_control/journal.py:263-273`、`strata_cli/cli.py:2176-2183`）。

## 根拠と調査範囲

parser 定義と呼び出し元は `strata_cli/cli.py:255-269`、`strata_cli/cli.py:1391-1408`、件数検証・並べ替え・読み込み・一覧化は `strata_control/journal.py:254-273`、共通エラー処理は `strata_cli/cli.py:527-542` と `strata_cli/cli.py:2166-2183` です。調査対象 revision は上記 commit に固定しました。ソース parser と処理経路を根拠に記述し、CLI help の実行、build、テスト、性能測定は行っていません。
