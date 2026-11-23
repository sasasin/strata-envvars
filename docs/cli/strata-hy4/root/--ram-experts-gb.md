# `strata-hy4 --ram-experts-gb`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（トップレベル） |
| オプション | `--ram-experts-gb` |
| 別名 | なし |
| 値 | GiB 単位の数値（`double` として `atof` で変換）。0 以上で上限を有効化し、負数はこの指定による上限を無効にする |

## 役割

HY4 の expert 配置で、tiered loading 時に host RAM に置く expert の budget 上限を指定します。host expert は pinned memory 経由で GPU が読む場合と、CPU が計算する場合があり、RAM budget を超える cold tail は SSD 上に残して実行時にモデルファイルから読み出します。通常のモデル実行と `--serve` のどちらでも同じ値が設定に渡されます（`engine/src/hy4flash/run/hy4_main.hip.cpp:455-458, 575-576`, `engine/src/hy4flash/run/hy4_serve.hip.h:272-273`, `engine/src/hy4flash/run/hy4_gpu_model.hip.h:789-791, 1090-1110`）。

## 使い方

```sh
# expert の host RAM budget を最大 16 GiB にしてモデルを実行
strata-hy4 --model ./model.strata --ram-experts-gb 16 --tokens ./tokens.txt --gen 32

# server モードで同じ上限を指定
strata-hy4 --model ./model.strata --ram-experts-gb 16 --serve
```

## 値と既定値

- 値は必須です。値を省略すると `ERR --ram-experts-gb needs a value` を標準出力へ出し、終了コード 2 で終了します（`engine/src/hy4flash/run/hy4_main.hip.cpp:377-383`）。
- parser は `atof` で変換し、範囲検証や変換失敗の明示的な拒否をしません。たとえば数値に変換できない文字列は `atof` の結果 0 として扱われ、上限 0 が設定されます（`engine/src/hy4flash/run/hy4_main.hip.cpp:455-458`）。
- 省略時の内部値は `-1.0` です。この値は CLI による cap を無効にし、host RAM budget の算定に任せます（`engine/src/hy4flash/run/hy4_main.hip.cpp:367`, `engine/src/hy4flash/run/hy4_gpu_model.hip.h:830-832`）。負数を明示した場合も cap は無効です。
- 同じオプションを複数回指定した場合、内部 cap 値は最後の指定値になります。0 以上の指定ごとに環境変数も更新されますが、最後が負数なら環境変数の更新は行われません（`engine/src/hy4flash/run/hy4_main.hip.cpp:455-458`）。

## 実行時の動作

parser は値を `ram_experts_gb` に格納し、0 以上なら `STRATA_HY4_RAM_GB` にその文字列を設定します。通常実行ではこの値が `GpuModel::ram_experts_gb_cap` に渡されます（`engine/src/hy4flash/run/hy4_main.hip.cpp:455-458, 654-655`）。serve 経路も同じ `ram_experts_gb` を serve options に渡し、`GpuModel` に設定します（`engine/src/hy4flash/run/hy4_main.hip.cpp:575-576`, `engine/src/hy4flash/run/hy4_serve.hip.h:272-273`）。

expert loading が tiered mode に入ると、まず `HY4_RAM_BUDGET_GB` が設定されていればそれを、なければ `STRATA_HY4_RAM_GB` を使って budget を作ります。どちらもなければ OS の total/available memory 等から安全側の budget を算定します。その後、指定値が 0 以上なら算定値との小さい方を使います。そのため既存の `HY4_RAM_BUDGET_GB` は `STRATA_HY4_RAM_GB` より優先されますが、CLI の cap がその値より小さければ CLI の指定が上限として効きます（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:805-832`）。

GPU に全 expert を載せられる場合は full-load 経路になり、RAM cap を使う tiered loading は行われません。tiered loading では、必要 host memory が budget を超える場合に CPU expert mode を有効化し、CPU resident experts の総量が budget を超えると hot-to-cold 順の rank 配置に沿って cold tail を SSD に回します（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:842-848, 1090-1110, 1420-1436, 1486-1502`）。

## 適用条件と副作用

- cap は expert 配置の host RAM budget に対する上限で、プロセス全体のメモリ使用量を制限するものではありません。VRAM 使用量や trunk、KV cache 等の予算を直接指定するオプションでもありません（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:145-166, 805-834`）。
- tiered loading で budget を超える expert は SSD cold tier に置かれ、実行時にモデルファイルから必要に応じて読み出されます（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1090-1110`）。
- `--ssd-experts` は `ram_experts_gb` と両 RAM budget 環境変数を 0 に設定し、cold I/O を direct に設定します。オプションの並び順によって環境変数の値は変わりますが、loader は `HY4_RAM_BUDGET_GB` を優先し、かつ cap として保持された CLI 値との小さい方を使います（`engine/src/hy4flash/run/hy4_main.hip.cpp:455-465`, `engine/src/hy4flash/run/hy4_gpu_model.hip.h:810-832`）。
- tiered loading で pinned host arena の確保に失敗すると、CPU expert mode で tiered loading を再試行します（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1157-1172`）。

## 出力とエラー

RAM budget のために expert を SSD に残す場合、標準エラーに budget、要求量、SSD に残す expert 数とサイズが出力されます（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1097-1110`）。値の数値検証による専用エラーは parser にありません。モデル読み込み自体に失敗した場合は loader のエラーを標準エラーに出し、通常実行は `load_gpu_model` の失敗を受けて終了コード 1 を返します（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1499-1502`, `engine/src/hy4flash/run/hy4_main.hip.cpp:658-659`）。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:367, 375-383, 455-458` — 既定値、引数欠落時の処理、parser、環境変数への反映。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:575-576, 654-659`、`engine/src/hy4flash/run/hy4_serve.hip.h:272-273` — serve / 通常実行の設定伝搬。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:805-834, 842-848` — RAM budget の環境変数優先順位、CLI cap 適用、自動 CPU + SSD tiering。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:1090-1110, 1157-1172, 1420-1436, 1486-1502` — cold tier の割り当て、確保失敗時の fallback、tiered loading の適用条件と失敗伝搬。
