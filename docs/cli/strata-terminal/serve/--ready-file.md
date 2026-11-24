# `--ready-file`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata serve` |
| オプション | `--ready-file` |
| 別名 | なし |
| 値 | 新規に作る JSON instance record の絶対パス |

## 役割

サーバーの API が bind され、モデル状態が確定した後に、稼働中インスタンスを示す JSON ファイルを作ります。監視プロセスなどが起動完了を知るために使えます。このファイルは稼働証明として単独で信頼するものではなく、利用側は instance ID をライブ telemetry と照合する必要があります。

## 使い方

```sh
# 既存の設定ファイルを使い、起動完了時に新しい instance record を作る
strata serve --profile /path/to/run-config.json --ready-file /tmp/strata-ready.json

# 起動せずにパスを含む有効な起動計画を確認する（ファイルは作らない）
strata serve --profile /path/to/run-config.json --ready-file /tmp/strata-ready.json --plan
```

指定先の親ディレクトリが存在し、ファイルもシンボリックリンクもまだ存在しないパスを指定してください。`--plan` でもこの条件は検証されるため、例のパスを再利用する場合は前回の正常終了でファイルが削除されたことを確認します。

## 値と既定値

値は文字列として受け取り、既定値はありません。Terminal CLI は起動計画を組み立てるときに値を検証します。パスは絶対パスでなければならず、親ディレクトリは既存のディレクトリでなければなりません。指定先が既存ファイルまたはシンボリックリンクなら拒否されます。チェックは `terminal/serve/ready.py:16-24` にあります。空文字列は Terminal CLI の条件分岐で未指定と同じ扱いになり、転送されません（`terminal/strata_cli/cli.py:845-849`）。

## 実行時の動作

Terminal CLI は値を `serve.ready.preflight` に渡し、検証済みのパスを内部サーバーの `--ready-file` 引数に転送します。`--plan` の場合も起動計画にはパスが含まれますが、サーバーを起動しないためファイルは作成されません（`terminal/strata_cli/cli.py:845-865, 979-981`）。

通常起動では、サーバー自身も同じ検証を行います。API bind 後、instance ID、PID、API URL、bind 済み host/port、model ID、モデル状態、API 状態、作成時刻を含む schema version 1 の JSON record を出力します。遅延ロードが有効な場合の `model_state` は `unloaded`、それ以外は `ready` です（`terminal/serve/server.py:9285-9288, 9721-9723, 9752-9767`）。

ファイルは UTF-8 の JSON と改行で書かれ、POSIX では作成モード `0600` を指定し、排他的作成で既存ファイルを上書きしません。書き込み・flush・fsync が行われます（`terminal/serve/ready.py:27-37`）。Windows の ACL の実効設定は、このソース範囲だけでは確認できません。

## 適用条件と副作用

このオプションを省略すれば ready file は作られません。指定時は API が bind された後にファイルを作成します。正常な停止処理では、ファイル内の instance ID と PID が現在のサーバーに一致する場合だけ削除します（`terminal/serve/server.py:9811-9814`、`terminal/serve/ready.py:40-46`）。プロセスが強制終了されるなど停止処理を通らない場合はファイルが残り得るため、再利用前に稼働中インスタンスと照合し、古いファイルだと確認してから手動で除去してください。ファイルは credentials を含まず、PID への操作権限を与えるものでもありません。利用側は instance ID をライブ telemetry と照合する必要があります（`terminal/serve/ready.py:1-6`）。

## 出力とエラー

絶対パスでない、親ディレクトリがない、または対象が既に存在する場合は preflight が拒否します。Terminal CLI では通常のエラー出力経路を通り、JSONL モードでは `failed` event と終了コードを返します（`terminal/strata_cli/cli.py:970-978, 2248-2255`）。内部サーバーを直接起動した場合は argparse のエラーになります（`terminal/serve/server.py:9285-9288`）。

preflight 後のファイル作成に失敗すると、stderr に `[strata] could not write ready file (<例外型>)` を出し、終了コード `6` で終了処理に進みます。書き込み途中の例外では作成したファイルを削除します（`terminal/serve/server.py:9763-9768`、`terminal/serve/ready.py:27-37`）。

## 根拠

- `terminal/strata_cli/cli.py:67-88` — Terminal CLI の `serve` parser と `--ready-file` の登録。引数に型変換や既定値の指定はない。
- `terminal/strata_cli/cli.py:821-865` — launch plan での preflight、内部サーバーへの引き渡し、計画へのパス記録。
- `terminal/strata_cli/cli.py:954-994` — `--plan` ではサーバーを起動せず、通常時に foreground server を開始する分岐。
- `terminal/serve/server.py:9157-9177, 9283-9288` — 内部サーバー側 parser と起動時の再検証。
- `terminal/serve/server.py:9721-9723, 9752-9768, 9811-9814` — API bind 後の record 作成・公開、書き込み失敗、正常停止時の削除。
- `terminal/serve/ready.py:16-46` — パス条件、JSON の排他的作成、POSIX の作成モード、所有インスタンス確認付き削除。
