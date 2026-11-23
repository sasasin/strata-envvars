# `strata-hy4-sycl --gen`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4-sycl` |
| コマンド | `strata-hy4-sycl`（ルート） |
| オプション | `--gen` |
| 別名 | なし |
| 値 | 整数として `atoi` で変換される値。正の値で生成ループを実行する。 |

## 役割

オフライン実行で prompt token 列を prefill した後に生成する token 数の上限を指定します。通常経路では各ステップで logits の最大値に対応する token を選びます。`--draft dfly2` を指定し、かつ `--gen` が正なら DFly2 speculative decoding の経路を選びます。`--serve` は別のサービス経路です。

## 使い方

`ids.txt` に入力 token ID を用意し、既存の空ディレクトリ `./gen-run` を出力先として実行する例です。

```sh
strata-hy4-sycl --model model.strata --tokens ids.txt --gen 32 --out ./gen-run
```

## 値と既定値

`--gen` を省略したときの内部値は `0` です。値は `atoi` で変換され、正の値かどうかだけで通常生成経路への分岐が決まります。明示的な範囲検証や数値形式の検査はありません。したがって `0` や負数では通常の生成ループに入りません。無効な文字列の扱いは `atoi` に委ねられています。別名は登録されていません。parser は同じ引数を複数回受け取ると、その都度 `gen` に代入します。

## 実行時の動作

オフライン経路は `--model` を必須とし、`--load-only` でない場合は `--tokens` から整数列を読みます。読み込んだ列が空なら `no tokens` を出して終了コード 2 となります。`--gen` が 0 以下でも、このモデル読み込み・prefill を省略する指定にはなりません。`--load-only` は `--gen` にかかわらず expert 設定後に終了するため、生成しません。

`--ctx` を正の値で指定していない場合、KV cache 等に渡す context 上限は `max(T0 + gen + 16, 131072)`（`T0` は入力 token 数）になります。`--ctx` が正ならその値が使われます。

prefill 後、通常経路では最後の prompt 位置の logits の argmax を最初の生成 token とし、最大 `gen` 回まで token を追加します。EOS token も出力列に含めてから停止し、EOS 以外なら次の forward と argmax を繰り返します。`--draft dfly2` かつ `gen > 0` では speculative branch が通常 branch より先に選ばれ、`gen` を `Spec::run` の生成上限として渡します。

`--draft dfly2` を使わない場合は、正の `--detcheck` または `--wincheck` がそれぞれの検査 branch を選ぶため、通常の `gen > 0` 生成 branch には進みません。speculative branch はこれらの検査 branch より先に判定されます。

## 適用条件と副作用

`--serve` が有効な場合は `--gen` の解析後にサービス処理へ進み、`ServeOpts` に生成数を渡しません。serve は request ごとの `q.max_new` と context の残りを使って生成上限を決めるため、この文書のオフライン生成指定とは別です。

オフライン生成では標準出力に `generated ids:` を出し、`--out` のディレクトリ（省略時 `.`）に `gen_ids.txt` を書きます。生成が始まらない場合でも通常完了すれば `top5.txt` を書きます。`HY4S_MARGINS` が設定され、通常の greedy 生成で margin が記録された場合は `margins.txt` も書きます。これらは `std::ofstream` で開かれ、既存ファイルがあれば切り詰めて上書きします。出力ディレクトリを作成する処理はなく、出力 stream の open/write 失敗を確認する処理もありません。

## 出力とエラー

- 値を省略すると parser は標準出力に `ERR --gen needs a value` を出し、終了コード 2 で終了します。
- オフラインで `--model` がない場合は usage を標準エラーに出し、終了コード 2 です。モデル読み込み失敗は `load: ...` を標準エラーに出し、終了コード 1 です。
- 通常生成中の forward 失敗は `forward: ...` を標準エラーに出して終了コード 1 です。speculative 経路で `Spec::run` が error を返した場合は `spec: ...` を標準エラーに出し、終了コード 1 です。
- SYCL 例外は `SYCL exception: ...` を標準エラーに出し、終了コード 4 です。
- 通常完了時は生成 ID を標準出力に表示し、`gen_ids.txt` に末尾空白と改行を付けて保存します。通常経路では EOS 到達時も EOS ID を列に含みます。

## 根拠

- parser の初期値と整数変換: `engine/src/hy4flash/sycl/sy_main.cpp:104,156`。値を省略した場合と未知引数の処理: 同 `:109-116,190-197`。
- serve 分岐と `ServeOpts` への設定項目: 同 `:215-248`、`engine/src/hy4flash/sycl/sy_serve.h:28-48`。serve 側で `q.max_new` と context 残量から request の上限を決める箇所: 同 `:464-479`。オフライン側のモデル必須、model 読み込み、tokens 読み込み、空入力判定、context の既定値、speculative 分岐条件: `sy_main.cpp:250-279,260-275`。
- `--load-only` による早期終了、DFly2 初期化、生成前処理: 同 `:294-319`。
- speculative 経路の上限引数、エラー処理、表示と `gen_ids.txt` 書き込み: 同 `:379-408`。生成上限・EOS 停止・forward 上限確認を含む `Spec::run` の処理: `engine/src/hy4flash/sycl/sy_spec.h:154-179`。
- 通常経路の argmax 選択、最大回数ループ、EOS 判定、forward 失敗、表示、ファイル出力、および `detcheck` / `wincheck` 分岐との優先順: `engine/src/hy4flash/sycl/sy_main.cpp:409-410,459-460,527-551,573-601`。`top5.txt` の書き込み: 同 `:603-606`。
- context 上限が runner に渡されること: `engine/src/hy4flash/sycl/sy_main.cpp:277-283`。KV cache の割当てに `max_ctx` を使うこと: `engine/src/hy4flash/sycl/sy_graph.h:535-545,560-574`。
- SYCL 例外の表示と終了コード: `engine/src/hy4flash/sycl/sy_main.cpp:612-616`。
