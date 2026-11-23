# `strata-hy4-sycl --spec-rv`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl`（トップレベル） |
| オプション | `--spec-rv` |
| 別名 | なし |
| 値 | 整数。各 speculative draft slot で使う縮小語彙候補数 |

## 役割

DFly2 speculative decoding の draft 候補採点で、各 slot に対して使う候補数を指定します。正の値では DFly2 backbone が出した上位候補だけを後段で採点します。`0` は full `lm_head` を使う設定です。既定値は 256 です。

## 使い方

```sh
strata-hy4-sycl --model model.strata --tokens ids.txt --draft dfly2 --gen 128 --spec-rv 512
```

## 値と既定値

- `SpecCfg.rv` の既定値は `256` です（`engine/src/hy4flash/sycl/sy_spec.h:21-30`）。
- 引数は `atoi` で整数化され、値の範囲や変換結果を検証する処理はありません（`engine/src/hy4flash/sycl/sy_main.cpp:179-189`）。数値でない文字列も `atoi` の結果 `0` として扱われ、明示的な拒否にはなりません。
- DFly2 の候補数 `N` は `min(rv, 1024)` です。正の値が 1024 を超える場合は 1024 に制限されます（`engine/src/hy4flash/sycl/sy_dfly2.h:692-700`）。
- `N <= 0` の場合は候補リストを使わず、full `lm_head` を実行する分岐に入ります（同 `:650-657`, `:660-688`, `:752-783`）。したがって `0` は明示的に全語彙を使い、負数も同じ実装経路になります。
- 同じ option を複数回指定した場合は parser のループで都度同じ設定値へ代入されるため、最後の指定が残ります（`engine/src/hy4flash/sycl/sy_main.cpp:105-115`, `:179-189`）。

## 実行時の動作

parser は値を `scfg.rv` に格納します。local 実行では DFly2 の `Spec` 構築時に `cfg.rv` が `DFly2.rv` へコピーされます（`engine/src/hy4flash/sycl/sy_spec.h:65-71`）。serve 実行では `scfg` が `ServeOpts.spec` に渡され、speculative decoding が有効な場合に `Spec` へコピーされます（`engine/src/hy4flash/sycl/sy_main.cpp:215-248`; `engine/src/hy4flash/sycl/sy_serve.h:303-308`）。

正の `N` では backbone の `lm_head` から各 slot の上位 `N` 個の token ID を得て、その候補を DFly2 の hidden-correction scorer で採点します（`engine/src/hy4flash/sycl/sy_dfly2.h:650-657`, `:660-688`）。greedy draft はその候補内から上位候補を選び（同 `:824-849`）、確率的 draft は同候補上で分布を作ります（`engine/src/hy4flash/sycl/sy_dfly2.h:861-865`）。`N <= 0` では各 slot の full `lm_head` logits を使う分岐です（同 `:772-783`, `:835-840`）。この値は候補生成・採点側の幅を変え、実行 token 数を指定するものではありません。

## 適用条件と副作用

- local 実行で speculative decoding に入るのは `--draft dfly2` かつ `--gen` が正のときです（`engine/src/hy4flash/sycl/sy_main.cpp:279-280`, `:379-382`）。この条件を満たさない呼び出しでも option は parser に受理されますが、通常の local decode は `scfg.rv` を使用しません。
- `--serve` では parser 値が `ServeOpts.spec` に渡ります。server 側では `--draft off` でなく、model に drafter があり、chunk が 8 以上の場合に speculative 経路を準備します（`engine/src/hy4flash/sycl/sy_serve.h:248-256`, `:271-308`）。実際の request では生成枠があり画像を含まない場合に `spec->run` を使います（同 `:464-475`）。
- `--draft dfly2` に必要な DFly2 tensor が model にない場合、local 実行では初期化エラー（`sy_main.cpp:310-315`）、serve では `ERR --draft dfly2: ...` を返して終了します（`sy_serve.h:248-251`, `:271-278`）。この失敗は `--spec-rv` 固有の範囲検査ではありません。
- 文書化された既定値・候補数上限はソースから確認できますが、特定の値による速度や生成品質の優劣はこの調査では測定していません。

## 出力とエラー

- 値を省略すると `nxt()` が stdout に `ERR --spec-rv needs a value` を出し、終了コード 2 で終了します（`engine/src/hy4flash/sycl/sy_main.cpp:107-115`, `:186`）。
- `--draft dfly2` の local 実行では初期化成功時に stderr に `[dfly2] drafter ready (... rv=<値> ...)` を出します（`engine/src/hy4flash/sycl/sy_main.cpp:310-316`）。
- speculative 実行中のエラーは local では stderr の `spec: ...`、serve では protocol 出力の `ERR spec: ...` として扱われます（`engine/src/hy4flash/sycl/sy_main.cpp:386-390`; `engine/src/hy4flash/sycl/sy_serve.h:468-475`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:105-115,179-189` — CLI 引数読み取り、`atoi` 変換、欠落値・未知引数の処理。
- `engine/src/hy4flash/sycl/sy_spec.h:21-30,65-71` — 既定値と `SpecCfg` から `DFly2.rv` への設定。
- `engine/src/hy4flash/sycl/sy_dfly2.h:650-688,692-700,752-783,824-865` — 候補数上限、縮小候補と全語彙の採点・選択経路。
- `engine/src/hy4flash/sycl/sy_main.cpp:279-280,310-316,379-390`; `engine/src/hy4flash/sycl/sy_serve.h:248-256,271-308,464-475` — local/serve での speculative 経路適用条件と失敗出力。
