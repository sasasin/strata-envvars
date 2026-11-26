# `--api-key-env`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--api-key-env` |
| 別名 | なし |
| 値 | 環境変数名 `NAME`（文字列）。名前自体の形式検証はない |

## 役割

API キーをコマンドライン引数へ直接書かず、指定した環境変数から読み込み、起動設定の API キーとして使います。キーの実値をシェル履歴やプロセスの引数一覧に載せたくない場合に使えます。parser は値を `NAME` として受け取り、`os.environ` から値を取得します（`terminal/strata_cli/launch/cmd.py:137-138, 290-294`）。

## 使い方

```sh
strata launch --model q2_0 --access lan --api-key-env STRATA_LAUNCH_KEY --no-tui
```

実行前に `STRATA_LAUNCH_KEY` を環境へ設定してください。`NAME` はキーそのものではなく、キーを格納した環境変数の名前です。例では `--no-tui` を付けて起動後にアドレスを表示して戻ります。

## 値と既定値

- 値を1つ取ります。省略時は argparse の既定値 `None` となり、このオプションによる環境変数の読み込みはありません（`terminal/strata_cli/launch/cmd.py:137-138`）。
- 指定した変数が未設定、または値が空文字列なら `ValueError` になり、起動処理を続けません。変数名と値の前後空白を取り除く処理はありません。そのため空白だけの値は空とは判定されず、そのままキー値になります（`terminal/strata_cli/launch/cmd.py:290-294`）。
- `NAME` が空文字列なら `if a.api_key_env` の条件を通らず、読み込みません。空の名前を有効な変数名として扱う仕様ではありません（`terminal/strata_cli/launch/cmd.py:290-294`）。
- 同じオプションを複数回指定した場合の独自処理はありません。`argparse` の通常の単一値引数として処理されます。

## 実行時の動作

`settings_from_args()` は、まず `--preset` で読み込んだ設定（または新規設定）を基にし、`--api-key` の値を反映した後、`--api-key-env` があればその環境変数の値で `api_key` を設定します。したがって両方を指定すると、環境変数の値が `--api-key` の値に優先します。環境変数が未設定・空なら、先に `--api-key` や preset に値があってもエラーです（`terminal/strata_cli/launch/cmd.py:215-221, 288-294`）。

`--no-api-key` も同時に指定した場合、`--api-key` または `--api-key-env` を使ったことが分かればキーを保持し、「キーが指定されたので保持する」という警告を追加します。キー指定がなければ `--no-api-key` が preset のキーも消して、キーなし設定にします。`--no-api-key` がなければキーがある設定は `no_key` を解除します（`terminal/strata_cli/launch/cmd.py:295-301`）。

設定値は起動用の run config の `api_key` に反映されます。`--save-preset` で保存する場合は launch preset にもキーが入ります。preset の保存関数はユーザー専用ファイルとして書き込み、Unix 系ではモード `0600` を設定します（`terminal/strata_cli/launch/runner.py:724-739`、`terminal/strata_cli/launch/store.py:1-7, 40-60, 76-85`）。キーの設定状況を JSON 出力するときは実値でなく `"set"` と出し、人向けの起動結果ではマスクした値を表示します（`terminal/strata_cli/launch/cmd.py:975-979, 988-990`）。

`--access` が `local` 以外で、キーもキーなし共有の指定もなければ、`strata launch` は既存キーを再利用するか新しいキーを作ります。`--api-key-env` から有効な値を読み込めた場合はキーが設定済みになるため、この自動生成は行われません。変数が空なら自動生成へ進まず、前述のエラーになります（`terminal/strata_cli/launch/cmd.py:290-294, 402-411`）。

## 適用条件と副作用

このオプションは `strata launch` の設定処理で環境変数を読み取ります。サーバーへ渡す設定の `api_key` を指定し、サーバー側では API の認証に使われます（`terminal/strata_cli/launch/runner.py:724-739`、`terminal/serve/server.py:9202-9205`）。`--plan` でも `settings_from_args()` は plan 分岐より前に実行されるため、変数の読み込みと未設定・空値のエラー判定は行われます（`terminal/strata_cli/launch/cmd.py:844, 882-900`）。

環境変数の値は通常の起動設定と同様に run config に書き込まれます。`--save-preset` を使えば preset にも保存されます。環境変数を参照し続けるのではなく、起動時に読み取った値を設定へ取り込みます（`terminal/strata_cli/launch/cmd.py:290-294`、`terminal/strata_cli/launch/runner.py:724-739`、`terminal/strata_cli/launch/store.py:76-85`）。

## 出力とエラー

環境変数が未設定または空の場合、人向け出力では `strata: The environment variable NAME is empty or not set.` を標準エラーへ出し、終了コード `2` になります。`--output json` では同じエラーが JSON の `error.message` として標準出力へ出て、終了コードは `2` です（`terminal/strata_cli/launch/cmd.py:291-294, 759-764, 1009-1012`）。

`--api-key-env` の値 `NAME` 自体を省略すると argparse が引数エラーとして扱います（parser 定義 `terminal/strata_cli/launch/cmd.py:137-138`）。

## 根拠

- parser: [`terminal/strata_cli/launch/cmd.py:130-140`](../../../../../../Niko1221/Strata/terminal/strata_cli/launch/cmd.py) — `strata launch` の共有設定群に定義。
- 値の取り込みとオプション間の優先順位: [`terminal/strata_cli/launch/cmd.py:215-221, 288-301`](../../../../../../Niko1221/Strata/terminal/strata_cli/launch/cmd.py)。
- 共有時のキー自動生成: [`terminal/strata_cli/launch/cmd.py:402-411`](../../../../../../Niko1221/Strata/terminal/strata_cli/launch/cmd.py)。
- 起動設定への反映: [`terminal/strata_cli/launch/runner.py:724-739`](../../../../../../Niko1221/Strata/terminal/strata_cli/launch/runner.py)。
- preset のプライベート保存: [`terminal/strata_cli/launch/store.py:1-7, 40-60, 76-85`](../../../../../../Niko1221/Strata/terminal/strata_cli/launch/store.py)。
- エラーの出力形式と終了コード: [`terminal/strata_cli/launch/cmd.py:759-764, 1009-1012`](../../../../../../Niko1221/Strata/terminal/strata_cli/launch/cmd.py)。
- 索引のスコープ: [`docs/cli/README.md:836-842`](../../README.md)。
