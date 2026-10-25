# `--api-expect`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune run` |
| オプション | `--api-expect` |
| 別名 | なし |
| 値 | 回答に対して検索する Python 正規表現文字列 |

## 役割

`--mode api` で候補設定を測定するとき、HTTP API が返す回答が期待する内容に合うか確認します。期待式に合わない候補は、速くても正しい測定結果として扱われません。`protocol` モードではこの値は使われません（`strata_cli/cli.py:431-439,1771-1786`）。

## 使い方

```sh
strata tune run --engine ./strata --backend cpu --model my-model \
  --mode api --config ./strata-my-model.json \
  --api-expect '(?i)hash table'
```

`api` モードでは `--config` と空でない `--api-expect` の両方が必要です。期待式はシェルで一つの引数になるよう引用してください。既定のプロンプトは `In one short sentence, what is a hash table?` です（`strata_cli/cli.py:435-439,1771-1784`）。

## 値と既定値

値は argparse の文字列で、既定値は `None` です。parser 自体はパターン構文や空文字列を検証しません。`--mode api` の実行分岐で値の真偽を確認し、未指定または空文字列なら `--mode api needs --api-expect: ...` エラーを返します。この条件を満たす正規表現は Python の `re.search` に渡されます（`strata_cli/cli.py:437-439,1777-1779`; `strata_control/tune_api.py:216-222`）。

検索は大文字小文字を無視し、`.` が改行にも一致するフラグで行われます。`re.search` のため、パターンが回答全体を覆う必要はありません。全体一致が必要なら `^...$` などで利用者が指定します。繰り返し指定時の専用処理はなく、argparse の通常の単一値引数として扱われます（`strata_control/tune_api.py:218-222`; parser は `strata_cli/cli.py:437-439`）。

## 実行時の動作

`--mode api` のとき CLI は `--api-expect` を `make_api_measure` に渡し、その測定関数が HTTP API のストリーム応答を確認します。回答テキスト（`content`）があれば回答に対して、回答が空で推論テキストだけの場合は `reasoning_content` に対して期待式を検索します。どちらもない応答は不一致判定より先に測定エラーになります。期待式に一致しなければ `MeasurementError` となり、その候補の測定値は採用されません（`strata_cli/cli.py:1780-1784`; `strata_control/tune_api.py:193-223`）。

API 測定はベースライン、候補、および最後のベースライン再測定に使われます。不一致・正規表現エラーなど測定 callable の例外はチューナーが候補状態 `UNMEASURED`（エラー文字列に timeout があれば `TIMEOUT`）として記録し、その候補を選定対象から外します。ベースラインが失敗すると比較は行われません（`strata_control/tuning.py:423-476,486-509,591-655`）。

## 適用条件と副作用

このオプションが回答を検査するのは `--mode api` のみです。API モードでは `--config` から worker を起動し、候補ごとの設定は一時 JSON ファイルのコピーとして作られます。測定後に worker を停止し、その一時ファイルを削除します。元の設定ファイルはこの経路では書き換えません（`strata_cli/cli.py:1771-1784`; `strata_control/tune_api.py:263-292`）。

正規表現の構文は事前 validation されません。不正な式は `re.search` 実行時の例外となり、チューナーで測定失敗として記録されます。CLI は通常の事前エラー（API モードで設定または期待値がない場合）には終了コード 2 を返します。一方、候補測定の失敗はジョブ結果に記録され、`strata tune run` の通常の結果出力経路に進みます（`strata_cli/cli.py:1773-1784,1802-1807`; `strata_control/tune_api.py:218-222`; `strata_control/tuning.py:486-509`）。

## 出力とエラー

人間向け出力では API モード開始時にポートと期待値を表示します。`--output json` ではこの進捗表示を行わず、ジョブ結果を JSON で返します。期待不一致の理由は候補の失敗としてレポートに含まれます（`strata_cli/cli.py:1788-1807,1822-1823`; `strata_control/tuning.py:486-509,655-663`）。

## 根拠

- parser、既定値、help 文: `strata_cli/cli.py:431-439`
- API モードでの必須条件と引数転送: `strata_cli/cli.py:1771-1786`
- 応答の選択、正規表現検索、回答不一致: `strata_control/tune_api.py:193-225`
- 候補設定一時ファイル、worker の終了、一時ファイル削除: `strata_control/tune_api.py:259-292`
- 測定例外を候補失敗に記録し、失敗候補を報告する処理: `strata_control/tuning.py:486-509,655-663`
