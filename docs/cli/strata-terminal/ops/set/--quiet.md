# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops set` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。省略時は `False`。 |

## 役割

成功時の人向け標準出力を抑制します。`ops set` がレシピを保存したときの `Saved recipe ...` などを表示したくない場合に使えます。parser は `ops` 配下の one-shot サブコマンドにこのフラグを追加しています（`strata_cli/cli.py:255-267, 512-515`）。

## 使い方

```sh
strata ops set restart startup_wait_s=360 --profile my-profile --quiet
```

`startup_wait_s=360` は `runtime.restart` レシピに対する例です。`--quiet` 自体は位置引数や `KEY=VALUE` の解釈を変えません。

## 値と既定値

値は不要です。`argparse` の `store_true` により、指定時は真、未指定時は偽です。無効な値の検査はありません。`ops set` の必須引数はレシピ名、`KEY=VALUE` 形式の assignment、および必須の `--profile` です。`--plan` と `--output {human,json}` も同じコマンドで指定できます（`strata_cli/cli.py:258-275`）。

## 実行時の動作

`strata ops set` は assignment を `recipes.propose_value()` に渡します。`--plan` がなければ `recipes.save()` で保存し、通常の人向け成功メッセージを標準出力へ返します（`strata_cli/cli.py:1423-1430`）。`--quiet` はこの処理内容や保存の有無を変えず、`main()` が `_run()` の標準出力を最大64 KiBまで捕捉して成功時には出力しないことで表示を抑えます（`strata_cli/cli.py:2196-2214, 2236-2247`）。

`--plan` を付けると保存せず、変更案を返す経路になります（`strata_cli/cli.py:1425-1427`）。既定の人向け出力形式ではこの経路の結果も標準出力に書かれますが、`--quiet` が付いていて処理が成功すれば抑制されます。`--output json` またはその one-shot alias `--json` を使うと `main()` は JSON 出力を選び、JSON/JSONL 出力時は quiet の捕捉を行わないため、機械可読出力は抑制されません（`strata_cli/cli.py:2232-2242`）。

## 適用条件と副作用

このオプションは `ops` 配下の one-shot コマンド群に共通追加されています。`ops set` の場合、保存・履歴記録・revision 更新の動作は `--quiet` で変わりません。通常の set は提案値の検証後、ロックを取り、旧版を履歴へ保存してから新しいレシピを保存します（`strata_control/recipes.py:214-240`）。`--quiet` は実行中に標準出力へ出る人向け情報だけを制御し、標準エラーや外部コマンド出力を一律に隠すものではありません（`strata_cli/cli.py:2241-2247`）。

`--plan` は保存しませんが、`--quiet` 単独では dry-run になりません。実際に値を保存する例では `--plan` を付けない限りレシピが更新されます。

## 出力とエラー

成功時、quiet の人向け標準出力は表示されません。`--output json` / `--json` の成功 JSON はそのまま標準出力に出ます。エラーは `_error()` 経由で標準エラーへ出力され、quiet でも抑止されません（`strata_cli/cli.py:2166-2188, 2241-2247`）。quiet 捕捉中に標準出力があった後で非ゼロ終了した場合、その捕捉内容は標準エラーへ移されます。64 KiBを超えて切り詰められた場合は、その旨も標準エラーへ出ます（`strata_cli/cli.py:2196-2207, 2244-2247`）。

assignment は空でない `KEY=VALUE` 形式である必要があり、レシピ種別ごとの対応キー・型・範囲が検証されます。例として restart の `startup_wait_s` は整数に変換され、`1..600` の範囲外は拒否されます（`strata_control/recipes.py:77-94, 278-296`）。レシピが存在しない、assignment が未対応、値が不正、保存中に revision が競合する場合も失敗します（`strata_control/recipes.py:180-196, 214-240, 278-296`）。quiet はこれらの失敗を無視・回復せず、終了コードやエラー処理を変更しません。

## 根拠

- parser と option scope: `strata_cli/cli.py:255-275, 512-515`
- 保存／plan 経路: `strata_cli/cli.py:1423-1430`
- quiet 出力制御とエラー処理: `strata_cli/cli.py:2166-2188, 2196-2247`
- recipe 値の変換・検証: `strata_control/recipes.py:77-94, 278-296`
- 保存・履歴・revision 競合: `strata_control/recipes.py:214-240`
- recipe 読み込み時の失敗: `strata_control/recipes.py:180-196`
