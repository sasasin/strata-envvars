# `--output`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-24 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile use-config` |
| オプション | `--output` |
| 別名 | なし（`--json` は別に登録された alias） |
| 値 | `human` または `json` |

## 役割

成功・失敗の結果を人間向け、または機械処理向けの形式で stdout に出します。profile の保存や plan の有無を切り替えるオプションではありません。

## 使い方

```sh
# 保存せず切り替え案を JSON で確認する
strata profile use-config four-gpu --from-config /absolute/path/next-model.json --plan --output json

# profile の参照先を更新し、結果を JSON で受け取る
strata profile use-config four-gpu --from-config /absolute/path/next-model.json --output json
```

## 値と既定値

値は `human` と `json` に限られ、省略時は `human` です。別の値や値なしは argparse の引数エラーになります。`--output` は値を格納する通常の引数として登録されており、同じ指定を複数回渡した場合は後の値が使われます（`terminal/strata_cli/cli.py:110-116`）。

このサブコマンドでは `--json` も共通 one-shot option として登録され、`--output json` の alias です。両方を指定して矛盾する値を渡した場合は、parser の引数処理順で最後に指定された値が `output` に残ります（`terminal/strata_cli/cli.py:539-546`）。

## 実行時の動作

`--output json` の場合、成功結果を `schema_version: 1` と `ok: true` を含む JSON オブジェクトとして stdout に出します。plan 成功時は profile 名、revision、変更前後の `source_config`、参照先設定から読んだ `model_name`（存在する場合）、`would_save` を含みます。保存成功時は更新後 profile、前後の revision、変更前後の参照先を含みます（`terminal/strata_cli/cli.py:1008-1024,566-573`）。

`human` の場合、plan は参照先の変更案を、保存時は保存結果と「running instance unchanged」を stdout に出します（`terminal/strata_cli/cli.py:1015-1024`）。表示形式の選択によって `--plan` の保存抑止、`--if-revision` の照合、profile の更新処理は変わりません。

## 適用条件と副作用

`--output` は `profile use-config` に限って登録された出力形式指定です。実際の config 検証、plan 分岐、保存と revision 更新は両形式で共通です。従って、`--plan` なしなら profile の保存と履歴作成が行われ、`--plan` ありなら保存されません。どちらも稼働中 instance を変更しません（`terminal/strata_cli/cli.py:1008-1024`、`terminal/strata_control/profiles.py:270-281,284-313`）。

## 出力とエラー

`--output json` では処理エラーも stdout に JSON で出力し、`schema_version: 1`、`ok: false`、`error.code`、`error.message` を含みます。通常の人間向けエラーは `strata: ...` を stderr に出します。profile 関連の `ValueError` / `ProfileError` は CLI 共通の例外処理を通り、例外に指定された終了コードを返します（`terminal/strata_cli/cli.py:558-563,2248-2255,2266-2270`）。

`--output` に未対応の値を指定した場合はコマンド処理前に argparse が拒否します。実行時には、存在しない・不正な config などのエラーが選択した出力形式で報告されます。config の読み込み失敗はコード `5`、preview 後の profile 変更や `--if-revision` 不一致はコード `6` です（`terminal/strata_control/profiles.py:135-150,270-281,284-313`、`terminal/strata_cli/cli.py:1008-1013`）。

## 根拠

- `terminal/strata_cli/cli.py:110-116` — `profile use-config` parser と `--output` の選択肢・既定値。
- `terminal/strata_cli/cli.py:539-546` — one-shot コマンドに対する `--json` alias の登録。
- `terminal/strata_cli/cli.py:997-1024` — `output` に応じた出力形式、plan・revision 照合・保存の分岐。
- `terminal/strata_cli/cli.py:558-573,2248-2270` — 成功・失敗 JSON と人間向けエラーの出力、終了コード処理。
- `terminal/strata_control/profiles.py:135-150,270-281,284-313` — config 検証、参照先の提案、revision 条件付き保存。

調査範囲は上記 commit の checkout 内の Terminal CLI parser、profile 処理、出力処理です。CLI の実行確認や各 OS の配布バイナリとの照合は行っていません。
