# `strata split-engine apply --config`

調査対象: Strata commit `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata split-engine apply` |
| オプション | `--config` |
| 別名 | なし |
| 値 | 必須の `FILE`。run config JSON ファイルのパス |

## 役割

アプリが起動に使う run config を入力し、この PC で all-cards split engine を使う条件を満たすか判定します。条件を満たした場合は、入力 config をもとに split engine 用 config を組み立てます。`--config` 自体は入力ファイルを読む指定で、変換後の config を保存するには別途 `--out` が必要です（`strata_cli/split_cmd.py:1-5,19-21,35-53`）。

## 使い方

```sh
strata split-engine apply --config /path/to/run-config.json
```

機械可読出力や split 用 config の保存を指定する場合は、同じ `apply` parser の `--output json`、`--out FILE` を併用できます（`strata_cli/split_cmd.py:19-22`）。

## 値と既定値

- `--config` は `required=True` のため省略できません。値は `FILE` として受け取り、CLI 側で追加のパス形式検証や既定値設定はしません（`strata_cli/split_cmd.py:19-20`）。
- パスは現在の作業ディレクトリを基準に解決されます。ファイルは UTF-8（BOM 付きも可）で読み、JSON のトップレベルが object であることを要求します。読み込み失敗、JSON 不正、object 以外は失敗になります（`strata_cli/split_cmd.py:35-40`）。
- 重複指定時の独自処理はありません。argparse の通常の値引数として登録されています（`strata_cli/split_cmd.py:19-20`）。

## 実行時の動作

1. `--config` の JSON object を読み込みます。
2. JSON の encode/decode によって辞書を複製し、その複製を `strata_control.split_engine.apply_run_config` に渡します。判定処理が config を書き換えても入力辞書には反映されません（`strata_cli/split_cmd.py:35-43`）。
3. split engine の採用条件として、Linux、同一ベンダー・同一モデルの複数 GPU、対応アーキテクチャとカード数、モデル形式・メモリ条件などを確認します。run config の `gpu`、`args` 内の `--native` / `--mtp` / `--kv` / `--max-context`、`drafting`、`user_args`、`replicas` なども判定材料です（`strata_control/split_engine.py:190-261,492-530`）。
4. 指定の GPU 構成に対応する `strata-split-N` 実行ファイル、ドラフト層または選択された drafter、および `draft_vocab_en.bin` が見つからない場合は split を採用しません（`strata_control/split_engine.py:536-565`）。
5. 採用時は入力 config を土台に split engine 用の `exe`、`args`、`env`、`split_fallback` などを作ります。通常 engine の config は `split_fallback` に保持されます（`strata_control/split_engine.py:264-288,560-565`）。

split mode は config の `split_engine` を参照し、環境変数 `STRATA_SPLIT_ENGINE` が空でない場合はこちらが優先されます。未指定・未知値は `auto` として扱われます（`strata_control/split_engine.py:395-408`）。未テスト条件を許容する環境変数 `STRATA_SPLIT_ALLOW_UNTESTED=1` も CLI から判定関数へ渡されます（`strata_cli/split_cmd.py:41-43`）。

## 適用条件と副作用

- `--config` で指定したファイルは読むだけです。split 用 config を作る判定処理も複製に対して行われます（`strata_cli/split_cmd.py:35-43`）。
- 判定のため、実行環境の GPU、RAM、モデルファイル、隣接する engine package、およびドラフト関連ファイルの有無を調べます。調査時点のコードでは split engine プログラム自体をこの CLI が起動する処理はありません（`strata_control/split_engine.py:292-296,492-530,536-565,594-613`）。
- split を採用し `--out` も指定された場合に限り、出力先の隣に `<出力名>.tmp` を作成し、JSON を書いてから `os.replace` で出力先へ置き換えます。出力先が既存なら置き換わり、`--out` が入力と同じパスなら入力ファイルが置き換わり得ます。`--out` の親ディレクトリが無い場合などの書き込みエラーは、この処理内で捕捉されません（`strata_cli/split_cmd.py:44-53`）。
- `apply_run_config` 内部で判定中の例外が起きた場合は config を元に戻し、通常の layer split へフォールバックします（`strata_control/split_engine.py:631-656`）。

## 出力とエラー

- `--config` の読み込み・JSON 形式エラーでは、人向け出力なら `strata: The run config could not be read (<例外型名>).` を stderr に出し、終了コード `5` を返します。`--output json` の場合は `schema_version: 1`、`ok: false`、`error.code: split_engine_failed` を含む JSON を stdout に出します（`strata_cli/split_cmd.py:26-40`）。
- 判定が成功した場合は終了コード `0` です。JSON 出力は `split`、`line`、`warn`、`reasons`、`cards`、`written` を含みます。人向け出力は判定行、または通常 layer split を使う旨の行です（`strata_cli/split_cmd.py:54-59`）。
- 自動判定で split を使わない理由が `quiet` 扱いの場合、判定行は空になり、人向け出力は `Using the normal layer split.` になります。明示的な mode `on` などでの非採用理由は `line` として表示されます（`strata_control/split_engine.py:476-489,631-656`; `strata_cli/split_cmd.py:58-59`）。
- `--config` 自体を省略した場合は必須引数の parser エラーです（`strata_cli/split_cmd.py:19-20`）。

## 根拠

- parser 定義と値の必須性: `strata_cli/split_cmd.py:16-22`
- 読み込み、object 検証、複製、split 判定、`--out` 時の書き込み、出力形式と終了コード: `strata_cli/split_cmd.py:25-59`
- split 条件・run config の参照項目: `strata_control/split_engine.py:190-261,395-429,492-565`
- split config の生成内容と通常 config の退避: `strata_control/split_engine.py:264-288`
- 判定失敗時の通常 split へのフォールバック: `strata_control/split_engine.py:631-656`

なお、ここでは同一 revision の CLI を起動して `--help` を確認していません。値と実行挙動は checkout 内の parser 定義と使用箇所から確認しました。
