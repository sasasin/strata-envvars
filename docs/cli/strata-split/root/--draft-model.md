# `strata-split-N --draft-model`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-split` |
| コマンド | `strata-split-N`（`--serve` モード） |
| オプション | `--draft-model` |
| 別名 | なし |
| 値 | DFlash2 runtime pack のファイルパス（文字列） |

## 役割

`--draft-model` は、`strata-split-N` が `--draft dflash2` で起動するときに使う DFlash2 runtime pack を指定します。指定した pack は GPU に読み込まれ、DFlash2 drafter が各 lane の次トークン候補を作るために使います。`--draft mtp` のままではこの値は読み込まれず、単独では DFlash2 を有効にしません（`engine/src/split/tools/sfnx.cpp:67, 86-88, 108-114`）。

## 使い方

```sh
# 2 カード用 split engine を DFlash2 で起動する例
strata-split-2 --serve --native /models/target.gguf \
  --draft dflash2 --draft-model /models/dflash2.pack \
  --draft-vocab /models/draft_vocab.bin
```

`--draft-vocab` を省略する場合は `--mtp DIR` が必要で、`DIR/draft_vocab.bin` が語彙ファイルとして使われます。実行ファイル名の `N` はビルド対象カード数に応じた `2`、`3`、`4` です（`engine/src/split/CMakeLists.txt:116-121`）。

## 値と既定値

- 値は `--draft-model` の直後の argv 要素を文字列として受け取ります。別名、既定の pack パス、拡張子による選別はありません（`engine/src/split/tools/sfnx.cpp:76-81, 87`）。
- 同じオプションを複数回指定すると、parser が `draft_model` に順次代入するため最後の値が残ります（`engine/src/split/tools/sfnx.cpp:76-81, 87`）。
- オプション自体は必須ではありません。`--draft dflash2` が有効になった場合に限って、空でない値が必要です。値がない場合は parser が `--draft-model needs a value` を出します。値が空文字列の場合も、後段の必須引数検査で拒否されます（`engine/src/split/tools/sfnx.cpp:78-80, 110-112`）。
- 指定値は DFlash2 runtime pack として開かれます。pack は `DF2P` magic と version 1 を持ち、shape がこの engine 対応である必要があります。パスの存在、pack の形式・shape、VRAM への適合は pack 読み込み時に検査されます（`engine/src/core/dflash2.cpp:187-196, 231-243`）。

## 実行時の動作

1. parser は `--draft-model` の値を `Args::draft_model` に保存します。draft source の初期値は `mtp` です。引数解析後に非空の `FNX_DRAFT` があれば、CLI の `--draft` より優先して draft source を置き換えます。従って `FNX_DRAFT=mtp` の場合は `--draft-model` を指定しても DFlash2 pack は読み込まれません。一方、`FNX_DRAFT=dflash2` なら `--draft-model` が必要です（`engine/src/split/tools/sfnx.cpp:65-68, 73-88, 107-114`）。
2. DFlash2 選択時は `--native` と `--draft-model` に加え、`--draft-vocab FILE` または `--mtp DIR` のいずれかが必要です。後者だけを指定した場合、語彙ファイルは `DIR/draft_vocab.bin` に補完されます（`engine/src/split/tools/sfnx.cpp:110-114`）。
3. 起動時に draft vocabulary を int32 token ID の列として読み、空ファイルと target model の語彙範囲外の ID を拒否します。native model の `output.weight` が Q8_0 であることも要求し、その token 行と token embedding を DFlash2 bridge に渡します（`engine/src/split/tools/sfnx.cpp:1061-1090`）。
4. bridge は pack を読み込み、対応する構造か検査して GPU に配置します。drafter と draft head は最初のカードに置かれ、`--batch` の lane 数分の drafter を確保します。この確保は engine の生成より先に行われるため、その後の K/V pool に使えるカードメモリに影響します（`engine/src/split/tools/sfnx.cpp:1117-1133`; `engine/src/split/src/df2_bridge.hpp:1-5, 30-34`; `engine/src/split/src/df2_bridge.cpp:44-89`; `engine/src/core/dflash2.cpp:187-243`）。

## 適用条件と副作用

- `--draft-model` が実際に参照されるのは最終的な draft source が `dflash2` の場合だけです。`--draft` に別の値を指定しても、非空の `FNX_DRAFT` があれば環境変数側が選択を上書きします（`engine/src/split/tools/sfnx.cpp:107-114`）。
- DFlash2 を含むビルドである必要があります。split engine は opt-in で、DFlash2 bridge は `strata_kernels` と `strata_core` の target がある場合にリンクされます。非対応ビルドでも parser は引数を受理しますが、DFlash2 を attach する段階で `this engine was built without DFlash2` になります（`engine/CMakeLists.txt:839-844`; `engine/src/split/CMakeLists.txt:104-114, 132-149`; `engine/src/split/src/engine.cu:1222-1249`）。
- 有効時は pack と補助 buffer を GPU VRAM に確保します。pack が開けない、形式・shape が不正、pack が VRAM に収まらない、draft vocabulary が開けない・空・範囲外などで起動が失敗します（`engine/src/core/dflash2.cpp:190-196, 231-243`; `engine/src/split/src/df2_bridge.cpp:55-65, 76-88`; `engine/src/split/tools/sfnx.cpp:1064-1074`）。
- ファイルは読み取り専用で開かれます。pack や vocabulary を書き換える処理は確認できません（`engine/src/core/dflash2.cpp:190-192`; `engine/src/split/tools/sfnx.cpp:1064-1068`）。

## 出力とエラー

- 値を伴わない引数、`--draft` の不正値、DFlash2 選択時の必須引数不足など、引数検査段階の例外は `sfnx: <理由>` を stderr に出して終了コード 2 で戻ります（`engine/src/split/tools/sfnx.cpp:78-80, 105-116`; `engine/src/split/tools/sfnx.cpp:1107-1115`）。
- model / pack / vocabulary 読み込みや attach 中の失敗は、stdout に `ERR <理由>`、stderr に `sfnx: failed: <理由>` を出して終了コード 1 で終了します（`engine/src/split/tools/sfnx.cpp:1094-1103, 1117-1135`）。
- 読み込み成功時は stderr に DFlash2 の card、draft token 数、drafter 数、VRAM 使用量を表示します（`engine/src/split/tools/sfnx.cpp:1089-1091`）。

## 根拠

- `engine/src/split/tools/sfnx.cpp:65-117` — option の parser、`FNX_DRAFT` 上書き、必須条件、語彙ファイル既定位置。
- `engine/src/split/tools/sfnx.cpp:1059-1091` — vocabulary と target model head の検査、pack の bridge への引き渡し、成功時出力。
- `engine/src/split/tools/sfnx.cpp:1117-1135` — pack 読み込みと engine 初期化の順、失敗処理。
- `engine/src/split/src/df2_bridge.cpp:44-91` — pack 読み込み、GPU 確保、lane ごとの drafter と head の構築。
- `engine/src/core/dflash2.cpp:187-268` — pack のファイル形式・shape・VRAM・upload 検査。
- `engine/src/split/CMakeLists.txt:104-114, 116-150` および `engine/src/split/src/engine.cu:1222-1249` — DFlash2 のビルド条件と attach 条件。

調査範囲は上記 commit の Strata ソースです。CLI を実行した help 出力や build 済み実行ファイルの実地挙動は確認していません。
