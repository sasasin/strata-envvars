# `strata-hy4-sycl --force-route`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl`（トップレベル、`root` scope） |
| オプション | `--force-route` |
| 別名 | なし |
| 値 | route ファイル群を置いたディレクトリパス（文字列） |

## 役割

MoE の各層で通常計算する routed expert の top-k expert ID と重みを、指定ディレクトリの `.npy` ファイルから読み込んで使います。router の通常計算は引き続き行われますが、その出力ではなくファイル由来の値が routed expert の実行に渡ります（`engine/src/hy4flash/sycl/sy_graph.h:1066-1076,1119-1132`）。SYCL グラフ経路を無効にして eager 経路へ進ませる診断用途にもなります（同 `:1382-1391`）。

## 使い方

```sh
# 入力 token ID とモデルを指定して、事前に用意した route 配列を使う
strata-hy4-sycl --model model.strata --tokens ids.txt --gen 16 --force-route ./routes
```

ルートファイルは実行時に読むため、呼び出し時点で `./routes` に対象層のファイルが必要です。通常の `strata-hy4-sycl` 実行ではトークン入力が空だと `no tokens` で終了します（`engine/src/hy4flash/sycl/sy_main.cpp:267-275`）。

## 値と既定値

- 値は `nxt()` で次の argv 文字列をそのまま受け取ります。数値変換やパス検証は parser では行いません（`engine/src/hy4flash/sycl/sy_main.cpp:105-115,168`）。
- 省略時の文字列は空で、route ファイルを読みません（同 `:93,168`; `engine/src/hy4flash/sycl/sy_graph.h:1123`）。
- 値を省略すると `ERR --force-route needs a value` を stdout に出して flush し、終了コード 2 で終了します（`engine/src/hy4flash/sycl/sy_main.cpp:109-115`）。空文字列を明示した場合も空として扱われ route 読み込みは無効になります。
- 同じ引数を複数回指定すると、parser が文字列を順次代入するため最後の値が残ります（同 `:105-115,168`）。

## 実行時の動作

`Runner` にディレクトリ文字列を渡し、各 routed MoE 層の処理時に `L<層番号>_topk_idx.npy` と `L<層番号>_topk_w.npy` を読み込みます（`engine/src/hy4flash/sycl/sy_main.cpp:283-287`; `engine/src/hy4flash/sycl/sy_graph.h:1119-1127`）。どちらも float32 配列として読み、現在の chunk の token 位置 `cur_p0` から `T * 16` 個を取り出します。ID は `int32_t` にキャストされ、重みはそのまま `h_w` にコピーされます（同 `sy_graph.h:1124-1132`）。従って必要な値の並びは token ごとに 16 個です。

loader はファイルをバイナリで開き、先頭 10 byte の後にある header 長を使って残りを 4 byte float として読みます。NumPy magic、dtype、shape、バイトオーダーは検査しません（`engine/src/hy4flash/sycl/sy_graph.h:37-50`）。route を生成する側が `.npy` として整合した配列を用意する必要がありますが、実装が検証するのは読み込み成否と ID 配列の要素数が `(cur_p0 + T) * 16` 以上であることだけです。重み配列の要素数や両配列の形状・値域は検査されません（同 `:1124-1132`）。

## 適用条件と副作用

- route は `run_routed_experts` が呼ばれる MoE 層で読み込まれます。route 読み込みは chunk ごと・層ごとに行われ、通常の router 計算後に routed expert の入力 ID・重みを置き換えます（`engine/src/hy4flash/sycl/sy_graph.h:1066-1076,1119-1132,1231-1243`）。
- `--load-only` は model load / setup 後に forward 処理へ入る前に終了するため、このモードでは route ファイルを読みません（`engine/src/hy4flash/sycl/sy_main.cpp:267-275,298-320`）。環境変数 `HY4S_SKIP_EXPERTS` との相互作用は、`use_gx` が偽なら route を読み込んだ後に expert 出力をゼロ化します。`use_gx` が真ならその環境変数判定より先に GPU experts 経路から戻るため、同判定は適用されません（`engine/src/hy4flash/sycl/sy_graph.h:1123-1149,1236-1243`）。環境変数の説明は [`HY4S_SKIP_EXPERTS`](../../../envvars/HY4S_SKIP_EXPERTS.md) を参照してください。
- `--serve` モードでは CLI parser は値を受け取りますが、server 用 `ServeOpts` に route ディレクトリを渡さず、その後 standalone 実行処理より前に server を起動して戻ります。そのため本オプションは server 実行には適用されません（`engine/src/hy4flash/sycl/sy_main.cpp:105-115,168,215-248`）。
- route ディレクトリが空でない場合、graph replay の条件から外れて eager 経路になります。また適応型 VRAM expert cache の commit・step も抑止されます（`engine/src/hy4flash/sycl/sy_graph.h:374-385,1382-1391`）。
- このオプション自身は入力ファイルを読みますが、書き込み・修正はしません。通常の dump 出力など他のオプションによる副作用は別に発生し得ます。

## 出力とエラー

いずれかの層の ID/weight ファイルを開けない、読み込みに失敗する、または ID 配列の要素が不足する場合、stderr に `force-route: cannot load layer <番号>` を出し、プロセスを終了コード 5 で終了します（`engine/src/hy4flash/sycl/sy_graph.h:1124-1129`）。パスやファイルの妥当性は事前検査されないので、失敗は該当する routed 層の処理時に発生します。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:93-115,168` — 空の初期値、次 argv を取る parser、値欠落時の stdout と終了コード 2。
- `engine/src/hy4flash/sycl/sy_main.cpp:215-248,283-287` — server 分岐で route が転送されないこと、および standalone `Runner` への設定。
- `engine/src/hy4flash/sycl/sy_graph.h:37-50,1066-1076,1119-1132` — `.npy` の読み方、router 後の route 値差し替え、要素数確認、失敗時の終了。
- `engine/src/hy4flash/sycl/sy_graph.h:374-385,1382-1391` — force-route 使用時の graph と adaptive VRAM cache の条件。
