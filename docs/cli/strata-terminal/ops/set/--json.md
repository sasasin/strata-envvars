# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops set` |
| オプション | `--json` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

`strata ops set` の結果を機械処理向け JSON で標準出力に出します。このフラグ自体はレシピの値や保存可否を変えません。通常の `set` は提案値を保存し、`--plan` を併用すると保存せず変更案を返します。

## 使い方

既存の `components.verify` レシピ `check` に値を提案し、保存せず JSON で確認する例です。`demo` プロファイルと `check` レシピがあらかじめ存在する必要があります。

```sh
strata ops set check live=true --profile demo --plan --json
```

## 値と既定値

値は取りません。省略時の出力形式は `human` です。`--json` は `--output json` の別表記として働き、両方を指定した場合も最終的な出力形式は JSON になります。フラグに値を付ける構文は parser で定義されていません。

## 実行時の動作

parser は `set` 用 parser を含む `ops` の one-shot parser 群に `--json` を追加します。`main()` はこのフラグが真なら `output` を `json` に設定してからコマンドを実行します。`_ops()` は `output == "json"` を機械出力モードとして扱います。

成功時、`set` の JSON 出力は `schema_version: 1` と `ok: true` を含み、保存したレシピと revision を `recipe`、`previous_revision`、`revision` に含めます。`--plan` 併用時は `recipe`、`revision`、`would_save` を返し、保存処理には進みません。したがって `--json` 単独は保存を防ぎません。

`--json` は出力形式を選ぶだけで、代入値の型や許容範囲を変えません。`KEY=VALUE` の解釈は対象レシピの kind によって決まり、未知のキーや kind に合わないキーは拒否されます。

## 適用条件と副作用

この option は `strata ops set` の leaf parser に属します。`--profile` は必須で、位置引数としてレシピ名と `KEY=VALUE` の指定が必要です。`--json` 自身によるファイル・ネットワーク・プロセスへの副作用はありません。

副作用は `--json` ではなく `set` の通常動作に伴います。`--plan` を付けない場合、値が有効なら `.ops/<profile>/<name>.json` のレシピを保存します。変更がある場合は旧 revision を履歴へ保存した上で新しい内容に置き換えます。提案値が現行値と同じ場合は保存内容・revision は変わりません。

## 出力とエラー

成功 JSON は標準出力に一行で出力されます。`--plan` 時の `would_save` は提案レシピと現行レシピが異なるかを示します。値の形式・型・範囲、recipe の読み込み、権限、revision 競合などで失敗すると、JSON モードでは `schema_version: 1`、`ok: false`、`error`（`code` と `message`）を含むエラー JSON を出力し、通常の人向けエラーは stderr に出しません。終了コードはエラーの種類に応じた値です。引数構文のエラーは argparse が処理します。

## 根拠

- `strata_cli/cli.py:255-275` — `ops set` の parser、必須 `--profile`、`KEY=VALUE`、`--plan`、および各 action 共通の `--output`。
- `strata_cli/cli.py:508-515` — `ops_items` を含む one-shot parser に、値なし `store_true` の `--json` を追加。
- `strata_cli/cli.py:2223-2236` — parser 実行後、`--json` を `output = "json"` に正規化。
- `strata_cli/cli.py:535-542` — 成功応答の機械 JSON と人向け出力。
- `strata_cli/cli.py:1391-1430` — `_ops()` の出力形式判定、`set` の提案、`--plan` 分岐、保存処理、成功 payload。
- `strata_cli/cli.py:2166-2188` — `ValueError`、`OSError`、`ClientError` の JSON エラー経路。
- `strata_control/recipes.py:278-296` — `KEY=VALUE` の分割、kind ごとの型変換、無効な値の拒否、提案値の検証。
- `strata_control/recipes.py:93-114` — recipe schema と kind 別 validation。
- `strata_control/recipes.py:214-237` — revision の再確認、変更なしの場合の no-op、履歴保存と更新。

調査は指定 commit の checkout にある parser と実装を対象にしました。同一 revision の CLI `--help` や Release 配布物は照合していません。
