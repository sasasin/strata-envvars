# `--config`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata drafting fetch` |
| オプション | `--config` |
| 別名 | なし |
| 値 | `FILE`。run config のファイルパス。必須指定ではない |

## 役割

run config を読み、モデルのデータフォルダーと drafting の選択を参照します。`fetch --if-needed` では、選択したモデルに DFlash2 pack が必要かを判定する入力にもなります。通常の `fetch`（`--if-needed` なし）では、config のモデル名や drafting 設定によってダウンロード自体を制限せず、config からデータフォルダーを選ぶ用途です。

## 使い方

```sh
strata drafting fetch --config strata-qwen.json --if-needed
```

`--config` は `strata drafting plan` にも登録されています。同じデータフォルダーとモデル情報を使った取得計画を確認できます。

## 値と既定値

- parser は `--config FILE` を値一つを取る文字列引数として登録します。指定省略時は `None` です。ファイル存在、JSON の object 形式、run config の schema は parser では検証しません（`strata_cli/drafting_cmd.py:22-29`）。
- 指定時は UTF-8-SIG として読み、`json.loads` で解析します。ファイルを読めない場合または JSON 構文が不正な場合は例外を捕捉し、空の設定 `{}` として続行します（`strata_cli/drafting_cmd.py:40-46`）。したがって、この場合に `--config` のデータフォルダーや drafting/model 情報は使われません。JSON として有効でも object 以外の値は明示的に拒否されず、後続の `.get()` で失敗し得ます（同 `:44-54`）。
- 同じ `--config` を複数回指定した場合の専用処理はありません。`argparse` の通常の単一値引数として最後の値が Namespace に入ります（登録箇所 `strata_cli/drafting_cmd.py:24`）。

## 実行時の動作

`--data-dir` があればそちらが優先されます。なければ config の `args` から `--pack` または `--mtp` のパスを探し、そのパスの親からモデルの data folder を推定します。config から推定できなければ `Catalog().data_dir()` を使います（`strata_cli/drafting_cmd.py:47-54`、`strata_control/drafting.py:203-212`、`strata_cli/launch/catalog.py:494-501`）。

`--mode` を明示した場合は config の `drafting` より優先されます。省略時は config の `drafting` を読み、値もなければ drafting 側の既定 `auto` として扱われます。`--family` を指定した場合は family がモデル適合判定に使われ、config の `model_name` より優先されます（`strata_cli/drafting_cmd.py:54`、`strata_control/drafting.py:23-24, 107-112, 136-138`）。

- `strata drafting plan` は config 等から判定を作りますが、ファイルを取得しません。config または `--mode` を使ってモデルについて問い合わせ、必要でない場合は結果の `gb` を `0.0` にします（`strata_cli/drafting_cmd.py:63-73`）。
- `strata drafting fetch --if-needed` は `needs_pack` が false なら取得せず成功終了します。true のときだけ `ensure` を呼びます（`strata_cli/drafting_cmd.py:60-79`）。この revision では `ENGINE_SERVES_DFLASH2 = False` であり、`needs_pack` の条件にこの値との AND があるため、`--if-needed` を付けた呼び出しは config の内容にかかわらず取得をスキップします（`strata_control/drafting.py:141-146, 179-183`）。
- `--if-needed` を付けない `fetch` は `needed` の値によらず `ensure` を実行します。すでに 1 MiB を超える pack があればそれを保持して返し、なければ取得処理へ進みます（`strata_cli/drafting_cmd.py:60-62, 74-88`、`strata_control/drafting.py:114-122`、`strata_control/drafting_fetch.py:54-64`）。この場合 `--config` は保存先選択に関係しますが、config の drafting/model 値は取得可否に使われません。

## 適用条件と副作用

通常の `fetch` は明示実行された場合にネットワーク取得を行い、data folder 配下の `dflash2/src/` に一時・取得ファイルを作成します。固定された Hugging Face revision のファイルをサイズ・SHA-256 検証付きで取得し、pack を一時ファイル経由で作成した後、元の取得ファイルを削除します。生成物は `<data-dir>/dflash2/qwen3.8-flash-next-dflash2.q8.pack` です（`strata_control/drafting.py:88-100`、`strata_control/drafting_fetch.py:54-59, 63-101`）。

`--if-needed` を付けたときだけ config の mode/model 情報は取得条件に影響します。判定では `auto` は GPU class の提案に置換され、family があれば `qwen` / `gyro` かを確認し、なければ config の model name が Qwen3.8-Flash-Next の形式に適合するかを調べます。ただし現 revision では engine serving 対応フラグが false のため、これらの値が適合していても取得条件を満たしません（`strata_control/drafting.py:102-112, 141-146, 179-183`）。

## 出力とエラー

`--output` の選択肢は `human`（既定）、`json`、`jsonl` です（`strata_cli/drafting_cmd.py:29`）。`--if-needed` により取得を省略すると、人間向けには `Nothing to download.`、JSON/JSONL では `skipped: true` の結果を出して終了コード 0 です（同 `:74-79`）。実際に取得する場合、JSONL は進捗イベントを出し、成功時は pack path を結果として出します（同 `:81-99`）。

取得・pack の `DraftingError` と取得禁止の `AcquisitionRefused` は、機械向けには JSON error、人間向けには stderr の `strata:` エラーとして表示され、終了コード 5 です（`strata_cli/drafting_cmd.py:87-94`）。ファイルの欠落・破損した JSON 構文は上記のとおり空 config にフォールバックします。JSON 配列や文字列のように `.get()` を持たない有効 JSON の場合の CLI 表示・終了コードは専用処理で定義されておらず、この調査では確定できません。

## 根拠

- parser と config 読み込み・値の優先順位・取得分岐・出力: `strata_cli/drafting_cmd.py:17-99`
- data folder の推定と DFlash2 の必要判定、現 revision の serving 対応状態: `strata_control/drafting.py:102-122, 136-183, 203-212`
- 実際の pinned download、pack 作成、取得ファイル削除: `strata_control/drafting_fetch.py:29-39, 54-101`
- CLI のサブコマンド登録と dispatch: `strata_cli/cli.py:172-173, 2144-2146`
