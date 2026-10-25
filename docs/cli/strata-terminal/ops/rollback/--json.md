# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops rollback` |
| オプション | `--json` |
| 別名 | なし（同じ出力形式は `--output json` で指定可能） |
| 値 | 値を取らない真偽フラグ |

## 役割

成功時の結果を機械処理しやすい JSON 1行で標準出力へ出します。rollback の対象 revision や保存内容は変えず、出力形式だけを選びます。

## 使い方

```sh
strata ops rollback restart --profile local --to 0123456789abcdef --json
```

`restart` は recipe 名、`local` は profile 名、`--to` の値は復元したい履歴の revision です。例中の revision は形式例なので、実行時は `strata ops history restart --profile local` で確認した実在の revision に置き換えてください。`--output json` も同じ出力形式を選びます。

## 値と既定値

`--json` 自体は値を取らず、指定なしが既定です。parser は各 `ops` action に共通で `--output {human,json}`（既定 `human`）を定義し、さらに `--json` を追加します。解析後に `--json` が指定されていれば `output` を `json` に設定するため、併記した `--output human` より `--json` が優先されます。`--output` に `human` または `json` 以外を渡すと argparse が拒否します。

## 実行時の動作

rollback 成功時、`--json` は標準出力に次の形の JSON を出します（recipe のフィールドは復元された内容です）。`schema_version` は `1`、`ok` は `true`、加えて `recipe`、`previous_revision`、新しい `revision` が含まれます。

```json
{"schema_version":1,"ok":true,"recipe":{},"previous_revision":"…","revision":"…"}
```

このフラグは状態変更を無効化しません。`rollback` は `--to` で指定した履歴 recipe を検証し、現在の revision を競合確認した上で、現在の内容を履歴として保全してから復元内容を recipe ファイルへ保存します。復元内容が現在と同じなら保存処理は変更なしで終了します。JSON モードでもこの処理は同じです。recipe を実行する動作ではありません。

## 適用条件と副作用

`--json` は `strata ops rollback` に適用され、rollback の実行可否や保存対象の選択条件を変えません。rollback には `name`、必須の `--profile PROFILE`、必須の `--to REVISION` が必要です。revision は16桁の小文字16進数でなければなりません。対象履歴は通常ファイルで64 KiB以下であり、内容から計算した revision が指定値と一致し、recipe schema と profile/name に対する検証を通る必要があります。POSIX では履歴ファイルが owner-only であることも確認されます。

復元時はプロファイル内の `.ops/<profile>/<name>.json` と `.history/<name>/` の recipe 保存領域を読み書きします。POSIX では保存先ディレクトリ・recipe ファイルにも owner-only 権限条件が適用されます。パーサが `ops` の全 action を共通リストへ含めて `--json` を付けるため、この説明の対象コマンドでは利用できます。

## 出力とエラー

JSON モードの成功出力は標準出力です。`ProfileError` など `ValueError` 系の失敗は `{"schema_version":1,"ok":false,"error":{"code":...,"message":"..."}}` 形式で標準出力へ出し、エラーコードを終了コードとして返します。JSON 指定がない場合は `strata: ...` を標準エラーへ出します。無効な revision、履歴なし・不一致、recipe の検証失敗、保存中の revision 競合などが失敗経路です。ファイル I/O の `OSError` はコード6でエラー化されます。引数不足・形式不正など parser のエラーは argparse の usage/error と終了コード2です。

## 根拠

- `strata_cli/cli.py:255-277` — `ops rollback` parser、位置引数 `name`、必須 `--profile`・`--to`、`--output` の選択肢と既定値。
- `strata_cli/cli.py:508-516` — `ops_items` 全体への `--json` 追加。
- `strata_cli/cli.py:2217-2236` — `--json` を `output=json` に反映する共通処理。
- `strata_cli/cli.py:1391-1394,1436-1439` — JSON モード判定と rollback 呼び出し、成功 payload。
- `strata_cli/cli.py:527-542,2166-2183` — JSON 成功・失敗出力、ValueError/OSError のエラー経路。
- `strata_control/recipes.py:253-275` — revision 形式、履歴読込・検証、rollback から保存への流れ。
- `strata_control/recipes.py:214-237` — 現 revision の競合確認、同値時の変更なし終了、履歴保全、recipe ファイルへの保存。
- `strata_control/recipes.py:180-196` — recipe ファイルの型・サイズ・権限・schema 読み込み検査。
- `strata_control/profiles.py:30-35` — `ProfileError` の終了コード既定値。
- 配置と option scope: `docs/cli/README.md:548-557` に `strata ops rollback` の階層と `--json` が掲載されています。
