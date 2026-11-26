# `strata connect --key`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connect <app>` |
| オプション | `--key` |
| 別名 | なし |
| 値 | `KEY` を1つ取る文字列。parser 上の型・選択肢・形式検証はない |

## 役割

接続先アプリ用の設定を表示、検査、または書き出すときに、Strata サーバーの API key を明示します。値は `--key-env`、`--preset` から得た起動情報、既定の空値より優先され、アプリ設定の認証値および `--check` のリクエストに使われます。

## 使い方

```sh
# 環境変数にある鍵で OpenCode 用設定を表示（鍵は通常マスクされる）
strata connect opencode --key "$STRATA_API_KEY"

# 環境変数名を渡して、同じく OpenCode 用設定を表示
strata connect opencode --key-env STRATA_API_KEY

# 明示した鍵でサーバー接続を確認
strata connect opencode --key-env STRATA_API_KEY --check
```

## 値と既定値

- `--key KEY` は通常の文字列引数です。parser に型変換、空でないことの検査、形式検証はありません。値を省略すると argparse の引数エラーになります。`--key` を複数回指定した場合は、通常の `store` 動作で最後の値が残ります（登録箇所: `terminal/strata_cli/launch/cmd.py:170`）。
- 実行時は値の truthiness で選ぶため、空文字は明示値として採用されず、後順位へ進みます。明示値、`--key-env` で指定した環境変数の値、起動中の launch または `--preset` の鍵、空文字の順です。環境変数が未設定または空でもエラーにはせず、後順位に進みます（`terminal/strata_cli/launch/cmd.py:1074-1079`）。
- 最終的な鍵が空なら、アプリ設定生成用の `Target` では `strata-local` に置き換えられます。これは Strata のテスト済み設定で、サーバーに鍵が設定されていない場合の placeholder です（`terminal/strata_cli/launch/harness.py:21`, `339-340`）。
- `--key` 自体に鍵の長さ・文字種・サーバーとの一致を検証する処理はありません。

## 実行時の動作

`strata connect` の parser は `--key KEY` を登録し、`run_connect` が上記の優先順位で鍵を決めて harness の `Target` に渡します。harness ごとのレンダラーはこの値を設定ファイルや環境設定へ埋め込みます。たとえば OpenCode の `providers.strata.settings.apiKey` と Cline の `openAiApiKey` に入り、Codex 用設定では環境変数名 `STRATA_API_KEY` が指定されます（`terminal/strata_cli/launch/cmd.py:163-182, 1074-1080`; `terminal/strata_cli/launch/harness.py:119-125, 144-155, 286-297`）。

鍵は既定で人間向け表示からマスクされます。`--show-key` を付けると人間向けの設定表示では実値が出ます。JSON 出力では値がマスクされ、`--show-key` でも解除されません（`terminal/strata_cli/launch/cmd.py:1081-1086, 1120-1136`）。

`--check` を併用すると、同じ鍵でアプリ形式の prompt と tool call をサーバーへ送り、認証を含む接続設定を確認します。`--write` と併用した場合、check が失敗すると書き込みは行われず終了コード 1 です。`--write` 単独の確認・バックアップ・ファイル更新条件は同コマンドの別オプションによります（`terminal/strata_cli/launch/cmd.py:1087-1107, 1147-1157`; `terminal/strata_cli/launch/check.py:1-7, 36-43`）。

## 適用条件と副作用

- `<app>` を指定した場合に適用されます。アプリ名が認識されない場合は候補を含むエラーを stderr に出し、終了コード 2 で終了します。アプリ名を省略した一覧モードでは鍵を使いません（`terminal/strata_cli/launch/cmd.py:1052-1073`）。
- 鍵は生成設定の表示内容に含まれるため、人間向け出力で `--show-key` を付けると秘密値が端末出力へ露出します。通常はマスクされます。JSON でも鍵はマスクされます（`terminal/strata_cli/launch/cmd.py:1081-1086, 1120-1136`）。
- `--write` を使うと、確認後にファイルを作成または更新します。既存ファイルは先にタイムスタンプ付き `.strata-bak-...` へコピーされ、書き込みファイルは可能なら mode `0600` に設定されます。これは鍵を含み得る設定ファイルへの副作用であり、`--dry-run` では書き込みません（`terminal/strata_cli/launch/cmd.py:1019-1050`; `terminal/strata_cli/launch/harness.py:355-399`）。

## 出力とエラー

- 解析対象外のオプションは `strata connect` の案内付きで stderr に出て、終了コード 2 になります（`terminal/strata_cli/cli.py:2325-2334`; `terminal/strata_cli/launch/cmd.py:186-201`）。
- `--check` の疎通または prompt/tool call が失敗した場合は終了コード 1 です。`--write` も指定していた場合、check 失敗時点でファイルは書き込まれません（`terminal/strata_cli/launch/cmd.py:1087-1107, 1147-1155`）。
- `--write` は対話端末で確認を求めます。非対話環境で `--yes` も `--dry-run` もない場合はエラーと終了コード 2、確認への否定応答では書かずに終了コード 0 です。書き込み中の `OSError` は人間向け出力または JSON に失敗内容を記録し、終了コード 1 になります（`terminal/strata_cli/launch/cmd.py:1019-1050`）。

## 根拠

- `terminal/strata_cli/launch/cmd.py:163-182` — `connect` parser と `--key`、鍵関連オプションの登録。
- `terminal/strata_cli/launch/cmd.py:703-725, 1052-1086` — 起動情報・preset の取得、URL等と鍵の優先順位、harness への渡し、表示時のマスク。
- `terminal/strata_cli/launch/harness.py:21, 119-125, 144-155, 286-347` — placeholder、各アプリ設定への鍵の埋め込み、対象の構築。
- `terminal/strata_cli/launch/cmd.py:1019-1050, 1087-1107, 1120-1157` — 確認・書き込み・check の失敗経路と出力。
- `terminal/strata_cli/launch/harness.py:355-399` — 設定ファイルの dry-run、バックアップ、書き込み、権限設定。
- `terminal/strata_cli/launch/check.py:1-7, 36-43` — check が鍵を Authorization と `x-api-key` header に付ける処理。
