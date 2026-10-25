# `strata ops show` の `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops show` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

human 出力を選んだときに、recipe の表示を標準出力へ出さないためのフラグです。recipe の読み込みや検証、出力形式は変えません。

## 使い方

```sh
strata ops show restart --profile default --quiet
```

この例は `default` profile の `restart` recipe を読み込みます。成功時、human 出力では標準出力に recipe を表示しません。

## 値と既定値

値は不要です。`action="store_true"` で定義され、指定しなければ無効です。空値などを受け取るオプションではありません。`--quiet` の追加時に既定値は `argparse.SUPPRESS` なので、未指定時は実行側の `getattr(a, "quiet", False)` が無効として扱います（`strata_cli/cli.py:508-515`, `2236-2243`）。

## 実行時の動作

`--quiet` は `strata ops show` の parser だけに個別宣言されるのではなく、全 `ops` one-shot parser に共通オプションとして追加されます（`strata_cli/cli.py:255-267`, `508-515`）。`show` は recipe と revision を読み込み、成功ペイロードを `_success` に渡します（`strata_cli/cli.py:1416-1418`）。既定の human 出力では `_success` が payload を整形 JSON として標準出力へ出します（`strata_cli/cli.py:535-541`）。

CLI の共通処理は、`--quiet` が有効で出力形式が human の場合、`_run` の標準出力を捕捉します。コマンドが成功すれば捕捉内容を出力せず、`show` の JSON 表示が抑制されます（`strata_cli/cli.py:2236-2248`）。

`--output json` またはその alias `--json` を指定した場合、quiet 処理の分岐を通らず JSON 結果を出力します。したがって機械可読の成功ペイロードは抑制されません（`strata_cli/cli.py:508-515`, `535-541`, `2232-2237`）。

```sh
strata ops show restart --profile default --quiet --output json
```

## 適用条件と副作用

recipe は通常どおり読み込まれます。パスの決定では profile と recipe 名の形式を検証し、ファイルを読む際は通常ファイルであること、サイズが 64 KiB 以下であること、POSIX では owner-only 権限であることを確認してから、JSON を読み込んで schema・profile・ID・kind・parameters を検証します（`strata_control/recipes.py:32-35`, `62-65`, `93-114`, `180-196`）。これらの読み取り・検証は `--quiet` によって省略されません。

`show` の経路では recipe の書き換えや外部プロセス起動は行われません。これは `_ops` の `show` 分岐が `recipes.load` と成功出力のみを呼ぶことに基づきます（`strata_cli/cli.py:1416-1418`）。

## 出力とエラー

- human 出力で成功した場合、`--quiet` なしでは JSON 表示を標準出力に出し、`--quiet` ありではその標準出力を抑制します（`strata_cli/cli.py:535-541`, `2236-2248`）。
- `--output json`／`--json` では `--quiet` を付けても JSON 成功結果を標準出力に出します（`strata_cli/cli.py:535-541`, `2232-2237`）。
- recipe が見つからない場合は `ProfileError` として終了コード 5 のエラーになり、通常の human 出力ではエラーメッセージを標準エラーへ出します。JSON 出力ではエラーオブジェクトを標準出力へ出します（`strata_control/recipes.py:190-196`, `strata_cli/cli.py:527-532`, `2166-2173`）。
- parser が認識しない引数などの構文エラーは `argparse` の処理で終了し、quiet の標準出力捕捉に入る前に処理されます（`strata_cli/cli.py:2223-2231`）。

## 根拠

- parser の階層と `ops` 共通引数: `strata_cli/cli.py:255-267`, `508-515`
- `show` の読み込みと成功結果: `strata_cli/cli.py:1416-1418`
- success/error の出力先: `strata_cli/cli.py:527-541`
- `--json` の正規化と quiet の捕捉・失敗時再出力: `strata_cli/cli.py:2232-2248`
- recipe の識別子・内容検証、読み込み失敗: `strata_control/recipes.py:32-35`, `62-65`, `93-114`, `180-196`

索引は [`docs/cli/README.md`](../../../README.md) の [`strata ops show`](../../../README.md) を参照してください。
