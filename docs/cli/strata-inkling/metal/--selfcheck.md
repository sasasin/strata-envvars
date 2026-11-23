# `strata-inkling-metal --selfcheck`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling-metal` |
| オプション | `--selfcheck` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

Metal 版 Inkling-2-Mini エンジンでモデルを読み込み、runner の初期化後に入力 token 列を1回実行して、得られた logits に非有限値（NaN / Inf）がないか確認します。これは参照実装との一致や生成品質を比較する検査ではなく、forward が成功して logits が有限であることを確認する簡易チェックです。Metal backend の `selfcheck()` 仮想関数が行う device/kernel 検査とは別経路で、この CLI フラグからその関数は呼び出されません（`engine/src/inkling2/metal/ink_metal_main.cpp:517-548`、`engine/src/inkling2/metal/ink_metal_backend.mm:444-458`）。

## 使い方

```sh
# 読み取り可能な Inkling `.strata` モデルを Metal で forward し、logits の有限性を確認
strata-inkling-metal --model /path/to/model.strata --selfcheck
```

`--native` は `--model` の別名です。モデル指定は必須です。検査入力を変える場合は `--ids` を併用できます（`engine/src/inkling2/metal/ink_metal_main.cpp:444-445,460-463,470-473,511-515`）。

## 値と既定値

値を取りません。parser は `--selfcheck` を受け取るたびにフラグを true にします。複数回指定しても同じ状態です。値を続けて書く構文はなく、その値は別の引数として解析されます（`engine/src/inkling2/metal/ink_metal_main.cpp:432-467`）。

指定しない場合、この selfcheck forward は実行されません。`--model` / `--native` でモデルファイルを指定しない場合は usage を stderr に表示して終了コード 2 となります（`engine/src/inkling2/metal/ink_metal_main.cpp:470-473`）。

## 実行時の動作

1. `--model` または `--native` のパスを読み取り専用で開き、`.strata` ヘッダーと manifest 等を読み込みます。既定では続けてモデルファイルのページを warm します。`--no-warm` はこの warm を省きますが、selfcheck 自体は省きません（`engine/src/inkling2/metal/ink_metal_main.cpp:444,458,481-488`、`engine/src/inkling2/metal/ink_metal_common.h:356-382,829-848`）。
2. Metal runner を初期化し、shader library と pipeline を用意します。初期化に失敗すると `[ERROR] runner init: ...` を stderr に出して終了コード 1 です（`engine/src/inkling2/metal/ink_metal_main.cpp:475-493`、`engine/src/inkling2/metal/ink_metal_runner.h:230-255`）。
3. `--ids` がなければ固定の8 token `[200001, 200004, 15496, 11, 1268, 527, 499, 30]` を使います。指定があればその token 列を使います。slot 0 を reset し、全 token を位置 0 から順に与える1回の forward を実行して、最後の位置の logits と top-1 token を求めます（`engine/src/inkling2/metal/ink_metal_main.cpp:460-463,511-531`）。
4. stdout に入力長 `P`、GPU 実行時間、非有限 logits 数、top-1 と top-5 を `[SELFCHECK]` 行で表示します。非有限値が1つ以上あれば終了コード 1、すべて有限なら後続処理がなければ終了コード 0 です（`engine/src/inkling2/metal/ink_metal_main.cpp:535-548,616`）。

`--selfcheck` は他のモードを排他しません。たとえば `--bench`、`--spec-check`、`--par-sweep` も指定すると selfcheck の後にそれらも実行されます。`--image` が指定されている場合は selfcheck より先に画像 encode を実行します。`--dump-logits PATH` は selfcheck と同じ forward を発生させ、成功時に logits を float のバイナリとして書きます。保存先の open に失敗した場合も、その失敗を報告せず処理を続けます（`engine/src/inkling2/metal/ink_metal_main.cpp:496-509,517-548,560-614`）。

## 適用条件と副作用

Metal 版の `strata-inkling-metal` に適用されます。CMake では Metal サブディレクトリを `APPLE` 条件で追加します（`engine/src/inkling2/CMakeLists.txt:203-205`）。モデルファイルを開いて読み、ページ warm と Metal 上の forward を行います。`--selfcheck` 単独ではファイルを書き出しません。`--dump-logits` を併用したときは指定先への書き込みを試みます。

`--ids` の各項目は parser で `atoi` により整数化され、空のカンマ区切り要素は捨てられます。この parser 箇所では token ID の範囲検証はありません（`engine/src/inkling2/metal/ink_metal_main.cpp:460-463`）。不正・不適合 token の後続処理の挙動はこの引数解析だけからは確定できないため、利用する ID は対象モデルの token ID として有効なものにしてください。

## 出力とエラー

- モデルを開けない、形式が不正、読み込みに失敗する場合はモデル読込エラーを stderr に出し、終了コード 1 です（`engine/src/inkling2/metal/ink_metal_main.cpp:481-486`、`engine/src/inkling2/metal/ink_metal_common.h:356-393`）。
- forward が失敗すると `[ERROR] selfcheck forward: ...` を stderr に出して終了コード 1 です。forward が成功しても logits に NaN / Inf があれば `[SELFCHECK]` の結果行を出した後、終了コード 1 です（`engine/src/inkling2/metal/ink_metal_main.cpp:531-543`）。
- 有限値を得たことは表示されますが、期待 logits との比較・許容誤差・独立した正解値検証はこの CLI 経路にはありません（`engine/src/inkling2/metal/ink_metal_main.cpp:535-543`）。

## 根拠

- `engine/src/inkling2/metal/ink_metal_main.cpp:417-467` — CLI parser、フラグ設定、`--ids` の token 変換、未知引数のエラー。
- `engine/src/inkling2/metal/ink_metal_main.cpp:470-493` — モデル必須条件、Metal context、モデル読込、既定 warm、runner 初期化と失敗経路。
- `engine/src/inkling2/metal/ink_metal_main.cpp:511-548` — 既定入力、selfcheck forward、logits 検査と表示、`--dump-logits` の書き込み。
- `engine/src/inkling2/metal/ink_metal_main.cpp:560-616` — 他モードとの併用と最終終了コード。
- `engine/src/inkling2/metal/ink_metal_runner.h:230-255` — runner の Metal shader / pipeline 初期化。
- `engine/src/inkling2/metal/ink_metal_common.h:356-393,829-848` — モデルファイルの open / header 検査と warm 処理。
- `engine/src/inkling2/metal/ink_metal_backend.mm:444-458` — backend の別系統の `selfcheck()` 実装。CLI の `--selfcheck` からは呼ばれない。
- `engine/src/inkling2/CMakeLists.txt:203-205` — Metal backend を Apple 環境で構成に含める条件。
