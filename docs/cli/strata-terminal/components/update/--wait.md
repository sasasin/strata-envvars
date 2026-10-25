# `strata components update --wait`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update` |
| オプション | `--wait` |
| 別名 | なし |
| 値 | `SECONDS`。Python の `float` として解析される |

## 役割

engine が serving 中の場合に、engine の更新・切替を拒否する前に、停止するまで最大何秒待つかを指定します。engine の差し替え中や test start 中に serving engine と競合しないための待機時間です。

## 使い方

```sh
strata components update --wait 300
```

engine が serving 中なら最大300秒、停止するのを待ちます。待機時間はダウンロード時間を含まず、後述の serving 状態確認から数えます。

## 値と既定値

- `--wait` は値を必須とし、`float` へ変換します。parser に最小値・最大値・有限値の validation はありません。数値に変換できない値は `argparse` の引数エラーになります（parser 定義: `strata_cli/update_cmd.py:34-35`）。
- 省略時の parser 値は `None` で、実行 context には `0.0` として渡されます（`strata_cli/update_cmd.py:182-184`）。ただし通常の人間向け TTY では、engine が serving 中かつ `--wait` が未指定相当の場合に、待つかを対話で質問します。`y` / `yes` なら6時間を待機上限として設定します（`strata_cli/update_cmd.py:237-252`）。
- `0` は未指定と同様に false 扱いとなるため、TTY では上記の質問が出ます。非対話実行または machine-readable 出力では質問せず、engine 更新経路で serving 中なら即時に拒否されます（`strata_cli/update_cmd.py:183`, `237-252`; `strata_control/updater.py:302-307`）。
- 負数は truthy のため対話質問を飛ばしますが、待機関数は `wait <= 0` で即時に `Busy` を返します。正数の待機上限を過ぎても serving が続く場合も `Busy` になります（`strata_control/updater.py:300-310`）。

## 実行時の動作

`--wait` は `strata components update` と `strata update` に共通する parser 定義にあり、`components update` 側でも `_common` を通して登録されます（`strata_cli/update_cmd.py:30-35`, `50-56`）。値は update context の `wait` に設定されます（`strata_cli/update_cmd.py:182-184`）。

通常更新では、明示的な正の `--wait` があると、最初の対話確認を行わずに更新処理へ進みます。engine のアーカイブをダウンロードした後、staging 前に serving 状態を確認し、停止するまで最大指定秒数を待ちます。さらに、新 engine の test start 後、切替直前にも再確認します。したがって待機はダウンロードより後に起こり、2回の確認それぞれで上限時間が適用されます（`strata_cli/update_cmd.py:210-213`; `strata_control/updater.py:926-948`, `956-979`）。

`--check` は確認レポートを返す分岐であり、待機の事前処理にも更新実行にも進まないため、`--wait` は効果を持ちません（`strata_cli/update_cmd.py:203-210`）。また、`--no-engine` で engine 更新を無効にした場合、更新本体には serving 待機箇所がありません（`strata_cli/update_cmd.py:213`; `strata_control/updater.py:1283-1288`）。

## 適用条件と副作用

- serving 判定は Strata の管理対象 runtime と共有 activity lease を調べます。判定時に取得する exclusive lease は確認後に閉じられ、保持されません（`strata_control/updater.py:275-297`）。
- 人間向け TTY で未指定相当の場合、engine が serving 中で、`launch-` で始まる profile でなければ「待って更新するか」を質問します。非TTYまたは `--output json/jsonl` では質問せず、更新処理側の busy 拒否に委ねます。Strata 自身の `launch-` は対話確認を飛ばし、停止方法を示す拒否経路に進みます（`strata_cli/update_cmd.py:237-252`; `strata_control/updater.py:65-75`）。
- `--wait` は停止を要求したり serving engine を終了したりしません。待機中は3秒間隔で状態を再確認し、経過時間またはキャンセルを検出すると拒否します（`strata_control/updater.py:300-311`, `333`）。
- `strata components update` は rollback parser とも `_common` を共有しますが、この文書の対象は update です。rollback 側では同じ context 値を rollback 前の serving 判定に使います（`strata_cli/update_cmd.py:57-59`; `strata_control/updater.py:1033-1044`）。

## 出力とエラー

待機中は通常出力で「An engine is serving; waiting for it to stop before updating.」が表示され、`jsonl` では `waiting` event が出ます。`json` モードでは event は標準出力に出しません（`strata_control/updater.py:308-310`; `strata_cli/update_cmd.py:62-84`）。

上限時間内に停止しない場合は `Busy` エラーとなり、終了コード7で拒否されます。engine は serving 中に更新・test start されません（`strata_control/updater.py:65-75`, `300-310`）。

## 根拠

- Parser とコマンドスコープ: `strata_cli/update_cmd.py:30-59`。CLI からの登録・dispatch: `strata_cli/cli.py:139-140`, `2135-2137`。
- 値の context への格納、`--check`、通常更新への分岐、対話確認: `strata_cli/update_cmd.py:163-213`, `237-252`。
- serving 検出、待機・timeout、busy の終了コード: `strata_control/updater.py:54-75`, `275-311`。
- engine 更新内の待機箇所: `strata_control/updater.py:926-948`, `956-979`。rollback の待機箇所: `strata_control/updater.py:1033-1044`。

調査範囲は上記 commit の checkout 内にある Python CLI と updater 実装です。Release 配布物や異なる OS/backend 上での実行は確認していません。
