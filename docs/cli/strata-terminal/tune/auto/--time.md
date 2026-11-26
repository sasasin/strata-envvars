# `strata tune auto --time`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune auto` |
| オプション | `--time` |
| 別名 | なし |
| 値 | 浮動小数点数。チューニングに使う時間（分）。ソースに正の値の範囲指定はない |

## 役割

自動チューニングの時間予算を指定します。モードごとの既定予算を置き換え、実行時は測定できる候補の数と、ラウンドや確認測定を続けるかの判断に使われます。所要時間を厳密に制限するタイムアウトではなく、現行設定の最初の測定は予算チェックより前に行われます。

## 使い方

```bash
# quick モードで時間予算を 30 分にする
strata tune auto MODEL --time 30

# thorough モードで時間予算を 45.5 分にする
strata tune auto MODEL --mode thorough --time 45.5

# 実測を始めず、指定時間での候補計画を表示する
strata tune auto MODEL --time 30 --plan
```

`MODEL` にはインストール済みモデル、保存済みプロファイル名、または run configuration（JSON）を指定します（`terminal/strata_cli/tune_commands.py:27`）。

## 値と既定値

- parser は `type=float` で値を読み、parser 上の既定値は `None` です（`terminal/strata_cli/tune_commands.py:41`）。数値に変換できない値は argparse の型変換で拒否されます。
- 値の正数範囲や有限値を確認する専用 validation は、このオプションの parser と実行経路にはありません。
- 値を省略すると、`--mode quick`（既定）では 20 分、`--mode thorough` では 120 分が使われます（`terminal/strata_control/autotune.py:54-80`）。指定値は分から秒へ換算され、モードの既定値を上書きします（`terminal/strata_cli/tune_commands.py:342-344`）。
- `--time 0` は条件式で偽として扱われ、予算未指定と同じくモード既定値になります（同上）。負数は未指定扱いにならず、負の秒数として後続に渡されます。正数を指定する前提で使ってください。
- `--time` の重複指定を独自処理するコードはありません。argparse の通常の単一値引数として解析されます。

## 実行時の動作

実測では、`Options` に渡された秒単位の予算を使い、現行設定の基準測定が成功した後に残り時間を見積もって候補を計画します（`terminal/strata_cli/tune_commands.py:342-345`、`terminal/strata_control/autotune.py:397-438`）。quick モードは予算と平均測定時間から試す候補数を絞ります（`terminal/strata_control/autotune.py:838-850`）。thorough モードでは候補数をこの段階で予算に合わせて絞らず、測定ラウンド・最終確認の前に残り予算を確認します（同 `:845-850`、`:453-460`、`:590-595`、`:734-742`）。

予算の判定では、各 engine 実行の前に平均実行時間の 2 回分を残す条件を使い、超過時は残りの探索・確認を止めます（`terminal/strata_control/autotune.py:245-246`、`:458-460`、`:740-742`）。そのため、実際に完了する測定数は予算、測定時間、モード、候補の有無によって変わります。`--plan` を付けると同じ予算で候補をプレビューし、実測を開始しません（`terminal/strata_cli/tune_commands.py:349-353`、`terminal/strata_control/autotune.py:856-866`）。

## 適用条件と副作用

- これは `strata tune auto` の時間予算です。索引には同じ `--time` が `strata tune plan` と `strata tune run` にもありますが、それらは別コマンド・別 parser のオプションであり、この文書の対象外です（索引 `docs/cli/README.md:704-754`、`terminal/strata_cli/cli.py:423-452`、`terminal/strata_cli/tune_commands.py:21-42`）。
- 実測を行う通常経路では engine を起動して設定を測定します。基準測定は時間予算による候補の打ち切りより前に実行されます（`terminal/strata_control/autotune.py:397-427`）。
- 計測対象時間から、GPU lock・他の engine や高負荷状態・空きメモリを待つ時間は除外されます（`terminal/strata_control/autotune.py:225-229`、`:320-346`）。したがって、この値だけでコマンド全体の壁時計時間は上限づけられません。
- チューニング結果が改善または既定設定の確認となった場合、別途 `--no-save` を指定しなければプリセットを保存します。`--time` 自体は保存を抑止しません（`terminal/strata_cli/tune_commands.py:408-410`）。

## 出力とエラー

- 実測中に予算が尽きた場合、候補ラウンドまたは確認測定を途中で止め、結果に時間切れの注記を加えます（`terminal/strata_control/autotune.py:458-460`、`:740-742`）。それまでに測定した結果は通常の結果処理へ進みます。
- `--plan` は指定予算の分数と予定測定時間を計画出力に表示します（`terminal/strata_control/autotune.py:863-866`、`terminal/strata_cli/tune_commands.py:428-442`）。
- `0` や負数をエラーにする専用メッセージは確認できません。負数や有限でない浮動小数点値について、有効な利用値としての保証や安定した実行結果はソースから確認できないため、挙動を推測しません。

## 根拠

- `terminal/strata_cli/tune_commands.py:21-50` — `auto` parser と `--time` の型・既定値の宣言。
- `terminal/strata_cli/tune_commands.py:309-345` — target・他引数の検査、分から秒への変換、時間予算を渡す箇所。
- `terminal/strata_cli/tune_commands.py:349-353`、`:408-425` — plan 分岐、結果保存条件と出力・終了コード。
- `terminal/strata_control/autotune.py:54-80` — モード別の既定予算と `Options.resolved()`。
- `terminal/strata_control/autotune.py:225-246`、`:320-346` — 経過時間の計算と待ち時間の除外。
- `terminal/strata_control/autotune.py:397-460`、`:527-529`、`:590-595`、`:734-742`、`:838-866` — 基準測定、候補計画、時間切れ判定、確認測定、plan の予算利用。
- `terminal/strata_cli/cli.py:423-452` — 別コマンド `tune plan/run` にも別定義の `--time` があること。
