# `--mode`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout は `main...origin/main` で、未コミット変更はありません。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune auto` |
| オプション | `--mode` |
| 別名 | なし |
| 値 | `quick` または `thorough`（1値必須） |
| 既定値 | `quick` |

## 役割

自動チューニングで探索する候補の範囲と測定回数を選びます。`quick` は短い探索、`thorough` はより多くの候補と追加確認を行うモードです。ここで行うのは実行設定の測定・探索であり、モデルの学習ではありません。コマンドは利用者の現在の run configuration を基準に比較します。

## 使い方

```sh
strata tune auto <profile-or-config.json> --mode thorough
```

`<profile-or-config.json>` には保存済みプロファイル名または run configuration の JSON パスを指定します。省略時と同じ動作を明示する例は `strata tune auto <profile-or-config.json> --mode quick` です。

## 値と既定値

- parser は `quick` / `thorough` のみを受理し、省略時は `quick` です。別名はありません。
- `quick` の既定予算は20分（1200秒）、候補測定は2ラウンド、最終候補の追加確認ペアは0です。
- `thorough` の既定予算は最大2時間（7200秒）、候補測定は3ラウンド、最終候補は予算に余裕があれば5ペアで追加確認されます。
- `--time MINUTES` を指定すると予算を上書きしますが、モードに紐づく候補選択、ラウンド数、確認回数は切り替わりません。CLI 実装では `--time 0` は未指定として扱われ、負数は明示予算として渡されます。
- `--mode` に他の値を渡すと argparse の choices 制約で引数解析に失敗し、コマンド処理は開始されません。

## 実行時の動作

`quick` は各候補を時間予算に収まる範囲で先頭から選び、残り時間から見積もった実行可能数を上限にします。`thorough` は適用可能な候補をすべて計画に含め、通常候補より後に「thorough のみ」の候補を試します。どちらも候補を一つずつ基準設定と交互に測定します。候補がその PC・backend・目的に合わない場合や、engine が対応しない設定などは別条件で除外されます。

`thorough` は warm-up を1回から2回に増やします。また `--use coding` と context が64K未満の場合は長文 prompt も測定対象に含めます（quick の coding はこの条件分岐では長文を追加しません）。長い context では両モードとも context に応じた長文 prompt を含めます。

`--time` がない場合に予算を決めるのは `--mode` です。待機時間（GPU lock、他の engine や busy CPU、メモリ待ち）はチューニング予算の経過時間から差し引かれます。そのため、実時間が表示上の予算を超える場合があります。`thorough` の5確認ペアも、残り予算が不足すれば実行されません。

実行対象は設定済み engine の起動を複数回行い、固定 request set で測定します。結果が `improved` または `default_confirmed` で、`--no-save` が指定されていないときは preset を保存します。新しい preset は有効化され、以降の該当モデル起動時に run configuration の上へ適用されます。`--no-save` の有無にかかわらず、測定 trial の履歴記録は試みられます。チューニング中に設定ファイルそのものを書き換える処理はこの経路にはありません。

## 適用条件と副作用

`--mode` は `strata tune auto` のみに適用されます。同じ `strata tune` 階層にある `strata tune run --mode` は `protocol` / `api` を選ぶ別 parser であり、この文書の値とは異なります（`strata_cli/cli.py:431-434`）。

チューニングは engine の起動と測定 request を行い、既定では成功結果に対する preset 保存と trial 履歴記録を行います。`--mode` 自体は GPU/backend を直接選択しません。適用可能な候補はモデル family、backend、engine が受理する flag、目的、回答の再現性などにより絞られます。候補実行前には空きメモリ等の guard があり、起動できない候補はスキップされます。

## 出力とエラー

人間向け出力では進捗行を stderr に出し、完了時に測定結果を表示します。`--output json` の場合は進捗行を抑え、完了時に JSON を stdout に出力します。結果は改善時・基準設定が最速と確認された場合に終了コード0、キャンセル時130、それ以外の結果は6です。対象設定の読込失敗は通常2、engine が見つからない場合は5です。

モード値の誤りは `auto()` 実行前の parser 段階で拒否されます。チューニング中の基準測定失敗、メモリ不足、PC の騒音・ドリフト、時間不足などは測定結果として報告され、必ずしも `--mode` の値エラーとはなりません。

## 根拠

- `strata_cli/tune_commands.py:20-28` — `auto` parser、対象引数、`--mode` の choices・default・help。
- `strata_cli/cli.py:486` — `tune auto` parser の登録。
- `strata_cli/cli.py:2217-2231` — parser による引数解析と未知引数の拒否。
- `strata_cli/tune_commands.py:174-197` — target 読込、実行時 option への mode 受け渡し、`--time` の予算変換。
- `strata_control/autotune.py:50-76` — mode ごとの既定予算、ラウンド数、確認ペア数。
- `strata_control/autotune.py:217-236` — 待機時間を除外した予算経過時間と予算判定。
- `strata_control/tune_knobs.py:380-405` — quick/thorough の候補選択と thorough 専用候補。
- `strata_control/autotune.py:369-377` — thorough の warm-up 回数と coding 時の長文測定条件。
- `strata_control/autotune.py:417-433` — 候補数の予算制御、round 数、確認 run 数の計画。
- `strata_control/autotune.py:564-603` — thorough の追加確認と予算不足時の分岐。
- `strata_cli/tune_commands.py:205-219` — 人間向け進捗 stderr、status 更新、WorkerSession 構築。
- `strata_cli/tune_commands.py:228-261` — tuner 実行、trial 記録、成功時の preset 保存、出力と終了コード。
- `strata_control/presets.py:268-305` — preset 作成時の既定有効化。
- `strata_control/presets.py:441-460` — active preset を run configuration に重ねる起動時の処理。
- `strata_control/autotune.py:303-338` — engine を使った測定 run と trial 結果の記録。

調査範囲は上記 checkout のソースです。同一 revision の CLI `--help` と Release 配布物は確認していません。
