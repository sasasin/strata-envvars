# `strata-hy4-sycl --ctx`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl` |
| オプション | `--ctx` |
| 別名 | `--max-context`（同じ parser 変数へ代入） |
| 値 | 整数として `atoi` で変換される値 |

## 役割

推論で扱う最大 context 長を指定する。SYCL runner に渡され、KV cache と indexer 用バッファの容量を決める。`--serve` では prompt 長の上限と生成可能な残り長にも使われる。通常の一括実行と server 起動では、省略時の既定値が異なる。

## 使い方

```sh
# トークン ID ファイルを使う通常実行で、context 容量を 8192 に設定
strata-hy4-sycl --model model.strata --tokens ids.txt --ctx 8192

# line protocol server の context 容量を 8192 に設定
strata-hy4-sycl --serve --native model.strata --ctx 8192
```

## 値と既定値

- `--ctx` の後の引数を `atoi` で整数化して `max_ctx` に格納する。`--max-context` も同じ変数に格納され、両方を指定した場合は引数走査で後に現れた値が残る（`engine/src/hy4flash/sycl/sy_main.cpp:105-115,131,157`）。
- 明示的な正の値はそのまま使用される。0 以下は明示値として採用されず、通常実行では `max(T0 + gen + 16, 131072)`、`--serve` では `131072` が使われる（`engine/src/hy4flash/sycl/sy_main.cpp:226-230,276-278`）。通常実行の `T0` は読み込んだ token 数。
- 独立した範囲・最大値・最小値の validation は見当たらない。値の変換は `atoi` に委ねられ、値が不正な場合の専用エラー処理はない。正の過大値も parser では拒否されず、メモリ確保時の結果は実行環境に依存する。
- 値を省略すると `nxt()` が標準出力に `ERR --ctx needs a value` を出して終了コード 2 で終了する（`engine/src/hy4flash/sycl/sy_main.cpp:109-115`）。

## 実行時の動作

通常実行では `max_ctx` が `Runner` に渡され、KV cache の sparse slot 数、pooled index buffer、score buffer の幅や token 保持領域の確保に反映される。sparse slot 数は `max_ctx` に 8 を加えた後、16 の倍数に切り上げる（`engine/src/hy4flash/sycl/sy_main.cpp:277-283,321`、`engine/src/hy4flash/sycl/sy_graph.h:363-364,535-574`）。KV cache は `kv_host_above` との比較などにより host または device に確保されるため、`--ctx` 単独で配置先は決まらない（`engine/src/hy4flash/sycl/sy_graph.h:541-553`）。

`--serve` では `ServeOpts.max_ctx` として runner に渡り、起動時に `READY <max_ctx> stop` として標準出力にも通知される（`engine/src/hy4flash/sycl/sy_main.cpp:215-248`、`engine/src/hy4flash/sycl/sy_serve.h:258-263,331-333`）。受信 prompt の token 数が `max_ctx` 以上なら `ERR prompt exceeds context (...)` を返してその要求を処理しない。生成数は prompt と終端用の 1 token 分を差し引いた残り容量で制限される（`engine/src/hy4flash/sycl/sy_serve.h:380-387,464-472`）。

通常実行では、`--draft dfly2` かつ `--gen` が正の場合に speculative decoder に `max_ctx` が渡され、context 終端に近づくと draft 長を縮め、上限で終了する（`engine/src/hy4flash/sycl/sy_main.cpp:279,379-390`、`engine/src/hy4flash/sycl/sy_spec.h:154-182`）。

## 適用条件と副作用

- `--ctx` は `--serve` の有無にかかわらず parser が受理する。server 起動では `--native` が必須で、未指定なら標準出力に `ERR --native FILE.strata is required` を出して終了コード 2 となる（`engine/src/hy4flash/sycl/sy_main.cpp:215-220`）。
- 指定値は KV cache・indexer 等の容量計算に影響し、必要メモリを増減させる。parser に上限検査はないため、大きな値が実際に確保できるかは GPU/host の空き容量などに依存する。確保失敗時の具体的な例外・表示は SYCL runtime と allocator の経路に依存し、この調査では特定できない。
- 初期化時には context と cache の容量を含む `[runner] ... ctx ...` の診断が標準エラーに出る（`engine/src/hy4flash/sycl/sy_graph.h:628-631`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:104-115,131,157` — 初期値、値取得、`--ctx` と `--max-context` の parser 登録、値省略時の終了。
- `engine/src/hy4flash/sycl/sy_main.cpp:215-230,276-283,321` — serve への値の受け渡し、各実行経路の既定値、Runner と token 領域への適用。
- `engine/src/hy4flash/sycl/sy_graph.h:535-574,628-631` — context に応じた KV/indexer buffer の容量と診断出力。
- `engine/src/hy4flash/sycl/sy_serve.h:258-263,331-333,380-387,464-472` — server での context 通知、prompt 拒否、生成長制限。
- `engine/src/hy4flash/sycl/sy_spec.h:154-182` — speculative decode における context 終端での停止・draft 長調整。

通常実行経路で `max_ctx` を生成上限として直接検査する parser 後の分岐は確認できなかった。通常実行全体の context 超過時に allocator/runtime が返す具体的なエラー表示は、ソースから特定できない。
