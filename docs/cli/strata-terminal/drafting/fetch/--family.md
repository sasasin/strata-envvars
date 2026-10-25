# `--family`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata drafting fetch` |
| オプション | `--family` |
| 別名 | なし |
| 値 | family 名（`NAME`）。文字列として受理される。 |

## 役割

モデルの run config がない場合に、DFlash2 drafter の対象モデル family を指定するための値です。`drafting` 共通 parser に置かれており、`strata drafting plan` にも同じ `--family` があります。索引では本書は `fetch` スコープの項目です。値は DFlash2 がそのモデルに対応するかの判定に使われます（`strata_cli/drafting_cmd.py:17-29,40-55`、`strata_control/drafting.py:107-111`）。

## 使い方

```sh
strata drafting fetch --family qwen --if-needed
```

`--family` は `NAME` を1つ受け取ります。`--config` と併用した場合も parser は受理します（`strata_cli/drafting_cmd.py:23-29`）。

## 値と既定値

- `--family` の省略時は `None` です。family の値に `choices`、型変換、専用エラー処理は設定されていません。family は小文字化して `SUPPORTED_FAMILIES` と照合され、現行の対応値は `qwen` と `gyro` です。前後空白の除去は行われません（`strata_cli/drafting_cmd.py:25`、`strata_control/drafting.py:102-111`）。
- 不明な family も parser では拒否されません。判定関数が非対応扱いにします（`strata_control/drafting.py:107-111`）。
- `--family` を省略すると、run config の `model_name` から `Qwen3.8-Flash-Next` とその量子化名・Gyro build に該当するかを判定します（`strata_control/drafting.py:104-111`）。
- `--config` も指定したときは、その config の `model_name` も読み取られますが、`--family` があれば family 判定が優先され、model name による判定へは進みません（`strata_cli/drafting_cmd.py:40-55`、`strata_control/drafting.py:107-111`）。

## 実行時の動作

`--family` は `_inputs()` の戻り値に入り、`drafting.needs_pack()` と `drafting.decide()` に渡されます。`plan` は対象 family かどうかを含む判定内容を表示します。`fetch` は `--if-needed` を指定した場合に限り `needed` が偽なら取得をスキップし、指定しなければ `drafting_fetch.ensure()` を呼びます（`strata_cli/drafting_cmd.py:54-78,87-99`）。

この revision では `ENGINE_SERVES_DFLASH2 = False` です。そのため `needs_pack()` は常に偽となり、`strata drafting fetch --if-needed --family ...` は family にかかわらず取得をスキップして `Nothing to download.`（機械出力時は `skipped: true`）を返します（`strata_control/drafting.py:141-146,179-183`、`strata_cli/drafting_cmd.py:74-79`）。`--if-needed` を付けない `fetch` では family は取得可否を制限せず、`ensure()` が drafter を取得・検査・pack します（`strata_cli/drafting_cmd.py:74-89`、`strata_control/drafting_fetch.py:54-101`）。

config の読み込みに失敗（読み込み I/O error または JSON decode error）した場合は空 config として続行します。family 判定は指定値を使い、データディレクトリは `--data-dir` がなければ Strata の既定値へフォールバックします（`strata_cli/drafting_cmd.py:40-55`）。

## 適用条件と副作用

family による適合判定は DFlash2 の選択・必要判定にだけ関係し、取得処理そのものの条件にはなりません。現在の engine serving 無効状態では `--if-needed` の取得を抑止しますが、無条件の `fetch` はネットワークから固定 revision のファイルを取り込み、hash/size 検査後に pack を生成します。取得元ファイルは pack 後に削除されます（`strata_control/drafting.py:141-146,179-183`、`strata_control/drafting_fetch.py:63-101`）。

## 出力とエラー

- `--if-needed` による skip は人向け出力で `Nothing to download.`、JSON/JSONL 指定では `ok: true` と `skipped: true` を出し、終了コード 0 です（`strata_cli/drafting_cmd.py:74-79`）。
- 取得・pack の `DraftingError` または acquisition 拒否は、人向けでは stderr に `strata: ...`、機械出力では `ok: false` / `drafting_failed` を出し、終了コード 5 です（`strata_cli/drafting_cmd.py:87-94`）。
- 欠落した `--family` 値は argparse の引数エラーになります。一方、未知の値は parser ではエラーにならず、DFlash2 適合判定で非対応となります（`strata_cli/drafting_cmd.py:25`、`strata_control/drafting.py:107-111`）。

## 根拠

- parser と値の受け渡し: `strata_cli/drafting_cmd.py:17-29,40-55`
- plan/fetch の分岐、skip、結果・失敗出力: `strata_cli/drafting_cmd.py:57-99`
- 対応 family、family と model name の優先、DFlash2 有効条件: `strata_control/drafting.py:102-111,141-146,162-183`
- ダウンロード、検査、pack、入力ファイル削除: `strata_control/drafting_fetch.py:54-101`

調査範囲は上記 commit の checkout 内の Terminal CLI と `strata_control` 実装です。別 platform の Release artifact での実行確認は行っていません。
