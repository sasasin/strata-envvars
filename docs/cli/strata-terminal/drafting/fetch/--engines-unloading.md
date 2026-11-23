# `--engines-unloading`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata drafting fetch` |
| オプション | `--engines-unloading` |
| 別名 | なし |
| 値 | 値を取らない boolean flag。指定すると `True`、省略すると `False`。 |

## 役割

新しいモデルの開始前に既存の Strata engine が停止して VRAM を返す予定であることを split engine の事前判定へ伝えます。これにより、停止前の GPU 空き容量ではなくカード容量を使って split engine が開始可能かを見積もります。fetch コマンド自身が engine を停止する機能ではありません。特に `--if-needed` と併用すると、split engine が使われる見込みなら DFlash2 drafter の取得を省略する判定になります。

## 使い方

```sh
# アプリと同様に、既存 engine の停止後に split engine が使われる見込みなら取得を省く
strata drafting fetch --config ./run-config.json --engines-unloading --if-needed
```

このオプションは通常の `--help` 出力には表示されません（parser で `argparse.SUPPRESS` が指定されています）。ただし現行 parser は受け付け、索引上の scope は `strata drafting fetch` です。

## 値と既定値

値・引数は不要です。`argparse` の `store_true` で登録され、未指定時は偽です。別名、値の範囲、空値の解釈はありません。値を続けて渡した場合、その値はこの flag の値にはならず、コマンドの他の引数として parser による処理を受けます。

## 実行時の動作

`fetch` と `plan` は共通 parser でこの flag を登録します。`fetch` では設定ファイルと引数から入力を組み立てる際、実効 mode が `auto` または `mtp` で、かつ `--no-split` がない場合に split engine の事前判定を行います。`--engines-unloading` があると実 GPU probe の各カードについて `free_mib` を `None` に置き換えます。split engine の判定は `free_mib=None` を「空き容量不明」としてカード全容量で計算するため、稼働中 engine が保持している VRAM は見積もり上 busy とされません。

事前判定が split engine を選ぶと、入力の mode を `mtp` に切り替えます。続く `needs_pack` / `needs_tuned` の判定は drafter の選択を見ており、`fetch --if-needed` はそれらが不要なら取得を行わず成功扱いで終了します。split engine はモデル内蔵の MTP draft layer を使うため、この経路で DFlash2 pack を求めません。`--if-needed` がない明示的な fetch では、この flag は `ensure_for` の取得処理に引き渡されず、split 判定結果による skip も行いません。

`--no-split` がある場合は split 判定自体をせず、この flag は fetch の取得要否に影響しません。mode が `off` または `dflash2` の場合も split 判定の条件外です。設定の `mtp` が false で実効 mode が `auto` のときは先に mode が `off` へ変わるため、同様に split 判定されません。split の事前判定内で例外が起きた場合も `False`（split を見込まない）として扱われます。

この flag は状態を主張する入力であり、engine の停止確認はしません。従って、解放予定の Strata engine が残ったまま使うと、その占有分を含めずカード全容量で判定します。ほかの GPU 利用プロセスが使っている VRAM もこの見積もりから除外されます。

## 適用条件と副作用

split engine の事前判定は対応する Linux / Windows 系のシステムで GPU probe を行い、カード数・種類、モデルや engine 引数、RAM などの条件も判定します。`--engines-unloading` はその判定に使うカードのメモリ情報だけを置き換えます。GPU の probe 自体は行われますが、この flag によるファイル変更、ネットワークアクセス、engine の停止はありません。後続の fetch が実際に必要と判断された場合のダウンロード・pack 作成は通常の fetch 処理です。

判定の情報が不足したり例外が発生したりすると split 不採用として継続します。その場合 `--if-needed` は DFlash2 が必要と判断されれば取得へ進むことがあります。逆にこの flag が full VRAM 前提で split を採用し、`--if-needed` が DFlash2 を省略しても、実際の start が別条件で split を使えない場合の fallback では通常の drafter が必要になる可能性があります。

## 出力とエラー

`--if-needed` で DFlash2 が不要と判定された場合、human 出力は `Nothing to download.`、JSONL 出力は `skipped: true` の result event となり、終了コード 0 です。必要と判断された場合は通常の取得処理へ進みます。取得時に `DraftingError` または acquisition 拒否が起きると、machine 出力では `drafting_failed`、human 出力では stderr に `strata: ...` を出し、終了コード 5 です。split 判定の内部例外だけではこの flag 起因のエラーにはならず、split 不採用として処理が続きます。

## 根拠

- `terminal/strata_cli/drafting_cmd.py:22-38` — `plan` と `fetch` の共通 parser、`store_true` 登録、help 非表示。
- `terminal/strata_cli/drafting_cmd.py:45-61` — split 判定への入力、VRAM 情報の置換、例外時に `False` とする経路。
- `terminal/strata_cli/drafting_cmd.py:101-136` — 実効 mode、`--no-split` 条件、判定後に mode を `mtp` とする処理。
- `terminal/strata_cli/drafting_cmd.py:240-246, 267-272, 281-305` — 必要性判定、`--if-needed` の skip、実取得と出力・失敗経路。
- `terminal/strata_control/split_engine.py:96-103, 477-513` — 空き VRAM が不明なカードを全容量として数える規則、事前判定が扱う条件と例外処理。
- `terminal/strata_control/drafting.py:1611-1622` — DFlash2 pack / tuned pack の必要性判定。
- `app/host/server/control-runtime.mjs:401-406` — ホストアプリが fetch にこの flag と `--if-needed` を渡す経路。
- `docs/cli/README.md:349-361` — `strata drafting fetch` のコマンド階層と option scope の索引。
