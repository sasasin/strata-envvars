# `strata-hy4 --trace-m`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（root） |
| オプション | `--trace-m` |
| 別名 | なし |
| 値 | 整数。`atoi` で変換される。 |

## 役割

prompt の末尾から M token を選び、各 token を1件ずつ処理したときと M token をまとめて処理したときの中間テンソルを比較できるよう、レイヤー・演算ごとの値を保存します。CUDA/HIP 版 `strata-hy4` の offline 実行にある診断経路です。索引上の parser は `engine/src/hy4flash/run/hy4_main.hip.cpp` です（`docs/cli/000_cli_tools.md:11`、`docs/cli/README.md:1277-1282`）。

## 使い方

```sh
strata-hy4 --model model.strata --tokens ids.txt --trace-m 4 --out trace-run
```

`ids.txt` は token ID を並べた入力ファイルです。出力先には既存データと重ならないディレクトリを指定してください。`--out` を省略すると出力先は `.` になり、trace の `seq*` / `win` ディレクトリと同名の `.npy` ファイルを既存の出力先へ書き込みます（`engine/src/hy4flash/run/hy4_main.hip.cpp:347,484-486,632-638,801-813`）。

## 値と既定値

値は必須で、`atoi` の戻り値が使われます。省略時は `trace_m = 0` で trace を実行しません。値が 0 以下の場合も分岐条件 `trace_m > 0` を満たさず、trace は実行されません。数値形式・正の範囲・prompt 長との整合性を検証する処理はありません。整数として解釈できない文字列は `atoi` により 0 になります（parser と既定値: `engine/src/hy4flash/run/hy4_main.hip.cpp:373,436,793`）。

値を省略すると parser の `nxt()` が `ERR --trace-m needs a value` を stdout に出して終了コード 2 で終了します（`engine/src/hy4flash/run/hy4_main.hip.cpp:377-383,436`）。

## 実行時の動作

通常の offline 経路では、モデルの初期化後に token 入力を prefill し、その後 `trace_m > 0` なら生成処理に進む前に trace を実行します。M は `--trace-m` の値、開始位置は `p0 = T0 - M - trace_off` です。各位置を1 tokenずつ `forward_chunk` に渡して `out/seq0` から `out/seq<M-1>` 相当のディレクトリへ保存し、続けて同じ範囲を M token の一括入力として `out/win` に保存します。実際のパスの先頭は `--out` の値です。完了すると stdout に `[trace] M=... window p0=... dumped` を出して終了コード 0 で戻ります（`engine/src/hy4flash/run/hy4_main.hip.cpp:686-705,793-817`）。

保存対象は attention / MLP など各レイヤー処理後の中間値です。`--dump-layer N` を併用すると、指定レイヤーの追加 attention 内部値も保存対象になります（`engine/src/hy4flash/run/hy4_graph.hip.h:1934-1942,2167-2182`）。

## 適用条件と副作用

この処理は `--serve` の server 経路には適用されません。`--serve` の場合、引数を解析した後、offline の model・token 処理および trace 分岐に到達する前に `hy4_serve_main` を呼び出して戻ります（`engine/src/hy4flash/run/hy4_main.hip.cpp:544-611,793-817`）。また、trace は prompt の prefill とモデル初期化の後に走るため、それらが失敗すれば実行されません。

関連オプションとの作用は次のとおりです。

- [`--trace-off`](--trace-off.md) は窓の開始位置をずらし、`--trace-mut` と併用したときに書き換える token 位置にも使われます（`engine/src/hy4flash/run/hy4_main.hip.cpp:437-438,796-798`）。
- [`--trace-mut`](--trace-mut.md) が 0 以上なら、trace 実行前に `tok[T0 - 1 - trace_off]` をその値へ置き換えます。入力 token 列の変更はプロセス内の診断用バッファに対するもので、入力ファイルを書き換える処理はありません（同: 798）。
- [`--dump-layer`](--dump-layer.md) は追加の内部 attention dump の対象レイヤーを指定します（`engine/src/hy4flash/run/hy4_main.hip.cpp:439,801-802`）。
- `--out` は trace 出力の親ディレクトリです。各 `.npy` は `fopen(..., "wb")` で開かれるため同名ファイルを上書きします。ファイルを開けない場合、保存 helper はエラーを通知せず戻ります（`engine/src/hy4flash/run/hy4_graph.hip.h:77-96`）。

`--trace-m`、`--trace-off` と `--trace-mut` の値に対する範囲検証は確認できません。特に M が prompt 長を超える場合や `trace_off` が窓の範囲を外す場合について、ソース上の拒否・補正はありません。正の M と、prompt 内に収まる窓を指定してください（位置計算と token 参照: `engine/src/hy4flash/run/hy4_main.hip.cpp:796-813`）。

各 `forward_chunk` が失敗した場合は trace 分岐から終了コード 1 で戻りますが、この分岐自身は `err` の内容を出力しません（同: 807,813）。ディレクトリ作成や GPU 実行の失敗について、ここで個別の診断表示を行う処理は確認できません。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:373,436-438` — 既定値、parser 登録、関連 trace オプション。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:377-383` — 値がない場合の stdout と終了処理。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:632-638,686-705` — token 入力と offline のモデル初期化後の処理順。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:793-817` — trace 窓、逐次・一括 forward、出力先作成、成功・失敗時の戻り値。
- `engine/src/hy4flash/run/hy4_graph.hip.h:77-96,1934-1942,2167-2182` — NPY ファイルの書き込み、保存対象、追加の layer 内部 dump。
- `docs/cli/000_cli_tools.md:11`、`docs/cli/README.md:1277-1282,1351-1353` — `strata-hy4` の parser scope と索引上の配置、関連 option。
