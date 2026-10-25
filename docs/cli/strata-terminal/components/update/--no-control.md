# `--no-control`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update` |
| オプション | `--no-control` |
| 別名 | なし |
| 値 | 取らないフラグ。未指定時は無効（`False`）。 |

## 役割

通常は更新対象となる Strata Control の取得・検証・切り替えを、この更新実行では省略します。エンジン更新や `--app` によるデスクトップアプリ更新を止めるフラグではありません。

## 使い方

```sh
strata components update --no-control
```

## 値と既定値

引数 parser は `action="store_true"` で定義され、値を取りません。省略時は `False`、指定時は `True` です。値の検証や値域はありません。`strata update` にも同じ定義がありますが、この文書の対象は `strata components update` のスコープです。`rollback` parser には定義されていません。`strata_cli/update_cmd.py:42-59`

## 実行時の動作

通常更新では `update_cmd.run` が `--no-control` の真偽を反転し、`updater.run_update(..., control=...)` に渡します。`run_update` は `control=False` の場合、Control 更新関数を実行ステップ一覧に加えません。そのため Control feed 項目の選択、Control パッケージのダウンロード・展開・`--version` による試験起動、`active.json` の切り替え、Control 更新履歴の記録は行われません。`strata_cli/update_cmd.py:210-224`、`strata_control/updater.py:1145-1192`、`strata_control/updater.py:1274-1296`

このフラグだけではエンジンは無効になりません。エンジンは既定で更新対象のままで、`--no-engine` は別のフラグです。`--app` を併用すればアプリ installer の処理も独立して実行されます。`strata_cli/update_cmd.py:48-56`、`strata_control/updater.py:1283-1285`

`--check` を併用すると更新ステップには進まず、`updater.check` が Control を含む feed 状態を報告します。したがって `--no-control` は check 結果から Control を除外しません。`strata_cli/update_cmd.py:203-209`、`strata_control/updater.py:624-640`

Control 更新を省略しても、更新コマンド全体の acquisition 許可確認、feed のオープンと状態保存、engine の更新処理は独立して残ります。また `--wait` を指定していない場合、Control を更新しないときでも更新前の serving 確認・待機判定を通ります。`strata_control/updater.py:1277-1285`、`strata_cli/update_cmd.py:197-245`

内部では Terminal の起動 runner が `strata update --no-control --output jsonl` を起動してエンジンを取得します。この経路でも Control 更新を含めず、イベント出力を JSON Lines にします。`strata_cli/launch/runner.py:542-575`

## 適用条件と副作用

このオプションが影響するのは `run_update` の Control 更新ステップだけです。Control はインストール済みのままになり、更新は後続の別の更新実行まで行われません。Control 更新ステップを省くため、そのステップに固有の Control archive の取得、stage folder の作成・削除、Control version の試験起動、既存 Control directory の整理や active pointer の置換も発生しません。`strata_control/updater.py:1145-1192,1283-1285`

## 出力とエラー

省略した Control は `run_update` の `results` に結果項目を作らないため、通常の結果一覧や JSON 出力にも Control の更新結果は含まれません。ほかの有効な更新ステップの結果は通常どおり出力されます。`strata_control/updater.py:1283-1297`、`strata_cli/update_cmd.py:211-224`

このフラグは feed 取得や acquisition 制限を回避しません。たとえば acquisition が拒否された場合、CLI は人間向けには標準エラーへ `strata: ...`、JSON/JSONL 向けには `ok: false` とエラーを出し、終了コード 5 を返します。Ctrl-C は終了コード 130 です。`strata_cli/update_cmd.py:163-234`

## 根拠

- Parser と同一コマンド階層の定義: `strata_cli/update_cmd.py:42-59`、トップレベルへの登録と dispatch: `strata_cli/cli.py:139-140,2135-2137`。
- フラグの `control=not a.no_control` への変換、check 分岐および出力: `strata_cli/update_cmd.py:197-224`。
- `check` が Control 状態を常に含める実装: `strata_control/updater.py:624-640`。
- Control 更新処理と `run_update` のステップ選択: `strata_control/updater.py:1145-1192,1274-1297`。
- 起動 runner による内部呼び出し: `strata_cli/launch/runner.py:542-575`。

この調査は指定 revision のソース checkout に基づきます。CLI help や Release 配布物との照合は行っていません。
