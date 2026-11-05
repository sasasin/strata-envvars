# `strata split-engine apply --out`

調査対象: Strata commit `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 調査時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata split-engine apply` |
| オプション | `--out` |
| 別名 | なし |
| 値 | `FILE`。出力ファイルのパス。parser は追加の形式・存在確認をしない |

## 役割

split engine を使う判定になった場合に、変換後の run config を指定先へ書き出します。必須オプションではありません。`--config` で読み込んだ設定を元に判定し、split engine 用に変換したコピーを出力するため、入力 config は書き換えません（`strata_cli/split_cmd.py:19-21,35-53`）。

## 使い方

```sh
strata split-engine apply --config ./run-config.json --out ./split-run-config.json
```

出力先には、置換されても問題のない新しいパスを指定してください。既にあるファイルも置換対象です。

## 値と既定値

- `--out FILE` は値を1つ取ります。省略時の既定値は `None` で、判定が split engine 使用可でもファイルは書きません（`strata_cli/split_cmd.py:20-22,44-53`）。
- parser にパス形式・親ディレクトリの存在・出力先の新規性を検証する処理はありません。パスは `Path(a.out)` として扱われます（`strata_cli/split_cmd.py:45-48`）。
- 同じ `--out` を複数回指定した場合、`argparse` の通常動作で最後の値が使われます。空文字列は parser では拒否されませんが、実行時の真偽判定で出力処理を行いません（`strata_cli/split_cmd.py:21,45`）。

## 実行時の動作

1. `--config` の JSON を読み込み、JSON object であることを確認します。内容を JSON round-trip したコピーに対して `apply_run_config` を呼びます（`strata_cli/split_cmd.py:35-43`）。
2. `--out` があり、かつ判定結果 `decision.use_split` が真の場合だけ、コピーを整形 JSON として `<FILE>.tmp` に書き、`os.replace` で `<FILE>` に置き換えます。テンポラリファイルは作成時 mode `0600`、同名の既存テンポラリは truncate されます。出力先に既存ファイルがある場合も `os.replace` が置換します（`strata_cli/split_cmd.py:44-53`）。
3. 判定が不可なら `--out` を指定しても出力しません。split engine の適用条件には Linux、2〜4枚の同一メーカー・同一モデル/VRAMのカード、対応モデルとメモリ、コンテキスト長などがあり、満たさない場合は通常の layer split とする判定になります（`strata_control/split_engine.py:190-261`）。実機情報・RAM・GGUF を読み取って判定し、GGUF 読み取り失敗も「使わない」判定にします（同 `:492-535`）。
4. `STRATA_SPLIT_ALLOW_UNTESTED=1` は未テスト条件の許容判定に渡されます（`strata_cli/split_cmd.py:41-43`、`strata_control/split_engine.py:190-233`）。この変数は `--out` のファイル操作には直接作用しません。

## 適用条件と副作用

- `--out` 自体は判定を split engine 側へ変えません。判定が true のときだけ出力先を作成または置換します。判定が false のときはそのパスに触れません（`strata_cli/split_cmd.py:43-53`）。
- 出力先の親ディレクトリは自動作成されません。書き込み中の失敗では一時ファイルが残る可能性があります。入力 config は読み込み後のコピーを変換するため、入力パスへの書き戻しはありません（同 `:35-52`）。
- split engine 判定は run config の `split_engine` 設定と `STRATA_SPLIT_ENGINE` も参照します。環境変数が設定されている場合は config 値より優先されます（`strata_control/split_engine.py:395-408`）。

## 出力とエラー

- 人間向け出力（既定）では、適用可否の説明を stdout に1行出します。JSON 出力 (`--output json`) では stdout に `split`、判定理由、カード数、`written`（書き込みなしなら `null`）などを含む JSON を出します（`strata_cli/split_cmd.py:22,54-59`）。
- config が読めない、JSON が不正、またはトップレベルが object でない場合は終了コード `5`。人間向けでは stderr に `strata: ...`、JSON 出力では `split_engine_failed` を含むエラー JSON を出します（同 `:28-40`）。
- 出力先への OS ファイル操作が失敗した場合、上位 CLI が通常の OS エラーとして処理し終了コード `6` を返します。人間向けは stderr、JSON 出力時は JSON エラーです（`strata_cli/cli.py:2178-2195,529-534`）。parser の引数不足・未知引数は argparse が拒否し、終了コード `2` で usage/error を表示します（同 `:2250-2259`）。

## 根拠

- parser と必須性・既定値: `strata_cli/split_cmd.py:16-22`
- config 読み込み、コピー、判定、出力書き込み・置換、結果表示: `strata_cli/split_cmd.py:25-59`
- CLI からの dispatch と例外の終了コード: `strata_cli/cli.py:174-175,2156-2158,2178-2195`
- split engine の mode 優先順位: `strata_control/split_engine.py:395-408`
- 判定条件、未テスト条件、適用変換: `strata_control/split_engine.py:190-261,492-565,631-656`
