# `--trace-off`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（トップレベル、CUDA/HIP） |
| オプション | `--trace-off` |
| 別名 | なし |
| 値 | 整数。`atoi` で変換される |

## 役割

`--trace-m` が有効なとき、入力 token 列の末尾に残す token 数を指定する。trace window は `T0 - M - trace_off` から始まり、末尾に `trace_off` 個を残した `M` 個の token を一つずつ処理した結果と、まとめて処理した結果を比較できる形で dump する。単独では処理を切り替えず、trace window の位置調整に使う。

## 使い方

```sh
# token 列の末尾に 4 token を残し、その直前の 8-token window を trace する
strata-hy4 --model model.strata --tokens prompt.ids --trace-m 8 --trace-off 4 --out /tmp/hy4-trace
```

`prompt.ids` は `--tokens` が読む整数 token 列である。window を入力範囲内に収める値を指定すること。

## 値と既定値

- 値を1つ取り、`atoi` で `int` に変換する。既定値は `0`。
- 数値範囲や非負条件を検証する処理はない。`atoi` で数値として読めない文字列は `0` になり、数値の後ろにある非数値部分は変換結果に含まれない。
- 同じ引数を複数回指定すると、引数解析ループで後に指定した値が残る。
- 値を省略すると `ERR --trace-off needs a value` を標準出力に出し、終了コード `2` で終了する。

## 実行時の動作

解析値は `trace_off` に格納され、通常の prefill が完了した後、`trace_m > 0` の場合だけ trace 分岐で参照される。window の開始位置は `p0 = T0 - trace_m - trace_off`。続いて `seq0` から `seq<M-1>` まで各1 token の `forward_chunk` を実行し、`win` ディレクトリでは同じ window を一括で処理する。処理後は `[trace] M=... window p0=... dumped` を標準出力に出して終了コード `0` で戻り、通常の生成処理には進まない。

`--trace-mut` が `0` 以上の場合は、trace window の末尾 token `tok[T0 - 1 - trace_off]` をその値に差し替えてから両方の経路を実行する。`--trace-mut` の既定値は `-1` なので、指定しなければ token 列は変更されない。trace は prefill 後に実行されるため、モデル読み込み・初期化・prefill の失敗は trace に到達する前に終了する。

## 適用条件と副作用

- 効果が出るのは `--trace-m` が正のときだけ。`--trace-m` が未指定または `0` 以下なら、`--trace-off` は読み込まれても使われず、通常の実行経路へ進む。
- window の範囲を検査する条件は trace 分岐にない。`trace_m` と `trace_off` の組み合わせで `p0` や token 添字が入力範囲外になる可能性があるため、入力 token 列に収まる値を指定する。範囲外の値に対する安全な動作はソースから確認できない。
- dump は `--out` の値（未指定時は `.`）の下に `seq0`…`seq<M-1>` と `win` のディレクトリを作り、各層の `engram`（該当層のみ）、`attn`、`mlp` の中間値を `.npy` ファイルとして保存する。既存ディレクトリは再利用され、同名ファイルは `fopen(..., "wb")` により上書きされる。
- `.npy` の `fopen` に失敗した場合、保存関数はその場で戻るだけでエラーを報告しない。trace 分岐自体が `create_directories` の例外を処理する箇所は確認できず、その場合の終了表示・コードは特定できない。
- `forward_chunk` が `false` を返すと trace 分岐は終了コード `1` を返すが、この分岐では `err` の内容を表示しない。

## 出力とエラー

引数値の欠落時は標準出力にエラーを出して終了コード `2`。未知の引数は標準エラーに `unknown arg ...` を出して終了コード `2`。trace 成功時の完了表示は標準出力。trace 内の forward 失敗では終了コード `1` となる。ファイル保存失敗は保存関数内で無視され、trace 成功表示だけでは全ファイルの書き込み成功を確認できない。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:373` — `trace_off` の既定値は `0`。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:375-384` — 値を要求し、省略時はエラーを表示して終了コード `2`。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:436-438` — `--trace-off` の parser と `atoi` 変換。隣接する `--trace-m` / `--trace-mut` の parser。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:498-505` — 未知引数のエラー出力と終了コード `2`。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:347`、`engine/src/hy4flash/run/hy4_main.hip.cpp:484-485` — 出力先の既定値 `.` と `--out` の設定。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:632-639`、`engine/src/hy4flash/run/hy4_main.hip.cpp:686-705` — token 列の読み込み、空 token 列の失敗、trace 前のモデル初期化。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:793-817` — trace 有効条件、window 開始位置、`--trace-mut` との相互作用、逐次/一括 forward、ディレクトリ作成、成功出力と終了。
- `engine/src/hy4flash/run/hy4_graph.hip.h:77-97` — `.npy` 保存先を `wb` で開き、open 失敗を無視する保存関数。
- `engine/src/hy4flash/run/hy4_graph.hip.h:207-217`、`engine/src/hy4flash/run/hy4_graph.hip.h:1934-1942`、`engine/src/hy4flash/run/hy4_graph.hip.h:3431-3442` — dump 設定、配列保存、層ごとの中間値名。
- `docs/cli/README.md:1279-1281`、`docs/cli/README.md:1351-1354` — `strata-hy4` CUDA/HIP のトップレベル scope と対象リンク。

調査範囲は上記 commit の CUDA/HIP `strata-hy4` parser と trace 経路。安全性を確認できない範囲外 window の挙動、およびディレクトリ作成失敗時の例外処理は確認できていない。
