# `strata profile show --quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile show` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らないフラグ。省略時は `False`、指定時は `True`。 |

## 役割

成功時の人向け標準出力を抑制します。`profile show` はプロフィール内容を表示するコマンドですが、`--quiet` を付けると成功時の表示を出しません。`--output json` または `--json` の機械可読出力は抑制されません。

## 使い方

```sh
strata profile show default --quiet
```

実効設定も計算する例:

```sh
strata profile show default --effective --quiet
```

## 値と既定値

- 値の引数はありません。`argparse` の `store_true` で定義され、既定値は `argparse.SUPPRESS` です。未指定時に属性が作られない場合も、実行側が `getattr(a, "quiet", False)` として扱うため、実質的な既定値は `False` です。
- 同じフラグを複数回指定しても真偽値のままです。
- `--quiet=true` のような値付き指定や未知の引数は parser に拒否され、通常の argparse usage/error 経路となります。

## 実行時の動作

`--quiet` は `profile show` parser 専用の宣言ではなく、`profile show` を含む one-shot parser 群へ共通に追加されています。この適用範囲は索引上の `strata profile show` のスコープと一致します。

メイン処理は `--quiet` が真で、出力形式が `human` の場合、標準出力を一時バッファへリダイレクトしてコマンドを実行します。終了コードが 0 ならバッファ内容を捨てます。終了コードが非 0 なら捕捉した標準出力を標準エラーへ出し、バッファが 64 KiB を超えて切り詰められた場合は省略を示すメッセージも標準エラーへ出します。

`--output json` を指定すると、`--quiet` があっても JSON は標準出力に出ます。`--json` は `--output json` の別表記として処理され、同じく quiet 抑制を迂回します。なお `profile show` の `--output human` 成功表示も JSON 形式の整形済み payload であるため、quiet が抑制する対象にはこの出力も含まれます。

show は保存済みプロフィールを読み込み、基本情報と revision を返します。`--effective` を付けた場合はさらに launch plan を計算し、参照する run config の読込、override の検証、API key の検査などを行います。`--quiet` 自体はプロフィール内容や plan の計算を変更せず、出力だけを制御します。

## 適用条件と副作用

- `--quiet` は標準出力だけを捕捉します。エラー出力はそのまま見えます。quiet 下でも JSON 出力は無音化されません。
- 成功しても、プロフィール読込時にアクセス権エラーがあり、対象が Strata のユーザーファイルであれば、読み直す前にアクセス権を修復してファイルの権限を変更する場合があります。これは `--quiet` の作用ではなく、プロフィール読込共通の挙動です。
- `--effective` を付けない場合、実効値計算や launch plan 構築には進みません。`--effective` 時は run config などの内容に応じて追加エラーになり得ます。

## 出力とエラー

- `--quiet` + human 出力 + 成功: 標準出力はありません。
- `--quiet` + `--output json` / `--json` + 成功: 通常の成功 JSON を標準出力へ出します。
- プロフィールが見つからない、壊れている、または読めない場合は `_run` の例外処理からエラーになります。存在しないプロフィールは終了コード 5 で、通常は `strata: ...` が標準エラーに出ます。quiet はこのエラーを隠しません。
- 引数解析エラーは quiet の出力捕捉を始める前に発生し、usage とエラーを標準エラーへ出して終了コード 2 となります。

## 根拠

- parser と `--output` / `--effective` の定義: `strata_cli/cli.py:77-80`
- quiet の共通追加と未指定時の扱い: `strata_cli/cli.py:508-515`, `strata_cli/cli.py:2236-2248`
- `--json` の形式切替とquiet回避条件: `strata_cli/cli.py:513-515`, `strata_cli/cli.py:2232-2237`
- profile show の処理、`--effective` 条件、成功表示: `strata_cli/cli.py:958-968`, `strata_cli/cli.py:1015-1020`
- 成功 payload の JSON 表示とエラーの標準エラー出力: `strata_cli/cli.py:527-542`
- プロフィールのファイル読込、通常ファイル確認、1 MiB 上限、未存在時コード: `strata_control/profiles.py:150-166`
- profile name の validation とファイルパス決定: `strata_control/profiles.py:25-55`
- アクセスエラー時の読込再試行・権限修復: `strata_control/private_files.py:476-484`
- effective plan の生成、設定検査、API key 検査: `strata_cli/cli.py:745-792`
- `_run` の ValueError / OSError 等のエラー変換: `strata_cli/cli.py:2119-2193`

調査範囲は上記 commit の Terminal CLI ソースです。別 OS 上での実際の権限修復結果や、個々のプロフィール・run config に依存するエラー内容は実行環境を用いた検証をしていません。
