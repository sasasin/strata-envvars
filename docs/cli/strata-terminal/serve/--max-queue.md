# `--max-queue`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata serve` |
| オプション | `--max-queue` |
| 別名 | なし |
| 値 | 整数 `N`。`0..4096` |

## 役割

推論 API の同時受付数を制限します。上限は有効な engine slot 数に `N` を加えた値で、実行中の要求と engine turn を待つ要求を含む受付済み要求数に適用されます。`serve/server.py` では `max(1, engine.batch) + max_queue` を admission limit とし、上限到達後の新しい要求を拒否します（`serve/server.py:3962-3965,3981-3991`）。

## 使い方

```sh
strata serve --profile my-profile --max-queue 16
```

`--profile` には保存済み profile 名または run config のパスを指定します。実際に server を起動せず有効設定と起動引数を確認するには `--plan` を加えます（`strata_cli/cli.py:47,63,915-942`）。

## 値と既定値

- Python CLI parser は整数として受け取り、明示値は `0..4096` に制限します。範囲外は `--max-queue must be in 0..4096` で失敗します（`strata_cli/cli.py:55,924-925`）。
- 省略時は保存済み profile、run config の `max_queue` が順に参照され、どちらにも値がなければ `None` です。この場合 admission limit は設定されません（`strata_cli/cli.py:745-765`; `serve/server.py:3962-3965`）。
- `0` は有効値です。slot 数を超える追加 admission 枠を設けません（`serve/server.py:3962-3965`）。
- 保存済み profile の `max_queue` も整数 `0..4096` で検証されます（`strata_control/profiles.py:66-74,108-109`）。

## 実行時の動作

CLI の実効値は、コマンドライン指定、保存済み profile、run config、既定値の順で選択されます。run config 由来以外の値は `--max-queue N` として server 起動引数へ渡されます。したがってコマンドライン値は profile と run config の値を上書きします。`strata serve` 自体は server を前景起動し、設定を永続化しません（`strata_cli/cli.py:745-765,782-805,940-953`）。

server は `POST /v1/chat/completions`、`POST /v1/messages`、`POST /v1/responses` の受付前に枠を予約します。予約数が上限以上なら、その要求を HTTP `429`、エラーコード `admission_full`、`Retry-After: 1` で返し、拒否カウンターを増やします。処理終了後は予約を解放します（`serve/server.py:3981-3996,6760-6777,6891-6894`）。ここで数えるのは各 API 要求であり、画像生成など別 endpoint の要求ではありません（受付対象 endpoint: `serve/server.py:6760-6763`）。

## 適用条件と副作用

- `--max-queue` だけでは待ち時間期限は設定されません。`--queue-timeout` を指定する場合は `--max-queue` も必要です。この依存関係は CLI の実効値検証と server の最終検証の両方にあります（`strata_cli/cli.py:770-771`; `serve/server.py:8263-8268`）。
- `--queue-timeout` を併用すると、要求が最初の engine turn を待つ期限が加わります。期限超過は HTTP `429`、コード `queue_wait_timeout` になります。期限は要求開始時に設定され、engine への最初の送信時に解除されます（`serve/server.py:5171-5173,1812-1817,6857-6862`）。ストリーミング中に期限切れとなる場合は SSE の error event と `[DONE]` が送られます（`serve/server.py:7192-7195`）。
- 受付上限は server 起動時に `Service` へ設定される値で、engine の slot 数自体は変更しません（`serve/server.py:3868-3874,8443-8446`）。server の状態 snapshot には `max_queue`、算出 admission limit、現在の予約数、拒否数が含まれます（`serve/server.py:6491-6499`）。
- `--plan` は起動計画を出力して終了し、通常の server 起動処理には進みません（`strata_cli/cli.py:940-942`）。

## 出力とエラー

CLI で範囲外を指定すると `_serve_error` 経由でエラーになります。通常の human 出力ではエラー表示、`--output json` では JSON エラー、`--output jsonl` では `failed` イベントが出力されます。`--output json` は `--plan` と併用する必要があります（`strata_cli/cli.py:829-835,915-925`）。値の整数変換に失敗した場合は argparse の引数エラーになります（parser 定義: `strata_cli/cli.py:55`）。

server 起動後、admission 枠が満杯なら上記の HTTP `429 admission_full` 応答です。`--queue-timeout` による待ち期限切れも別の `429 queue_wait_timeout` 経路です（`serve/server.py:6760-6777,6857-6862`）。

## 根拠

- parser と CLI 検証: `strata_cli/cli.py:46-56,915-942`
- 実効値・profile/config の優先順位と server 引数への転送: `strata_cli/cli.py:745-805`
- profile override の型・範囲: `strata_control/profiles.py:66-79,101-112`
- server parser・優先値・必須条件・Service への設定: `serve/server.py:8165-8168,8259-8268,8439-8446`
- admission 上限、予約・拒否・解放: `serve/server.py:3962-3996,6760-6777,6891-6894`
- 待ち期限と応答経路: `serve/server.py:5171-5173,1812-1817,6857-6862,7192-7195`

調査は上記 revision の checkout 内にある Python CLI と server 実装を対象にしました。別 platform の配布バイナリや Release artifact は照合していません。
