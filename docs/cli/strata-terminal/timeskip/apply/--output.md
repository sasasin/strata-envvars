# `strata timeskip apply --output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata timeskip apply` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

適用結果とエラーの表示形式を選びます。`human` は人向けの短い表示、`json` は機械可読な JSON を標準出力へ出します。このオプションは適用先や適用内容を変えず、出力形式だけを切り替えます。

## 使い方

```sh
strata timeskip apply <run_id> --output json
```

`<run_id>` は `strata timeskip run` が記録した実行 ID です。適用前に差分を確認する場合は、同じコマンドに `--dry-run` を付けられます。

## 値と既定値

- parser は `choices=("human", "json")` を指定し、省略時は `human` です。大文字小文字の変換や独自の補正はありません。空文字やそれ以外の値は `argparse` に拒否され、usage とエラーが標準エラーへ出て終了コード 2 になります。
- このオプションは `apply` parser にのみ登録されています。`timeskip run`、`status`、`list` にも同名の parser option がありますが、それぞれ別スコープです。
- `--json` alias はありません。

## 実行時の動作

`human` の通常適用成功時は、変更した相対パスを `applied ...` と表示し、続けて rollback copy の場所を表示します。dry-run 成功時は `would write:` と、削除予定があれば `would remove:` を表示します。適用対象が空なら `(no changes)`、dry-run の書き込み対象が空なら `(nothing)` です。

`json` では成功結果を `{"schema_version":1,"ok":true,"apply":...}` の JSON オブジェクトとして1行で出力します。dry-run の場合は結果内の `would_write` / `would_remove`、通常適用では `wrote` / `removed` / `rollback` / `checkpoint` 等が返ります。エラー時は `{"schema_version":1,"ok":false,"error":{"code":...,"message":"..."}}` を標準出力へ出します。出力形式の判定は `_timeskip` の成功・エラー経路で `a.output == "json"` を使い、JSON envelope は共通 helper が生成します。

`--restore` を併用すると retained result の適用分岐を通らず、元の baseline を復元する別処理になります。この場合も `--output json` は `restore` 成功 payload の形式を選びます。`--restore` 経路では `--dry-run` と `--attempt` は参照されません。

## 適用条件と副作用

`--output` 自体はファイルを書きません。ただし `--output` の値にかかわらず、通常の `apply` は `--dry-run` がなければ workspace を変更します。保存済み run の `--workspace` 指定先（省略時は記録された workspace）を baseline の内容と照合し、一致しなければ競合として適用を拒否します。一致した場合、選択 checkpoint または `--attempt` で指定した candidate のファイルを反映し、削除対象ファイルを除去する前に destination の rollback copy を run state directory 配下に作ります。適用中に失敗すると rollback copy から destination を戻します。

インベントリ照合とコピーでは `.git`、`__pycache__`、`.strata` の各ディレクトリとシンボリックリンクが対象外です。したがって、これらを含む作業ツリー全体の同一性を保証する照合ではありません。

`--attempt` は整数の revision attempt 番号で、省略時には retained checkpoint を適用します。指定した attempt が記録されていない、または candidate directory がない場合は失敗します。`--dry-run` は destination の照合と差分算出を行いますが、destination への書き込みや rollback copy 作成は行いません。

## 出力とエラー

- 保存済み run が見つからない、選択 checkpoint / baseline がない、attempt がない等の `TimeSkipError` は終了コード 2 です。`human` では `strata: ...` を標準エラーへ、`json` では共通エラー JSON を標準出力へ出します。
- destination が run 開始後に変わっていると `conflict` として拒否され、終了コード 6 です。通常の適用でファイル操作に失敗して rollback された場合も終了コード 6 です。
- `--output json` は標準出力に JSON を出します。出力ファイルを指定するオプションではありません。

## 根拠

- 対象 revision、調査日、予定リンク、コマンド階層: `docs/cli/README.md`（調査対象 commit と `strata timeskip apply` の項目）。
- parser の値、既定値、scope: `strata_cli/cli.py:380-393`。
- `apply` の出力分岐、`restore` との相互作用、error code の選択: `strata_cli/cli.py:1524-1555`。
- 成功・エラー envelope と標準出力/標準エラー: `strata_cli/cli.py:527-542`。
- run record の再構成: `strata_cli/cli.py:1605-1618`。
- destination の digest 照合、dry-run、rollback copy、変更・復元: `strata_control/time_skip.py:597-664`。
- inventory の対象範囲と symlink 除外: `strata_control/time_skip.py:241-261`。tree copy の ignore 規則: `strata_control/time_skip.py:271-285`。
- run store がデータをロードする経路: `strata_control/time_skip.py:715-716`。
