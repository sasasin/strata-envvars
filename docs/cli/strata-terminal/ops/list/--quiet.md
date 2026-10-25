# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops list` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ |

## 役割

`strata ops list` が human 形式で出す recipe 一覧や空一覧の案内を、成功時に標準出力へ表示しないようにします。recipe の読み取りや一覧取得そのものは実行されます。

## 使い方

```sh
strata ops list --profile default --quiet
```

`--profile` は必須です。通常は `--output human` が既定値です。

## 値と既定値

値を付けずに指定します。parser は `action="store_true"` として登録し、既定値は `argparse.SUPPRESS` です。指定しなければ `quiet` 属性は設定されず、処理時の `getattr(a, "quiet", False)` は false になります。複数回の指定も同じ true 値です。引数値を付ける形式はありません。`--quiet` の値や未知の引数は parser が受け付けず、通常の argparse usage/error 経路になります。

## 実行時の動作

`ops list` は対象 profile の recipes を読み、human 出力では各 recipe の ID と kind（読み込みエラー項目なら error）を表示します。空の場合は `No recipes; use strata ops init --profile NAME` を表示します。`--quiet` があり出力形式が human のとき、CLI は `_run` の標準出力を最大 64 KiB の capture に取り込み、終了コード 0 なら破棄します。recipe 一覧の読み取り処理は省略されません。

`--output json` またはその alias `--json` を併用すると、quiet capture は適用されず、JSON 成功 payload が標準出力へ出ます。したがって machine-readable な一覧を抑止するフラグではありません。

## 適用条件と副作用

この `--quiet` は `strata ops` 全体ではなく、parser 上の one-shot 各 action に登録されています。`list` はその対象です。list の実処理は recipe directory の JSON ファイルを列挙・読み込みます。コード上、list 処理から recipe を作成・更新する呼び出しはありません。

recipe ファイルの読み込みに失敗した場合、`list_recipes` は `ProfileError` の内容をその recipe の `error` 項目に格納して一覧に含めます。この場合も `ops list` 自体は成功出力を返すため、human 形式ではそのエラー項目も `--quiet` により表示されません。JSON 形式なら項目の error は出力されます。

## 出力とエラー

quiet の human 成功出力は標準出力に出ません。`_run` が非 0 を返し、capture に human 標準出力があれば、それを標準エラーへ書き戻します。capture が 64 KiB を超えて切り詰められた場合は、その旨の文も標準エラーへ出ます。CLI の `ValueError`、`OSError`、`ClientError` などのエラーは `_error` から標準エラー（JSON 指定時は JSON）へ出力され、quiet capture は標準エラーを捕捉しません。

## 根拠

- `strata_cli/cli.py:255-268` — `ops` の action parser、`list` の位置付け、必須 `--profile` と `--output` の既定値。
- `strata_cli/cli.py:508-515` — ops action parser 群を含む one-shot parser への `--quiet` 登録（値なし、`store_true`）。
- `strata_cli/cli.py:535-542` — 成功時の human / JSON 出力と終了コード。
- `strata_cli/cli.py:1391-1403` — `ops list` が recipe を取得し、項目または空一覧案内を出す経路。
- `strata_cli/cli.py:2166-2193` — 捕捉対象の例外とエラー出力先・終了コード。
- `strata_cli/cli.py:2196-2214` — quiet capture の容量と切り詰め処理。
- `strata_cli/cli.py:2232-2248` — `--json` の処理、JSON 時の quiet 適用除外、成功出力の破棄と失敗時の stderr への復元。
- `strata_control/recipes.py:199-211` — recipe directory の列挙、個別 `ProfileError` の error 項目化。
