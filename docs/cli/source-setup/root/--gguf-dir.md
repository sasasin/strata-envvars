# `--gguf-dir`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（`2026-11-03` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh`、`START-HERE.bat`、`SETUP.bat`、更新 wrapper からも委譲） |
| オプション | `--gguf-dir` |
| 別名 | なし |
| 値 | GGUF shard が置かれたディレクトリ。parser 上は任意の文字列で、既定値は未指定（`None`）。 |

## 役割

手元にあるモデル GGUF shard の場所を setup に渡します。通常のモデル setup では、指定した場所から選択モデルの shard を読み、通常のモデル用ダウンロードを省きます。対応する画像 encoder (`mmproj`) や MTP draft layer、engine、Python helper など、GGUF shard 以外の必要物まで一括してローカルから供給する指定ではありません（`setup.py:10397-10421,10478-10515,10519-10524`）。

同じオプションは Intel Arc 向けの `--prepare-pack` 単独モードでも入力ディレクトリとして必要です。このモードはモデル shard の取得や変更を行わず、指定先の pack ディレクトリを作成・更新します（`setup.py:9321-9349,9658-9660,9723-9724`）。

## 使い方

通常の setup で、既存の GGUF shard が `/data/my-model` にある例です。

```sh
./setup.sh --family qwen --model IQ3_XXS --gguf-dir /data/my-model --no-start
```

pack のみを作る例です。`PACK_DIR` は生成物の出力先です。

```sh
python3 setup.py --prepare-pack /data/strata-pack --gguf-dir /data/my-model --family qwen --model IQ3_XXS
```

通常モードで `--family` と `--model` を省いた場合は対話で選べます。`--prepare-pack` では `--model` が必要で、`--family` を省略すると `qwen` になります（`setup.py:9325-9333`）。

## 値と既定値

`argparse` では `--gguf-dir` に型・存在確認・必須指定を設定しておらず、値はそのまま `Path` に渡されます。通常モードで未指定なら `<models-dir>/<選択モデルのタグ>` が使われます。指定時はその値が shard のある場所になります（`setup.py:9643-9644,10397-10400`）。

まず選択したモデルの標準 shard 1 名を探します。見つからない場合はディレクトリ直下の `*-00001-of-*.gguf` を列挙し、ファイル名に model 名を含む候補を優先します。候補が一つに定まれば採用し、その `-00001-of-0000N.gguf` から N と shard の stem を読み、同じ stem の全 shard を組み立てます。判定できなければ標準名を使い、後続処理で欠落として失敗します（`setup.py:3222-3242`）。ディレクトリ階層を再帰検索する指定ではありません。

## 実行時の動作

通常モードでは指定先から shard 一式を選び、`--gguf-dir` がある場合は不足 shard の通常ダウンロード分を 0 として扱い、モデル shard のダウンロード分岐も通りません（`setup.py:10397-10421,10482-10509`）。指定された GGUF は setup の所有ファイルとして扱われ、setup はそれらを削除しません。

setup は shard を GGUF として読み、tensor directory が示す必要サイズに足りるか検査します。欠落、読めない/不完全な GGUF、短い shard はエラーになります（`setup.py:3574-3601`）。Unsloth など pinned SHA-256 を持つファイルでは、サイズ違いまたは hash 違いでも完全な GGUF と確認できる場合は警告してそのまま使います。完全性を確認できない不一致は失敗します。指定されたファイルを setup が削除して再取得する経路はありません（`setup.py:3324-3371`）。

shard に `.done` 完了印がなく、whole shard と確認できる場合、setup は印を shard の隣に書こうとします。読み取り専用ディレクトリでは Strata 側の `marks/` に保存を試し、それもできない場合は警告して続行します（`setup.py:1098-1118,10410-10415`）。

`--prepare-pack PACK_DIR` と併用した場合は通常の setup を実行せず、`--gguf-dir` から先頭 shard を選んで `tools/iq_pack.py` に渡し、pack と tokenizer を `PACK_DIR` に作ります。`llama.cpp` の `gguf-py` がローカルにない場合は helper の取得が発生します。既に pack の `native_experts.txt` と `tokenizer/vocab.json` が両方あれば変換を省略します（`setup.py:9321-9349,9723-9724`）。この専用経路では通常 setup の全 shard 完全性検査は呼ばれません（`setup.py:9321-9349,3574-3601`）。

## 適用条件と副作用

- `--gguf-dir` は GGUF shard を使う family 向けです。ready-made pack の family では警告を出して値を解除し、同オプションを適用しません（`setup.py:10131-10133`）。
- 選択した shard 1 が Strata 非対応 quantization とファイル名から判定された場合や、候補モデルと一致しない場合は失敗し、対応候補の案内を出すことがあります（`setup.py:3271-3300,10400-10402`）。
- `--prepare-pack` の family は `FAMILIES` に限られます。省略時は `qwen`、別 family を指定するなら family と model の組み合わせが必要です。`--gguf-dir` と `--model` の不足、不正 family、生成 pack に tokenizer がない場合は停止します（`setup.py:9325-9347`）。
- 通常 setup は GGUF 以外に engine・Python packages、設定、必要に応じて vision encoder / MTP などを扱います。`--no-start` は setup 後のモデル起動を止める指定で、これらの setup 処理を止めるものではありません（`setup.py:9645-9647,10397-10524`）。
- `setup.py` を Apple Silicon の macOS で Control mode なしに起動すると、root parser を作る前に `metal/setup_mac.py` へ委譲されます。索引では同じ表記を `source-setup/mac/` の別 scope として扱っています。この文書の値の説明は root scope の `setup.py` parser に対するものです（`setup.py:9560-9568`、[CLI 索引](../../README.md#source-setup)）。

## 出力とエラー

通常の入力・shard 検査で問題が見つかると、`fail()` は理由と可能なら修正ヒントを表示し、終了コード 1 で停止します（`setup.py:965-972,3574-3601,10400-10402`）。たとえば指定先に shard がない、GGUF として読めない、tensor の必要サイズまでデータがない場合が該当します。CLI の argparse 構文・choices のエラーは argparse が処理します（parser 定義 `setup.py:9568-9575,9643-9644`）。

## 根拠

- `setup.py:9643-9644` — root parser の `--gguf-dir` 宣言。値は任意文字列。
- `setup.py:3222-3242,10397-10402` — shard の名前・個数の検出と通常 setup での使用。
- `setup.py:3574-3601,3324-3371` — GGUF 完全性、サイズ、pinned SHA-256 の検査と失敗/警告。
- `setup.py:1098-1118,10410-10415` — 完了印の書き込みと読み取り専用先での扱い。
- `setup.py:9321-9349,9658-9660,9723-9724` — `--prepare-pack` 専用経路、helper と pack の動作。
- `setup.py:10397-10524` — 通常 setup の shard download 分岐と、vision encoder 等の別処理。
- `setup.py:10131-10133,9560-9568` — ready-made pack での無効化と macOS の parser 委譲。
