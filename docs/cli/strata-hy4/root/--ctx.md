# `strata-hy4 --ctx`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（root） |
| オプション | `--ctx` |
| 別名 | `--max-context`（同じ値に代入される表記） |
| 値 | 整数。正数はコンテキスト上限として使用され、0 以下は未指定相当 |

## 役割

推論に使うコンテキスト長（トークン位置数）の上限を指定します。CUDA/HIP root CLI のオフライン実行では Runner と GPU メモリ計画に渡され、`--serve` モードではサーバーの上限として使われます。Metal / SYCL 版は別 parser・別スコープです。

## 使い方

```sh
# オフライン生成でコンテキスト上限を 8192 トークンにする
strata-hy4 --model SQ64.strata --tokens prompt.ids --gen 128 --ctx 8192

# engine line protocol サーバーのコンテキスト上限を指定する
strata-hy4 --serve --native SQ64.strata --ctx 32768
```

## 値と既定値

- parser は `atoi` で値を整数化し、正数・非正数の範囲検証や形式検証は行いません。数値として読めない文字列は `atoi` により 0 になり、非正数と同じ扱いになります。複数回指定した場合は、後に解析された `--ctx` または `--max-context` が同じ変数を上書きします（`engine/src/hy4flash/run/hy4_main.hip.cpp:375-384,402,487`）。
- オフライン実行では省略時または 0 以下の場合、読み込んだ token 数と `--gen` から `token数 + gen + 16` を設定します。画像 token の展開がある場合も、自動設定なら展開後の長さを使って再設定します。dump batch の特別経路では最終 fallback が `--dump-dfly-gen + 512` です（`engine/src/hy4flash/run/hy4_main.hip.cpp:633-638,679-691`）。
- `--serve` では正数指定がそのまま使われ、省略時または 0 以下では 32768 になります（`engine/src/hy4flash/run/hy4_main.hip.cpp:544-560`）。

## 実行時の動作

オフライン実行ではこの値（または自動決定値）を `plan_memory` に渡して chunk・KV 等の GPU メモリ計画を行い、その後 `Runner` の `max_ctx` として設定します。したがって上限は生成可能なコンテキストだけでなく、計画対象のメモリ量にも影響します（`engine/src/hy4flash/run/hy4_main.hip.cpp:647-652,691-703`; `engine/src/hy4flash/run/hy4_gpu_model.hip.h:402-404,434,452-483,564-566`; `engine/src/hy4flash/run/hy4_graph.hip.h:1240,2858-2862`）。

serve では `ServeOpts.max_ctx` に渡され、同じ GPU メモリ計画と Runner に使われます。サーバー起動時に `READY <上限> stop` を出力し、上限以上の prompt は `ERR prompt exceeds context` で拒否します。生成数は残りの room を超えないよう制限されます（`engine/src/hy4flash/run/hy4_serve.hip.h:291,306-307,371,418-425,540-550`）。

## 適用条件と副作用

- この文書は `engine/src/hy4flash/run/hy4_main.hip.cpp` の CUDA/HIP root CLI に限ります。索引上の Metal (`metal/`)・SYCL (`sycl/`) エントリはそれぞれ別 parser です（`docs/cli/README.md:1277-1289,1358-1373,1452-1460`）。
- コンテキスト上限が大きいほど KV / IndexPool 等のメモリ計画量が増え得ます。GPU 構成によって初期 KV slot や予約量を調整し、未設定の `HY4_KV_INIT_SLOTS`、`HY4_KV_STEP_SLOTS`、`HY4_RESERVE_GB` などをプロセス環境に設定する経路があります（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:459-483,545-566`）。この挙動は環境変数の設定状態や GPU に依存します。
- `--ctx` は数値の大小やモデル固有上限を parser で検証しません。正数を指定しても、実行可能なメモリ量やモデルが扱える長さを保証するものではありません。GPU 計画・モデル初期化の失敗は後続処理で発生し得ます。
- オフライン画像入力では、メモリ計画は画像 pad 展開より前に行われます。自動 context 値は展開後に更新されますが、すでに行った計画値は再計画されません（`engine/src/hy4flash/run/hy4_main.hip.cpp:647-648,666-685`）。

## 出力とエラー

- 値を省略すると stdout に `ERR --ctx needs a value` を出して終了コード 2 で終了します（`engine/src/hy4flash/run/hy4_main.hip.cpp:377-382`）。
- 不明なフラグは stderr に `unknown arg ...` を出して終了コード 2 です（`engine/src/hy4flash/run/hy4_main.hip.cpp:498-505`）。
- GPU メモリ計画時は stderr に `[plan] ctx ...` を出します。serve は起動後に `READY` を出し、prompt が上限以上ならプロトコル応答で拒否します（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:564-566`; `engine/src/hy4flash/run/hy4_serve.hip.h:371,423-425`）。

## 根拠

- parser・値変換・値欠落時の扱い: `engine/src/hy4flash/run/hy4_main.hip.cpp:375-384,402,487-505`。
- オフライン実行の自動値、メモリ計画、Runner への適用: `engine/src/hy4flash/run/hy4_main.hip.cpp:633-648,679-703`。
- serve の既定値と引き渡し: `engine/src/hy4flash/run/hy4_main.hip.cpp:544-560,611`、serve 内の計画と context 制限: `engine/src/hy4flash/run/hy4_serve.hip.h:291,306-307,371,418-425,540-550`。
- 既定メモリ計画の副作用: `engine/src/hy4flash/run/hy4_gpu_model.hip.h:459-483,545-566`。
- 索引では `--ctx` と `--max-context` が別リンクになっていますが、root parser は両方を同じ `max_ctx` に代入します（`docs/cli/README.md:1289,1316`; `engine/src/hy4flash/run/hy4_main.hip.cpp:402,487`）。索引の alias 表記はこの実装と一致していません。
