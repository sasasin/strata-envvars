# `--api-prompt`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune run` |
| オプション | `--api-prompt` |
| 別名 | なし |
| 値 | 文字列（必須値）。parser に型変換や空文字の検証はない |

## 役割

`strata tune run --mode api` が各候補を実際の worker HTTP API で測るときに送信するユーザープロンプトを指定します。候補ごとに worker を起動し、同じ prompt で chat completion を測定します。既定モードの `protocol` はエンジン独自の serve protocol を測るため、このオプションの値は使いません（`strata_cli/cli.py:431-439,1770-1786`、`strata_control/tune_api.py:41-47,275-286`）。

## 使い方

```sh
strata tune run --engine ./strata --backend cuda --model my-model \
  --mode api --config ./strata-my-model.json \
  --api-prompt 'What is a hash table?' \
  --api-expect 'hash table'
```

`--mode api` では `--config` と `--api-expect` が必要です。`--api-prompt` を単独で指定しても mode は切り替わらず、既定の `protocol` モードでは prompt は測定に反映されません（`strata_cli/cli.py:431-442,1770-1784`）。

## 値と既定値

値は argparse の通常の文字列引数です。既定値は `In one short sentence, what is a hash table?` で、短縮別名はありません。parser 定義に空文字や文字数の検証はありません。シェルから空文字を渡した場合も parser は受理し、そのまま API の user message の `content` に設定します（`strata_cli/cli.py:435-436`、`strata_control/tune_api.py:146-159`）。

## 実行時の動作

`_tune_run` は先に tuning plan と workload を作り、`--mode api` のときに `make_api_measure` を生成します。その際 `a.api_prompt` が `prompt` として渡されます。モードが `protocol` なら `tune_engine.make_measure` が選ばれ、`a.api_prompt` は利用されません（`strata_cli/cli.py:1763-1786`）。

API 測定では、prompt を `messages: [{"role":"user","content": ...}]` に含めた JSON を `/v1/chat/completions` に POST します。ストリーミング応答の回答本文（回答本文がない場合は reasoning 出力）を `--api-expect` の正規表現と大文字小文字を区別せず照合します。prompt 自体の長さはこのオプションで制限されませんが、worker/API やモデル側の制約は別途適用されます（`strata_control/tune_api.py:146-159,175-224`）。

この option は `--prompt-tokens` を変更しません。plan の workload と比較 identity は `--prompt-tokens`（既定 512）を使う一方、API モードで実際に送信する本文は `--api-prompt` です（`strata_cli/cli.py:427-428,1763-1770`）。異なる prompt を比較する場合、記録上の workload token 数が送信本文の token 数を表すとは限りません。

API モードでは `--config` が必須です。設定 JSON を読み、候補ごとの engine 引数を反映した一時 JSON を作成し、worker をその設定で起動します。worker は `127.0.0.1` の指定 API port（既定 8123）で `/health` 応答を待ってから測定されます。各候補の測定完了後、worker を終了し一時設定ファイルを削除します。元の設定ファイルは候補測定用に書き換えません。prompt は warm-up と反復測定にも同じ値で使われます（`strata_control/tune_api.py:49-78,80-104,259-293`、`strata_control/tuning.py:486-523`）。

## 適用条件と副作用

- API モードでのみ適用されます。API モードの既定値はなく、`--mode` 自体の既定は `protocol` です（`strata_cli/cli.py:431-439,1770-1786`）。
- API モードで `--config` がなければ終了コード 2 のエラー `--mode api needs --config`、`--api-expect` がなければ終了コード 2 のエラー `--mode api needs --api-expect` を返し、測定を開始しません（`strata_cli/cli.py:1771-1779`）。
- 候補ごとに worker 子プロセスを起動・停止し、一時設定 JSON を作成・削除します。worker のログは `strata-api-harness-*.log` という一時ファイルとして作成されますが、この実装では終了時の削除は確認できません（`strata_control/tune_api.py:80-89,123-135,275-293`）。
- 候補設定の反映や API 測定で候補が失敗すると、tuner は候補を `UNMEASURED`、`TIMEOUT`、または起動段階の `FAIL_BOOT` として記録し、根拠メッセージを最大 400 文字保持します。baseline が測定できない場合、通常の候補探索は進みません（`strata_control/tuning.py:423-482,486-509`）。

## 出力とエラー

人間向け出力では API port と照合に使う expectation が表示されます（`strata_cli/cli.py:1788-1795`）。正規表現に回答が一致しない場合、その候補は測定失敗になり、失敗理由には照合対象テキストの先頭部分が含まれます。失敗候補は推薦対象になりません。HTTP エラー、通信失敗、応答内容なし、reasoning だけで回答なし、usage の `completion_tokens` 欠如も測定エラーです（`strata_control/tune_api.py:205-232`）。候補測定エラーは tuner が捕捉して記録するため、個々の候補失敗はそれだけで CLI 全体の例外終了になるとは限りません（`strata_control/tuning.py:486-523`）。

不正な正規表現や JSON 構文エラーなど、CLI からの候補作成前に発生する全例外の最終表示・終了コードは、このオプションの parser と測定箇所だけからは一律に確定できません。なお parser 自体は prompt の内容を検証しません。

## 根拠

- parser、既定値、同じ `tune run` parser 上の mode と必須条件: `strata_cli/cli.py:414-459,1770-1786`
- plan workload と prompt の受け渡し、API/ protocol の分岐、人間向け表示: `strata_cli/cli.py:1763-1795`
- API リクエスト本文、応答と expectation の検査、測定失敗: `strata_control/tune_api.py:146-224`
- worker と一時候補設定のライフサイクル: `strata_control/tune_api.py:41-47,73-135,259-293`
- 候補測定失敗の job 記録: `strata_control/tuning.py:423-509`
