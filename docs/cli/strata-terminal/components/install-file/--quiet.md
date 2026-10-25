# `--quiet`

調査対象: Strata commit `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。調査対象 checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components install-file` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。省略時は無効 |

## 役割

成功した `install-file` の人向け標準出力を抑えます。エンジン package の検証・導入処理や終了コードは変えません。

## 使い方

```sh
strata components install-file ./strata-engine.zip --quiet
```

## 値と既定値

`argparse` の `action="store_true"` で登録されます。指定すると `quiet=True`、省略すると false 相当です。値を付ける形式ではありません。`--quiet=false` のような指定は受理されず、通常の引数エラーになります。短縮 alias は定義されていません。

この parser では `--quiet` は `update_cmd.py` の `_common()` ではなく、`cli.py` が `update_parsers` を含む one-shot parser 群へ追加します。`install-file` はその parser 群に含まれます。【根拠: `strata_cli/cli.py:508-515`、`strata_cli/update_cmd.py:59-62`】

## 実行時の動作

`main()` は `--quiet` が有効で出力形式が human の場合、コマンド実行中の標準出力を最大 64 KiB の capture に切り替えます。成功時は capture 内容を表示せず、失敗時は内容を標準エラーへ書き戻します。capture が上限を超えた場合は末尾 64 KiB を保持し、省略した旨も標準エラーに出します。【根拠: `strata_cli/cli.py:2196-2214`、`strata_cli/cli.py:2236-2248`】

したがって、human 出力では成功時の進捗表示と最終結果行が抑制されます。失敗時には `update_cmd.py` が標準エラーへ直接出す `strata: ...` のエラーに加え、quiet capture に入っていた標準出力も標準エラーへ戻されます。【根拠: `strata_cli/update_cmd.py:69-86`、`strata_cli/update_cmd.py:178-183`、`strata_cli/update_cmd.py:208-217`】

`--output json` または `--output jsonl`（`--json` は one-shot 用の JSON alias）と併用すると、構造化出力は抑制されません。JSON では最終結果が標準出力に残り、進捗 emitter は出力しません。JSONL では emitter がイベントを標準出力へ出し、最終結果も続けて出力します。`main()` は JSON/JSONL のとき quiet capture を使わず、`_emit_factory()` も JSONL イベントを出力するためです。【根拠: `strata_cli/cli.py:513-515`、`strata_cli/cli.py:2232-2243`、`strata_cli/update_cmd.py:65-86`、`strata_cli/update_cmd.py:208-216`】

## 適用条件と副作用

このオプションの作用範囲は CLI の人向け標準出力です。`install-file` はローカル package を展開し、署名と全ファイルを検証し、対象 PC に適合するか確認してからテスト起動と切替を行います。quiet はこれらの処理やファイル変更を無効化しません。選択した元 package ファイルは残されます。【根拠: `strata_control/updater.py:1088-1091`、`strata_control/updater.py:1092-1129`、`strata_control/updater.py:1130-1148`、`strata_control/updater.py:994-1006`】

人向けモードでは `--quiet` が成功時の進捗や結果を隠すため、完了確認が必要なら終了コードも確認してください。JSON/JSONL の構造化出力は `--quiet` では隠れません。

## 出力とエラー

quiet は失敗を無言にしません。`UpdateError`、署名・feed・acquisition の失敗は `update_cmd.py` が標準エラーへ `strata: ...` として表示し、例外の exit code を返します。割り込みは exit code 130 です。quiet による標準出力 capture がある場合は、失敗時にその内容も標準エラーへ戻されます。【根拠: `strata_cli/update_cmd.py:246-255`、`strata_cli/update_cmd.py:178-183`、`strata_cli/cli.py:2241-2248`】

## 根拠

- parser の共通追加と対象 parser: `strata_cli/cli.py:508-515`、`strata_cli/update_cmd.py:59-62`
- quiet の適用条件・capture・失敗時の再出力: `strata_cli/cli.py:2196-2214`、`strata_cli/cli.py:2217-2248`
- 出力形式と install-file 分岐: `strata_cli/update_cmd.py:65-86`、`strata_cli/update_cmd.py:174-217`
- package 検査、PC 適合判定、導入と切替: `strata_control/updater.py:1088-1148`、`strata_control/updater.py:994-1077`
