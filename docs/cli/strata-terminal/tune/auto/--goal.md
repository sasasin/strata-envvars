# `--goal`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更は表示されませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune auto` |
| オプション | `--goal` |
| 別名 | なし |
| 値 | `speed`、`full`、`room`、`room:MiB`。parser では文字列として受け取り、実行時に解釈する |

## 役割

探索する候補設定の選び方と、候補が基準設定よりメモリを多く使う場合の扱いを指定します。`speed`（既定値）/`full` は性能優先、`room` はメモリを空ける方針、`room:MiB` は指定量の VRAM を空ける方針です。`--goal` 自体はエンジン設定を直接適用する指定ではありません。探索結果に改善があれば、通常はチューニング preset として保存されます。

## 使い方

```sh
strata tune auto my-profile --goal room:4096
```

`my-profile` は保存済み profile 名、または実行設定 JSON を指します。コマンドには対象が必要です。

## 値と既定値

- 省略時は `speed`。
- `speed` と `full` は同じ内部値 `speed`、VRAM reserve `0` に変換されます。`full` は parser のヘルプ文字列には列挙されていませんが、実装が受理する別表記です。
- `room` は内部値 `room`、reserve `0` です。
- `room:<MiB>` は `<MiB>` を整数として読み、負数は `0` に丸めます。例: `room:-1` は reserve `0` と同じになります。
- 空文字列、不正な整数、`room` 以外の未知の値は実行時エラーになります。数値に上限はコード上確認できません。
- argparse 定義に `choices` や型変換はなく、値の検証はコマンド実行時に行われます。

## 実行時の動作

値は `_parse_goal()` で `(goal, reserve_mib)` に変換され、`autotune.Options` と候補計画の context に渡されます。候補 knob は、候補定義の `goals` に goal または `--use` の値が含まれる場合に限って計画対象になります。そのため `--use chat|coding` と候補の backend、モデル family、機器条件なども候補集合に影響します。`--goal` は測定スコアの種類を選びません。測定指標は別オプション `--use` によって決まります。

`room` では、探索候補の測定後に基準設定と比較して、RAM peak が基準より 5% と 512 MiB の許容幅を超えて増えた場合、VRAM 使用量が基準より 256 MiB を超えて増えた場合など、その候補を除外します。`room:<MiB>` では、基準が指定 reserve を満たしていたのに候補が満たさなくなる場合も除外します。これらは候補選定の制約であり、実行中の基準設定自体のメモリ使用量をこのオプションが保証・変更するものではありません。

全 goal に共通して、測定中の最小空き RAM が 3584 MiB を下回り、基準よりさらに 512 MiB 超少ない候補は除外されます。`room` と `--leave-ram` を併用した場合は、最小空き RAM が基準より `max(512 MiB, 総 RAM の 3%)` を超えて減った候補も除外されます。

さらに `room:<MiB>` の reserve は、設定にすでに `--vram-reserve-mib` がなく、engine family が `flash-next`、backend が `cuda` または `hip` で、engine がそのフラグを受け付ける（フラグ一覧が取得できない場合を含む）とき、基準引数へ `--vram-reserve-mib <MiB>` として追加されます。この引数が実際に有効かどうかは engine 側の対応状況に依存します。preset の選択情報には正規化後の goal と reserve が記録されます。

## 適用条件と副作用

- `room` 向け候補の有無は候補定義に依存し、全 backend・全モデルで同じ設定が試されるわけではありません。条件不一致や `--use` との不一致で候補が計画から外れることがあります。
- `--leave-ram PERCENT` を併用すると、値が `1..50` の場合、goal が `speed` でも内部 goal は `room` に変更されます。`0` は変更しません。範囲外はコード `2` で拒否されます。goal を `room` にしただけでは RAM の割合は指定されません。
- チューニングはモデル engine を複数回起動して測定します。`--work-dir` を指定しなければ一時作業ディレクトリを作り、試行ごとの設定・ログを置きます。`--status-file` を指定した場合は進捗 JSON を一時ファイル経由で置換しながら更新します。
- 試行記録は preset 保存の有無にかかわらず記録されます。結果が `improved` または `default_confirmed` なら、`--no-save` がない限り preset を作成します。`--goal` は既存の profile 設定ファイルを直接書き換えるオプションではありません。

## 出力とエラー

- 通常出力では進捗を stderr、最終結果を stdout に出力します。`--output json` では JSON 結果を stdout に出し、通常の進捗行は出しません。
- 未知の goal や `room:<MiB>` の整数変換失敗は、通常形式で `strata: <エラー>` を stderr に出し、終了コード `2`（または例外が持つ `exit_code`）になります。JSON 形式では `ok:false` と `error` を出します。
- 対象設定の解決に失敗した場合も同じエラー経路です。実行 engine が見つからない場合はコード `5`。
- ベース測定失敗、探索失敗または判定不能の結果は結果オブジェクトに含まれ、通常は終了コード `6`。成功（改善または既定設定確認）は `0`、割り込みによるキャンセルは `130` です。

## 根拠

- parser、既定値と構文: `strata_cli/tune_commands.py:20-46`。`--goal` の宣言は 29-30 行。
- goal の解釈、負数の補正、未知値エラー: `strata_cli/tune_commands.py:139-146`。
- 設定解決、`--leave-ram` の相互作用、reserve 引数の付加、候補 context と preset choice: `strata_cli/tune_commands.py:174-198`, `221-239`。
- エラー表示と JSON エラー: `strata_cli/tune_commands.py:103-108`。
- 実行結果の保存・出力・終了コード: `strata_cli/tune_commands.py:241-261`。
- goal と `--use` による候補絞り込み: `strata_control/tune_knobs.py:380-418`。
- goal による RAM/VRAM 候補上限の判定: `strata_control/autotune.py:692-711`。この判定は candidate の測定後に呼ばれます（`strata_control/autotune.py:479-500`）。
- 測定指標が `--use` により決まること: `strata_control/autotune.py:139-153`, `379-433`。
- 作業ディレクトリと試行ごとの config/log: `strata_cli/tune_commands.py:217-219`, `strata_control/tune_session.py:420-431`, `443-468`。
- 索引上のコマンド階層と文書パス: `docs/cli/README.md:804-824`。

調査は指定 revision の Python CLI と tuning 実装に限定しました。CLI `--help` の実行、Release 配布物、各 backend/engine が reserve をどのように実装するかは確認していません。
