# `strata-hy4-sycl --wincheck`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl` |
| オプション | `--wincheck` |
| 別名 | なし |
| 値 | 整数。`atoi` で変換し、正数のとき比較を実行する。実際の window 幅は最大 8 行 |

## 役割

通常の SYCL runner でモデルと入力 token を prefill した後、greedy decode で必要な token を進め、続く最大 8 token について「1 token ずつの forward」と「同じ token 群を一括 window で forward」したときの層 tap と logits を比較する診断オプションです。tap と logits の float 値をビット単位で照合し、window 実行が単独 step の結果と一致するかを確認します（`engine/src/hy4flash/sycl/sy_main.cpp:459-526`）。

## 使い方

`--model`（alias `--native`）と token ID を並べたファイルを指定します。`--wincheck-skip` で比較前に greedy decode する token 数を指定できます。通常経路の末尾で `--out` の場所に `top5.txt` が書かれるため、空の出力ディレクトリを用意して指定してください。

```sh
# 空の ./wincheck-output を用意した作業ディレクトリで、4 行 window を比較する
strata-hy4-sycl --model model.strata --tokens ids.txt --wincheck 4 --out ./wincheck-output

# greedy decode で32 token 進めてから比較する
strata-hy4-sycl --model model.strata --tokens ids.txt --wincheck 4 --wincheck-skip 32 --out ./wincheck-output
```

## 値と既定値

- parser の初期値は `0` です。`--wincheck N` は `atoi` で整数へ変換され、`N > 0` の場合だけ比較分岐に入ります。`0`、負数、整数に変換できない文字列では比較しません。正数に対する明示的な validation はなく、実行時の幅 `M` は `min(N, 8)` です（`engine/src/hy4flash/sycl/sy_main.cpp:97,170,459,462`）。
- 値を省略すると共通の値取得処理が `ERR --wincheck needs a value` を stdout に出し、終了コード `2` で終了します。同じフラグを繰り返すと、後に読まれた値で上書きされます（`engine/src/hy4flash/sycl/sy_main.cpp:105-116,170`）。
- `--wincheck-skip` の初期値は `0` です。正数ならその回数だけ greedy decode して比較位置を進めます。値も `atoi` で解釈され、正数でない場合はループを進めません（`engine/src/hy4flash/sycl/sy_main.cpp:97,171,469-479`）。

## 実行時の動作

通常のモデル初期化と全入力 token の prefill が終わった後、最終 logits の argmax を次 token とします。`--wincheck-skip` 回の 1 token forward で比較位置を進め、次の token から `M=min(N,8)` 個を逐次 forward して各行の tap と logits を保存します。続いて同じ token 列を `M` 行の一括 window として forward し、tap と logits を対応する逐次結果と比較します。tap 名・形状が合わない場合、その tap は値比較を飛ばします。比較対象は `memcmp` によるビット比較で、tap の差分数、logits の差分数、tap の最大絶対差を行ごとに出します（`engine/src/hy4flash/sycl/sy_main.cpp:469-526`）。tap は GPU 側データを待機後に host vector へ読み出す処理です（`engine/src/hy4flash/sycl/sy_graph.h:761-779`）。

比較時の MLA batch-invariant 設定は、プロセス環境変数 `HY4S_BATCH_INV` が未設定、または値の先頭が `0` 以外なら有効化されます。先頭が `0` の場合は setter を呼ばず、初期値（無効）のまま比較します。値の解釈と MLA split への反映は [`HY4S_BATCH_INV`](../../../envvars/HY4S_BATCH_INV.md) を参照してください（`engine/src/hy4flash/sycl/sy_main.cpp:463-464`; `engine/src/hy4flash/sycl/sy_spec.h:16-19`; `engine/src/hy4flash/sycl/sy_mla.cpp:13-14,1654-1656`）。

正の `--wincheck` は expert cache の初期化前にプロセス環境の `HY4S_VRAM_STATIC` を `1` で上書きします。これにより cache の adaptive 動作が無効になります（[`HY4S_VRAM_STATIC`](../../../envvars/HY4S_VRAM_STATIC.md); `engine/src/hy4flash/sycl/sy_main.cpp:298-304`; `engine/src/hy4flash/sycl/sy_common.h:33-40`; `engine/src/hy4flash/sycl/sy_vram_cache.h:793-797`）。

## 適用条件と副作用

- `--serve` は通常処理より先に serve handler へ return するため、この診断分岐には入りません。通常経路でも `--load-only` は cache / expert 初期化後、prefill 前に return するため比較しません。分岐順は speculative decode（`--draft dfly2` かつ `--gen > 0`）、`--detcheck`、`--wincheck`、通常の `--gen` です。したがって speculative decode が選ばれる場合や正の `--detcheck` がある場合は `--wincheck` より先にそちらが実行され、正の `--wincheck` が通常 `--gen` より先に選ばれます（`engine/src/hy4flash/sycl/sy_main.cpp:215-249,279-280,298-300,318-319,379-410,459,527`）。
- モデルと token ファイルを読み、SYCL device と expert cache を初期化したうえで診断 forward を複数回実行します。モデル未指定は usage を stderr に出して終了コード `2`、token 列が空なら `no tokens` と終了コード `2`、モデルロード・初期化・forward の失敗は該当エラーを stderr に出して終了コード `1` です。SYCL exception は `SYCL exception: ...` を stderr に出して終了コード `4` です（`engine/src/hy4flash/sycl/sy_main.cpp:251-275,262-265,294-306,348-350,472,486,496,612-615`）。
- 判定後は共通処理で `--out`（既定 `.`）配下の `top5.txt` を開いて書き込みます。`--dump` も指定されている場合は prefill 後に `logits.npy` も出力します。ファイル生成・書き込みの成否を確認する処理は `top5.txt` の箇所にはありません（`engine/src/hy4flash/sycl/sy_main.cpp:93,355-364,603-606`）。

## 出力とエラー

stdout に `wincheck p0=... M=... batch_invariant=...`、各行の tap / logits 差分、最後に `WINCHECK IDENTICAL` または `WINCHECK DIFFERS` を出します。差分判定は tap の値差または logits の値差で行います。比較結果に応じて終了コードを変更する処理はなく、差異があっても後続の通常終了処理に進みます（`engine/src/hy4flash/sycl/sy_main.cpp:502-526,612-616`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:97,105-116,170-171` — 初期値、値の取得、オプション parser。
- `engine/src/hy4flash/sycl/sy_main.cpp:215-254,266-300,318-319` — serve／通常経路の前提、モデル・token の扱い、cache 設定、早期 return。
- `engine/src/hy4flash/sycl/sy_main.cpp:344-373,379-410,459-526` — prefill 後の分岐順、skip、逐次／window forward、比較と出力。
- `engine/src/hy4flash/sycl/sy_main.cpp:603-616` — `top5.txt`、最終終了コードと SYCL exception。
- `engine/src/hy4flash/sycl/sy_spec.h:16-19`, `engine/src/hy4flash/sycl/sy_mla.cpp:13-14,1654-1656` — batch-invariant の値と利用。
- `engine/src/hy4flash/sycl/sy_graph.h:761-779` — tap の host 読み出し。
- `engine/src/hy4flash/sycl/sy_common.h:33-40`, `engine/src/hy4flash/sycl/sy_vram_cache.h:793-797` — 環境変数の上書きと static cache の判定。
