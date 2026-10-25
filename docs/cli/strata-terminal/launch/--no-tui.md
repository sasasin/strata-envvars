# `strata launch --no-tui`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--no-tui` |
| 別名 | なし |
| 値 | 値を取らないフラグ（`argparse` の `store_true`）。省略時は偽 |

## 役割

端末の対話画面（TUI）を開かず、通常の行形式で起動処理を進め、起動後にアドレスなどを表示してコマンドから戻ります。`strata_cli/launch/cmd.py` の parser は `--no-tui` を `store_true` として定義し、説明にも「画面を出さずに serve し、アドレスを表示して戻る」としています（`strata_cli/launch/cmd.py:127-140`）。引数値や独自の validation はありません。

## 適用条件と動作

- `--no-tui` が指定されると、標準入力・出力が端末につながっていても `interactive` が偽になり、TUI 分岐を通らず `Runner` による起動経路へ進みます（`strata_cli/launch/cmd.py:685-716, 780-785`）。TUI が利用できない環境でも通常の行形式へ切り替わる処理があります（`strata_cli/launch/cmd.py:691-696`）。
- `--preset NAME`、`--model NAME`、`--model-path PATH` など起動対象の指定がない状態で `--no-tui` を使うと、選択画面の代替として対象を尋ねることはせず、エラーを返します。人向け出力は標準エラーに `strata:` 付きの案内、終了コードは 2 です。`--output json` 併用時は失敗オブジェクトを JSON で出力します（`strata_cli/launch/cmd.py:634-641, 688-700`）。
- 既存モデルを別の `--data-dir` に移すかどうかの確認を抑止し、既存ファイルはその場に残します。移動するには `--move-data` が必要です。既存モデルの容量と新しい保存先を示す案内が出ます（`strata_cli/launch/cmd.py:504-526`）。
- 起動先ポートですでに異なる設定のサーバーが動作している場合、画面で再起動確認を出せないため、既定では変更せずに失敗します。置き換える意図がある場合は `--restart` を指定します。同じ設定のサーバーは再起動せず、既存アドレスを表示します（parser の説明 `strata_cli/launch/cmd.py:132-135`、Runner の処理 `strata_cli/launch/runner.py:1505-1538`）。
- `--no-tui` は `--yes` とは別です。Runner には `assume_yes` として `--yes`（または JSON 出力）の有無が渡され、エンジン未導入環境でのモデルダウンロード確認などに使われます。したがって `--no-tui` 単独ではすべての確認を無条件に肯定しません（`strata_cli/launch/cmd.py:715-716`、確認箇所 `strata_cli/launch/runner.py:665-670`）。

## 出力・失敗経路

起動が成功すると、画面モードに入らず、サーバー状態と URL、必要に応じて API key のマスク表示、監視・停止方法の案内を行って終了します（`strata_cli/launch/cmd.py:801-831`）。起動処理の `LaunchError` はそのメッセージとコードを使って失敗経路へ送られます（`strata_cli/launch/cmd.py:717-720, 784-787`）。指定対象がない場合の終了コード 2 や、カタログ不在時のコード 5 も同じ `fail` 経由で、人向けでは標準エラー、JSON モードでは構造化 JSON を出力します（`strata_cli/launch/cmd.py:634-641, 679-700, 711-712`）。

TUI 自体の例外を捕捉する `_tui` の「何も起動しなかった」という経路は、TUI 起動時だけの処理です。`--no-tui` ではその経路を通らず、通常の Runner のエラー処理が適用されます（`strata_cli/launch/cmd.py:554-564, 706-716`）。

## 使用例

```sh
strata launch --model iq3_xxs --context 128k --no-tui
strata launch --preset Office --no-tui
```

## 調査範囲

parser と `run_launch` の分岐、データ移動選択、Runner の既存サーバー確認およびエンジン未導入時の確認経路を確認しました。端末 TUI の表示仕様や個々のモデル選択値の validation はこのオプション固有の挙動ではないため、ここでは詳述していません。
