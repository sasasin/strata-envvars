# `strata-hy4 --dump-layer`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP） |
| オプション | `--dump-layer` |
| 別名 | なし |
| 値 | 層番号を表す整数。値は `atoi` で変換される |

## 役割

`--trace-m` が有効な比較実行で、指定した層の attention 内部バッファを追加で保存します。通常の生成ダンプを有効にするオプションではなく、層ごとの比較用ダンプに付加するデバッグ指定です。

## 使い方

```sh
# 入力 token 列の末尾付近を比較し、層 12 の attention 内部バッファも保存する
strata-hy4 --model model.strata --engram engram.strata --tokens ids.txt \
  --trace-m 4 --dump-layer 12 --out /tmp/hy4-trace
```

## 値と既定値

- 値は `atoi` で整数に変換されます。省略時の内部値は `-1` です。重ねて指定した場合は、引数走査中に後から指定した値で上書きされます（`engine/src/hy4flash/run/hy4_main.hip.cpp:373-374,439`）。
- 明示的な数値範囲チェックや、変換失敗の検出はありません。たとえば数値でない文字列は `atoi` により `0` になります。負数やモデルの層数以上の値も parser では拒否されません。
- `--dump-layer` の値は実行時に layer index `il` と等しいかで判定されます。層 index は `0` から始まるため、その範囲に一致しない値では層固有の内部バッファは選択されません（`engine/src/hy4flash/run/hy4_graph.hip.h:3415,2170,2182`）。
- 値を省略すると `nxt()` が stdout に `ERR --dump-layer needs a value` を出して `exit(2)` します（`engine/src/hy4flash/run/hy4_main.hip.cpp:377-383,439`）。

## 実行時の動作

- `--dump-layer N` だけでは層内部バッファは出力されません。値は `dump_layer_arg` に保存されますが、Runner の `dump_layer` に渡されるのは `--trace-m N` の `N > 0` 分岐内だけです。この分岐は Runner の dump を有効化し、各 token を1個ずつ `out/seq<i>` に、比較窓をまとめて `out/win` に forward します（`engine/src/hy4flash/run/hy4_main.hip.cpp:436-439,793-817`）。
- `--trace-m` の各単独 token 実行は `T=1` の decode 経路です。指定 layer では `in_cur_h.npy`、`in_qb.npy`、`in_qa.npy`、`in_ctx.npy`、`in_o.npy`、`in_gate.npy`、`in_oproj.npy` が出力対象になります。前半の attention バッファ群は decode のときだけ書かれ、`in_oproj.npy` は attention 後に書かれます（`engine/src/hy4flash/run/hy4_graph.hip.h:2108,2167-2183`）。
- 指定 layer 以外も含め、trace 分岐では `x_L<層番号>_attn.npy` と `x_L<層番号>_mlp.npy` など、通常の layer trace 用配列が各ディレクトリに保存されます。追加の `in_*` ファイルを選ぶ条件は `dump && il == dump_layer` です（`engine/src/hy4flash/run/hy4_graph.hip.h:1934-1942,2170-2183,3431-3442`）。
- 比較窓は `--trace-m` で指定したサイズのまま forward されます。`T <= 8` のときだけ attention の decode 用内部バッファ群（`in_cur_h` から `in_gate`）を保存するため、`--trace-m` が 9 以上なら `out/win` にはこの群は出ません。一方、`in_oproj.npy` は decode 条件の外で書かれるため、層番号が一致すれば `out/win` にも出ます。単独 token の `out/seq<i>` は `T=1` なので decode 用バッファ群も出力対象です（`engine/src/hy4flash/run/hy4_main.hip.cpp:810-813`、`engine/src/hy4flash/run/hy4_graph.hip.h:2108,2167-2183`）。

## 適用条件と副作用

- 対象は索引上の `strata-hy4`（CUDA/HIP）です。`strata-hy4-metal` と `strata-hy4-sycl` は別の CLI scope として索引化されています（`docs/cli/README.md:1277-1284,1358-1363,1452-1459`）。
- `--trace-m` が 0 以下または未指定なら、指定値を Runner に設定する trace 分岐に入らず、層内部バッファの追加出力はありません。別の `--dump` は logits や layer trace 用 dump を有効にしますが、通常経路では `r.dump_layer` に `dump_layer_arg` を設定していないため、それだけでは `--dump-layer` の対象層バッファを選択しません（`engine/src/hy4flash/run/hy4_main.hip.cpp:490,693-694,793-802`）。
- `--out` の既定値は `.` です。trace 分岐は `out/seq<i>` と `out/win` のディレクトリを作成してからファイルを保存します。`.npy` は `fopen(..., "wb")` で開かれるため、同名ファイルがあれば上書きされます（`engine/src/hy4flash/run/hy4_main.hip.cpp:347,485,803-813`、`engine/src/hy4flash/run/hy4_graph.hip.h:77-96`）。
- half 型の内部バッファは GPU から host にコピーして float32 に変換した後、NumPy 配列として書かれます。`maybe_dump` の float バッファも GPU から host にコピーして同形式で保存します（`engine/src/hy4flash/run/hy4_graph.hip.h:209-216,1934-1942`）。

## 出力とエラー

- 指定層の追加出力は各 `seq<i>` / `win` ディレクトリ内の `in_*.npy` ファイルです。trace 完了時は stdout に `[trace] M=... window p0=... dumped` を表示して 0 で終了します。forward が失敗すると stderr に `forward: ...` を出して 1 で終了します（`engine/src/hy4flash/run/hy4_main.hip.cpp:803-817`）。
- NPY 保存処理はファイルを開けなければ何も書かずに戻り、`fwrite` の結果も検査しません。そのため保存先の書き込み失敗が CLI エラーとして報告されるか、生成ファイルの完全性が保証されるかは、この処理からは確認できません（`engine/src/hy4flash/run/hy4_graph.hip.h:77-96`）。
- `--dump-layer` の層番号、`--trace-m` と入力 token 数の整合性について、専用の validation や範囲エラー出力は確認できませんでした。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:373-374,436-439`: 変数の初期値と parser。`atoi` を用い、別名はありません。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:377-383`: 値がない場合の stdout メッセージと終了コード。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:793-817`: `--trace-m` 分岐での dump 有効化、層値の設定、ディレクトリ作成、forward、完了・失敗経路。
- `engine/src/hy4flash/run/hy4_graph.hip.h:207-217,1934-1942`: Runner の dump 状態、GPU バッファの host copy と NPY 保存。
- `engine/src/hy4flash/run/hy4_graph.hip.h:2108,2167-2183`: decode 経路と指定 layer の attention 内部バッファ出力。
- `engine/src/hy4flash/run/hy4_graph.hip.h:3415,3431-3442`: 層 index の走査と各 layer trace 配列の保存。
