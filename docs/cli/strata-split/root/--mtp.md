# `--mtp`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-split` |
| コマンド | `strata-split-N`（N はビルド対象カード数） |
| オプション | `--mtp` |
| 別名 | なし |
| 値 | MTP runtime データのディレクトリ。値は必須。 |

## 役割

全カード分割 engine sFNX の MTP（draft layer）データを指定します。このオプションは必須で、読み込んだ MTP を engine に接続します。通常の起動では runtime ディレクトリに `draft_vocab.bin` も必要です（`--draft-vocab` で別ファイルを指定できます）。

## 使い方

```sh
strata-split-2 --serve --native /path/to/model.gguf --mtp /path/to/mtp-runtime
```

これは parser の構文例です。`strata-split-N` の実際の実行ファイル名はビルド・配布形態により異なります。NVIDIA/AMD の命名と同梱条件は [`strata-split` 索引節](../../README.md#strata-split) を参照してください。

## 値と既定値

- `--mtp` は次の argv 要素を値としてそのまま文字列に受け取り、`mtp_dir` に格納します。オプション自体に既定値はありません。値が次に無い場合は `--mtp needs a value`、未指定または空文字の場合は `--native and --mtp are required` で拒否されます（`src/split/tools/sfnx.cpp:72-84, 101`）。
- 同じオプションを複数回指定すると、parser の文字列代入により最後の値が残ります（`src/split/tools/sfnx.cpp:75-84`）。ディレクトリの存在・内容は parser では検査せず、MTP 構築時に読み込みます。
- 通常の build では値を runtime ディレクトリとして扱い、そこから `draft_vocab.bin`（または `--draft-vocab` で指定したファイル）と MTP tensor/expert ファイルを読み込みます（`src/split/src/model.cpp:1194-1215`、`src/split/src/model.cpp:913-950`）。
- `FNX_27B` build ではディレクトリ値は文字列 `nextn` でなければならず、draft layer は GGUF 内のものを使います。この場合 `--draft-vocab` による語彙ファイル指定が必須です（`src/split/src/model.cpp:1142-1148`）。この条件分岐は build 時の `FNX_27B` によるため、実行時にモデルを見て通常 build から切り替わる仕様ではありません。

## 実行時の動作

`main()` は parser の後、モデルを読み込んでから `fnx::Mtp` を `--mtp` の値（および任意の `--draft-vocab` 値）で構築し、続けて engine を作成して `mtp_attach()` を呼びます（`src/split/tools/sfnx.cpp:1050-1060`）。MTP が全カードにあることを attach 時に確認し、draft vocabulary からモデル語彙 ID への対応表を作ります（`src/split/src/engine.cu:1175-1177, 1231-1232`）。

接続された draft layer は speculative decoding の候補生成に使われます。サーバーの各 session は `--spec` の K 値と lookup 値を受け取ります（K の既定値は 6。`src/split/tools/sfnx.cpp:65-68, 440, 454`）。MTP データを指定しただけで `--spec` の値が変わることはありません。

## 適用条件と副作用

- MTP の語彙 ID ファイルは int32 token ID の列で、空でなく、各 ID がモデル語彙範囲内であることを検査します。通常 build では既定ファイルが `<--mtp の値>/draft_vocab.bin` です。`--draft-vocab` はこの既定パスを置き換えます（`src/split/src/model.cpp:1194-1215`）。
- 通常 build では runtime 内の `dense.bin` と `dense.txt` を開いて mmap し、`FNX_MTP_EXPERTS` が未設定または `q2_0` なら `experts.bin`、`q4_0` なら `experts-q4_0.bin` を読みます。その他の環境変数値は失敗します（`src/split/src/model.cpp:913-950`）。この環境変数は `--mtp` の値を変えず、expert ファイル形式の選択に作用します。
- MTP の重みは各カードへ配置されてから engine が作られます。engine の arena は残り VRAM を基準にするため、MTP の配置は engine が利用できる VRAM に影響します（`src/split/src/engine.hpp:85-87`）。起動時にデータを読み込み、engine に接続するオプションです。
- 索引によれば Terminal の `strata launch --split-engine auto|on|off` が sFNX の起動判断を担います。`--mtp` 自体は独立実行ファイル sFNX の引数であり、Terminal の `strata launch` 引数ではありません（[`docs/cli/README.md`](../../README.md#strata-split)、同索引の起動説明）。

## 出力とエラー

- parser エラー（値なし、必須引数不足、未知引数など）は stderr に `sfnx: <理由>` を出して終了コード 2 になります（`src/split/tools/sfnx.cpp:77-79, 98-104, 1040-1048`）。
- runtime ディレクトリや語彙ファイルを開けない、形式・語彙範囲が不正、tensor が欠落・不適合など、モデル/MTP/engine 初期化中の例外は `ERR <理由>` を stdout に、`sfnx: failed: <理由>` を stderr に出し、終了コード 1 で終了します（`src/split/tools/sfnx.cpp:1030-1035, 1050-1061`）。具体的な MTP ファイル検査とエラーは `src/split/src/model.cpp:913-957, 1194-1233` にあります。

## 根拠

- parser と必須条件: `src/split/tools/sfnx.cpp:65-104`
- 起動時のモデル・MTP 構築と attach: `src/split/tools/sfnx.cpp:1050-1061`
- runtime directory の読込と形式検査: `src/split/src/model.cpp:913-957, 963-1007, 1194-1233`
- `FNX_27B` build の特則: `src/split/src/model.cpp:1142-1167`
- engine attach と VRAM 上の配置順: `src/split/src/engine.hpp:85-93`、`src/split/src/engine.cu:1175-1232`
- command scope・launch 連携: `docs/cli/README.md:1510-1533`（索引確認用。parser 挙動の根拠は Strata ソース）

調査範囲は上記 checkout のソースです。同一 revision の `strata-split-N --help` 実行ファイルや Release archive は確認しておらず、配布済み artifact の実際の同梱内容・個々の GPU 環境での実行可否はここでは確認していません。
