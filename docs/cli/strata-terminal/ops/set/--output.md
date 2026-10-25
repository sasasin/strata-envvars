# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops set` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

成功結果と、通常の処理エラーを人向けテキストまたは機械処理向け JSON で出力します。`strata ops set` はレシピの型付きパラメーターを変更するコマンドです。`--output` は表示形式だけを選び、値の変更内容や保存の有無は `--plan` の指定で決まります。

## 使い方

```sh
strata ops set restart startup_wait_s=240 --profile my-profile --output json
```

`--profile` は必須で、`--output` を省略すると `human` です。変更内容を保存せず確認するときは `--plan` を加えます。

```sh
strata ops set restart startup_wait_s=240 --profile my-profile --plan --output json
```

## 値と既定値

- parser は `human` と `json` のみを受理し、既定値は `human` です。別名はありません。
- `--output` の指定重複時の特別な処理はありません。`argparse` の通常の扱いに従い、同じ引数を複数渡せば最後に解析された値が使われます。
- `--output` に別の値を渡すと parser が拒否し、usage とエラーを stderr に出して終了コード 2 になります。

## 実行時の動作

`ops` サブコマンド群は共通 parser ループ内で `--output` を受け取り、`set` の実装は `a.output == "json"` を出力モード判定に使います（`strata_cli/cli.py:255-275, 1391-1394`）。

- `--output json` では成功時に標準出力へ1行の JSON を出します。通常保存時は `schema_version`, `ok`, `recipe`, `previous_revision`, `revision` を含みます。`--plan` 時は `schema_version`, `ok`, `recipe`, `revision`, `would_save` を含み、ファイルは保存しません（`strata_cli/cli.py:1423-1430, 535-542`）。
- `--output human` で通常保存した場合は `Saved recipe <name>: <旧revision> -> <新revision>` を標準出力へ出します（`strata_cli/cli.py:1428-1430`）。
- `--output human --plan` の場合、専用の人向け文は渡されず、`_success` が整形済み JSON を標準出力へ出します（`strata_cli/cli.py:1425-1427, 535-542`）。したがって、この組み合わせは出力形式が JSON です。
- JSON モードの成功出力には `ensure_ascii=False` と `allow_nan=False` が使われます（`strata_cli/cli.py:535-538`）。

値の内容は `--output` ではなく位置引数 `KEY=VALUE` と対象レシピの kind で決まります。現行実装で設定できる組み合わせは、`runtime.restart` の `startup_wait_s`（整数）、`engine.calibrate.measure` の `report_dir`（文字列）、`components.verify` の `live=true|false` です。未知のキー、kind と合わないキー、空の値は拒否されます。整数値は recipe validation で `1..600`、レポート先は空でない絶対パスであることが検証されます（`strata_control/recipes.py:93-114, 278-296`）。

保存モードではレシピを検証してから revision を照合し、変更がある場合は旧版を履歴へ退避してレシピを保存します。同じ値なら保存内容は変更されず、revision も変わりません（`strata_control/recipes.py:214-237`）。これらは `--output` の形式に関係なく行われます。

## 適用条件と副作用

`--output` 自体は出力形式を選択し、レシピへの書き込みは抑止しません。`--plan` がない成功経路では `recipes.save` が実行され、変更時はプロファイル内の `.ops/<profile>/<name>.json` と `.history/<name>/` に反映されます。保存時にはプロファイル単位のロックと revision 比較を行い、同時編集を検出するとエラーにします（`strata_cli/cli.py:1423-1430`, `strata_control/recipes.py:38-64, 214-237`）。

`--plan` は値を提案・検証し `would_save` を返しますが、保存処理には進みません（`strata_cli/cli.py:1423-1428`）。レシピがない、壊れている、型や範囲が不正、ファイル権限・安全条件に合わない場合はコマンドが失敗します。recipe ファイルは通常ファイルで64 KiB未満、POSIX では owner-only（mode `0600`）であることなどを loader が要求します（`strata_control/recipes.py:180-196`）。

## 出力とエラー

- 成功時の出力先は標準出力です。`--output json` では成功・通常エラーとも JSON 形式になります。共通エラー形式は `{"schema_version":1,"ok":false,"error":{"code":...,"message":"..."}}` です（`strata_cli/cli.py:527-542`）。
- 不正な `KEY=VALUE`、未対応のパラメーター、範囲外の値、見つからないレシピ、競合などは `_run` の例外処理からエラー出力され、`ProfileError` に設定された終了コード、または既定コードで終了します。JSON でない場合は `strata: <message>` を stderr に出します（`strata_cli/cli.py:2166-2188`, `strata_control/recipes.py:180-196, 278-296`）。
- parser が拒否する値や不足引数は `_run` より前に `argparse` が処理し、usage/error を stderr に出して終了コード 2 になります（`strata_cli/cli.py:255-275, 2223-2231`）。

## 根拠

- 索引上の配置と `strata ops set` の option scope: `docs/cli/README.md:527-536`。
- parser、選択肢、既定値および位置引数: `strata_cli/cli.py:255-275`。
- `--output` 判定、plan/保存分岐、成功出力: `strata_cli/cli.py:1391-1394, 1423-1430, 535-542`。
- parser 後の引数エラーと例外出力: `strata_cli/cli.py:2166-2188, 2217-2235`。
- レシピの読み込み・値の変換・validation: `strata_control/recipes.py:93-114, 180-196, 278-296`。
- 保存、revision 競合検出、履歴退避: `strata_control/recipes.py:214-237`。
