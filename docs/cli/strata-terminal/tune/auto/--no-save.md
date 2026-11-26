# `--no-save`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune auto` |
| オプション | `--no-save` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

チューニング測定と結果表示を行いながら、結果を自動適用されるプリセットとして作成する処理を抑止する。既定では `--no-save` は無効で、改善結果または現在設定が最速と確認された結果をプリセットに保存する。指定すると、そのプリセット作成を行わない。

## 使い方

```sh
# 保存済みプロファイルを測定するが、プリセットは作成しない
strata tune auto my-profile --no-save
```

対象には保存済みプロファイル、インストール済みモデル名、または実行設定 JSON を指定できる。`--plan` と併用した場合は計画表示だけで終了し、測定もプリセット作成も行わない。

## 値と既定値

値は不要で、`argparse` の `store_true` フラグである。省略時は `False`、指定時は `True` となる。値の範囲や追加の validation はない。`--no-save=false` のような値付き形式はこの定義では受け付けない。

## 実行時の動作

`strata tune auto` は対象設定とエンジンを解決し、通常の測定を実行する。完了後には試行結果をプリセットの `history.jsonl` に記録し、結果に応じて最後のチューニングレポートを保存する。`--no-save` が指定されていない場合に限り、結果の outcome が `improved` または `default_confirmed` なら `presets.create(...)` を呼び、プリセットを作成・有効化する。指定時はその作成分岐を飛ばすため、プリセットファイルと有効プリセットの索引はこの処理では更新されず、プリセット作成時に行う設定値の安全性検査も通らない。結果データの `preset` は `null`、`values.preset_name` は `null` となり、改善時の人間向け表示も保存名を含まない。

したがって、このフラグは測定や全てのディスク書き込みを無効にするものではない。`presets.record_trials(...)` と `tune_report.save(...)` はフラグに関係なく実行される。また、`--work-dir` を指定しない場合の一時作業ディレクトリは終了時に削除され、指定した場合は保持される。`--status-file` 指定時は進捗・完了状態の JSON も更新される。

## 適用条件と副作用

- プリセット作成を抑止する条件は、`--no-save` が真であること。未指定時も outcome が `improved` または `default_confirmed` 以外ならプリセットは作成されない。
- `--plan` は対象やエンジンの検査後に計画を出力して戻るため、測定後の保存処理に到達せず、このフラグとの実行上の差はない。
- `--no-save` でも測定のためエンジンを起動する。失敗時に取得されたエンジンログがある場合は、末尾最大 256 KiB がプリセットディレクトリの `last-failed-engine.log` に保存される。
- 試行履歴の追記で `OSError` が発生しても握りつぶされる。レポート保存も書き込み不可時には失敗を示すパスを返さず、通常の結果処理を継続する。

## 出力とエラー

測定完了後、既定の human 出力は標準出力に結果を表示し、`--output json` なら `schema_version: 1` と `ok: true` を含む JSON を標準出力に出す。進捗メッセージは human モードでは標準エラーに出る。`--no-save` 指定時に改善結果が出た場合、結果は表示されるがプリセット名は付かない。

ターゲット解決など測定開始前の失敗は human モードで `strata: ...` を標準エラーに出し、JSON モードでは `ok: false` のエラー JSON を標準出力に出す。関数は対象解決失敗時にそのエラーコード、エンジン不在時に `5`、専用チューニング不要の Hy4-Flash / Inkling-2-Mini で `2` を返す。測定完了後は `improved` と `default_confirmed` が `0`、中断が `130`、その他の outcome が `6`。プリセットを作成しないこと自体はエラーではない。

## 根拠

- `terminal/strata_cli/tune_commands.py:21-50` — `strata tune auto` parser と `--no-save` の `store_true` 宣言、他のフラグの既定値。
- `terminal/strata_cli/cli.py:514-515,1722-1723` — parser 登録と `auto` 処理への dispatch。
- `terminal/strata_cli/tune_commands.py:309-353` — 対象解決、専用チューニング対象の拒否、`--plan` の早期終了、エンジン不在時の失敗。
- `terminal/strata_cli/tune_commands.py:371-425` — 測定実行、割り込み処理、履歴記録、`--no-save` によるプリセット作成分岐、レポート保存、出力と終了コード。
- `terminal/strata_control/presets.py:293-334` — プリセット JSON の作成と既定での有効化。
- `terminal/strata_control/presets.py:293-302` — プリセット作成前の設定値安全性検査。
- `terminal/strata_control/presets.py:551-570` — `history.jsonl` への試行結果追記。
- `terminal/strata_control/tune_report.py:87-103` — `last-tune-report.txt` の保存先と書き込み失敗時の扱い。
- `terminal/strata_cli/tune_commands.py:101-114` — 人間向け／JSON のエラー出力形式。
