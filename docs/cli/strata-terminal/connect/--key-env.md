# `--key-env`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connect` |
| オプション | `--key-env NAME` |
| 別名 | なし |
| 値 | API key を格納した環境変数の名前。引数は必須。 |

## 役割

`strata connect <app>` がアプリ用の設定を表示・生成するときに使う API key を、環境変数から読み込みます。環境変数名を渡すオプションであり、値そのものをコマンドライン引数に書かずに済みます。たとえば `STRATA_API_KEY` を参照させます。

## 使い方

```sh
# STRATA_API_KEY の値を使って OpenCode 向け設定を表示
strata connect opencode --key-env STRATA_API_KEY

# 読み込んだ key でサーバー到達性と prompt/tool call を確認
strata connect opencode --key-env STRATA_API_KEY --check
```

`--key-env` は `strata connect` のオプションです。`strata launch` の `--api-key-env` とは別の parser・別の用途です。

## 値と既定値

- `NAME` は argparse 上必須の文字列です。省略すると parser の usage error になります（値の型変換や専用の名前形式 validation はありません）。
- 既定値はありません。オプションを省略した場合は、`--key`、実行中 launch または `--preset` の key が候補になります。
- 指定した環境変数が存在しない、または値が空文字列の場合、エラーにはせず次の候補へ進みます。最終的に key が得られない場合も `strata connect` は空 key を target に渡し、設定生成では `strata-local` という placeholder を使います。
- 環境変数名の重複指定は argparse の通常の `store` 動作で最後の指定が残ります。

## 実行時の動作

key の選択順は次の通りです。各候補は truthy な値の場合に採用されるため、空値は次の候補へ進みます。

1. `--key KEY`
2. `--key-env NAME` で参照した環境変数の値
3. `--preset` で選択された preset、または既定では実行中 launch の key
4. 空文字列

この key は `harness.target` に渡され、各 harness が定義する設定ファイルや環境出力で使われます。たとえば OpenCode の設定には key が入り、Codex CLI では `STRATA_API_KEY` の環境設定として出力されます。一方、全 harness が key を設定に使うわけではありません。`--key-env` で指定した環境変数名自体をアプリ設定へ引き継ぐ動作でもありません。key がない場合は、target 用に `strata-local` が使われます。

`--show-key` を付けない通常の人向け表示では、設定中の key はマスクされます。`--output json` でも生成されたファイル内容と文字列フィールドの key はマスク対象です。`--show-key` は人向け表示を実 key に切り替えるため、表示内容の取り扱いに注意してください。

## 適用条件と副作用

- `<app>` を省略した場合、`strata connect` は対応アプリ一覧を表示して終了するため、key の選択や使用は行いません。
- 通常の表示だけでは生成先ファイルを書き換えません。`--write` を付けると、生成した設定ファイルを書き込みます。既存ファイルは先にバックアップされ、JSON merge 対象は既存キーを保ちながら新しい設定で上書きします。key を含む可能性があるファイルには mode `0600` の設定も試みます。
- `--write` は既定で確認を求めます。TTY がない状態では `--yes` なしの書き込みを終了コード 2 で拒否します。`--yes` を指定すると確認を省略します。
- `--check` は選択された key を使って対象 server に prompt と tool call のリクエストを送ります。ネットワーク接続と server の推論を発生させるため、単なる設定表示とは異なります。

## 出力とエラー

- 環境変数が未設定・空でも、そのこと自体ではエラーにならず、後続の key 候補または placeholder が使われます。
- 環境変数名の値が不正な形式だという専用 validation/error はソースにありません。`NAME` の引数自体を省略した場合は argparse がエラーを出します。
- 未知の `<app>` は標準エラーに候補アプリを含むメッセージを出し、終了コード 2 になります。
- `--check` が失敗した場合、人向け出力は失敗内容を表示して終了コード 1、JSON 出力も `ok: false` とエラー情報を返して終了コード 1 になります。確認処理は prompt と tool call の両方を評価します。
- `--write` を非 TTY で `--yes` なしに実行すると標準エラーに案内を出し、終了コード 2 になります。

## 根拠

- `strata_cli/launch/cmd.py:148-165` — `connect` parser と `--key-env` の宣言、`NAME` が必須で既定値・validation 指定がないこと。
- `strata_cli/launch/cmd.py:842-870` — app の要否・未知 app の処理、preset 解決、および `--key` → 環境変数 → launch/preset → 空値の選択順。
- `strata_cli/launch/cmd.py:871-896,897-929` — JSON・人向け出力のマスク、`--check` の実行と失敗時の終了コード。
- `strata_cli/launch/cmd.py:930-948` — `--write` の確認、非 TTY での拒否、設定ファイル書き込み。
- `strata_cli/launch/harness.py:22,253-268` — key がない場合の placeholder、target とアプリ設定の生成。
- `strata_cli/launch/harness.py:209-235` — 各アプリの設定ファイル・環境出力に key を渡す定義。
- `strata_cli/launch/harness.py:275-298,310-311` — ファイルのバックアップ、JSON merge、mode `0600` の試行、表示用マスク。
- `strata_cli/launch/check.py:36-43,111-155` — check リクエストに key を使うことと、接続・HTTP 失敗の説明。
