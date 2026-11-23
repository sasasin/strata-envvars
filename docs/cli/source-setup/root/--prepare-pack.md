# `setup.py --prepare-pack`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（トップレベル） |
| オプション | `--prepare-pack` |
| 別名 | なし |
| 値 | 必須の pack 出力先ディレクトリ `PACK_DIR` |

## 役割

すでに手元にある GGUF モデルから、Strata エンジンが読む pack（インデックス、dense 重み、tokenizer など）を作ります。Intel Arc 向けに `strata launch` が使う準備工程で、エンジンのインストールやモデルのダウンロードを行う通常セットアップとは別の経路です。GGUF ファイルは読み取り元であり、pack は `PACK_DIR` に作られます（`terminal/setup.py:10820-10824,11403-11405`）。

## 使い方

```sh
# 既存の Qwen GGUF shard から pack を作る
python terminal/setup.py --prepare-pack ./data/packs/iq3_xxs \
  --gguf-dir ./models/iq3_xxs --family qwen --model IQ3_XXS
```

`--gguf-dir` と `--model` はこの経路で必須です。`--family` を省略すると処理内で `qwen` が選ばれます。実際の family と model は、指定した GGUF に合う組み合わせにしてください（`terminal/setup.py:10825-10837`）。

## 値と既定値

- `PACK_DIR` は `--prepare-pack` の直後に渡す値です。argparse が値を要求しますが、setup 側ではパスの形式や空き容量を事前検証せず、`tools/iq_pack.py --out PACK_DIR` に渡します。同ツールは出力ディレクトリを作成します（`terminal/setup.py:11322-11324`; `terminal/tools/iq_pack.py:598-609,618-625`）。
- `--gguf-dir DIR` がない場合は「GGUF ファイルのあるフォルダーが必要」として失敗します。`--model` がない場合も失敗します。`--family` の省略値は `qwen`、未知の family は拒否されます。処理側のエラー案内は `qwen`、`swift`、`coder`、`gyro` を選ぶよう示します（`terminal/setup.py:10825-10832`）。
- 共有 parser では `--family` と `--model` に choices が定義されます。`--model` は `model_alias` で正規化され、許可された model 名に限られます（`terminal/setup.py:11227-11233`）。この prepare 経路では `FAMILIES` の family と、同 family に合う model を組み合わせる必要があります。
- `--gguf-dir` からモデル名に対応する先頭 shard を探し、shard 名に総数があればその番号分の shard を入力として扱います。対応ファイルがない、未対応形式である、shard が欠けている、GGUF が壊れている場合は packer 側で失敗します（`terminal/setup.py:3627-3647,3692-3718`; `terminal/tools/iq_pack.py:145-172`）。

## 実行時の動作

1. parser が引数を読み、`--gguf-dir` を Strata 自身の model ファイルとして登録します。続いて `--prepare-pack` が指定されていれば `prepare_pack_only` を呼び、通常のインストール処理へ進みません（`terminal/setup.py:11385-11405,1261-1268`）。
2. `prepare_pack_only` は family/model と shard を解決し、GGUF の利用可否を確認します。失敗条件には、必須値の不足、無効な family、選択した family/model のファイルがない場合などがあります（`terminal/setup.py:10825-10837,3627-3647,3692-3718`）。
3. 出力先に `native_experts.txt` または `tokenizer/vocab.json` がなければ、`tools/iq_pack.py --gguf <先頭 shard> --out <PACK_DIR>` を起動します。family の `pack_args` があれば追加します。packer は全 shard を読み、pack のインデックスや dense 重み、tokenizer を作成します。標準経路では experts を元 GGUF から読むため、`experts.bin` は明示指定なしには作りません（`terminal/setup.py:10838-10848`; `terminal/tools/iq_pack.py:598-609,621-630,714-734`）。
4. `native_experts.txt` と `tokenizer/vocab.json` がすでに存在すると packer を呼ばず再利用し、tokenizer の vocab がなければエラーにします。両 marker がそろっているとき、setup 側で pack と指定 GGUF の対応関係までは検証しません（`terminal/setup.py:10843-10848`）。

