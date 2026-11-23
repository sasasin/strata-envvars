# `strata-split-N --draft-vocab`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-split` |
| コマンド | `strata-split-N`（N = 2/3/4、`--serve` モード） |
| オプション | `--draft-vocab` |
| 別名 | なし |
| 値 | 語彙 ID ファイルのパス。ファイル形式は方式によって異なる検査を受ける |

## 役割

MTP または DFlash2 の speculative drafting で使う draft vocabulary ファイルを指定します。ファイルには main model の token ID が並び、その順序が draft head の行との対応を決めます。指定を省略した場合の既定パスは MTP runtime directory 内の `draft_vocab.bin` です。DFlash2 方式では `--mtp` のディレクトリを語彙ファイルの既定場所としても使えます。parser はオプション値を文字列として保存し、形式や存在確認はモデルのロード時に行います（`engine/src/split/tools/sfnx.cpp:65-87,110-114`、`engine/src/split/src/model.cpp:1230-1256`）。

## 使い方

```sh
# MTP 方式で独自の語彙ファイルを使う
strata-split-2 --serve --native MODEL.gguf --mtp MTP_DIR --draft-vocab VOCAB.bin

# DFlash2 方式で独自の語彙ファイルを使う
strata-split-2 --serve --native MODEL.gguf --mtp MTP_DIR --draft dflash2 --draft-model DFLASH2.pack --draft-vocab VOCAB.bin
```

## 値と既定値

- 値はパス文字列です。parser は次の argv 要素を受け取り、値がなければ `--draft-vocab needs a value` として引数解析を失敗させます。数値範囲やパスの形式は parser では検査しません（`engine/src/split/tools/sfnx.cpp:76-87`）。
- 同じオプションを複数指定すると、引数を走査するたびに同じ文字列フィールドへ代入するため、最後の指定が残ります（`engine/src/split/tools/sfnx.cpp:76-86`）。
- MTP では値を省略または空文字にすると `--mtp` の値に `/draft_vocab.bin` を連結したファイルを使います。通常の MTP 起動には `--native` と `--mtp` が必要です（`engine/src/split/src/model.cpp:1230-1234`、`engine/src/split/tools/sfnx.cpp:107-114`）。
- DFlash2 では `--draft-vocab` を省略または空文字にすると、`--mtp DIR` があれば `DIR/draft_vocab.bin` を使います。`--mtp` も指定しない場合は明示的な `--draft-vocab FILE` が必要です（`engine/src/split/tools/sfnx.cpp:108-114`）。
- MTP のファイルは空でなく、サイズが 4 byte 単位で、全要素が main model の語彙範囲 `0 <= id < vocab_size` に入る必要があります。読み取りエラーやファイルサイズまで読み切れなかった場合も拒否されます（`engine/src/split/src/model.cpp:1232-1255`）。
- `FNX_27B` ビルドの MTP では例外があり、`--mtp` の値は `nextn` 固定で、語彙ファイルの明示が必須です。この分岐では同様に空ファイルと語彙範囲外 ID を拒否します（`engine/src/split/src/model.cpp:1172-1202`）。
- DFlash2 のファイルは 4 byte ごとに `int32_t` として読み取られ、空ファイルと語彙範囲外の ID は拒否されます。MTP と異なり、ここではファイルサイズの 4 byte 整合性や `ferror` は別途検査していません（`engine/src/split/tools/sfnx.cpp:1061-1072`）。
- 両方式ともコード上で ID の重複検査はありません。MTP は語彙 ID から draft index への表を構築し、同じ ID が重複すると後の位置が表に残ります（`engine/src/split/src/engine.cu:1307-1308`）。

ファイルは生の `int32_t` 配列として読み取られ、Strata 側で byte order を変換する処理は確認できません。対応する byte order やファイル生成手順の仕様は、この調査範囲のソースからは確定できません。

## 実行時の動作

`--draft-vocab` の文字列は MTP 方式では `Mtp` の構築に渡され、MTP runtime ファイル群とともに読み込まれます。読み込んだ ID のリストは各 GPU card に分割され、draft head の `output.weight` 行の選択に使われます。engine は同じリストから token ID を draft vocabulary 内の位置へ対応づけます（`engine/src/split/tools/sfnx.cpp:1123-1133`、`engine/src/split/src/model.cpp:1257-1275`、`engine/src/split/src/engine.cu:1251-1308`）。

DFlash2 方式では同ファイルから ID を読み、main model の `output.weight` の該当行を選び、pack・選択行・embedding の callback とともに bridge へ渡します。bridge のロードは Engine の構築より先に行われます（`engine/src/split/tools/sfnx.cpp:1061-1091,1123-1133`）。

`--draft` の選択は `FNX_DRAFT` が空でない場合に環境変数の値で上書きされます。そのため、`--draft dflash2` を指定していても `FNX_DRAFT=mtp` なら MTP 側が選ばれ、同じ `--draft-vocab` の値は MTP に渡ります。`FNX_DRAFT` の有効値は `mtp` と `dflash2` で、それ以外は引数解析エラーです（`engine/src/split/tools/sfnx.cpp:107-114`）。

## 適用条件と副作用

- このオプションは `strata-split-N` の `--serve` parser scope にあります。MTP と DFlash2 のどちらをロードするかは `--draft` と `FNX_DRAFT` の決定結果で変わります（`engine/src/split/tools/sfnx.cpp:82-87,107-114,1123-1133`）。
- ファイルを読み込んでホストメモリ上の ID 配列を作り、モデル出力行を選択して GPU 側の draft 処理へ渡します。オプション自体によるファイルの書き換えはありません（`engine/src/split/src/model.cpp:1232-1275`、`engine/src/split/tools/sfnx.cpp:1061-1091`）。
- モデル語彙にない ID、空ファイル、開けないファイルは起動時に拒否されます。MTP では MTP データのロード・card ごとの読み込み失敗も起動を失敗させます（`engine/src/split/src/model.cpp:1232-1275`）。DFlash2 では `output.weight` が存在しないか Q8_0 でない場合も拒否されます（`engine/src/split/tools/sfnx.cpp:1064-1074`）。

## 出力とエラー

- 値の欠落、未知の引数、必須引数不足など引数解析時の例外は `stderr` に `sfnx: <理由>` と出力され、終了コード 2 になります（`engine/src/split/tools/sfnx.cpp:76-80,105-115,1107-1115`）。
- モデル・語彙ファイルのロード失敗は `stdout` の protocol line `ERR <理由>` と `stderr` の `sfnx: failed: <理由>` に出力され、終了コード 1 で終了します（`engine/src/split/tools/sfnx.cpp:1094-1102,1123-1135`）。
- DFlash2 ではロード成功時、選択した draft token 数・drafter 数・VRAM 使用量を `stderr` に表示します（`engine/src/split/tools/sfnx.cpp:1089-1092`）。

## 根拠

- `engine/src/split/tools/sfnx.cpp:73-117` — parser、必須引数、`FNX_DRAFT` による方式選択、DFlash2 の語彙パス補完。
- `engine/src/split/tools/sfnx.cpp:1061-1092,1123-1135` — DFlash2 のファイル読み込み・検査・出力行選択・bridge への受け渡し、および失敗経路。
- `engine/src/split/src/model.cpp:1230-1275` — MTP の既定パス、ファイル形式・値域検証、card 別の語彙 head ロード。
- `engine/src/split/src/engine.cu:1251-1308` — MTP 語彙の engine への接続と token ID 対応表。
