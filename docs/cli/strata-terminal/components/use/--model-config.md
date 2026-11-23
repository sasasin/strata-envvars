# `strata components use --model-config`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components use` |
| オプション | `--model-config` |
| 別名 | なし |
| 値 | `RUN_CONFIG.json`。parser 上は任意の文字列 |

## 役割

このコマンドでは `--model-config` の値は受理されますが、エンジン切り替えには使われません。共通 parser が全サブコマンドに追加し、実行時に `Context.run_config` へ渡す一方、`components use` の処理はそのフィールドを参照しません。したがって、このオプションを付けても対象モデルの設定を選んだり、設定ファイルを検査したりはしません（parser 登録: `terminal/strata_cli/update_cmd.py:47-56,84-87`、Context 作成と `use` への分岐: `terminal/strata_cli/update_cmd.py:314-320,337-338`、切り替え処理: `terminal/strata_cli/update_cmd.py:466-472`）。

同じ共通引数は `strata update` の試験起動では利用されます。そちらでは指定値を `Path` にし、設定を読み込む経路がありますが、`components use` は更新処理に進まずエンジン一覧・切り替え処理へ進むため、この用法とは異なります（`terminal/strata_control/updater.py:1342-1358`）。

## 使い方

```sh
# newest を選択する例。RUN_CONFIG.json はこのコマンドでは参照されない。
strata components use newest --model-config RUN_CONFIG.json
```

`engine` 位置引数にはインストール済みエンジンのバージョン、フォルダー名、または `newest` を指定します（`terminal/strata_cli/update_cmd.py:84-87`）。

## 値と既定値

- 値は必須で、`metavar` は `RUN_CONFIG.json` です。型変換、choices、パス検証は parser に設定されていません。省略時の値は `None` です（`terminal/strata_cli/update_cmd.py:47-56`）。
- 指定した値は `Context.run_config` に格納されますが、このコマンド経路では参照されないため、存在しないパスや不正な JSON を指定しても、そのことを理由に拒否されません（`terminal/strata_cli/update_cmd.py:319-320,337-338,466-472`）。
- 値を付けずに `--model-config` だけを指定した場合は argparse の引数解析エラーになります。空文字列を値にした場合も、`use` の切り替え処理では使用されません。

## 実行時の動作

`--model-config` 自体による実行時効果はありません。`use` の処理は、指定されたエンジンを一覧から解決し、当該 PC で実行可能か確認した後、稼働中モデルの終了を待つか拒否し、インストール済みエンジンへ切り替えます（`terminal/strata_cli/update_cmd.py:466-472`、`terminal/strata_control/engine_library.py:211-228`）。選択したエンジンが既に使用中なら変更せず、そうでなければ次回以降に使うエンジン選択を保存します。モデル設定ファイルを読み書きする処理はこの経路にありません（`terminal/strata_control/engine_library.py:277-312`）。

更新処理の試験起動では `Context.run_config` が参照されますが、`components use` 分岐の後にある更新処理には到達しません（`terminal/strata_cli/update_cmd.py:337-338,351-368`、`terminal/strata_control/updater.py:1342-1358`）。

## 適用条件と副作用

`--model-config` のファイル内容・ファイル存在・JSON 形式は `components use` の適用条件ではありません。コマンド本体には別途、選択したエンジンの適合性確認と実切り替えがあります。切り替えはダウンロードや削除をせず、選択を保存します。Qwen 系では選択したエンジンが別の GPU メーカー向けで、同じ PC にその GPU もある場合、次回以降の GPU メーカー選択も保存されます（`terminal/strata_cli/update_cmd.py:469-472`、`terminal/strata_control/engine_library.py:277-293`）。

## 出力とエラー

このオプション固有の検証エラーや警告はありません。コマンド全体では、未インストールまたは曖昧なエンジン名は終了コード 2、実行できないエンジンや再検証に失敗したエンジンは終了コード 5、モデル稼働中の切り替え拒否は終了コード 7 になります。通常出力は人向けメッセージ、`--output json` / `jsonl` では成功・失敗の JSON です（`terminal/strata_control/engine_library.py:184-197,202-207,211-228,296-312`、`terminal/strata_cli/update_cmd.py:307-312,374-378`）。

## 根拠

- parser 登録と既定値: `terminal/strata_cli/update_cmd.py:47-56,84-87`。
- 共通 Context への格納、`components use` の分岐: `terminal/strata_cli/update_cmd.py:314-320,337-338`。
- `use` が対象エンジンを解決して切り替える箇所: `terminal/strata_cli/update_cmd.py:466-472`、`terminal/strata_control/engine_library.py:211-228,277-312`。
- `run_config` を実際に読む更新試験起動経路: `terminal/strata_control/updater.py:1342-1358`。
- 対象コマンドと文書配置の確認: `docs/cli/README.md:229-241`。