同じ出力先に既存 pack がある場合、packer がその中のファイルを更新することがあります。別のモデル用 pack や保持したいデータがある場所を `PACK_DIR` に指定しないでください。入力 GGUF は Strata の own-file 扱いとなり、その隣に完了 marker を書かず、`PACK_DIR` も入力フォルダーとは別に指定できます（`terminal/setup.py:11393-11394,1261-1268`; `terminal/tools/iq_pack.py:621-625,727-730`）。

## 適用条件と副作用

- この経路は同梱の `terminal/tools/iq_pack.py` を実行します。packer の GGUF 読み込みは Strata の `gguf_reader` を使い、GGUF をダウンロードしません（`terminal/tools/iq_pack.py:59-61,623-625`; `terminal/setup.py:10821-10824`）。packer が型変換を必要とする場合は `_paths.gguf_lib()` を通じて reader/quantizer を選び、設定済み `STRATA_GGUF_PY` があれば利用しますが、これは取得処理ではありません（`terminal/tools/iq_pack.py:109-118,231-250`; `terminal/tools/_paths.py:57-72`; `terminal/setup.py:4219-4223`）。
- 出力先には `index.txt`、`dense.bin`、`native_experts.txt`、`tokenizer/` などが書かれます。処理途中で失敗した場合も、出力先に途中ファイルが残ることがあります。入力 GGUF の内容は変更しません（`terminal/tools/iq_pack.py:1-16,307-318,714-730,738-787`）。
- parser の help 文はこのオプションが llama.cpp の `gguf-py` を取得すると説明していますが、現行 prepare 関数は取得処理を呼ばず、packer も外部ツールのダウンロードを行いません。したがって help 文のその説明は現行処理と食い違います（`terminal/setup.py:11322-11324,10821-10824,1131-1157`; `terminal/tools/iq_pack.py:598-625`）。
- `--output jsonl` を指定した場合は、prepare 分岐の前に JSONL 出力が初期化されます（`terminal/setup.py:11385-11387,11403-11405`）。

## 出力とエラー

- 成功時は packer が成功コードを返した後、setup が `model prepared: <PACK_DIR>` を表示して終了コード `0` を返します（`terminal/setup.py:10846-10849`）。
- 不足値、無効な family、利用できないモデルファイル、tokenizer が生成されない場合、setup の `fail` はエラーと案内を表示して終了コード `1` で停止します。`iq_pack.py` の非ゼロ終了も `run` が失敗として扱い、setup の `fail` によって終了コード `1` になります（`terminal/setup.py:1049-1056,10825-10847,1131-1157`）。
- `--prepare-pack` の値がない、または parser の choices にない `--family` / `--model` を渡した場合は argparse が拒否します（`terminal/setup.py:11226-11233,11322-11324,11385`）。

## 根拠

- `terminal/setup.py:11322-11324` — parser 定義と help 文。
- `terminal/setup.py:11227-11233,11385-11405` — family/model の parser 制約、引数処理、prepare 専用分岐。
- `terminal/setup.py:10820-10849` — 必須条件、family 既定値、GGUF 検証、pack 作成・再利用、成功条件。
- `terminal/setup.py:3627-3647,3692-3718` — GGUF shard の探索と利用不可ファイルの判定。
- `terminal/setup.py:1049-1056,1131-1157` — setup エラー終了と子プロセス失敗処理。
- `terminal/tools/iq_pack.py:1-16,598-630,714-734,727-787` — packer の入力・出力、tokenizer と marker、生成物。
- `terminal/tools/iq_pack.py:59-61,109-118,231-250`、`terminal/tools/_paths.py:57-72` — GGUF 読み込みと、必要な変換時の reader/quantizer 選択。
