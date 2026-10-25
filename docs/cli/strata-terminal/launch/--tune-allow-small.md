# `--tune-allow-small`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--tune-allow-small` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ |

## 役割

自動チューニングで、設定によって回答が標準とわずかに異なる可能性がある候補も試行対象にします。これは回答の変化を許容する明示的な選択です。既定では無効です。

## 使い方

```sh
strata launch --model iq3_xxs --tune quick --tune-allow-small --no-tui
```

`--tune` の `quick` または `thorough` と併用してください。`--tune` を省略した場合の既定値は `skip` なので、このフラグだけでは tuner は実行されません。

## 値と既定値

- parser は `action="store_true"` で定義され、引数値は取りません。指定しなければ `False`、指定すれば `True` です。反復指定を拒否する独自 validation はありません（`strata_cli/launch/cmd.py:111-113`）。
- 新しい設定の `LaunchSettings.tune_allow_small` は `False` です（`strata_cli/launch/settings.py:95-97`）。
- フラグは `True` の場合にだけ設定へ反映されるため、保存 preset がすでに `True` のとき、CLI によって明示的に無効化する方法はこのオプションにはありません。`settings_from_args` は preset を読み込んでから、指定時に値を `True` にします（`strata_cli/launch/cmd.py:200-203,248-251`）。

## 実行時の動作

launch のチューニング処理は `s.tune == "skip"` なら直ちに終了します。そうでなければ `quick` または `thorough` を tuner の `--mode` に対応させ、`tune_allow_small` が真のときだけ子プロセス引数 `--allow-small-differences` を追加します（`strata_cli/launch/runner.py:1325-1350,1356-1360`）。その子 parser も値なしの `store_true` です（`strata_cli/tune_commands.py:20-35`）。

この転送値は tuner の `Options.allow_placement` になります（`strata_cli/tune_commands.py:193-197`）。チューニング候補の `placement` 群は CPU/GPU の分担が変わるため標準と回答がわずかに異なり得る分類で、既定では候補から除外されます。フラグを許可すると、この分類の候補も、モデル family・backend・マシン条件・engine が受け付ける引数など他の条件を満たす場合に限り候補になります（`strata_control/tune_knobs.py:12-14,90-110,353-356,399-435`）。「すべての配置候補を必ず実行する」指定ではありません。

チューニング結果は通常の launch preset の適用経路へ戻ります。結果を再利用する preset がすでにチューニング済みの場合、または同じ構成の保存済み測定がある場合は、新たな測定を省くことがあります（`strata_cli/launch/runner.py:1332-1349`）。Launch 設定の表示用フラグ文字列にも、真の場合はこのオプションが含まれます（`strata_cli/launch/settings.py:272-299`）。

## 適用条件と副作用

- `--tune quick|thorough` を選んだ起動でのみ効果があります。`skip` では無効フラグを渡さず、チューニングもしません（`strata_cli/launch/settings.py:95-96`、`strata_cli/launch/runner.py:1325-1359`）。
- 候補の試行前に、同じ launch が管理する稼働中 server をチューニング用に停止し、測定後に再起動する通常経路があります。停止できない場合は `LaunchError`（code 6）になります（`strata_cli/launch/runner.py:1396-1415`）。GPU/CPU を使う測定が行われ、候補の追加により試行対象が増えることがあります。所要時間は選択モードと候補条件に依存し、固定時間はこのフラグだけでは保証されません。
- `quality`（数値を意図的に変える）候補や `nonrepeatable` 候補を許可するオプションではありません。`--allow-not-repeatable` は別フラグであり、この launch オプションからは転送されません（`strata_cli/tune_commands.py:33-35,193-196`、`strata_control/tune_knobs.py:353-356`）。
- preset に対して指定した場合は今回の設定を有効にします。設定の保存は `--save-preset` など launch の保存動作に従い、このフラグ自体が独立して preset を書き換えるわけではありません。

## 出力とエラー

このフラグ単独の専用出力や validation error は定義されていません。候補が回答差の許可を必要として除外された場合、tuner 内部では理由として「回答がわずかに変わる可能性」を記録します（`strata_control/tune_knobs.py:410-413`）。launch 実行時の一般的なエラーは stderr（通常出力）または JSON error（JSON 出力）へ変換され、KeyboardInterrupt は code 130 として扱われます（`strata_cli/launch/cmd.py:634-641,832-837`）。

## 根拠

- `strata_cli/launch/cmd.py:111-113,200-203,248-251` — parser と preset を元にした設定反映。
- `strata_cli/launch/settings.py:95-96,272-299` — 既定値と設定表示文字列。
- `strata_cli/launch/runner.py:1325-1361,1386-1415` — `skip` 判定、tuner 引数への転送、測定および server 停止。
- `strata_cli/tune_commands.py:20-35,193-197` — tuner 側の parser と候補許可設定。
- `strata_control/tune_knobs.py:12-14,90-110,353-356,399-435` — 回答差分類、候補例、許可判定と適用条件。

調査は指定 commit のソース checkout に限定しています。CLI help、配布 Release artifact、実機ごとの候補集合・測定時間は確認していません。
