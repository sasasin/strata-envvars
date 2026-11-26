# `--key-env`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connect` |
| オプション | `--key-env` |
| 別名 | なし |
| 値 | `NAME`。API キーを格納した環境変数の名前 |

## 役割

`strata connect <app>` がアプリ用の設定を表示・生成するとき、API キーを環境変数から取得する。指定した環境変数の値そのものがキーとして使われ、変数名をアプリ設定へ渡すものではない。アプリごとの設定や環境変数を組み立てるため、キーが実際に必要なアプリでは `--write` で設定ファイルを保存する前に利用できる。

## 使い方

```sh
# STRATA_API_KEY の値を使って Codex CLI 用設定を表示する
strata connect codex --key-env STRATA_API_KEY
```

## 値と既定値

- `NAME` は値を取る位置引数ではなく、`--key-env` に続ける1つの文字列である。省略時の既定値はなく、環境変数も自動では参照しない（`terminal/strata_cli/launch/cmd.py:168-182`）。
- 指定した環境変数が存在しないか値が空文字列の場合、専用エラーにはならず、次の候補へ進む。空白だけの値を除外する検証はこの箇所にはない（同 `:1074-1079`）。
- 有効なキーの選択順は `--key` の非空値、`--key-env NAME` の非空な環境変数値、選択された preset または起動中 launch のキー、最後に空文字列である。最後の空文字列は harness 用 placeholder `strata-local` に変換される（同 `:1076-1079`、`terminal/strata_cli/launch/harness.py:21,339-340`）。
- `--key-env` を複数回指定した場合の特別な処理はなく、`argparse` の通常の `store` 引数として最後に解析された値が残る（`terminal/strata_cli/launch/cmd.py:171`）。

## 実行時の動作

`strata connect` は `--preset` があればその名前に一致する起動中 launch と保存済み preset を、なければ最初の起動中 launch を既定情報として調べる。そこから URL・キー・モデル・context を取得し、明示値があればそれらを優先する。`--key-env` の値は `os.environ.get(NAME)` で読み、上記の優先順で採用する（`terminal/strata_cli/launch/cmd.py:703-725,1074-1080`）。

選ばれたキーは harness の `Target` に入り、各アプリの設定ファイルや案内用環境変数の内容に使われる。たとえば Codex 用の設定は `STRATA_API_KEY` を参照する形式で、別に同名環境変数値を案内する（`terminal/strata_cli/launch/harness.py:144-149,286-292`）。このため `--key-env` は環境変数名を保存する指定ではなく、読み出した実値を設定生成に使う指定である。

人向け出力では、既定で設定内容中のキーをマスクし、キーが設定に含まれる場合は `--show-key` で実値を表示できる（`terminal/strata_cli/launch/cmd.py:1081,1123-1136`）。JSON 出力は設定ファイル文字列をマスクして返す（同 `:1082-1086`）。`--check` はこのキーで prompt と tool call をサーバーへ送り、いずれかが失敗すれば終了コード `1` となる（同 `:1087-1107,1147-1155`）。

## 適用条件と副作用

- `--key-env` 自体は環境変数の存在やキー形式を検証しない。指定変数が未設定・空なら preset / 起動中 launch のキー、それもなければ placeholder が使われるため、意図したサーバー認証に使えるキーになっているかは実行環境と選択元に依存する（`terminal/strata_cli/launch/cmd.py:1074-1079`、`terminal/strata_cli/launch/harness.py:21,339-340`）。
- `--write` を付けると生成設定にキーが含まれる場合がある。既存ファイルは通常バックアップ後に置換され、JSON の merge 対象は既存キーを保ちつつ生成値を優先する。書込後は権限を `0600` に設定しようとするが、権限変更の失敗は無視される（`terminal/strata_cli/launch/cmd.py:1019-1050`、`terminal/strata_cli/launch/harness.py:355-399`）。
- 書込み前の確認を省略するには `--yes` が必要で、非対話環境で `--yes` も `--dry-run` もない場合は終了コード `2`。`--dry-run` はファイル変更を行わず予定を報告する（`terminal/strata_cli/launch/cmd.py:1022-1038`、`terminal/strata_cli/launch/harness.py:355-360,387-399`）。
- JSON モードでは `--show-key` の有無にかかわらず生成テキストはマスクされる（`terminal/strata_cli/launch/cmd.py:1081-1086`）。

## 出力とエラー

- `--key-env` の引数値がない場合は parser が引数エラーとして扱う。`connect` に未知オプションを渡した場合は stderr に候補付きメッセージを出し、終了コード `2`（`terminal/strata_cli/launch/cmd.py:186-198`、`terminal/strata_cli/cli.py:2325-2334`）。
- 環境変数の未設定・空値そのものはエラー出力にならず、上記の候補へフォールバックする（`terminal/strata_cli/launch/cmd.py:1074-1079`）。
- `--write` 中にファイル書込みで `OSError` が起きると、失敗したファイルと後続の未書込みファイルを報告し、終了コード `1`。`--check` の失敗も終了コード `1` で、JSON 出力ではエラー情報を含む（同 `:1039-1050,1097-1118`）。

## 根拠

- `terminal/strata_cli/launch/cmd.py:163-182` — `connect` parser と `--key-env NAME` の定義、周辺オプション。
- `terminal/strata_cli/launch/cmd.py:703-725` — preset / 起動中 launch のキーなど既定情報を解決する処理。
- `terminal/strata_cli/launch/cmd.py:1052-1086` — app 名の解決、キーの優先順位、harness 設定への入力と JSON マスキング。
- `terminal/strata_cli/launch/cmd.py:1019-1050,1087-1119,1120-1155` — 書込み・確認・人向け出力と終了経路。
- `terminal/strata_cli/launch/harness.py:21,144-163,286-315,339-399,432-433` — placeholder、アプリ別のキー利用、設定の生成・保存・マスキング。
- `terminal/strata_cli/cli.py:2235-2237,2248-2265,2325-2334` — connect の実行先と共通エラー処理。

調査範囲は現行 checkout の parser と Strata 所有 Python 実装である。個々の外部アプリが生成された設定・環境変数をどう読み込むか、また環境変数値の妥当性をサーバーがどう検証するかは、このオプション文書のソース範囲からは確認していない。
