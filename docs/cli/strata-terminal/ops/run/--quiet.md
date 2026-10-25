# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops run` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると真になる |

## 役割

人間向け出力を抑えるフラグです。`ops run` が成功したとき、通常の標準出力に出す実行結果を表示しません。レシピの実行自体や、その記録は抑制しません。

## 使い方

事前に内容を確認したレシピを実行する例です。`inspect-components` と `demo` は利用環境に合わせたレシピ名・プロファイル名に置き換えてください。

```sh
strata ops run inspect-components --profile demo --quiet
```

## 値と既定値

- 値は不要です。`argparse` の `store_true` で定義され、省略時は偽です。
- 同じオプションを複数回指定しても真のままです。値を付ける形式は parser が受理しません。
- `--json` は同じ one-shot parser に追加される機械可読出力の指定です。`--quiet` と併用すると、JSON 出力が優先されて抑制されません。

## 実行時の動作

- `--quiet` は `strata ops run` の parser に、`ops` 配下の one-shot parser 共通処理で追加されます。値は `a.quiet` に保持されます（`strata_cli/cli.py:508-515`）。
- `main()` は `quiet` が真で `output` が `human` の場合、実行を標準出力の一時バッファへリダイレクトします。コマンドが成功すればバッファを出力せず終了し、失敗すれば捕捉した標準出力を標準エラーへ戻します（`strata_cli/cli.py:2217-2248`）。
- `ops run` の実行結果は通常、整形 JSON を標準出力へ出します。成功時には `--quiet` により隠れ、失敗時には標準エラーへ戻されます（`strata_cli/cli.py:1451-1464`）。この出力抑制は JSON モードには適用されません。
- レシピの実行中は `recipes.run()` の標準出力を標準エラーへ振り替えます。したがって、実行中に標準エラーへ出る進捗・メッセージは `--quiet` でも抑制されません（`strata_cli/cli.py:1451-1457`）。

## 適用条件と副作用

- `--quiet` 自体は表示制御だけです。`ops run` は保存済みレシピを読み、レシピの種類に応じて runtime restart、engine calibration measurement、または components 検査を実行します。実行内容・ファイル等への影響はレシピ種別に依存します（`strata_control/recipes.py:363-428`）。
- `engine.calibrate.measure` レシピでは毎回 `--exclusive` も必要です。`--quiet` はこの条件を変えず、条件を満たさない場合は実行前にエラーになります（`strata_cli/cli.py:1448-1457`; `strata_control/recipes.py:395-396`）。
- `--output json` または `--json` と併用した場合は機械可読 JSON を標準出力へ出します。`main()` が JSON 出力のとき quiet 捕捉を行わないためです（`strata_cli/cli.py:2232-2243`）。
- 捕捉バッファは最大 64 KiB で、超過時は末尾を保持します。失敗時に内容が切り詰められていた場合、標準エラーに省略通知を追加します（`strata_cli/cli.py:2185-2214`, `2241-2248`）。

## 出力とエラー

- 成功した人間向け実行では、捕捉された標準出力を表示しません。失敗時は捕捉内容を標準エラーへ戻し、コマンド本来の終了コードを返します（`strata_cli/cli.py:2241-2248`）。
- `_error()` が出すエラーは標準エラーへ直接書き込まれるため、quiet でも表示されます（`strata_cli/cli.py:527-533`）。`ops run` の結果が失敗を示す場合、終了コードは結果内の `exit_code`、なければ `5` です（`strata_cli/cli.py:1458-1464`）。
- JSON モードでは、結果 JSON が標準出力に出て、失敗時は結果の終了コード（既定 `5`）を返します。quiet による表示抑制はありません（`strata_cli/cli.py:1458-1464`, `2232-2237`）。

## 根拠

- parser と `ops run` 固有の引数: `strata_cli/cli.py:255-290`
- one-shot parser への `--quiet` / `--json` 追加: `strata_cli/cli.py:508-515`
- `ops run` のレシピ実行・出力・終了コード: `strata_cli/cli.py:1391-1464`
- quiet 時の標準出力捕捉と JSON 例外: `strata_cli/cli.py:2185-2248`
- レシピの前提確認、実行分岐、ジャーナル記録と副作用: `strata_control/recipes.py:363-435`
