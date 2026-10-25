# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定時に有効 |

## 役割

成功したときの人向け標準出力を抑制します。更新処理や進捗イベント自体を止めるオプションではありません。

## 使い方

```sh
python strata.py components update --quiet
```

ソース checkout のルートから実行する例です。配布済み `strata` を使う場合は同じ引数を `strata components update --quiet` として指定します。

## 値と既定値

値は不要です。`store_true` として登録され、既定では属性自体が namespace に追加されず、指定すると真になります。したがって、通常の人向け出力が既定です。引数位置・型・範囲の追加 validation はありません。

## 実行時の動作

`strata_cli/cli.py` は `update_cmd.add_parsers` でサブコマンド parser を登録した後、one-shot parser 群に `--json` と `--quiet` を追加します。この配列には `update_parsers` が含まれるため、`strata components update` でも受理されます。フラグは `argparse.SUPPRESS` を既定値として追加され、未指定時の namespace を変えません（`strata_cli/cli.py:139-140,508-516`）。

`main` は `--quiet` が有効で、`--output` が `human` の場合、標準出力を最大 64 KiB のバッファに捕捉してコマンドを実行します。終了コードが 0 なら捕捉した出力を表示しません。非 0 なら捕捉内容を標準エラーへ出し、64 KiB を超えて切り詰めた場合は省略を示す行も標準エラーへ出します（`strata_cli/cli.py:2196-2214,2232-2248`）。

更新処理の開始行、進捗表示、終了時の feed・各コンポーネント結果は標準出力に書かれるため、人向けモードでの成功時は抑制されます（`strata_cli/update_cmd.py:62-84,211-224`）。`--check` の人向けレポートも標準出力なので、成功時は同様に抑制されます（`strata_cli/update_cmd.py:203-209,132-160`）。

## 適用条件と副作用

このフラグは表示経路だけを変えます。feed の読込、署名済み更新の検証、engine/Control の更新、`--app` が指定された場合の app installer 取得は、それぞれ通常どおり実行されます（`strata_cli/update_cmd.py:197-224`; `strata_control/updater.py:1274-1297`）。既存 engine の稼働時に対する `--wait` 判定も別処理のままです（`strata_cli/update_cmd.py:210,237-251`）。

`--output json` または `--output jsonl` を指定すると `main` は quiet 捕捉を使わず、機械可読出力をそのまま出します。one-shot コマンド用の `--json` は `--output json` に変換されるため、これも quiet より優先して出力されます（`strata_cli/cli.py:512-515,2232-2237`; `strata_cli/update_cmd.py:62-71,203-220`）。

## 出力とエラー

更新時の例外（feed、署名、取得拒否など）は `update_cmd.run` が人向けなら標準エラーへ直接書き、対応する非 0 終了コードを返します。この標準エラー出力は `main` の標準出力捕捉の対象外です（`strata_cli/update_cmd.py:163-172,225-234`; `strata_cli/cli.py:2241-2248`）。個別コンポーネントの失敗は結果に記録され、最後の人向け結果行は標準出力に出た後、非 0 終了時には quiet 捕捉から標準エラーへ移されます（`strata_control/updater.py:1274-1297`; `strata_cli/update_cmd.py:217-224`）。

## 根拠

- parser の登録と quiet の追加: `strata_cli/cli.py:139-140,508-516`
- quiet 捕捉と終了時の出力先: `strata_cli/cli.py:2196-2214,2232-2248`
- 更新コマンドの標準出力・エラー処理: `strata_cli/update_cmd.py:62-84,163-234`
- 更新結果と終了コードの集約: `strata_control/updater.py:1274-1297`
- 調査対象 revision と索引上の位置: `docs/cli/README.md:5,242-260`

調査は上記 commit の Terminal CLI ソースと同 checkout の `python strata.py components update --help` に限ります。Release archive ごとの挙動差は確認していません。
