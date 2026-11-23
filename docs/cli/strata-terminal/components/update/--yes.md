# `strata components update --yes`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update` |
| オプション | `--yes` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定時 `True`、省略時 `False` |

## 役割

対話式確認を行わずに更新処理を進めるためのフラグです。署名付き feed からこの PC 用エンジンと Control を更新する通常処理で、対話式確認をスクリプトから回答できない場合などに使います。ただし、稼働中モデルを止める許可にはならず、停止には別途 `--stop-model` が必要です。

## 使い方

```sh
# エンジンと Control を更新し、確認プロンプトを出さない
strata components update --yes

# 稼働中モデルの停止も許可し、更新後に同じ設定で再起動する
strata components update --yes --stop-model --start-again
```

## 値と既定値

値や引数は不要です。`argparse` の `action="store_true"` で登録されており、省略時は偽です。別名、値の validation、数値境界はありません。繰り返し指定しても真偽値の指定として扱われます。登録は `terminal/strata_cli/update_cmd.py:70-79` です。

## 実行時の動作

`strata components update` の `--yes` は、直接の `strata update` と同じ更新処理に渡されます（parser は `terminal/strata_cli/update_cmd.py:70-79`、共通実行先への dispatch は `terminal/strata_cli/cli.py:2210-2212`）。`--yes` が指定されると `_ask_factory` は質問関数を返さず、更新中のモデル停止確認や更新後の再起動確認を対話で尋ねません（`terminal/strata_cli/update_cmd.py:400-410`）。

このフラグ単独ではモデル停止を許可しません。モデルが動作中で、`--stop-model` がない場合、更新は停止前に中断され、exit code 7 で「何も変更していない」旨と再実行方法を出します。停止を明示的に許可するのは `--stop-model` で、停止したモデルを更新後に再起動するにはさらに `--start-again` が必要です。これらは `--yes` とは別に `ModelGate` へ渡され、停止許可と再起動判断に使われます（`terminal/strata_cli/update_cmd.py:414-417`、`terminal/strata_control/engine_update.py:300-323,369-399`）。

## 適用条件と副作用

- エンジン更新が必要なモデルが稼働中でなければ、`--yes` は確認を抑止して通常の更新処理へ進みます。更新処理は feed の読込み後に `update_with_models` を通じて engine と Control の更新を実行し、成功時は結果を表示します（`terminal/strata_cli/update_cmd.py:351-373`）。実際のネットワーク取得・インストールは更新処理側で行われます。
- `--yes` と `--stop-model` を指定してモデルを停止した場合、`--start-again` も指定しない限り、更新後もモデルは停止したままです。更新が失敗した後も、すでに停止したモデルは再起動確認の対象になりますが、確認を抑止している場合は自動再起動されません（`terminal/strata_control/engine_update.py:369-399,405-425`）。
- モデルが Strata の管理下で止められないサービス等によって起動されている場合は、停止許可の指定にかかわらず exit code 7 で拒否されます。更新中に新たにモデルが起動した場合も、その停止が許可されないと更新を中断します（`terminal/strata_control/engine_update.py:301-307,327-345`）。
- `--output json` / `jsonl` も質問を行わない実行経路です。その場合、`--yes` の有無は確認の抑止に追加の違いをもたらしません（`terminal/strata_cli/update_cmd.py:305,400-403`）。

## 出力とエラー

`--yes` 自体は確認メッセージを出しません。通常の人向け出力は `--output human` の既定で、失敗メッセージは stderr の `strata: ...` 形式です。JSON/JSONL 出力時は失敗を JSON にし、エラーコードを含めます（`terminal/strata_cli/update_cmd.py:305-312,369-384`）。稼働中モデルがあり `--stop-model` がないときは exit code 7 で更新しません。モデルを停止した後に再起動できなかった場合は、更新完了でも exit code 8 になり得ます（`terminal/strata_control/engine_update.py:310-317,419-424`）。

## 根拠

- `terminal/strata_cli/update_cmd.py:70-79` — `components update` parser と `--yes`、`--stop-model`、`--start-again` の登録。
- `terminal/strata_cli/cli.py:2210-2212` — `strata components update` を `update_cmd.run` へ渡す dispatch。
- `terminal/strata_cli/update_cmd.py:400-417` — `--yes` による質問関数の抑止と、停止・再起動許可の別々の伝達。
- `terminal/strata_control/engine_update.py:301-323,327-345` — 稼働モデルの停止同意、非対話時の拒否、更新中に起動したモデルの扱い。
- `terminal/strata_control/engine_update.py:369-425` — 停止モデルの再起動条件と再起動失敗時の結果。
- `terminal/strata_cli/update_cmd.py:351-384` — feed 取得・更新処理への進行、失敗時の出力形式と終了コード伝達。
