# `--mtp-draft-vocab`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン、root） |
| オプション | `--mtp-draft-vocab` |
| 別名 | なし |
| 値 | ファイルパス（トークン ID を並べたバイナリファイル） |

## 役割

MTP の draft head が候補として採点する語彙を、MTP ディレクトリ内の既定 subset から指定ファイルの subset に切り替えます。subset に含まれないトークンは draft の候補になりませんが、通常の検証側の語彙を削るオプションではありません。エンジンは指定ファイルの行だけで draft logits を計算します（`src/program/generate.cpp:790-791`、`src/core/mtp.cpp:692-739`、`src/core/mtp.cpp:1194-1197`）。

## 使い方

```sh
./strata generate --pack /models/pack --tokens "1,2,3" --mtp /models/mtp --spec 4 \
  --mtp-draft-vocab /models/draft_vocab.bin
```

`--tokens` は例示用です。MTP drafter は `--mtp` が指定され、かつ `--spec` が 2 以上の場合に動作します。`--spec` が 2 未満なら MTP は無視されます（`src/program/generate.cpp:806-812,5455-5459`）。

## 値と既定値

- 値は必須です。値を省略すると parser 共通処理が `<option> needs a value` を stderr に出して終了コード 2 で終了します（`src/program/generate.cpp:2418-2420`）。
- parser は値を文字列として保存するだけで、パスやファイル内容を parser 段階では検証しません。複数回指定した場合は引数走査中に後の値で置き換わります（`src/program/generate.cpp:2416-2420,2691`）。空文字列を値として渡すと空のまま扱われ、指定なしと同じ既定経路になります。
- 値を省略した場合の既定ファイルは `<mtp>/draft_vocab.bin` です。明示した場合はそのパスが使われます。相対パスの基準はプロセスの作業ディレクトリです（`include/strata/core/mtp.hpp:67-69,220-221`）。
- ファイル形式は符号付き 32-bit token ID の連続列です。MTP loader は読み込んだバイト列が 4 bytes 以上かつ 4 の倍数かを確認しますが、ID の範囲・重複・並びは検証しません（`src/core/mtp.cpp:692-706`）。同梱生成ツール `tools/draft_vocab.py` は subset を int32 配列として書き、生成時にはモデル語彙範囲を検査します（`tools/draft_vocab.py:103-108,139-141`）。

## 実行時の動作

明示パスは MTP drafter の bind 前に設定され、語彙 ID 列を読み込んで native head から該当行を GPU に集めます。subset が使われると、stderr に対象 token 数と head の MiB 数を出力します。subset が小さいほど draft head の確保量と計算対象行が減り、subset 外の token は draft できません（`src/program/generate.cpp:5460-5464`、`src/core/mtp.cpp:693-739`、`src/core/mtp.cpp:1194-1197`）。

同じ値は `--draft dflash2` にも渡されます。DFlash2 は明示パス、または `<mtp>/draft_vocab.bin` を bind 時に読み、head の行を subset 化します（`src/program/generate.cpp:16148-16157`、`src/core/dflash2.cpp:280-329`）。DFlash2 が head を bind/prepare できない場合は理由を含む stderr メッセージを出し、MTP draft に切り替えます（`src/program/generate.cpp:16153-16162`）。

## 適用条件と副作用

- 通常の MTP では `--mtp` と `--spec` 2 以上が必要です。MTP を使わない呼び出しでは、この値は通常の MTP head に適用されません（`src/program/generate.cpp:5455-5464`）。
- `STRATA_MTP_FULL_HEAD=1` の場合、MTP は subset ファイルの読み込みをスキップし、全語彙の native head を使います（`src/core/mtp.cpp:507-513,692-695`）。この環境変数の影響は MTP 実装に対するものです。DFlash2 側の同等な分岐は確認できません。
- ファイルが開けない、または長さが 4 bytes 未満／4 の倍数でない場合、MTP loader は subset を初期化せず、明示的なファイルエラーを出さずに全語彙 head の経路を使います（`src/core/mtp.cpp:113-118,692-695,1194-1197`）。DFlash2 loader も読み込み不能・不正長のファイルを空 subset として扱い、全 head 行に進みます（`src/core/dflash2.cpp:296-312`）。
- subset 行の VRAM 確保に失敗した場合、MTP bind は失敗し、上位でエラーを stderr に出して終了コード 1 になります（`src/core/mtp.cpp:698-702`、`src/program/generate.cpp:16143-16146`）。DFlash2 の確保失敗は前述の通り MTP への fallback 対象です。
- `--mtp-draft-vocab` 単独では subset 作成や検査を行わず、入力ファイルを読み取り、GPU 上に head subset を確保します。ファイル生成は別ツール `tools/draft_vocab.py` の責務です（`tools/draft_vocab.py:91-101,139-141`）。

## 根拠

- parser・usage: `src/program/generate.cpp:790-791,806-812,2416-2420,2691`
- MTP 適用条件と設定: `src/program/generate.cpp:5455-5464`
- MTP path 解決、subset 読み込み、head 行抽出・失敗: `include/strata/core/mtp.hpp:67-69,220-221`、`src/core/mtp.cpp:113-118,692-739`
- MTP logits の subset/full-head 切り替え: `src/core/mtp.cpp:1194-1197`
- DFlash2 への引き渡しと fallback: `src/program/generate.cpp:16148-16162`、`src/core/dflash2.cpp:280-329`
- subset 生成ツール: `tools/draft_vocab.py:1-5,103-108,139-141`
- 対象 scope と予定リンク: `docs/cli/README.md:1128-1134,1203-1205`

調査範囲は上記 checkout のソースです。同一 revision の CLI `--help` 実行や Release 配布物の照合は行っていません。
