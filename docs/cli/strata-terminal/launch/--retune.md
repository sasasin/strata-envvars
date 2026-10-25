# `--retune`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--retune` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると `True` |

## 役割

`strata launch` の tuning を実行し、同じモデルと設定についてこのコンピューターに保存済みの測定結果があっても再測定します。`--tune` が省略され、設定の tuning mode が `skip` の場合は `quick` に切り替えます。

## 使い方

```sh
strata launch --model q2_0 --retune --no-tui
```

既定の `quick` で測定します。測定モードを明示する場合は `--tune thorough` などを併用できます。`--tune skip` と同時に指定しても、`--retune` の処理が `skip` を `quick` に変更します。

## 値と既定値

- 値や回数指定はありません。複数回書いた場合も同じ真偽値のままです（`argparse` の `store_true`）。
- `--retune` 自体の既定値は `False` です。省略時、通常の tuning mode が有効なら、既存 preset の tuning 情報または同じモデル・選択条件の保存済み測定結果が再利用され、測定を省略する場合があります。
- `--retune` を指定して tuning mode が `skip` の場合は `quick` になります。preset などから既に `quick` / `thorough` が設定されている場合、その mode は維持されます。
- `--plan` と併用すると、計画上の tuning mode は表示しますが、計画表示後に終了するため測定しません。

## 実行時の動作

parser は `store_true` で値を受け取ります。設定組み立て後、`run_launch` が `--retune` と tuning mode `skip` の組み合わせを `quick` に補正し、runner にフラグを渡します。通常起動では、runner がエンジンとモデルを準備し、設定を保存した後に tuning を実行します。

通常モデルの tuning では、`--retune` がない場合に限り、既存 tuned preset、標準設定を測定済みとする記録、または同じモデル・選択条件の保存結果を再利用します。`--retune` があるとこの再利用判定を飛ばして tuner を起動し、CLI の `strata tune auto` に `quick` または `thorough` の mode を渡します。測定完了後は結果を使って launch を開始します。

起動前に同じ設定の server がすでに動作中でも、`--retune` がなければその server を再利用して終了できます。`--retune` を付けるとこの早期再利用を避けて tuning 経路へ進みます。tuning のために同じ launch の server が動作中なら先に停止し、測定後に再起動します。

## 適用条件と副作用

- `--tune` が `skip` のときだけ mode を `quick` に補正します。`--tune quick` / `--tune thorough` では指定された mode を使います。
- DeepSeek の複数ファイルモデルは通常モデルと異なる専用 tuner 分岐です。この分岐は保存済み結果の再利用判定より前に呼ばれるため、`--retune` による通常モデルの cache bypass は適用されません。ただし `--retune` は起動中 server の再利用判定には引き続き影響します。
- 測定には tuner の実行とモデル計測が伴います。測定対象の GPU を使うため、同じ launch の既存 server は停止されます。他のプログラムは停止しません。
- 同じ port を別 launch が使っている場合、通常の `--restart` 規則が別途適用されます。`--retune` は単独で `--restart` の代わりにはなりません。

## 出力とエラー

- tuning の開始・進捗・結果は launch のイベントとして表示されます。測定の結果が得られない DeepSeek 専用 tuner は警告して標準設定で続行します。通常モデルの tuner は測定後に結果を報告し、launch を続けます。
- 同じ launch の server を測定のため停止できない場合、エラーコード `6` で失敗し、先に `strata launch --stop` を実行するよう案内します。
- `--plan` は計画を表示し `Nothing was changed.` として終了します。`--retune` を付けても実測しません。

## 根拠

- `strata_cli/launch/cmd.py:127-131` — parser 定義と help。`cmd.py:713-716` は `skip` を `quick` に補正して runner を生成する処理。
- `strata_cli/launch/cmd.py:197-201,248-251` — preset/settings の初期化と `--tune` 設定の反映。
- `strata_cli/launch/cmd.py:731-760,784-787` — `--plan` の表示・終了経路と通常起動の呼び出し、launch error の処理。
- `strata_cli/launch/runner.py:1325-1362` — tuning mode、保存結果の再利用条件、tuner 起動。
- `strata_cli/launch/runner.py:1265-1269,1282-1323` — DeepSeek 専用 tuner 分岐と失敗時の扱い。
- `strata_cli/launch/runner.py:1398-1415` — tuning 前の server 停止と停止失敗経路。
- `strata_cli/launch/runner.py:1516-1538` — 同一 server の早期再利用、`--retune` / `--restart` による既存 server 判定。
- `strata_cli/launch/runner.py:2011-2044` — 起動処理の順序（設定準備、tuning、server 起動）。
- `bin/strata launch --help` — 同一 checkout の CLI help を補助資料として確認。parser 定義と一致。
