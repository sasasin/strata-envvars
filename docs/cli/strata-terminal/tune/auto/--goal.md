# `--goal`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune auto` |
| オプション | `--goal` |
| 別名 | なし |
| 値 | `speed`、`full`、`room`、`room:MiB`。`MiB` 部分は整数 |

## 役割

自動チューニングの目的を、速度優先にするか、実行時にメモリを空けることを優先するか指定する。`room:MiB` は空けたいグラフィックスメモリ量も指定する。値は候補設定の選別と、候補がベース設定よりメモリを余分に使う場合の採否に使われる。既定値は `speed`（`terminal/strata_cli/tune_commands.py:31-32`、`terminal/strata_cli/tune_commands.py:192-199`）。

## 使い方

```sh
# 速度優先（既定値）
strata tune auto qwen/IQ3_S --goal speed

# メモリを空ける目的でチューニング
strata tune auto qwen/IQ3_S --goal room

# グラフィックスメモリを 2048 MiB 空ける指定
strata tune auto qwen/IQ3_S --goal room:2048

# 実行せず、目的に沿った候補と計画を表示
strata tune auto qwen/IQ3_S --goal room:2048 --plan
```

`target` はインストール済みモデル、保存済みプロファイル、または run configuration の JSON を指定する（`terminal/strata_cli/tune_commands.py:27`）。`--plan` は実測を開始せず計画を返す（`terminal/strata_cli/tune_commands.py:349-353`）。

## 値と既定値

- 未指定時は `speed`。
- `speed` と `full` はどちらも内部値 `speed`、予約量 `0` に正規化される。`full` は parser の help 文にはないが、実際の値解釈では受理される（`terminal/strata_cli/tune_commands.py:31-32`、`terminal/strata_cli/tune_commands.py:192-194`）。
- `room` は内部値 `room`、予約量 `0`。
- `room:<整数>` は内部値 `room` とその整数を MiB 単位の予約量として扱う。負数は `0` に丸められ、上限値の検査はない（`terminal/strata_cli/tune_commands.py:195-198`）。
- 大文字小文字を変えた値、空値、整数でない `room:` 値などは受理されない。`argparse` の定義に `choices` や独自 `type` はなく、実行時の `_parse_goal` が不正値を `ValueError` にする（`terminal/strata_cli/tune_commands.py:31-32`、`terminal/strata_cli/tune_commands.py:192-199`）。
- 同じ `--goal` を複数回指定した場合の独自処理はなく、`argparse` の通常の単一値引数として最後に指定した値が使われる（`terminal/strata_cli/tune_commands.py:31-32`）。

## 実行時の動作

`auto()` は最初に値を正規化し、チューニング対象を解決する。不正な goal は対象解決と同じ例外処理経路でエラーになり、JSON 出力時は JSON エラー、それ以外は `strata: ...` を標準エラーへ出し、終了コード `2`（通常の不正 goal）を返す（`terminal/strata_cli/tune_commands.py:309-323`、`terminal/strata_cli/tune_commands.py:101-114`）。

`room` はチューニング文脈へ渡され、候補ノブの goal 条件に合わない設定は候補から外される。`--use` で選んだ用途に合致する候補は goal が異なっても残り得る（`terminal/strata_cli/tune_commands.py:342-345`、`terminal/strata_control/autotune.py:926-932`、`terminal/strata_control/tune_knobs.py:425-448`）。

実測時、goal が `room` なら候補がベースより RAM 使用量を大きく増やす場合、空き RAM を減らす場合、VRAM を 256 MiB 超多く使う場合などに候補を拒否する。`room:<MiB>` の VRAM 予約は、合計 VRAM が取得でき、ベース実行で指定した空き量を満たしているときに限り、候補が許容誤差 128 MiB を超えて予約分を侵食する場合に拒否条件となる。いずれも候補の採否条件であり、goal 自体がベース設定のメモリ使用量を必ず減らす保証ではない（`terminal/strata_control/autotune.py:713-732`）。

`room:<MiB>` の予約量は、`flash-next` 系で backend が `cuda` または `hip`、かつエンジンフラグ情報が未取得か `--vram-reserve-mib` をサポートすると判断できる場合、ベース引数に同フラグが未設定ならベース設定へ追加される。それ以外の family/backend や非対応と判明したエンジンでは、この追加は行われない（`terminal/strata_cli/tune_commands.py:336-345`、`terminal/strata_cli/tune_commands.py:377-382`）。

`--leave-ram` が 0 より大きく、goal が `speed` なら goal を `room` に切り替える。したがって `--goal speed --leave-ram 20` の実行では room の候補選別・メモリ制約が適用される（`terminal/strata_cli/tune_commands.py:328-332`）。

## 適用条件と副作用

`--plan` を付けない実行では、現在の設定と候補設定をエンジンで測定する。チューニング結果が `improved` または `default_confirmed` で `--no-save` を付けていない場合、goal と予約量を含む選択条件で preset を保存する。測定結果のレポートも保存される（`terminal/strata_cli/tune_commands.py:355-387`、`terminal/strata_cli/tune_commands.py:395-425`）。

room のメモリ判定は使用可能な測定値や総メモリ情報がある場合に限られる。特に VRAM 予約の追加・侵食判定は family、backend、エンジンフラグ情報、VRAM 計測値に依存する。各 backend における外部エンジンの `--vram-reserve-mib` の完全な実装意味までは、この CLI 側コードだけでは確定できない。

## 出力とエラー

不正値は終了コード `2` で失敗する。通常出力ではエラー文を標準エラーに、`--output json` では `ok: false` とエラー内容を標準出力に出す（`terminal/strata_cli/tune_commands.py:101-114`、`terminal/strata_cli/tune_commands.py:314-323`）。

## 根拠

- `terminal/strata_cli/tune_commands.py:21-50` — `strata tune auto` の parser。`--goal` は既定値 `speed` の文字列引数で、`choices` 制約や別名はない。
- `terminal/strata_cli/tune_commands.py:192-199` — goal の実値解釈、`full` の互換受理、`room:MiB` の整数変換と負数の丸め。
- `terminal/strata_cli/tune_commands.py:309-345` — goal 検証、`--leave-ram` との相互作用、Options と tuning context への受け渡し。
- `terminal/strata_cli/tune_commands.py:349-353`, `377-425` — 計画のみの経路、room 予約のベース引数への追加、測定後の preset / report 保存。
- `terminal/strata_control/tune_knobs.py:425-452` — goal と用途による候補設定の選別。
- `terminal/strata_control/autotune.py:713-732` — RAM / VRAM 使用量による候補の拒否条件。
- `docs/cli/README.md:736-755` — `strata tune auto` のコマンド階層と `--goal` の索引リンク。
