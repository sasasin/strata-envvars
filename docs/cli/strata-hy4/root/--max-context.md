# `--max-context`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP） |
| オプション | `--max-context` |
| 別名 | なし（同じ parser は別表記 `--ctx` も受理。索引では別項目） |
| 値 | `atoi` で整数に変換する値。正値は最大 context token 数として使用 |

## 役割

推論で確保・計画する最大 context 長を指定します。KV cache や IndexPool の容量、GPU メモリ計画に使われ、serve モードでは各 prompt に許す context 上限にもなります。CUDA/HIP root のオプションです。Metal と SYCL の同名オプションは別 scope で、既定値などが異なるためこの文書の対象外です（`engine/src/hy4flash/run/hy4_main.hip.cpp:402, 559, 648, 691-692`、索引 `docs/cli/README.md:1279, 1316, 1391, 1480`）。

## 使い方

```sh
# CUDA/HIP 版で prompt と生成を合わせた context 上限を指定
strata-hy4 --model SQ64.strata --tokens prompt.ids --gen 256 --max-context 8192
```

`--model` と `--tokens` のファイルは実行環境に合わせて指定してください。`--ctx` も同じ変数を設定します。両方または同じオプションを複数回指定すると、引数列で後に現れた値が残ります（`engine/src/hy4flash/run/hy4_main.hip.cpp:402, 487`）。

## 値と既定値

- 引数は `atoi` で整数化されます。parser に正数・上限・形式の検証はありません。0 以下は明示的な上限として扱われず、自動値にフォールバックします。数値でない文字列も `atoi` の結果が 0 となり、同じ自動値経路に入ります（`engine/src/hy4flash/run/hy4_main.hip.cpp:402, 487, 633`）。
- `--serve` では正値を `ServeOpts.max_ctx` に渡し、0 以下または省略時は `32768` です（`engine/src/hy4flash/run/hy4_main.hip.cpp:545-560`）。
- 通常の offline 実行では、正値が指定されない場合、prompt token 数 `T0` と `--gen` の値に 16 を加えた値を使用します。画像 pad の展開で prompt が伸びる場合も、自動設定なら展開後の token 数を使って計算し直します。dump batch 経路で prompt がない場合は `--dump-dfly-gen` に 512 を加えた値です（`engine/src/hy4flash/run/hy4_main.hip.cpp:633-638, 666-692`）。
- メモリ計画は、offline 実行の自動値決定前に context を参照するため、その段階で値が 0 以下なら一時的に `32768` を計画値として使います（`engine/src/hy4flash/run/hy4_main.hip.cpp:648`）。

## 実行時の動作

offline 実行では指定値を `plan_memory` に渡し、返された chunk とともに `Runner` を構築します。context 長に応じて KV/IndexPool のメモリ見積もりや初期確保量が変わります。単一 GPU かつ 44 GiB 未満などの条件では、`--max-context` が初期 KV 枠を超えると、未設定の場合に `HY4_KV_INIT_SLOTS` と `HY4_KV_STEP_SLOTS` をプロセス環境へ設定し、KV を段階的に拡張する計画を行います。GPU メモリに収まらない場合の host memory 利用判断にも context が関係します（`engine/src/hy4flash/run/hy4_main.hip.cpp:648`、`engine/src/hy4flash/run/hy4_gpu_model.hip.h:434-482, 511-566`）。

serve モードでは `ServeOpts.max_ctx` を `Runner` と serve loop に渡します。prompt が上限以上なら `ERR prompt exceeds context (...)` を protocol 出力して要求を拒否し、生成可能な room もこの上限から算出します（`engine/src/hy4flash/run/hy4_main.hip.cpp:555-560, 611`、`engine/src/hy4flash/run/hy4_serve.hip.h:306-307, 371, 423-424, 540-550`）。

## 適用条件と副作用

- `--max-context` 自体の値による parser-level validation はありません。範囲外の大きな値を指定すると、その値に応じたメモリ計画・確保が行われます。GPU/host memory の不足などで確保に失敗する可能性がありますが、具体的な境界値はカード、モデル、他の設定にも依存し、ソース上で固定値としては定義されていません（`engine/src/hy4flash/run/hy4_main.hip.cpp:648-665`、`engine/src/hy4flash/run/hy4_graph.hip.h:1596-1618`）。
- offline 経路では `plan_memory` が条件に応じて `HY4_KV_INIT_SLOTS`、`HY4_KV_STEP_SLOTS`、`HY4_HOST_NEED_GB`、`HY4_RESERVE_GB` を設定する場合があります。これは子プロセス起動ではなく、この `strata-hy4` プロセスの環境に対する変更です。既に各変数が設定されている場合は、該当する自動設定を行いません（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:405-410, 468-481, 532-563`）。
- serve と offline で未指定時の既定値は異なります（serve は 32768、offline は prompt/生成長などから計算）。Metal/SYCL バイナリでは同名 option の parser・既定値が別に定義されています（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1513, 1591, 1642, 1706`、`engine/src/hy4flash/sycl/sy_main.cpp:131, 157, 229, 277`）。

## 出力とエラー

- 値が欠落すると parser は stdout に `ERR --max-context needs a value` を出して終了コード 2 で終了します（`engine/src/hy4flash/run/hy4_main.hip.cpp:377-383, 402`）。
- 不明な引数は stderr に `unknown arg ...` を出し、終了コード 2 です（serve 時は protocol にも `ERR unknown flag ...` を出します）。値の構文や範囲だけを理由にした専用エラーは parser にはありません（`engine/src/hy4flash/run/hy4_main.hip.cpp:498-505`）。
- context 計画の概要は stderr の `[plan] ctx ...` 行に出力されます（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:564-566`）。serve で prompt が上限以上の場合の拒否メッセージは上記のとおりです（`engine/src/hy4flash/run/hy4_serve.hip.h:423-424`）。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:352, 375-383, 402, 487` — 変数の初期値、引数解析、整数変換、同じ変数を設定する `--ctx`。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:545-560, 611, 633-648, 666-692` — serve/offline の既定値、メモリ計画、画像展開後の自動値、Runner への適用。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:434-482, 511-566` — context を使う GPU メモリ計画と、条件付き環境変数設定・診断出力。
- `engine/src/hy4flash/run/hy4_serve.hip.h:291, 306-307, 371, 423-424, 540-550` — serve 側での Runner 設定、protocol の READY/context 拒否、生成可能長。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1240-1246, 1596-1618` — Runner が context を保持し、KV cache の初期確保量に使う箇所。
- 別 backend との比較: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1491, 1513, 1591, 1642, 1706`、`engine/src/hy4flash/sycl/sy_main.cpp:104, 131, 157, 229, 277`。
