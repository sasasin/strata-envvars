# `strata-inkling --prompt-ids`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（root） |
| オプション | `--prompt-ids` |
| 別名 | なし |
| 値 | トークン ID の列、または `@ファイルパス` |

## 役割

プロンプトとして与える token ID 列を指定する。CUDA/HIP 版 `strata-inkling` の直接生成と、参照 logits・batch・speculative・ring の各検査モードで使われる。通常の `--serve` と `--bench` はこの値を消費しない。

## 使い方

```sh
strata-inkling --native model.strata --prompt-ids 200002,200004,100 --gen 4
strata-inkling --native model.strata --ring-check 128 --prompt-ids @prompt-ids.txt
```

ファイル指定時は `@` の後ろのファイルを読み、その内容を ID 列として解析する。ファイルはバイナリモードで読み込まれるため、テキストの文字コード変換は行われない（`engine/src/inkling2/ink_main.cpp:957-963`）。

## 値と既定値

値は `next()` で次の argv 要素から文字列として取得する。値の指定が末尾で欠けると `missing value after --prompt-ids` を stderr に出して終了コード 2 で終了する（`engine/src/inkling2/ink_main.cpp:845-849,957-958`）。別名はない。

通常は `1,2,3` のような整数列を指定する。`parse_id_list` は基数 10 の `strtol` で各整数を読み、各整数の直後にカンマがあれば読み飛ばす。空列や数値として読み始められない要素は失敗し、`bad token id list` となる（`engine/src/inkling2/ink_serve.h:290-304`）。

このパーサは token ID の非負性、モデル語彙数内であること、`long` から `int32_t` への変換範囲を検証しない。これらを満たさない値がモデル実行でどう扱われるかは、このオプションの parser からは保証できない（同 `ink_serve.h:290-304`）。

同じ引数を複数回指定した場合は、parser が都度同じ文字列変数に代入するため最後の値が残る（`engine/src/inkling2/ink_main.cpp:841,957-963`）。空文字列は通常の直接生成では既定の固定 ID 列に切り替わる。`--dump-ref` では `1,2,3,4,5,6,7,8` が既定値（同 `ink_main.cpp:336-341,1102-1107`）。

## 実行時の動作

値が `@` で始まる場合、`@` を除いたパスを開いてファイル全体を読み、以降はその内容を ID 列として扱う。ファイルを開けない場合は `cannot read <path>` を stderr に出し、終了コード 2 で終了する（`engine/src/inkling2/ink_main.cpp:959-963`）。ファイル読み込み失敗は、後続のモード選択より前に処理される。

直接生成では、解析した ID を位置 0 から順に slot 0 の prefill batch に投入し、最後の ID の位置で logits を取得する。その logits から生成を始め、生成 token ID を stdout に出す（`engine/src/inkling2/ink_main.cpp:1102-1116,1132-1146`）。このモードで値を省略または空にすると固定 ID 列を使う。

同じ値は以下の検査モードにも渡される。検査モードは main の分岐順により `--ring-check`、`--batch-check`、`--spec-check` の順で選ばれ、選択されたモードには空でない ID 列が必要（`engine/src/inkling2/ink_main.cpp:1044-1069`）。`--dump-ref` では ID 列ごとの logits を計算し、指定した出力ファイルを `wb` で開いて書くため、既存ファイルは上書きされる（同 `ink_main.cpp:325-365`）。

`--prompt-ids` 単独ではモードを切り替えない。`--serve` では serve loop に入り値は使われず、`--bench` では bench 関数に分岐して値は使われない（`engine/src/inkling2/ink_main.cpp:1071,1093-1098`）。`--info`、`--export-tokenizer`、`--selfcheck`、`--kld-eval` も先に分岐する。これらと併記しても `--prompt-ids` は各モードに反映されない（同 `ink_main.cpp:1039-1043`）。

## 適用条件と副作用

- `--ring-check`、`--batch-check`、`--spec-check` では、値が空または ID 列として解析できない場合、エラーメッセージを stderr に出して終了コード 2 となる。`--batch-check` の場合は parse の詳細理由を表示せず、他の2モードでは得られた理由を付記する（`engine/src/inkling2/ink_main.cpp:1044-1069`）。
- 直接生成・`--dump-ref` では空文字列を既定値として扱うが、文字がある不正な ID 列は解析エラーで終了コード 2 となる（同 `ink_main.cpp:336-341,1102-1107`）。
- モデルを開く、backend を初期化する、slot を確保する、または forward 処理に失敗した場合は、該当するエラーを stderr に出して終了コード 1 となる（同 `ink_main.cpp:328-355,1078-1104`）。
- `@file` は実行中のプロセスにファイル読み取りを発生させる。`--dump-ref` と併用すると別途バイナリ出力ファイルを作成または上書きする（同 `ink_main.cpp:959-963,358-364`）。

## 根拠

- parser、`@file` の読込み、値の上書き: `engine/src/inkling2/ink_main.cpp:841-849,957-963`
- ID 列の整数変換と失敗条件: `engine/src/inkling2/ink_serve.h:290-304`
- 検査モードでの必須条件と選択順: `engine/src/inkling2/ink_main.cpp:1044-1069`
- `--dump-ref` の既定列、forward、出力ファイル: `engine/src/inkling2/ink_main.cpp:325-365`
- 直接生成での prefill と token 出力: `engine/src/inkling2/ink_main.cpp:1097-1116,1132-1146`
- serve/bench で値が使われない分岐: `engine/src/inkling2/ink_main.cpp:1071,1093-1098`
