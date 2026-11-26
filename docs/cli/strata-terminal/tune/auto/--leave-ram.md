# `strata tune auto --leave-ram`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune auto` |
| オプション | `--leave-ram` |
| 別名 | なし |
| 値 | 整数 `PERCENT`、0〜50 |

## 役割

自動 tuning に「システム RAM を空けておく」希望を渡します。0 以外を指定し、目標が既定の `speed` の場合は目標を `room` に切り替えます。tuner は基準構成と候補の測定中の空き RAM を比較し、空き RAM を大きく減らす候補を除外します。

## 使い方

```sh
strata tune auto IQ3_S --leave-ram 20
```

`IQ3_S` はインストール済みモデル名の例です。対象としてモデル、保存済み profile 名、または run configuration（JSON）を指定できます（`terminal/strata_cli/tune_commands.py:27`）。

## 値と既定値

- 省略時は `0`。型は Python `int`、parser 上の metavar は `PERCENT` です（`terminal/strata_cli/tune_commands.py:33`）。
- 実行時に `0 <= 値 <= 50` を検証します。範囲外は終了コード `2` で失敗します（同 `:328-329`）。
- 整数に変換できない値は argparse の型変換で拒否されます（同 `:33`）。このオプションに重複指定専用の検証はありません。

## 実行時の動作

`auto` は値を `autotune.Options.ram_wish_pct` に渡します。`--leave-ram` が 0 以外で、解決後の goal が `speed` なら `room` に変更します。明示的な `--goal room` や `--goal room:MiB` と併用した場合も `room` のままで、`room:MiB` の VRAM reserve は別の値として保持されます（`terminal/strata_cli/tune_commands.py:31-33,192-199,328-344`）。

候補の判定では、goal が `room` で、割合が非ゼロ、総 RAM と両測定の最小空き RAM が取得できる場合に、候補の最小空き RAM が基準構成より `max(512 MiB, 総 RAM の 3%)` を超えて減ると候補を除外します。測定値は tuning worker 実行中に記録されます（`terminal/strata_control/autotune.py:721-724`; `terminal/strata_control/tune_session.py:344-347,470`）。

なお、実装は指定割合から「総 RAM の何％を必ず空けるか」という絶対的な空き容量を計算していません。値が 1〜50 のどれでも、この比較条件の有効・無効は非ゼロかどうかで決まり、比較幅は総 RAM の 3%（または 512 MiB）です。従って、指定割合の空き RAM が保証されるわけではありません。コード上、OS にメモリ上限を設定したり、エンジン引数として割合を渡したりもしません（`terminal/strata_cli/tune_commands.py:342-345`; `terminal/strata_control/autotune.py:721-724`）。

成功結果が `improved` または `default_confirmed` で `--no-save` が指定されていない場合、preset を作成・有効化します。非ゼロ値は preset の `choices.leave_ram_pct` に記録されます（`terminal/strata_cli/tune_commands.py:396-410`; `terminal/strata_control/presets.py:293-295,308-313`）。

## 適用条件と副作用

- 値の検証は対象設定を読み込み、Hy4 / Inkling の tuning 対象外判定をした後に行われます（`terminal/strata_cli/tune_commands.py:314-329`）。
- メモリ比較は `room` 目標でのみ有効です。`--leave-ram 0` では割合による比較をしません（`terminal/strata_control/autotune.py:721-724`）。
- 実際の tuning ではモデル engine を起動して測定します。`--plan` を併用すると候補計画を表示して終了し、tuner の測定には進みません（`terminal/strata_cli/tune_commands.py:349-353,371-387`）。
- 保存条件を満たすと preset の作成・有効化に加え、試行履歴と tuning report の保存処理が行われます。`--no-save` は preset 保存を抑止しますが、試行履歴・report の保存経路とは別です（同 `:396-425`）。

## 出力とエラー

範囲外の値は `--output human` では `stderr` に `strata: --leave-ram is a percentage from 0 to 50` を出し、終了コード `2` です。`--output json` では同じエラーを `ok: false` の JSON として標準出力に出します（`terminal/strata_cli/tune_commands.py:50,109-114,328-329`）。

## 根拠

- `terminal/strata_cli/cli.py:514,1722-1723` — `tune auto` parser の登録と実行先。
- `terminal/strata_cli/tune_commands.py:21-50` — parser、型、既定値、関連オプション。
- `terminal/strata_cli/tune_commands.py:314-353` — 対象適用条件、範囲検証、goal 切替、tuner options への受け渡し、計画表示。
- `terminal/strata_control/autotune.py:54-67,713-732` — RAM 希望値と候補のメモリ超過判定。
- `terminal/strata_control/tune_session.py:344-347,462-470` — tuning 実行中の空き RAM 測定と結果への記録。
- `terminal/strata_cli/tune_commands.py:396-425`; `terminal/strata_control/presets.py:293-313` — preset 作成条件と割合の保存。
