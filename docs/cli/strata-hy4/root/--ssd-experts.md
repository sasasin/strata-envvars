# `--ssd-experts`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP root） |
| オプション | `--ssd-experts` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

CUDA/HIP 版 `strata-hy4` の tiered expert loading で、ホスト RAM に専門家重みを常駐させず、CPU が計算する cold expert をモデルファイルから必要時に読み出す構成にします。GPU に専門家重み全体を載せられる場合は全体を VRAM に読み込む経路が先に選ばれるため、このフラグだけで常にストレージ読み出しになるわけではありません。

## 使い方

```sh
# CUDA/HIP 版でモデルを読み込み、tiered loading 時に RAM 常駐 expert を使わない
strata-hy4 --model ./model.strata --tokens ./prompt.ids --gen 16 --ssd-experts
```

`--ssd-experts` 自体に引数はありません。指定したモデルファイル上の cold expert をオンデマンドで読むため、実際の読み出し先はモデルファイルの保存場所です。このフラグはファイルを SSD へ移動したり、保存媒体を判定したりしません。

## 値と既定値

値を取らず、指定時の状態は `ram_experts_gb = 0.0` です。通常は RAM 予算を自動算出します（`--ram-experts-gb` がない場合の初期値は `-1.0`）。専用の値検証はありません。誤って値を後置すると、その値は別引数として扱われ、未知引数エラーになります。重複指定しても同じ環境値を再設定します。

## 実行時の動作

parser はフラグを読むと `ram_experts_gb` を 0 にし、`HY4_RAM_BUDGET_GB=0`、`STRATA_HY4_RAM_GB=0`、`STRATA_CPUEXP_COLD_IO=direct` をプロセス環境へ上書き設定します。`hy4_setenv` は Windows では `_putenv_s`、それ以外では上書き有効の `setenv` を使います（`engine/src/hy4flash/run/hy4_main.hip.cpp:455-466`、`engine/src/hy4flash/run/hy4_gpu_model.hip.h:405-410`）。

expert 全体を VRAM に載せられない場合、tiered loader は `HY4_RAM_BUDGET_GB` を優先して RAM 予算を読み、`STRATA_HY4_RAM_GB` は前者がない場合の代替として読みます。その後 CLI の RAM cap も上限として適用します（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:807-834`）。予算超過時は CPU mode に切り替え、RAM 予算を超える低優先順位側の expert を cold tier に分類します（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:842-849, 1090-1110`）。CPU expert 初期化後に cold set を登録し、対象 expert は処理時にファイルから読み込まれます（`engine/src/hy4flash/run/hy4_graph.hip.h:1564-1578`、`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2616-2645, 2699-2749`）。

`--ram-experts-gb` と併用した場合、後から指定した値は CLI cap に反映されますが、`HY4_RAM_BUDGET_GB=0` は `--ssd-experts` が設定したまま残るため、effective RAM 予算は 0 のままです。先に `--ram-experts-gb` を指定しても、後続の `--ssd-experts` が 0 にします。なお GPU 全体に Section 4 が収まる場合は tiered loader 自体に入らず、expert 全体を VRAM に読み込みます（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1420-1452, 1485-1503`）。

cold expert の direct I/O は Linux で `O_DIRECT`、Windows で `FILE_FLAG_NO_BUFFERING` を使います。利用できない場合、Linux は buffered read と `FADV_DONTNEED`、Windows は buffered overlapped read にフォールバックします。cold expert cache はプロセス RAM を使い、既定値は 256 MiB の cache 設定、reader 数は 8 です（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1297-1314, 1391-1427, 2726-2748`）。

## 適用条件と副作用

- 対象は索引でこのフラグを登録している CUDA/HIP root parser（`engine/src/hy4flash/run/hy4_main.hip.cpp`）です。モデル読み込みが必要な生成・serve 経路で、expert tiering が必要なときに効果が現れます。情報表示など model loading を通らない経路には cold tier を作る作用はありません。
- cold expert は使用時に `.strata` ファイルから読み込まれ、LRU cache と複数 reader を使います。Direct I/O が使えない環境では buffered I/O に切り替わるため、常に direct I/O が保証されるわけではありません。
- モデルファイルは読み取り専用で開かれます。フラグ自体によるモデルファイルの変更はありません。cold store の初期化では読み取り用ファイルハンドルと cache memory を確保します。
- expert が全量 VRAM に収まる経路では SSD cold streaming は有効になりません。Metal/SYCL 版への適用はこの文書の対象外です。

## 出力とエラー

cold tier が生成される場合、RAM 予算と cold expert 数を標準エラーに表示し、CPU expert 初期化時には cold cache の slot 数・reader 数・実際の I/O mode を表示します（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1097-1110, 1251-1263`、`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2742-2749`）。direct I/O の open に失敗してもフォールバックを試みます。buffered open または cache memory 確保にも失敗すると初期化エラーとなり、モデル load は失敗します（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1391-1427, 2734-2741`、`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1226-1228, 1499-1502`）。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:367, 455-466` — RAM cap の初期値、parser 分岐、環境値の設定。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:405-410, 807-834, 842-849, 1090-1110` — 環境変数の上書き、RAM 予算、CPU mode と cold tier の選定。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:1420-1452, 1485-1503, 1226-1235` — 全量 VRAM 経路と tiered fallback、読み込み失敗・tier mask の処理。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1564-1578` — CPU expert backend と cold expert set の初期化。
- `engine/src/hy4flash/run/hy4_cpu_experts.cpp:1297-1314, 1387-1427, 2616-2645, 2699-2749` — cold file I/O、フォールバック、要求時読み込みと cache 初期化。
- `docs/cli/README.md:1277-1282, 1345` — `strata-hy4` CUDA/HIP root scope と `--ssd-experts` の索引登録。
