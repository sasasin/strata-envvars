# `strata-hy4 --chunk`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP、サブコマンドなし） |
| オプション | `--chunk` |
| 別名 | なし |
| 値 | 整数として `atoi` で変換される値。正の値は指定 chunk、0 以下は自動選択 |

## 役割

推論エンジンが一度に処理する prompt token の chunk サイズを指定する。CUDA/HIP 版では値を GPU メモリ計画に渡し、通常推論または `--serve` の Runner の chunk 容量として使う。省略時は初期値 0 で、搭載 GPU の容量や実行条件に基づいて planner がサイズを選ぶ（`engine/src/hy4flash/run/hy4_main.hip.cpp:352,488,648-652`、`engine/src/hy4flash/run/hy4_gpu_model.hip.h:434-438,492-510`）。

## 使い方

```sh
# オフライン推論で prompt を最大 1024 token ずつ処理
strata-hy4 --model model.strata --tokens prompt.ids --chunk 1024

# serve 起動時にも同じ planner に明示値を渡す
strata-hy4 --serve --native model.strata --chunk 1024

# --chunk を省略して GPU に応じた自動選択を使う
strata-hy4 --model model.strata --tokens prompt.ids
```

## 値と既定値

- 値は `atoi` で整数化される。値を省略すると parser の `nxt()` が `ERR --chunk needs a value` を stdout に出して終了コード 2 で終了する（`engine/src/hy4flash/run/hy4_main.hip.cpp:375-383,488`）。
- 未指定時の `chunk` は 0。0 以下は自動選択経路に入り、正の値は planner が自動サイズを選ばずその値を使う（`engine/src/hy4flash/run/hy4_main.hip.cpp:352,488,648`、`engine/src/hy4flash/run/hy4_gpu_model.hip.h:492-510`）。
- 正の整数の範囲検証や上限補正は `--chunk` の parser と `plan_memory` の自動選択分岐にはない。負数は拒否されず、自動選択として扱われる。数値に変換できない文字列も `atoi` により 0 となり、自動選択経路に入る。したがって、指定値が Runner のメモリ確保可能範囲内かどうかはこの option の入力検証では保証されない（`engine/src/hy4flash/run/hy4_main.hip.cpp:488`、`engine/src/hy4flash/run/hy4_gpu_model.hip.h:492-510`）。
- 自動値はおおむね GPU 総メモリの段階に応じて 512、1024、2048、4096、8192 から候補を選び、multi-GPU 条件や推定ワーク領域・VRAM 使用量に応じて半減される。これはユーザー指定値の許容範囲ではなく、0 以下のときの planner 内部の選択規則である（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:492-508`）。

## 実行時の動作

通常推論では `plan_memory` に `--chunk` の値が渡され、決定したサイズが `g.planned_chunk` と `Runner` の `max_chunk` になる。Runner はこれを `Tc` に保存し、prefill ループで `min(Tc, 残り token 数)` を一回の `forward_chunk` に渡す（`engine/src/hy4flash/run/hy4_main.hip.cpp:648-652,692,749-763`、`engine/src/hy4flash/run/hy4_graph.hip.h:1240`）。chunk は単なるループ幅ではなく、Runner の各種作業領域や ring buffer の容量にも使われる（例: `engine/src/hy4flash/run/hy4_graph.hip.h:1437-1448,1596-1599`）。

`--serve` でも option 値は `ServeOpts` に渡され、serve 側が同じ `plan_memory` を呼び、結果を Runner に渡す。リクエストの prefill も `Tc` 以下の単位に分けて処理される（`engine/src/hy4flash/run/hy4_main.hip.cpp:555-560,611`、`engine/src/hy4flash/run/hy4_serve.hip.h:291-307,499-509`）。

planner は GPU メモリ量、空き容量、model の trunk/expert section サイズ、context、複数 GPU、vision、draft の有無などを見積もりに使う。さらに KV の host/device 配置や reserve の設定を検討し、未設定の場合は `HY4_KV_*`、`HY4_HOST_NEED_GB`、`HY4_RESERVE_GB` などをプロセス環境に設定する。計画値と推定値は `[plan]` 行として stderr に出力される（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:434-490,511-567`）。これらの自動選択・メモリ見積もりは、明示した正の chunk を planner が別値に調整する根拠にはならない。

## 適用条件と副作用

- この文書は索引上の `strata-hy4`、すなわち `engine/src/hy4flash/run/hy4_main.hip.cpp` の CUDA/HIP parser を対象にする。Metal (`strata-hy4-metal`) と SYCL (`strata-hy4-sycl`) にも同名 option があるが別コマンド scope なので、ここではその既定値や動作を含めない（索引 `docs/cli/README.md:1277-1285,1358-1365,1452-1457`）。
- 明示値が大きい場合にも parser に上限検証はなく、chunk に比例する作業領域等の確保を試みる。メモリ不足時の具体的な失敗表示や終了動作は、利用環境・失敗する確保箇所に依存するため、本調査では確定できない。
- planner は未設定の環境変数を設定するほか、model 読み込み、GPU メモリ照会、Runner 初期化を伴う。`--chunk` 自体がファイルを出力する処理は確認できない（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:441-447,520-567`、`engine/src/hy4flash/run/hy4_main.hip.cpp:617-659,692-705`）。

## 出力とエラー

- option 値が欠けると stdout に `ERR --chunk needs a value` を出し、終了コード 2 で終了する（`engine/src/hy4flash/run/hy4_main.hip.cpp:377-383,488`）。
- 不明な引数は stderr に `unknown arg ...` を出して終了コード 2 となる（serve 時には stdout にも `ERR unknown flag ...` を出す）が、これは `--chunk` 固有の値検証ではない（`engine/src/hy4flash/run/hy4_main.hip.cpp:498-505`）。
- 計画後は stderr に `[plan] ... chunk N ...` が出力される。GPU 容量・モデル・その他の指定により、0 以下から選ばれる N は異なる（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:564-567`）。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:352,375-383,488-505` — 初期値、値の取得、欠値・不明引数の処理。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:555-560,611,648-652,692,749-763` — serve/通常推論への伝播と prefill 呼び出し。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:434-510,511-567` — 自動選択、明示値の扱い、メモリ計画・環境変数設定・stderr 出力。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1240,1437-1448,1596-1599` — `Tc` として保持される chunk および容量依存の領域。
- `engine/src/hy4flash/run/hy4_serve.hip.h:291-307,499-509` — serve 側の計画と request prefill。
