# `strata runtime start --wait`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査開始時の checkout は `main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime start` |
| オプション | `--wait` |
| 別名 | なし |
| 値 | 秒数（`float`） |
| 既定値 | `300` 秒 |

## 役割

保存済み profile をバックグラウンドの owner host で起動し、起動状態の確認をどれだけ待つかを指定します。既定ではサーバーが `ready` または `failed` になるまで最大 300 秒待ちます。サーバーが準備できる前に CLI が戻っても、開始済みの owner host はバックグラウンドで動作を続けます。

## 使い方

```sh
strata runtime start --profile my-profile --wait 120
```

待たずに owner host が起動した時点で CLI に戻す例:

```sh
strata runtime start --profile my-profile --wait 0
```

## 値と既定値

- `argparse` の `type=float` で数値に変換されます。未指定時は `300` 秒です。
- 実行時に有限値かつ `0..600` 秒の範囲かを検証します。範囲外、`NaN`、無限値は拒否されます。小数値も受け付けます。
- `--wait 0` は有効です。起動待ちをゼロにし、owner host の起動が確認された時点で `state: starting` として返します。

## 実行時の動作

CLI は値を `management.runtime_action(..., wait=...)` に渡し、管理層は範囲を検証して、操作記録に `wait_s` として保存したうえで `runtime.start()` を呼び出します（`strata_cli/cli.py:1345-1356`、`strata_control/management.py:202-230`）。

`runtime.start()` は profile の候補を確認し、古い owner が残したプロセスの処理後に owner host をデタッチして起動します。その host の状態が現れるまで待ち、`--wait 0` なら状態を確認した段階で `starting` を返します。このとき host には `--startup-wait 300` が渡され、CLI が戻った後も server の起動・準備処理は続きます（`strata_control/runtime.py:546-584`）。

`--wait` が正数の場合、CLI は host の状態を約 0.2 秒ごとに確認し、`ready` または `failed` で戻ります。期限までにどちらにもならなければ `startup_wait_expired` を含む失敗結果を返します。これは起動処理のキャンセルではありません。host は残り得るため、後から `strata runtime status --profile NAME` で状態を確認できます（`strata_control/runtime.py:585-599`）。

この値は `--shutdown-timeout` とは別です。`--shutdown-timeout` は host に渡される停止猶予時間で、`--wait` の範囲検証とは別に `0..300` 秒で検証されます（`strata_cli/cli.py:210-212`、`strata_control/management.py:202-204`、`strata_control/runtime.py:561-563`）。

## 適用条件と副作用

- このオプションは `strata runtime start` の parser に属します。同じ名前の `--wait` が `runtime verify`、`runtime stop`、`runtime restart` にもありますが、各コマンドの既定値・意味は別です（`strata_cli/cli.py:203-212,216-229,245-246`）。
- 起動経路では owner host のログを追記モードで開きます。host の標準出力と標準エラーはそのログにまとめられます（`strata_control/runtime.py:548-574`）。
- タイムアウトで CLI が失敗を返しても host を停止しません。起動の成否は後続の `runtime status` で調べてください。
- `--plan` との併用では start 計画だけを返し、`wait` の範囲検証は行いますが、実際の待機や起動はしません（`strata_control/management.py:202-219`）。

## 出力とエラー

- human 出力では状態と、失敗時にはエラー文字列を表示します。`--output json` では同じ結果を JSON で出力します。戻り値が失敗なら結果の `exit_code` を CLI の終了コードにします（`strata_cli/cli.py:1357-1373`）。
- 起動完了前に期限が切れると `startup_wait_expired`、`state: starting`、最後に確認した `phase` を返し、終了コードは `8` です（`strata_control/runtime.py:585-599`）。
- 値が有限の `0..600` 秒でなければ、管理層が `start wait must be finite seconds in 0..600` として拒否します。CLI は `ValueError` としてエラー出力し、既定の終了コード `2` を使います（`strata_control/management.py:113-117,202-204`、`strata_cli/cli.py:2166-2173`）。
- owner host が状態を作る前に終了した場合は、ログの場所を示す `runtime host failed to start; inspect ...` で失敗し、終了コード `6` になります（`strata_control/runtime.py:576-582`）。

## 根拠

- `strata_cli/cli.py:197-212` — `runtime start` parser と `--wait` の型・既定値。
- `strata_cli/cli.py:1345-1373` — 値の管理層への転送と human/JSON 出力・終了コード。
- `strata_control/management.py:113-117,188-230` — 有限秒数の検証、start の範囲、計画・操作記録・実処理への転送。
- `strata_control/runtime.py:518-599` — 起動、host のデタッチ、`0` の扱い、ready/failed 待機、期限切れ結果。

確認範囲は上記 commit の checkout にある Terminal CLI と管理層のソースです。同一 revision の `--help` や Release 配布物は照合していません。
