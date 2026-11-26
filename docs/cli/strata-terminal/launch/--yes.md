# `--yes`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--yes` |
| 別名 | なし |
| 値 | なし。`argparse` の `store_true`。既定値は `False`。 |

## 役割

`strata launch` の実行中に確認を求められる一部の選択を、肯定扱いにするフラグです。モデル用エンジンがこの PC にまだなく、モデルをダウンロードする前の確認を省略する用途があります。すべての確認を無条件に承認するフラグではありません。特に、既に別設定で稼働中のモデルを停止・置換する許可にはならず、モデルファイルを新しいデータフォルダーへ移す指定にもなりません。

## 使い方

```sh
# モデルを指定して起動し、確認入力を省略する
strata launch --family qwen --model q2_0 --yes --no-tui
```

## 値と既定値

値を取りません。別名はありません。指定しなければ `False` です。値の範囲や重複値の検証はありません。オプションは `strata launch` に登録されています。`strata connect --yes` は別のサブコマンドに属し、ここで扱う起動オプションとは別スコープです。

## 実行時の動作

- `run_launch` は通常の `Runner` に `assume_yes=bool(a.yes or machine)` を渡します。したがって `--yes` を指定した場合と `--output json` の機械出力の場合、Runner のこの確認フラグが有効になります。
- 対応する実行経路では、モデル用エンジンがなく、モデルのダウンロードが発生する場合の確認を省略します。`--yes` なしで確認を拒否すると「Stopped. Nothing was downloaded.」を出し、終了コード `130` で返します。
- モデルに必要な新しいエンジンが既存環境で不足している場合、確認なしでエンジン更新へ進める分岐にも使われます。ただし、該当エンジンでモデルが稼働中なら、`--yes` の有無にかかわらず更新を見送る警告経路です。
- `--data-dir` と併用しても、既存モデルの移動は承認しません。移動しない選択となり、移動するには `--move-data` が必要です。
- `--plan` は計画表示のままです。実際の起動・ダウンロードは行わず、計画経路では `--yes` も既存モデルの移動を選びません。
- 端末入出力が TTY で、`--no-tui` と `--plan` を指定せず、モデルなどの選択肢を渡すと、画面モードの自動実行へ進みます。この経路は `run_tui` に `--yes` を引き渡さず、画面側のダウンロード確認や再起動確認を表示し得ます。そのため `--yes` が確認入力を省く挙動は、すべての対話モードに共通ではありません。自動化で画面を使わない例では `--no-tui` を併用してください。

## 適用条件と副作用

- `--yes` 単独では、異なる設定で同じポートを使う稼働中モデルや、同じ起動プロファイルの既存モデルを置き換えません。画面モードでは再起動確認が表示され、画面なしの経路では `--restart` を付けるか先に `strata launch --stop` を実行するよう案内して失敗します。同じ設定が既に稼働中なら再起動せず、その URL を返します。
- `--yes` によりダウンロード確認を省いた経路では、モデルなどの取得が始まり得ます。ダウンロード量はモデルにより大きく異なります。
- `--output json` も Runner 内では `assume_yes` を有効にしますが、これは出力形式に伴う実装上の挙動です。

## 出力とエラー

画面なしの起動で、異なる設定のモデルが既に稼働中の場合、`--yes` のみでは置換せず、エラーを標準エラーへ出して終了コード `6` を返します。`--restart` を指定したときだけ置換処理へ進みます。モデルのダウンロードを確認時に拒否した場合は終了コード `130` です。JSON 出力では `run_launch` の失敗を `ok: false` と `error` を含む JSON として標準出力へ出します。

## 根拠

- `terminal/strata_cli/launch/cmd.py:73-80` — `strata launch` の parser 登録とコマンド説明。
- `terminal/strata_cli/launch/cmd.py:141-152` — `--yes` を「running」グループに値なしの `store_true` として登録。
- `terminal/strata_cli/launch/cmd.py:600-622` — `--yes` では既存モデルを `--data-dir` へ移動せず、移動確認も省く分岐。
- `terminal/strata_cli/launch/cmd.py:849-877` — TTY・`--no-tui`・`--plan` による実行経路判定と Runner への `assume_yes` 転送。
- `terminal/strata_cli/launch/cmd.py:945-961` — 選択肢付き TTY 実行が TUI の自動実行へ分岐し、Runner エラーを終了コード付きで返す箇所。
- `terminal/strata_cli/launch/cmd.py:753-764, 897-925` — JSON 失敗出力、および `--plan` が変更なしの計画を表示する箇所。
- `terminal/strata_cli/launch/runner.py:974-986` — Runner の `assume_yes` と `restart` が別々の状態であること。
- `terminal/strata_cli/launch/runner.py:1171-1188` — 古いエンジンの更新確認を省略する条件。稼働中モデルがある場合は更新しない。
- `terminal/strata_cli/launch/runner.py:1271-1287` — エンジン未導入時のダウンロード確認、省略条件、拒否時のメッセージと終了コード。
- `terminal/strata_cli/launch/runner.py:2562-2588` — 同一設定なら再起動せず、異なる設定の置換には `--restart` または TUI の確認を要求する処理。
- `terminal/strata_cli/launch/app.py:498-535, 563-584, 693-712` — TUI の Runner が確認画面を使用し、`run_tui` の引数に `yes` がないこと。
