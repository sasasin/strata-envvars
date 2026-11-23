# `strata-hy4-sycl --chunk`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl`（SYCL、トップレベル） |
| オプション | `--chunk` |
| 別名 | なし |
| 値 | 整数として変換されるトークン数。正の値が指定時の設定として使われる |

## 役割

prefill で一度に処理するトークン数の上限を指定します。入力全体はこの上限以下のまとまりに分けて Runner に渡されます。値は Runner の最大 chunk として初期化にも使われるため、prefill の分割だけでなく、そのサイズに応じた作業バッファの確保にも関係します。オフライン実行と `--serve` のどちらにも適用されます（`engine/src/hy4flash/sycl/sy_main.cpp:215-248,278-283`）。

## 使い方

```sh
# トークン ID ファイルを使うオフライン実行で、prefill を最大 1024 トークンずつ処理
strata-hy4-sycl --model SQ32.strata --tokens ids.txt --chunk 1024

# engine line protocol サーバーの prefill 上限を 1024 トークンにする
strata-hy4-sycl --serve --native SQ.strata --chunk 1024
```

## 値と既定値

- `--chunk` は次の引数を `atoi` で整数変換して受け取ります。別名はありません（`engine/src/hy4flash/sycl/sy_main.cpp:104-115,158`）。
- 初期値は `0` です。指定値が正のときだけその値が採用され、それ以外は GPU の global memory が 11 GiB 以上なら `4096`、未満なら `2048` になります。オフライン経路では `engine/src/hy4flash/sycl/sy_main.cpp:276-283`、serve 経路では `:226-230` で決まります。
- 0、負数、または `atoi` が 0 を返す入力（例: 数字で始まらない文字列）はエラーにはならず、上記の既定値に戻ります。明示的な正の値に対する最小値・最大値の検証は見当たりません。複数回指定した場合は引数解析中に同じ変数へ順に代入されるため、最後に解析された値が残ります（`:105-116,158`）。
- 値を省略すると `nxt()` が標準出力へ `ERR --chunk needs a value` を出して終了コード `2` で終了します（`:108-115,158`）。

## 実行時の動作

オフライン経路では決定した値を `Tc` として `Runner` に渡し、prefill ループは残り入力数との小さい方を各回の処理トークン数 `T` にします。したがって最終 chunk は指定値より小さくなることがあります（`engine/src/hy4flash/sycl/sy_main.cpp:276-283,344-348`）。通常の生成 decode は1トークンずつ `forward_chunk` を呼びます（`:538-548`）。

`--serve` 経路も `ServeOpts::chunk` に設定した値を使って Runner を初期化します。serve の prefill でも `min(r.Tc, 残りトークン数)` で分割します（`engine/src/hy4flash/sycl/sy_main.cpp:215-248`; `engine/src/hy4flash/sycl/sy_serve.h:258-263,428-432`）。

Runner は `Tc` を使って複数の GPU 作業領域と Engram 用ホスト・デバイスバッファを確保します。たとえば `Tc` に比例する scratch、index、expert、Engram 領域があります（`engine/src/hy4flash/sycl/sy_graph.h:490-510,536-576,614-617,647-652`）。そのため chunk を大きくすると確保量も増えますが、必要メモリ量や性能への具体的な影響はこのコードの静的確認だけでは数値化できません。

## 適用条件と副作用

- SYCL の `strata-hy4-sycl` トップレベル parser が受け付けます。`--serve` の有無で別の parser には分かれず、同じ値がそれぞれの実行経路へ渡されます（`engine/src/hy4flash/sycl/sy_main.cpp:105-196,215-248`）。
- GPU の global memory は値を省略した場合、または変換後の値が正でない場合の既定値選択に使われます（`:230,256-259,278`）。
- serve では `--draft dfly2` と組み合わせる場合、chunk が 8 未満だと標準出力のプロトコル行 `ERR --draft dfly2 needs --chunk >= 8` を出して終了コード `2` になります。`--draft auto` では chunk が 8 未満だと speculative mode は有効になりません（`engine/src/hy4flash/sycl/sy_serve.h:248-256`）。この条件は serve 側にある検査です。
- 値を正数へ自動補正する以外の上限検証は確認できません。大きな値に対する確保可否や実行時の具体的な失敗条件は、実機・モデル・利用可能メモリに依存するため、ここでは断定しません。

## 出力とエラー

- 値の欠落は標準出力に `ERR --chunk needs a value` を出し、終了コード `2` です（`engine/src/hy4flash/sycl/sy_main.cpp:108-115,158`）。
- `--serve --draft dfly2` で chunk が 8 未満の場合は、標準出力に前述の `ERR --draft ...` 行を出し、終了コード `2` です（`engine/src/hy4flash/sycl/sy_serve.h:253-256`）。
- 不正な数値文字列や0以下は `--chunk` 固有のエラーを出さず、既定値に置き換わります（`engine/src/hy4flash/sycl/sy_main.cpp:158,230,278`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:104-115,158`: parser の初期値、引数取得、`atoi` による代入、値欠落時の処理。
- `engine/src/hy4flash/sycl/sy_main.cpp:215-248,276-283`: serve / オフライン各経路での既定値決定と Runner への引き渡し。
- `engine/src/hy4flash/sycl/sy_main.cpp:344-348,538-548`: prefill の分割と通常 decode の呼び出し単位。
- `engine/src/hy4flash/sycl/sy_graph.h:363-364,490-510,536-576,614-617,647-652`: Runner が最大 chunk を保持し、サイズ依存のバッファを確保する箇所。
- `engine/src/hy4flash/sycl/sy_serve.h:253-263,428-432`: serve の speculative decode 条件、Runner 初期化、prefill 分割。
