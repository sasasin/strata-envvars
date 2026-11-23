# `--wait`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components engines` |
| オプション | `--wait` |
| 別名 | なし |
| 値 | `SECONDS`。`argparse` の `float` 変換を受ける値 |

## 役割

このコマンドでは `--wait` は parser に受理されますが、実行時に参照されません。エンジン一覧を表示する処理は、稼働中のエンジンが停止するまで待つ処理を行いません。

## 使い方

```sh
strata components engines --wait 30
```

`30` は数値として解析されますが、このコマンドの一覧取得・表示の動作は変わりません。

## 値と既定値

- `--wait` は `type=float`、`metavar="SECONDS"`、既定値 `None` として登録されています。省略時は `None` です。
- 実行コンテキストを作る際には `a.wait or 0.0` が `ctx.wait` に代入されます。ただし `engines` 分岐は `ctx.wait` を読みません。
- この parser 定義には範囲検証がありません。数値に変換できない値は `argparse` の解析エラーになります。変換できた値（負数を含む）が一覧処理に与える効果はありません。

## 実行時の動作

`strata components engines` は `--wait` を含む共通オプション群を登録します。実行時には `list_engines(ctx)` を呼んで結果を人向けまたは JSON で出力し、ここで終了します。この一覧処理は稼働状況を読み取り、インストール済みエンジン情報とともに返しますが、変更・ダウンロードは行いません。`--wait` は稼働状況の取得を待機に変えません。

同じ `--wait` は `components use` などにも共通登録され、それらの処理では待機設定として使われます。この文書の対象である `components engines` ではその経路に入りません。

## 適用条件と副作用

値の有無にかかわらず、このオプションによる追加の待機や状態変更はありません。一覧処理自体は、コンポーネントディレクトリやエンジン情報を読み取り、稼働状況を照会します。インストール内容の変更やネットワーク取得は行いません。

## 出力とエラー

正常な実行では、通常形式または JSON 形式のエンジン一覧が出力されます。`--wait` 自体による待機通知・タイムアウト・稼働中エンジンを理由とした失敗経路はありません。秒数に数値変換できない引数は parser が受理しません。

## 根拠

- `terminal/strata_cli/update_cmd.py:47-56` — 共通 parser における `--wait` の `float` 型・既定値・説明。
- `terminal/strata_cli/update_cmd.py:82-83` — `components engines` が共通 parser を使うこと。
- `terminal/strata_cli/update_cmd.py:303-321` — `a.wait or 0.0` をコンテキストの `wait` に設定する箇所。
- `terminal/strata_cli/update_cmd.py:337-338,445-465` — `engines` コマンドの分岐が一覧処理を呼び、出力後に終了する箇所。
- `terminal/strata_control/engine_library.py:152-167` — 一覧処理が稼働状況を取得して一覧を返すこと、および読み取りのみで変更・ダウンロードしないこと。
- `terminal/strata_cli/update_cmd.py:500-515` — 対話待機を設定する `_maybe_wait`。`engines` 分岐からは呼ばれない。
- `terminal/strata_control/updater.py:381-391` — 実際の待機とタイムアウト判定を行う `wait_until_idle`。`engines` 分岐からは呼ばれない。
