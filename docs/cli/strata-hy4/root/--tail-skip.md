# `strata-hy4 --tail-skip`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP。`--serve` を付ける場合も同じ root parser） |
| オプション | `--tail-skip` |
| 別名 | なし |
| 値 | 整数として `atoi` で変換。CLI 値の範囲検証なし |

## 役割

HY4 の MoE 推論で、GPU に常駐していない CPU/cold tier の expert を一部スキップする opt-in 設定です。選ばれた expert を一律に省くのではなく、decode/verify の窓内でその expert が選択された最小 rank が指定値以上の場合に、その expert の CPU 側処理を外します。品質や出力が変わり得ます。

## 使い方

```sh
# rank 7 以上で対象となる CPU/cold-tier expert をスキップして生成
strata-hy4 --model model.strata --tokens prompt.tokens --gen 64 --tail-skip 7

# 同じ設定を serve 経路で使用
strata-hy4 --serve --model model.strata --tail-skip 7
```

## 値と既定値

- オプションを省略した場合の初期値は `0` で、環境変数による上書きがなければ無効です（`engine/src/hy4flash/run/hy4_main.hip.cpp:366`、`engine/src/hy4flash/run/hy4_graph.hip.h:230-231`）。
- 値は `atoi` で読みます。したがって整数として読めない文字列は通常 `0` になり、数値の後ろに文字がある入力も数値部分が変換されます。ソースに明示的な CLI 値の validation はありません（`engine/src/hy4flash/run/hy4_main.hip.cpp:375-384,415`）。
- `--tail-skip` を複数回指定すると、parser が同じ変数へ順に代入するため最後の値が残ります（同 `:375-384,415`）。値を省略すると `nxt()` が `ERR --tail-skip needs a value` を stdout に出し、flush 後に終了コード 2 で終了します（同 `:377-383`）。
- 実行時の有効値は 0 以下なら `STRATA_HY4_TAIL_SKIP` から読みます。環境変数は空でない場合に `atoi` され、1〜15 の値だけが採用されます。それ以外は 0 のままです（`engine/src/hy4flash/run/hy4_graph.hip.h:1585-1591`）。正の CLI 値は環境変数より優先されます。
- CLI 値自体には 1〜15 の範囲制限がありません。正の 1〜15 は rank 閾値として作用します。16 以上も有効値として報告されますが、routing slot の rank は 0〜15 なのでスキップ条件を満たしません（同 `:2194-2204,2211-2217,2305-2313`）。負数や 0 は CLI から無効化を強制せず、環境変数が有効ならその値へフォールバックします。

## 実行時の動作

parser は指定値を `tail_skip_arg` に保存し、serve 時は `ServeOpts.tail_skip` 経由で、通常経路では `Runner.tail_skip` に渡します（`engine/src/hy4flash/run/hy4_main.hip.cpp:415,555-569,692-700`、`engine/src/hy4flash/run/hy4_serve.hip.h:43-53,307-310`）。Runner の初期化時に前述の環境変数フォールバックを行い、値が正なら stderr に有効化メッセージを出します（`engine/src/hy4flash/run/hy4_graph.hip.h:1585-1595`）。

実際の判定は `run_hybrid_miss_layer` 内で `tail_skip > 0 && T <= 16` の場合だけ有効です。expert ごとに、その窓の最大16行・各16 routing slot における最小 rank を集計します。GPU 常駐ではなく tier 2 以上の miss で、窓内の最小 rank が閾値以上なら候補収集から除外し、CPU pair mask でも対象 pair を使わないようにします（`engine/src/hy4flash/run/hy4_graph.hip.h:2186-2217,2303-2317`）。このため、窓内のどれかの行で同じ expert が閾値より低い rank で選ばれると、その expert は窓全体でスキップ対象になりません。

## 適用条件と副作用

- 効果があるのは `run_hybrid_miss_layer` を通る decode/verify の hybrid miss 処理で、かつ `T <= 16` の場合です。値を有効にしても、該当する CPU/cold-tier miss がなければスキップ処理は発生しません（`engine/src/hy4flash/run/hy4_graph.hip.h:2186-2195,2211-2217`）。
- 対象 expert の演算を省くため、出力品質・生成結果が変化する可能性があります。ソースコメントも「100% lossless」は無効時に限るとしています（同 `:230-231`）。
- 有効値が正なら `stderr` に `[runner] STRATA_HY4_TAIL_SKIP=... is ON (opt-in)` の行を出します（同 `:1593-1595`）。カウンタ `tail_skipped_pairs` は該当 pair 数を記録しますが、この調査範囲で当該カウンタの出力箇所は確認できません（同 `:232,2310-2313`）。
- この文書は CUDA/HIP の `strata-hy4` parser を対象とします。Metal と SYCL は別 parser/scope であり、このオプションの対象としては索引に掲載されていません（`docs/cli/README.md:1277-1281,1344-1347,1358-1361,1452-1455`）。

## 出力とエラー

- 値なしの場合は stdout に不足値のエラーを出し、終了コード 2 で終了します（`engine/src/hy4flash/run/hy4_main.hip.cpp:377-383`）。
- オプション名が未知の場合は stderr に `unknown arg ...` を出して終了コード 2 です。serve 時には追加で stdout に `ERR unknown flag ...` を出します（同 `:498-504`）。
- 値の範囲外を理由としたエラーはありません。CLI の正の値は範囲検証されず、環境変数だけが 1〜15 に制限されます（`engine/src/hy4flash/run/hy4_main.hip.cpp:415`、`engine/src/hy4flash/run/hy4_graph.hip.h:1586-1595`）。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:366,375-384,415` — 初期値、引数値の取得と変換、値なし時のエラー。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:555-569,692-700`、`engine/src/hy4flash/run/hy4_serve.hip.h:43-53,307-310` — serve と通常実行で Runner へ値を渡す処理。
- `engine/src/hy4flash/run/hy4_graph.hip.h:230-232,1585-1595` — デフォルト、環境変数の読み込み・範囲確認、有効化ログ。
- `engine/src/hy4flash/run/hy4_graph.hip.h:2186-2217,2303-2317` — 適用条件、rank 集計、対象 expert/pair の除外。
- `docs/cli/000_cli_tools.md:11` と `docs/cli/README.md:1277-1281,1344-1347` — ツール ID、parser、`root/` scope、および索引リンク。索引上の掲載と parser 定義を照合しました。
