# `strata-hy4-metal --bench-m`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal runner） |
| オプション | `--bench-m` |
| 別名 | なし |
| 値 | `atoi` で整数化される M token 数 |

## 役割

オフライン prompt の末尾 M token を使って Metal runner の forward と head を繰り返し実行し、経過時間と GPU 時間、および kernel ごとの計測値を出力するベンチマーク分岐を選びます。起動時のモデル読み込みと prompt 全体の prefill の後に実行されます。

## 使い方

```sh
strata-hy4-metal --model /path/to/model.strata --tokens /path/to/token-ids.txt --bench-m 16
```

モデルと token ID ファイルを指定して実行します。M は prompt token 数以下にしてください。例のパスは実際の入力ファイルに置き換えます。

## 値と既定値

- 値は `atoi` で整数に変換されます。省略時は `0` で、`bench_m > 0` のベンチマーク分岐には入りません。その場合は通常のオフライン処理へ進みます。非数値文字列も `atoi` の変換結果として `0` になり、負数もベンチマーク分岐を有効にしません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1491,1573,1882`）。
- `--bench-m` の値に対する範囲検証は見当たりません。分岐は `p0 = T0 - bench_m` として prompt 末尾から M token を選びます。M が prompt 長を超えると負の位置が計算されるため、その値での実行は避けてください（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1882-1887`）。
- 同じオプションを複数回指定した場合、引数ループで都度代入されるため最後の値が残ります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1506,1573`）。
- 値を省いた場合に `argv` の範囲を確認する処理は、この引数取得 lambda にはありません。値を必ず指定してください（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1506,1573`）。

## 実行時の動作

モデルをロードし、token ID ファイルを読み込んで prompt 全体を prefill した後、最後の M token の位置 `p0 = T0 - M` を計算します。その区間に対して `forward_chunk`、`head`、`run_all` を6回実行し、各回の wall-clock 時間と `r.gpu_total` を標準エラーへ出力します。各回の後に `gpu_total` をゼロに戻し、続けて同じ区間をもう一度 forward/head し、保留中の kernel dispatch を20回ずつ個別実行して kernel 別プロファイルを出力します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1615-1635,1676-1705,1790-1817,1882-1896`）。

この分岐は通常の生成処理には進まず `return 0` します。prompt の prefill 結果（top-5 行）は分岐前に標準出力へ出力されます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1802-1817,1882-1896`）。

## 適用条件と副作用

- 索引上の scope は Metal backend の `strata-hy4-metal` です。CUDA/HIP や SYCL の同名に見える入口とは別の parser です（`docs/cli/README.md:1358-1364`、`engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1491,1573`）。
- `--model` と非空の token prompt が必要です。モデルロード後に token ファイルを読み、空なら `no tokens` を標準エラーへ出して終了コード 2 になります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1611-1623,1676-1705`）。
- 計測中は Metal GPU kernel を実行します。6回の区間計測に加え、最後の dispatch 群を20回ずつ再実行するため、単発の推論より多く GPU 計算を行います（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1884-1895`）。
- 計測分岐の `forward_chunk` 呼び出しは戻り値を確認していません。失敗時の扱いや終了コードをこの経路から保証できません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1886-1894`）。
- `--par-m` が同時に正値で指定された場合は、先に `par_m > 0` の分岐で比較処理を行って `return 0` するため、`--bench-m` の計測には到達しません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1857-1880`）。

## 出力とエラー

- 標準エラーに各反復の `[bench-m] M=... rep ...` 行と、`kernel_profile(20)` による `[prof3]` kernel profile が出ます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1884-1895,1351-1366`）。
- ベンチマーク専用分岐は計測後に終了コード 0 を返します。個々の `forward_chunk` の失敗を検出してエラーを返す処理はありません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1886-1896`）。
- モデルの読み込み失敗は `load: ...` を標準エラーへ出して終了コード 1、空 prompt は `no tokens` を出して終了コード 2 です（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1620-1623,1701-1705`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1506,1571-1574` — Metal runner の引数変数、引数取得、整数変換。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1611-1635,1676-1715` — 必須モデル、ロード、token 読み込み、空 prompt 判定と runner 初期化。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1790-1817` — prompt prefill、top-5 出力と通常処理の初期段階。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1857-1896` — `--par-m` との分岐順、`--bench-m` の位置計算、反復と終了。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1291-1329,1332-1349,1351-1367` — forward chunk の token 区間処理、head dispatch、個別 kernel profile。
- `docs/cli/README.md:1358-1364` — `strata-hy4-metal` の索引上の scope と対象リンク。
