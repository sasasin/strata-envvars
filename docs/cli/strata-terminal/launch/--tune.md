# `--tune`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更は表示されませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--tune` |
| 別名 | なし |
| 値 | `quick`、`thorough`、`skip` |

## 役割

起動前にこの PC 上でエンジン設定を測定し、速い設定を選ぶモードを指定します。通常モデルでは `strata tune auto` を実行し、測定結果が改善または標準設定が最速と確認された場合、選択した構成に対応する tuning preset を保存します。DeepSeek-V4.1-Flash は専用 tuner を使います（`strata_cli/launch/runner.py:1265-1266,1282-1294,1325-1357`; `strata_cli/tune_commands.py:20-25,246-261`）。

## 使い方

```sh
# 起動計画だけを表示する。測定・起動は実行しない
strata launch --model iq3_xxs --tune quick --plan

# quick 測定後に起動する
strata launch --model iq3_xxs --tune quick --no-tui

# thorough で測定し、すでにある測定結果も再測定する
strata launch --model iq3_xxs --tune thorough --retune --no-tui
```

## 値と既定値

- 値は `quick`、`thorough`、`skip` のいずれかです。前後の空白を除いて小文字化してから照合するため、大文字表記も正規化されます。空値、値の欠落、候補外の値は `argparse` の usage error になります（`strata_cli/launch/cmd.py:37-45,111`; `strata_cli/launch/settings.py:26`）。
- 新規 `LaunchSettings` の既定値は `skip` です。`--tune` を省略した場合、コマンドライン起動では測定しません。保存 preset を読み込んだ場合はその設定が基礎になり、明示した `--tune` が上書きします（`strata_cli/launch/settings.py:95`; `strata_cli/launch/cmd.py:197-203,248-250`）。
- `quick` は通常 tuner の既定約20分、`thorough` は最長約2時間の測定モードです。これは tuner の時間予算であり、実際の所要時間を保証する値ではありません（`strata_cli/tune_commands.py:22-28`; `strata_control/autotune.py:50-76`）。
- `--retune` を付けて `--tune` を省略した場合、`skip` は `quick` に補正されます。従って `--tune skip --retune` も実行時には quick になります（`strata_cli/launch/cmd.py:713-716`）。

## 実行時の動作

`strata launch` は設定・profile を準備した後、server 起動前に `Runner.tune()` を呼びます。`skip` は何もせず戻ります。通常のモデルでは `quick` / `thorough` を tuner の `--mode` に渡し、測定結果を JSON で受け取ります。`--tune-allow-small` が有効なら、追加で `--allow-small-differences` を渡します。これは通常 tuner で回答がわずかに変わる可能性のある候補設定も試す指定です（`strata_cli/launch/runner.py:1325-1361`; `strata_cli/tune_commands.py:27-35,193-197`）。

測定に先立ち、同じ launch profile で自分が起動した server が稼働中なら停止し、測定後は選ばれた設定で起動し直します。別の実行を停止するものではないと Runner の説明にあります。通常 tuner は `improved` または `default_confirmed` の結果を保存対象とし、起動側は保存された preset ID と測定日を設定に反映します（`strata_cli/launch/runner.py:1350-1361,1390-1415`; `strata_cli/tune_commands.py:246-253`; `strata_cli/launch/runner.py:2034-2043`）。

`--retune` がない場合、preset に既存の tuning preset が見つかる、標準設定が以前最速と確認済み、または同じモデル・選択肢・PC に対する保存済み tuning が見つかると、再測定を省略します。`--retune` はこれらの再利用を迂回します。同じ設定・port で既に serving 中なら通常は測定に入らず既存 server を再利用しますが、`--retune` はこの再利用判定も迂回します（`strata_cli/launch/runner.py:1332-1349,1505-1521`）。

DeepSeek-V4.1-Flash の複数ファイル経路では専用 tuner が呼ばれ、`quick` / `thorough` を渡します。`--tune-allow-small` は通常 tuner へ渡すフラグであり、この専用 tuner 呼び出しには渡されません（`strata_cli/launch/runner.py:1265-1269,1282-1294,1325-1331,1356-1359`）。

## 適用条件と副作用

- `--plan` は `Runner.plan()` を呼んで表示した後に終了する分岐です。計画表示では測定を開始しません（`strata_cli/launch/cmd.py:733-760`）。
- 通常 tuner はエンジンを複数回起動して設定を比較します。quick/thorough の実時間は PC、モデル、候補数等に依存します。測定中は他の重いプログラムを閉じるよう案内します（`strata_control/autotune.py:341-350,379-430`; `strata_cli/launch/runner.py:1360-1361`）。
- 通常 tuner の進捗用 JSON は launch ディレクトリ内の `<launch名>.tune.json` です。起動側は tuner 開始前に同名ファイルの削除を試み、tuner は進捗ごとに書き換えます。加えて tuner は試行履歴を記録し、改善または標準設定確認時には tuning preset を作成します（`strata_cli/launch/runner.py:1351-1359`; `strata_cli/tune_commands.py:149-155,240-253`）。
- `--tune-allow-small` 単独では `--tune` の `skip` を変更しないため、測定を開始しません（`strata_cli/launch/cmd.py:248-251`; `strata_cli/launch/settings.py:95-96`）。
- preset に対する `--tune` を含む起動フラグは、その起動用設定に反映されます。`--save-preset NAME` を併用すれば起動後の選択を launch preset に保存します。既存 preset を指定しただけでは、起動時に加えた変更はその preset に保存されません（`strata_cli/launch/cmd.py:197-203,788-792`）。

## 出力と失敗

- `--plan` は人間向けまたは JSON で計画を出力して正常終了します。チューナーの測定結果は含みません（`strata_cli/launch/cmd.py:733-760`）。
- 通常 tuner の結果は `faster`、`already fastest`、`busy PC`、`stopped`、`failed` などに整理されます。測定不能・PC が混雑して判定不能・tuner の失敗では標準設定で起動を続ける旨を出します。キャンセル時は設定を変更しない結果になります（`strata_cli/launch/runner.py:198-214,1386-1394`; `strata_control/autotune.py:341-350`）。
- 同一 profile の稼働 server を測定のため停止できない場合、`LaunchError` として起動を拒否し、`strata launch --stop` 後の再試行を案内します（終了コード 6、`strata_cli/launch/runner.py:1398-1415`）。
- 不正値は parser が拒否します。通常 tuner の結果・測定失敗と、launch parser / 起動処理自体のエラーは異なる経路です（`strata_cli/launch/cmd.py:37-45,111,2217-2231`; `strata_cli/launch/runner.py:1386-1394`）。

## 根拠

- `strata_cli/launch/cmd.py:37-45,75-82,111-112` — parser、値変換、help。
- `strata_cli/launch/settings.py:26,95-112` — 値候補、設定既定値、tuned 状態。
- `strata_cli/launch/cmd.py:197-203,248-251,713-716,733-760,784-804` — preset と CLI 値の反映、`--retune` 補正、plan・起動分岐、preset 保存。
- `strata_cli/launch/runner.py:1265-1269,1282-1323,1325-1415,1505-1521,2034-2043` — DeepSeek 専用経路、tuner 起動、再測定判定、server 停止・起動。
- `strata_cli/tune_commands.py:20-46,174-197,217-261` — 通常 tuner の parser、測定設定、preset 保存、結果と終了コード。
- `strata_control/autotune.py:50-76,341-350,379-430` — 測定モードの予算・反復数、tuner の実行。

調査はこの checkout のソースと CLI parser に限定しました。実機での測定時間、各 PC 上で選ばれる設定、GPU ごとの実測性能は確認していません。
