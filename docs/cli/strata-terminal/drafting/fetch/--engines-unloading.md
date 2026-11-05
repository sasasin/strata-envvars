# `strata drafting fetch --engines-unloading`

調査対象: Strata commit `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata drafting fetch` |
| オプション | `--engines-unloading` |
| 別名 | なし |
| 値 | 値なし。`store_true` フラグ |

## 役割

モデル実行設定から all-cards split engine の起動可否を早期判定するとき、現在 GPU 上で Strata の engine が保持しているメモリを、次の起動までに返却されるものとして扱います。アプリが既存 engine を停止する前に drafter の取得要否を問い合わせる用途を想定したフラグです。このフラグ自体は engine を停止・unload しません（`strata_cli/drafting_cmd.py:42-56`）。

## 使い方

```sh
strata drafting fetch --config /path/to/run-config.json --engines-unloading --if-needed
```

`--if-needed` を付けると、選択された実行経路で drafter の取得が不要な場合は取得を省略します。フラグは `strata drafting plan` と `fetch` の共通 parser で定義されています（`strata_cli/drafting_cmd.py:19-35`）。

## 値と既定値

- 値は取りません。指定すると `args.engines_unloading` が真になり、省略時は `store_true` の既定値で偽です（`strata_cli/drafting_cmd.py:31-32`）。
- 値の範囲や追加 validation はありません。値を後置する形式ではなく、同じフラグを複数回指定しても真のままです。help 表示からは `argparse.SUPPRESS` により隠されています（`strata_cli/drafting_cmd.py:31-32`）。

## 実行時の動作

`fetch` は引数を `_inputs()` に渡し、設定の drafting mode が `auto` または `mtp` で、かつ `--no-split` が指定されていないときに split 可否を問い合わせます。このときフラグの真偽が `_split_expected(..., unloading=...)` に渡ります（`strata_cli/drafting_cmd.py:61-85`）。

`unloading=True` の場合、split-engine のカード情報を取得した後、各カードの `free_mib` を `None` に置き換えます。split 可否判定の空きメモリ計算は `free_mib=None` ならカード全容量、既知の空き容量があればその値から 700 MiB の reserve を引くため、このフラグは「Strata engine が保持中の VRAM が返却された後」の見積もりに切り替えます（`strata_cli/drafting_cmd.py:42-56`、`strata_control/split_engine.py:99-104`）。カード情報取得や split 判定で例外が起きても `_split_expected()` は `False` を返し、早期問い合わせを理由にコマンドを失敗させません（`strata_cli/drafting_cmd.py:57-58`、`strata_control/split_engine.py:437-473`）。

split が予測されると `_inputs()` は選択 mode を `mtp` として扱い、DFlash2 pack が必要かどうかを再計算します（`strata_cli/drafting_cmd.py:80-85`、`strata_control/drafting.py:721-731`）。`--if-needed` があると `needed` が偽の場合に「Nothing to download.」または JSON の `skipped: true` を出して正常終了します（`strata_cli/drafting_cmd.py:90-118`）。

このオプションだけでは `fetch` を条件付きにはしません。`--if-needed` がない経路では、上記の判定後も `drafting_fetch.ensure()` が呼ばれ、DFlash2 pack の取得・準備を試みます（`strata_cli/drafting_cmd.py:113-138`）。

## 適用条件と副作用

- 効果があるのは `drafting.normalize(mode)` が `auto` または `mtp` で、`--no-split` が無効の場合です。`--mode dflash2`、`--mode off` などではこの split 判定分岐に入りません（`strata_cli/drafting_cmd.py:77-82`）。
- `--config` の `gpu`、`args`、`drafting`、`split_engine`、`replicas` 等が予測に使われます。`--config` が読めない場合は `_inputs()` が空設定として続行し、split 判定自体も例外時は偽として扱います（`strata_cli/drafting_cmd.py:61-80`、`strata_control/split_engine.py:447-473`）。
- これはメモリ見積もりの変更であり、実際に GPU メモリを解放したり、engine/GPU を操作したりはしません。システム RAM 等、カードの `free_mib` 以外の split 判定条件は引き続き判定されます（`strata_cli/drafting_cmd.py:51-56`、`strata_control/split_engine.py:437-473`）。
- `fetch` の通常取得経路ではネットワークアクセス、pack 生成、関連ファイル操作が発生し得ますが、それらは `--engines-unloading` による副作用ではなく `fetch` 本体の動作です（`strata_cli/drafting_cmd.py:126-138`、`strata_control/drafting_fetch.py:144-200`）。

## 出力とエラー

このフラグ固有の警告やエラー出力は確認できません。フラグにより split 判定が真になり、`--if-needed` による skip が成立すれば、human 出力は `Nothing to download.`、JSON/JSONL 出力は `{"schema_version":1,"ok":true,"event":"result","pack":null,"skipped":true}` です（`strata_cli/drafting_cmd.py:113-118`）。

通常の fetch が続いた場合、DFlash2 の取得・準備エラーは human 出力では stderr に `strata: ...`、機械可読出力では `ok: false` の JSON となり、終了コード 5 です。成功時は pack の場所を表示して 0 で終了します（`strata_cli/drafting_cmd.py:126-138`）。

## 根拠

- Parser と共通 option 定義: `strata_cli/drafting_cmd.py:19-35`
- フラグから split 判定への引き渡しと VRAM 情報の変更: `strata_cli/drafting_cmd.py:42-58,61-85`
- `--if-needed` の分岐、取得処理、出力と終了コード: `strata_cli/drafting_cmd.py:88-138`
- 空きメモリの扱いと split 早期判定: `strata_control/split_engine.py:99-104,437-473`
- drafter の要否判定: `strata_control/drafting.py:721-731`
- fetch が実行する取得・pack 処理: `strata_control/drafting_fetch.py:144-200`

調査範囲は上記 checkout の Python CLI と split-engine 判定コードです。別 OS や GPU 構成での実機挙動、アプリ側がこのフラグを組み立てる詳細は、この文書では検証していません。
