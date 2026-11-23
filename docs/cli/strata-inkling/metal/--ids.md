# `--ids`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling-metal`（Metal） |
| オプション | `--ids` |
| 別名 | なし |
| 値 | カンマ区切りの整数 token ID 列 |

## 役割

Metal 版 Inkling の診断・ベンチマーク用実行ファイルで、selfcheck と speculative decode parity check に渡すテスト prompt の token ID 列を指定する。通常の `--bench` と `--par-sweep` は別途生成した合成 prompt を使うため、これらだけを実行する場合 `--ids` は結果に使われない。parser と利用分岐は `engine/src/inkling2/metal/ink_metal_main.cpp:417-430,460-464,517-524,560-569,589-596`。

## 使い方

```sh
strata-inkling-metal --model model.strata --selfcheck --ids 200001,200004,15496
```

`--spec-check` でも同じ token 列が通常 decode と speculative decode の両方の prompt に使われる。

```sh
strata-inkling-metal --model model.strata --spec-check --ids 200001,200004,15496
```

## 値と既定値

- `--ids` の直後の引数をカンマで分割し、空でない要素ごとに `atoi` で `int32_t` の vector へ追加する。明示的な数値形式・範囲検証や変換エラー処理はこの parser にない（`engine/src/inkling2/metal/ink_metal_main.cpp:460-464`）。
- 空要素は読み飛ばす。従って空文字列やカンマだけの値では列が空のままとなり、後段で既定列 `{200001, 200004, 15496, 11, 1268, 527, 499, 30}` に置き換わる（`engine/src/inkling2/metal/ink_metal_main.cpp:511-515`）。
- `--ids` を複数回指定すると、各回の値は既存 vector に追加される。置き換えではない（`engine/src/inkling2/metal/ink_metal_main.cpp:430,460-463`）。
- `--ids` の値がない場合は `nxt()` が `missing value for --ids` を標準エラーへ出し、終了コード 2 で終了する（`engine/src/inkling2/metal/ink_metal_main.cpp:432-436,460-462`）。

## 実行時の動作

`--selfcheck` または `--dump-logits` が指定されると、runner の slot 0 をリセットし、`custom_ids` 全体を token 列として1回の forward に渡す。最終位置の logits を計算して top-1/top-5 等を表示し、NaN があれば終了コード 1 になる。`--dump-logits` を併用すると `fopen(..., "wb")` で指定先を開いて logits をバイナリ書き込みするため、既存ファイルは切り詰められる。open に失敗した場合のエラー表示・終了処理はなく、書き込みを行わず続行する（`engine/src/inkling2/metal/ink_metal_main.cpp:544-547`）。

`--spec-check` では同じ `custom_ids` から通常 decode と speculative decode をそれぞれ実行し、生成 token 列の一致数などを表示する（`engine/src/inkling2/metal/ink_metal_main.cpp:560-585`）。このオプション単独では prompt を変更せず、`--selfcheck`、`--dump-logits`、`--spec-check` のいずれかの処理経路と組み合わせて意味を持つ。`--bench` は `--prompt-len` から合成 token 列を作り、`--par-sweep` も専用の合成入力を作るため、`--ids` を参照しない（`engine/src/inkling2/metal/ink_metal_main.cpp:589-610`）。

## 適用条件と副作用

- `--model`（別名 `--native`）は必須。未指定なら usage を標準エラーに表示して終了コード 2 となる（`engine/src/inkling2/metal/ink_metal_main.cpp:444,470-473`）。
- ID の語彙範囲を検証する処理は確認できない。forward は token ID を Metal buffer にコピーし（`engine/src/inkling2/metal/ink_metal_runner.h:995-1016`）、embedding kernel はその値を埋め込み行の添字として使う（`engine/src/inkling2/metal/ink_metal_ops.metal:58-60,87-90`）。範囲外 ID の安全な扱い・GPU 側の結果はこのソースから確定できないため、モデル語彙内の ID を指定すること。
- selfcheck は入力 ID 数を1 batch として forward に渡す。`M <= 0` または `M > max_batch` は runner が `invalid batch M=...` を設定して失敗し、呼び出し側は `[ERROR] selfcheck forward: ...` を標準エラーに出して終了コード 1 とする（`engine/src/inkling2/metal/ink_metal_main.cpp:519-533`、`engine/src/inkling2/metal/ink_metal_runner.h:996-998`）。
- model load、runner 初期化、spec-check の decode が失敗した場合も、対応する `[ERROR]` を標準エラーに出して終了コード 1 となる（`engine/src/inkling2/metal/ink_metal_main.cpp:481-493,564-570`）。

## 根拠

- `engine/src/inkling2/metal/ink_metal_main.cpp:417-468` — CLI 引数解析、値の追加、未知引数のエラー処理。
- `engine/src/inkling2/metal/ink_metal_main.cpp:511-547` — 空列時の既定 prompt と selfcheck / logits 出力処理。
- `engine/src/inkling2/metal/ink_metal_main.cpp:560-610` — spec-check が prompt 列を使う箇所、および bench / parallel sweep が別入力を使う箇所。
- `engine/src/inkling2/metal/ink_metal_runner.h:996-1016` — batch サイズ検査と token ID の GPU buffer への転送。
- `engine/src/inkling2/metal/ink_metal_ops.metal:43-69,71-99` — BF16 / Q8 embedding kernel が token ID を行添字として参照する箇所。
