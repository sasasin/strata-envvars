# `--wait`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update` |
| オプション | `--wait SECONDS` |
| 別名 | なし |
| 値 | 秒数（浮動小数点数） |
| 既定値 | 未指定時は待機時間 `0` 秒。対話端末では待つか確認される場合がある |

## 役割

更新対象の engine が稼働中の場合に、停止するまで指定秒数を上限として待ちます。待機しても稼働が続いていれば更新を拒否し、稼働中の engine を置き換えたりテスト起動したりしません（`strata_cli/update_cmd.py:34-35`、`strata_control/updater.py:300-312,65-75`）。

## 使い方

```sh
strata components update --wait 300
```

この option は `strata_cli/update_cmd.py` の共通 parser で `strata update` と `strata components update` に追加されます。`strata components update` は同じモジュールの `run()` に dispatch されます（`strata_cli/update_cmd.py:30-59`、`strata_cli/cli.py:139-140`、`2135-2137`）。

## 値と既定値

- 値は Python `float` として解析されます。既定値は `None` で、実行 context には `a.wait or 0.0` として渡されます（`strata_cli/update_cmd.py:34-35`、`182-184`）。数値として解析できない値は `argparse` に拒否されます。
- 独自の範囲検証はありません。負数を指定すると `wait_until_idle()` は待たずに稼働中として失敗します。0 は待機時間 0 として扱われます（`strata_control/updater.py:300-307`）。
- 同じ option を複数回指定した場合の専用処理はありません。通常の `argparse.add_argument()` のため、最後の値が使われます（`strata_cli/update_cmd.py:34-35`）。

## 実行時の動作

- `--wait` に正の値を指定すると、CLI 側の事前確認・質問を飛ばし、更新処理側で待機します（`strata_cli/update_cmd.py:237-244`）。engine 更新では package のダウンロード後、展開・検証へ進む前と、テスト起動後の切り替え直前に serving 状態を再確認します（`strata_control/updater.py:938-948,955-979`）。稼働がなくなるまで指定秒数を上限として、3 秒間隔で確認します。期限は poll 後に再確認した時点で判定されるため、実際の拒否は期限より poll 間隔程度遅れることがあります（`strata_control/updater.py:300-312,333`）。
- 上限までに停止しない場合は `Busy`（終了コード 7）になります。ダウンロード後の確認で失敗した場合、検証済み archive は retry 用に保持されます（`strata_control/updater.py:65-75,945-947`）。更新処理は engine、Control、app installer の順に個別実行し、一つの失敗を報告しても後続項目は処理し得ます（`strata_control/updater.py:1274-1297`）。
- `--wait` を省略するか `--wait 0` とした場合、`strata components update` は最初に稼働状態を確認します。対話端末かつ Strata の `launch-` 管理下でない engine が稼働中なら待機するか質問し、`y` / `yes` で最大6時間待ちます。`--output json` / `jsonl` または stdin が非対話の場合は質問せず、更新側の busy 拒否に進みます。Strata 自身の launch が稼働中なら質問せず、停止手順を案内する拒否になります（`strata_cli/update_cmd.py:237-252`、`strata_control/updater.py:68-75`）。
- `--check` は feed の確認後に終了し、`_maybe_wait()` を呼ばないため、この option の待機は発生しません（`strata_cli/update_cmd.py:203-210`）。engine が更新不要などで engine 更新経路に入らない場合や `--no-engine` を指定した場合も、updater 内の `wait_until_idle()` は呼ばれません（`strata_control/updater.py:926-937`、`1274-1285`）。`--wait` は Control/app installer 自体の稼働停止待ちを指定するものではありません。
- 共通 parser は `strata components rollback` にも `--wait` を追加しますが、rollback の option 文書スコープは別です。rollback 実行時は、rollback 処理の冒頭で同じ待機関数を使います（`strata_cli/update_cmd.py:42-59,185-188`、`strata_control/updater.py:1033-1044`）。

## 出力と失敗

- 待機中は `waiting` イベントが通知されます。人向け出力では待機メッセージが表示され、`--output jsonl` ではイベントが JSON Lines で出力されます。`--output json` は進捗イベントを出しません（`strata_cli/update_cmd.py:62-84`）。
- 指定時間内に engine が停止しないと更新結果に失敗として記録され、終了コード 7 になります。人向け表示では失敗内容が結果行に出て、JSON 出力では `ok: false` と component result に反映されます（`strata_control/updater.py:65-75,1286-1297`、`strata_cli/update_cmd.py:212-224`）。
- `SECONDS` が数値として解析できない場合は parser error（通常の argparse 終了コード 2）です。負数は parser では拒否されず、serving engine がある待機箇所で直ちに Busy になります（`strata_cli/update_cmd.py:34-35`、`strata_control/updater.py:300-307`）。

## 根拠

- `strata_cli/update_cmd.py:30-59` — 共通 parser、値型・既定値、および update/rollback への登録。
- `strata_cli/update_cmd.py:163-224,237-252` — 値の context への受け渡し、`--check` 分岐、対話確認、出力と失敗処理。
- `strata_cli/cli.py:139-140,508-515,2135-2137` — parser 登録、one-shot `--json` / `--quiet` の追加、update command の dispatch。
- `strata_control/updater.py:65-75,300-312,317-336` — busy 失敗、待機条件、既定 poll 間隔と context。
- `strata_control/updater.py:926-979,1274-1297` — engine 更新中の待機位置、retry 用 archive、各 component の順次処理と失敗集約。
- `strata_control/updater.py:1033-1044` — rollback での待機利用。

調査範囲は上記 commit の checkout にある Terminal CLI と `strata_control` の実装です。Release 配布物や別 platform 上での実更新は確認していません。
