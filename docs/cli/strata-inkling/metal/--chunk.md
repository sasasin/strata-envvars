# `strata-inkling-metal --chunk`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling-metal` |
| コマンド | `strata-inkling-metal` |
| オプション | `--chunk` |
| 別名 | `--batch` |
| 値 | 整数として読み取られる値。runner では実効値の最低値が 64。作業セット条件により最大 256 までに補正される場合がある |

## 役割

モデル処理時に runner が扱う最大 batch token 数を設定する。通常の生成では prompt prefill をこの値以下のまとまりに分割し、runner の作業領域も実効値に合わせて確保する。

## 使い方

```sh
# モデルを読み込み、prompt 処理の chunk 上限を 128 に設定して benchmark を実行
strata-inkling-metal --model model.strata --chunk 128 --bench
```

`--batch` も同じ値を設定する別名である。

## 値と既定値

- 値は必須。省略時は CLI 初期値の `256` が使われる。値の取得に失敗すると `missing value for --chunk`（または `--batch`）を stderr に出し、終了コード 2 で終了する。
- 値は `atoi` で整数化される。専用の数値形式・正の範囲検査は parser にないため、整数として解釈できない文字列は 0 相当となり、負数もそのまま runner に渡る。
- runner は `max_batch = max(64, batch_cap)` とする。このため 64 未満、0、負数、または整数として読めない値は実効値 64 になる。通常の上限値を超える入力に対する parser の上限検査はない。
- 作業セットが `fixed_need` 以下になる分岐では、実効値が 256 より大きければ 256 に下げる。したがって実際に使われる値は指定値だけでは確定せず、Metal の作業セット条件にも依存する。
- 同じオプションを複数回指定したときは、引数走査中に同じ変数へ順番に代入されるため最後の値が残る。

## 実行時の動作

parser は `--chunk` と `--batch` のどちらも `max_batch` に値を代入し、その値を `runner.init` に渡す（`engine/src/inkling2/metal/ink_metal_main.cpp:432-468, 489-493`）。runner は最低値を 64 に補正し、Metal 作業セットの余裕が `fixed_need` 以下の場合には 256 を超える値を 256 に下げる（`engine/src/inkling2/metal/ink_metal_runner.h:230-239, 385-411`）。実効値は workspace buffer のサイズにも使われ、起動時の `runner ready` ログでは `batch=<実効値>` として stderr に表示される（同 `:457-519, 758-764`）。

通常の prompt prefill は `min(max_batch, 2048)` token ごとに区切って `forward_batch` へ渡す。並列 benchmark の prefill は `min(max_batch, 256)` で区切るため、値を 256 より大きくしてもこの経路の prefill chunk は 256 を超えない（`engine/src/inkling2/metal/ink_metal_main.cpp:138-159, 362-387`）。一方 `--selfcheck` は入力 token 全体を一度に `forward_batch` に渡し、runner は `M <= max_batch` を要求する。したがって `--selfcheck --ids` で作る入力が実効値を超えると `invalid batch M=...` で失敗する（同 `:517-533`; `engine/src/inkling2/metal/ink_metal_runner.h:995-1003`）。

この値は buffer 数や並列 slot 数を直接指定するものではない。buffer は実効 batch 値を使って確保されるため、大きな値は作業領域の確保量にも影響する（`engine/src/inkling2/metal/ink_metal_runner.h:457-519`）。

## 適用条件と副作用

- 対象は `strata-inkling-metal` の Metal 実装。CUDA/HIP 側の `strata-inkling` にある同名オプションの挙動をこの文書には含めない（parser: `engine/src/inkling2/metal/ink_metal_main.cpp:417-451`）。
- 値は runner 初期化時に反映される。Metal の作業セットが厳しい場合は値が 256 に制限され、実効値が指定値と異なることがある（`engine/src/inkling2/metal/ink_metal_runner.h:385-411`）。
- 実効値に応じて多数の workspace buffer のサイズが決まるため、値を大きくすると確保対象のメモリ量も増える。個々の buffer 確保が失敗した場合の全経路・表示は、このオプション固有のエラーとしては確認できなかった（同 `:457-519`）。

## 出力とエラー

- 値を省略すると `missing value for --chunk`（別名指定時は `--batch`）を stderr に出して終了コード 2 となる（`engine/src/inkling2/metal/ink_metal_main.cpp:432-437`）。
- 起動後、runner 準備完了時に実効値を含む `[ink_metal] runner ready: ... batch=...` を stderr に出す（`engine/src/inkling2/metal/ink_metal_runner.h:758-764`）。
- 不正な数値文字列や範囲外値に対する専用エラーはなく、`atoi` の結果と runner の下限・作業セット補正が使われる（`engine/src/inkling2/metal/ink_metal_main.cpp:450`; `engine/src/inkling2/metal/ink_metal_runner.h:238, 404-411`）。
- `--selfcheck` の入力 batch が実効値を超えると `forward_batch` が `invalid batch M=<値>` を設定し、呼び出し側が `[ERROR] selfcheck forward: ...` を stderr に出して終了コード 1 で終了する（`engine/src/inkling2/metal/ink_metal_runner.h:995-999`; `engine/src/inkling2/metal/ink_metal_main.cpp:529-534`）。

## 根拠

- `engine/src/inkling2/metal/ink_metal_main.cpp:417-468` — CLI 初期値、必須値取得、`atoi` 変換、`--chunk` / `--batch` parser、未知引数の失敗経路。
- `engine/src/inkling2/metal/ink_metal_main.cpp:489-493` — parser 値を runner 初期化へ渡し、初期化失敗時に stderr と終了コード 1 を返す箇所。
- `engine/src/inkling2/metal/ink_metal_main.cpp:138-159, 362-387` — 通常 prefill と並列 benchmark prefill の分割サイズ。
- `engine/src/inkling2/metal/ink_metal_main.cpp:517-534` — selfcheck が全入力を一度に処理し、失敗を表示する箇所。
- `engine/src/inkling2/metal/ink_metal_runner.h:230-239, 385-411` — runner の下限補正と作業セット条件による 256 への補正。
- `engine/src/inkling2/metal/ink_metal_runner.h:457-519, 758-764, 995-1003` — workspace 確保、実効値ログ、`forward_batch` の batch 検査。

調査範囲は上記 Strata checkout のソースであり、Metal 実機での動作・メモリ確保成否は実行確認していない。
