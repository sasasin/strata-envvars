# `--time`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune auto <target>` |
| オプション | `--time MINUTES` |
| 別名 | なし |
| 値 | 分単位の浮動小数値。parser に正の範囲・有限値の検証はない |

## 役割

`strata tune auto` のチューニングに使う時間予算を分単位で指定します。候補設定をどこまで試すか、測定を続けるかの判断に使われます。各測定処理を指定時間で強制終了するタイムアウトではありません。

## 使い方

```sh
strata tune auto <profile-name> --time 30
```

`<profile-name>` には調整対象の保存済み profile 名、または run config JSON を指定します。

## 値と既定値

- 値は `argparse` の `float` 変換で読み取られ、内部では 60 を掛けて秒に換算されます。
- 省略時は `--mode quick` なら 1,200 秒（20 分）、`--mode thorough` なら 7,200 秒（120 分）です。
- `--time 0` は `a.minutes` の偽値判定で「未指定」と同じ扱いになり、`--mode` に応じた既定予算へ戻ります。
- 負数は parser や `Options.resolved()` で拒否されません。負の予算では基準設定の測定後に候補数が 0 となり得ます。負数を時間指定として使うことは想定しないでください。
- このオプションに対する明示的な正数・上限・有限値 validation は確認できません。非数値は `float` 変換時に argparse が拒否します。

## 実行時の動作

CLI は `--time` の値を `budget_s` に渡します。quick モードでは基準測定後に残り予算と平均測定時間から候補数を見積もり、予算に収めるため試さない候補を記録します。quick / thorough の各ラウンド、結果確認、リクエスト単位設定の確認では、次の測定を始める前に予算を確認し、残り時間が足りなければ探索・確認を止めます。測定中の engine run をこの予算で中断する処理はありません。

時間予算の経過計算からは GPU lock、PC が静かになるまでの待機、メモリー解放待ちが差し引かれます。従って実際の壁時計時間が `--time` の値を超える場合があります。予算が短く全候補を比較できないときは、候補を省略した理由や未確認の設定を結果に残し、比較不足なら `inconclusive` となる経路があります。

## 適用条件と副作用

このオプションは `strata tune auto` のみに適用されます。同じ CLI にある `strata tune plan` / `strata tune run` の `--time` は別 parser・別文書のオプションです。

`--mode` と相互作用し、モード既定予算と探索計画を変えます。予算を設定してもチューニング処理自体は実行され、既定では結果が `improved` または `default_confirmed` のとき preset が保存されます。`--no-save` を併用するとこの保存を抑止できます。CLI は試行履歴も記録します。

## 出力とエラー

時間予算専用のエラーメッセージや終了コードはありません。人間向け出力では進捗が stderr、最終結果が stdout に出ます。`--output json` では進捗メッセージを出さず、最終結果の JSON を stdout に出します。通常の tuner 結果では `improved` / `default_confirmed` が終了コード 0、`inconclusive` 等のその他結果が 6 です。割り込みによる `cancelled` は 130 です。

## 根拠

- `strata_cli/tune_commands.py:20-46` — `strata tune auto` parser。`--time` は `float`、既定 `None`、単位は分。
- `strata_cli/tune_commands.py:178-197` — 値を秒へ換算して `autotune.Options.budget_s` に渡す箇所、および `--leave-ram` の validation。
- `strata_control/autotune.py:50-76` — `Options.resolved()` がモード別既定予算を設定。0 が既定値へ置き換わる。
- `strata_control/autotune.py:215-236,303-338` — 経過時間・待ち時間の除外・予算判定、および測定 run の実行単位。
- `strata_control/autotune.py:417-429,437-449,513-519,564-618,713-735` — 候補数の見積もり、候補省略、各ラウンドと確認処理での予算判定。
- `strata_control/autotune.py:340-367,630-648` — 中断・結果分類・構造化終了コード用データ。
- `strata_cli/tune_commands.py:205-215,228-261` — 出力先、preset 保存、最終出力と CLI 終了コード。
- `docs/cli/README.md:804-824` — `strata tune auto` のコマンド階層と索引上の予定リンク。

調査は指定 revision の checkout 上のソースと索引に限定しました。CLI の実行、Release artifact、各 backend での測定挙動は確認していません。
