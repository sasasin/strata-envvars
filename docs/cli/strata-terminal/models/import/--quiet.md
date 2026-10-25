# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models import` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らない真偽値フラグ。指定すると有効 |

## 役割

人向けの情報出力を抑制します。このコマンドは既存 GGUF ファイル群を採用せずに調べるプレビューであり、`--quiet` は成功時の人向け結果を標準出力に表示しないために使えます。

## 使い方

```sh
strata models import /models/example.gguf --plan --quiet
```

`PATH` は絶対パスで指定します。`--plan` は必須です。

## 値と既定値

- 値引数や短縮 alias はありません。parser は `store_true` で登録されるため、指定時は真、未指定時は偽として扱われます。
- 同じ one-shot parser 群へ `--quiet` を追加する際、既定値は `argparse.SUPPRESS` です。未指定時に namespace 属性を作らず、実行側では `getattr(a, "quiet", False)` により偽として扱います。
- `--quiet` の複数回指定を拒む検証はありません。`store_true` のため、複数回指定しても有効のままです。

## 実行時の動作

`strata models import` parser も含む one-shot parser 群には、parser 構築後に `--quiet` が共通追加されます。main 処理は `--quiet` が有効で出力形式が human の場合、コマンド処理中の標準出力を一時 capture します。コマンドが成功すれば capture した内容を表示せず、失敗して標準出力に内容があれば標準エラーへ再出力します。

`--output json` と併用した場合は JSON が標準出力へ出ます。main は `json` / `jsonl` 出力を quiet capture の対象外にして `_run` を直接呼ぶため、機械可読出力は抑制されません。

## 適用条件と副作用

- 対象は `strata models import` の parser に適用される `--quiet` です。他のコマンドにある同名オプションの動作はこの文書の対象外です。
- import parser では `--plan` が必須で、実行側は `models.plan_import()` を呼びます。これはローカル候補を調査し、モデルをコピー・採用しない処理です。`--quiet` 自体がファイルを書き換える処理はありません。
- `--quiet` が抑えるのは標準出力だけです。標準エラーへ直接書かれる診断は抑制しません。

## 出力とエラー

- 人向け出力で正常終了した場合、結果の標準出力は表示されません。
- 候補に問題がある場合、import 処理は人向け説明を標準エラーに出して終了コード `5` を返します。JSON 形式では `ok: false` と plan を標準出力に出して同じ終了コード `5` を返します。`--quiet --output json` でも JSON は保持されます。
- 必須の `--plan` がない場合は parser の引数検証で拒否されます。これは quiet 出力処理に入る前のエラーです。
- quiet capture 中にコマンドが失敗し、標準出力へすでに出力があった場合、その内容は標準エラーへ移されます。capture 上限 64 KiB を超えて切り詰められた場合は、標準エラーに省略通知も加わります。
- `PATH` が絶対パスでない、存在しない、GGUF が見つからない等の例外経路もあります。パス解決時の `ValueError` / `OSError` は通常人向けエラーとして標準エラーに出て、quiet によって隠されません。

## 根拠

- `strata_cli/cli.py:157-161` — `models import` parser、位置引数、必須 `--plan`、出力形式。
- `strata_cli/cli.py:508-515` — one-shot parser の集合に `models_import` が含まれ、`--quiet` を `store_true` / `default=argparse.SUPPRESS` で追加。
- `strata_cli/cli.py:550-561` — import の実行、候補問題時の標準エラー/JSON 出力と終了コード `5`、成功時の出力。
- `strata_cli/cli.py:708-723` — 成功時に表示される人向け結果。
- `strata_cli/cli.py:2196-2248` — quiet capture の容量、JSON 出力の除外、成功時の抑制、失敗時の標準エラーへの再出力。
- `strata_control/models.py:579-604` — `plan_import()` の絶対パス・存在・GGUF 検査と失敗条件。
- `strata_control/models.py:720-736` — plan 結果の状態、`would_write: False`、コピー・採用を行わないプレビューである旨。
