# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops rollback` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らないフラグ。省略時は無効、指定すると有効。 |

## 役割

rollback 成功時の human 向け案内を標準出力に表示しないようにします。rollback 自体を取り消し可能にしたり、保存処理を省いたりするフラグではありません。

## 使い方

```sh
strata ops rollback RECIPE --profile PROFILE --to 0123456789abcdef --quiet
```

`RECIPE` と `PROFILE` は対象のレシピ名・保存済みプロファイル名、`--to` の値は `strata ops history` で確認した復元先 revision に置き換えます。例の revision は形式を示す仮値です。

## 値と既定値

値は不要な `store_true` フラグです。指定しなければ `False`、指定すると `True` になります。parser は `--quiet` を各 `ops` one-shot サブコマンドへ追加し、その既定値を `argparse.SUPPRESS` にすることで、個別 subparser に同名引数を重複登録せず、未指定時に属性を作らない形にしています。実行側は `getattr(a, "quiet", False)` で未指定を `False` として扱います。同じフラグを複数回指定したときの値の効果は変わりません。

## 実行時の動作

`--quiet` が有効で `--output human` の場合、CLI は `_run` の標準出力を一時的に捕捉します。rollback が成功すると `Restored recipe …` という通常の成功案内は出力されません。実際の処理は通常どおり `recipes.rollback(profile, name, to)` を呼び、対象 revision を検査したうえで現在のレシピを更新します。更新前の内容は履歴へ保存されます。

`--output json` を指定した場合、または `--json` を使った場合は quiet 捕捉を行わず JSON 結果を出力します。`--json` は `--output json` に変換されます。したがって `--quiet` と JSON 出力を併用しても機械可読出力は抑制されません。

## 適用条件と副作用

このフラグは表示だけに作用し、rollback のファイル変更や revision 検査には影響しません。rollback 先は小文字 16 桁の revision でなければならず、履歴ファイルが存在し、その内容の revision が一致し、レシピとして検証できる必要があります。成功時には保存中の現 revision が履歴へ記録され、選択した内容で現在のレシピファイルが置き換えられます。保存先はプロファイル配下の `.ops/<profile>`、履歴はその `.history/<recipe>` 配下です。

## 出力とエラー

- quiet + human 出力で成功した場合、rollback の成功案内（標準出力）は表示されません。
- JSON 出力時は `--quiet` にかかわらず JSON 結果を標準出力へ出します。
- 無効な revision、履歴の欠落・破損、ファイル権限・形式の問題、同時更新による revision 不一致などは失敗します。通常の例外経路ではエラー文は標準エラーへ出力され、終了コードは例外の `exit_code` があればそれを、なければ 2 を使います。rollback の履歴不在は 5、同時更新の競合は 6 です。
- quiet モード中に処理が非ゼロ終了し、捕捉した標準出力があれば、その内容は標準エラーへ移されます。捕捉量は最大 64 KiB で、超過時は省略の通知も標準エラーへ出ます。rollback の一般的な失敗メッセージは `_error` が標準エラーへ直接書きます。

## 根拠

- 索引は `strata ops rollback` の `--quiet` を `strata-terminal/ops/rollback/--quiet.md` に割り当てています（`docs/cli/README.md:548-557`）。調査対象 checkout ではこの索引ファイル自体は存在しません。参照したのは依頼で指定された `strata-envvars` 側の索引です。
- rollback parser は `strata_cli/cli.py:255-277` にあり、共通 `--quiet` は全 `ops_items` に対して `strata_cli/cli.py:508-515` で登録されます。
- quiet の捕捉・失敗時の出力規則は `strata_cli/cli.py:2196-2214`、`strata_cli/cli.py:2217-2248`、エラー処理は `strata_cli/cli.py:527-532` と `strata_cli/cli.py:2119-2193` にあります。
- rollback の呼び出しと成功メッセージは `strata_cli/cli.py:1391-1394`、`strata_cli/cli.py:1436-1439`。JSON の選択は `strata_cli/cli.py:2232-2237` です。
- revision の形式、履歴内容の照合、復元・保存は `strata_control/recipes.py:253-275`。レシピ保存時の履歴退避と atomic 更新は `strata_control/recipes.py:214-237`、履歴・レシピ検証条件は `strata_control/recipes.py:93-114` と `strata_control/recipes.py:180-196` にあります。
