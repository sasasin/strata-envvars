# `--output`

調査対象: Strata commit `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata split-engine apply` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json`。既定値は `human`。 |

## 役割

`--output` は、split engine を使うかどうかの判定結果を人向けの1行か JSON オブジェクトで出力するかを指定します。判定規則や run config の変換を変更するオプションではありません。

このコマンドは `--config` で指定した run config を読み、現在の環境で split engine 用に適用できるかを調べます。成功時に変換後 config をファイルへ書くには、別途 `--out FILE` が必要です。

## 使い方

```sh
strata split-engine apply --config ./run-config.json --output json
```

`--out` を省略した例なので、判定結果を JSON で表示し、出力ファイルは作りません。

## 値と既定値

- 値は `human` または `json` のみです。argparse の `choices` によって他の値は受け付けられません。
- 省略時は `human` です。
- 短縮別名はありません。複数回指定時の特別な処理はなく、argparse の通常の同一 option の扱いになります。

## 実行時の動作

- `human` の成功時は、判定が返した説明行を出力します。説明行が空の場合は、split を使わないとき `Using the normal layer split.`、使うとき `decision.line` を出します。
- `json` の成功時は、標準出力に1個の JSON object を出します。キーは `schema_version`（`1`）、`ok`（`true`）、`split`、`line`、`warn`、`reasons`、`cards`、`written` です。`written` は変換後 config の出力先で、書き込みがなければ `null` です。
- `--output json` は表示形式だけを切り替えます。設定ファイルの書き込みは、判定が split engine の使用を決め、かつ `--out` が指定されている場合に限られます。入力 config は JSON として読み込まれ、別オブジェクトへ複製して判定・変換されるため、`--config` のファイル自体は変更されません。
- 判定時には Control の `apply_run_config` が呼ばれます。環境、GPU、メモリ、モデル情報、ドラフト層、engine package 等の条件に応じて split engine を適用できるかを決めます。`STRATA_SPLIT_ALLOW_UNTESTED=1` のとき、呼び出し側は未テスト構成を許可する指定も渡します。この環境変数や判定条件は `--output` の値で変わりません。

## 適用条件と副作用

`--output` 自体は読み取り専用の形式指定です。ただし、コマンド全体では config の読み込みと split 判定が行われ、判定に応じてシステム情報・モデルファイル等を確認します。split engine を使う判定になり `--out` も指定された場合、出力先の隣に `.tmp` ファイルを作成して JSON config を書き（作成 mode は `0600`）、`os.replace` で出力先へ置き換えます。従って、既存の `--out` ファイルは置き換えられます。

## 出力とエラー

- 入力 config を読み込めない、またはトップレベル JSON 値が object でない場合、`human` では `strata: ...` を標準エラーへ出し、`json` では `ok: false`、`error.code: "split_engine_failed"` とメッセージを含む JSON を標準出力へ出します。どちらも終了コードは `5` です。詳細な例外文ではなく例外型名をメッセージに含めます。
- 判定が split engine を使わないという結果は通常の成功結果で、終了コードは `0` です。JSON では `ok: true`、`split: false` と理由が返ります。
- 指定値が `human`／`json` 以外なら parser の選択肢検証で拒否されます。
- `--out` への書き込み失敗や `strata_control.split_engine` の import 自体に失敗した場合の専用エラー整形は、このコマンド実装にはありません。これらの経路での表示・終了状態は通常の `fail()` 経路として保証されていません。

## 根拠

- Parser のコマンド階層、必須 `--config`、`--out`、選択肢・既定値: `strata_cli/split_cmd.py:16-22`。
- 表示形式の選択、入力 config の読み込みと object 検証、失敗 JSON／stderr と終了コード: `strata_cli/split_cmd.py:25-40`。
- Control 呼び出し、未テスト許可の環境変数、出力条件、`.tmp` への書き込みと置換、成功出力: `strata_cli/split_cmd.py:41-59`。
- Terminal CLI からの dispatch: `strata_cli/cli.py:2153-2158`。
- `apply_run_config` が返す判定行と警告、通常の拒否時の説明: `strata_control/split_engine.py:631-655`。
- split 判定が環境・カード・モデル・メモリ等を確認し、通過時に config を変換する処理: `strata_control/split_engine.py:500-565`。
- 索引上の配置とコマンド scope: `docs/cli/README.md:1237-1244`（索引は本調査対象外として変更していません）。

