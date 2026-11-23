# `HY4_CPU_EXPERTS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HY4Flash GPU ローダーで、全 expert を GPU メモリに載せられず tiered loading に進む場合に、GPU に載らない expert を CPU で計算するモードを選ぶ。`1` など 0 以外の整数で CPU モードを指定し、`0` は通常の pinned host memory を GPU が読む経路を指定する。CPU モードでは host expert が `cpu_mask` に登録され、実行時に `CpuExperts` が初期化される。`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1486-1500`、`engine/src/hy4flash/run/hy4_graph.hip.h:1552-1583`。

## 値と判定

値は `getenv` で設定有無を調べ、設定されていれば `atoi(...) != 0` で判定する。文字列全体の妥当性検査はなく、`atoi` が読む数値部分が 0 以外なら有効。空文字、`0`、`false`、`abc`、`0anything` は 0 と判定され、`1`、`-1`、`2`、`1anything` は 0 以外と判定される。未設定の場合だけ、表の既定判定を使う。`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1491-1497`。

| 条件 | 未設定時 | 有効になる設定値 | 無効になる設定値 |
|---|---|---|---|
| Windows (`_WIN32`) の tiered loading | 推定 host expert 量が `host_mem_gb()` の 25% を超える、または 12 GB を超える、または `host_cpu_fast()` が true なら CPU モード | `atoi` の結果が 0 以外（例: `1`, `-1`, `1anything`） | `atoi` の結果が 0（例: 空文字, `0`, `false`, `0anything`） |
| その他の OS の tiered loading | 推定 host expert 量が `host_mem_gb()` の 45% を超える、または `host_cpu_fast()` が true なら CPU モード | 同上 | 同上 |

`host_cpu_fast()` は x86-64 では `__GNUC__` が定義される場合に `__builtin_cpu_supports("avx2")` を使い、定義されない場合は true を返す。AArch64 Linux では ASIMDDP、その他の AArch64 では true、それ以外では false を返す。設定値の判定に大文字小文字や空白の独自規則はなく、`atoi` の変換結果に従う。`engine/src/hy4flash/run/hy4_gpu_model.hip.h:384-400`。同ファイルのコメントは AVX-512 VBMI+VNNI と記すが、実際の `host_cpu_fast()` の条件は上記のとおりである。

## 有効になる条件

- `load_gpu_model(..., true)` が expert をロードし、全 expert を VRAM に載せる経路に入らず tiered loading を行う必要がある。全 Section 4 が VRAM に収まって正常にロードされた場合は `loaded_full` が true となり、この変数を読み取らない。`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1420-1486`。
- 分散実行で `STRATA_HY4_DISTRIBUTED` が有効かつ `g.expert_shard >= 0` の場合、shard 読み込みから先に戻るため、この変数による判定を通らない。`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1400-1409`。
- 既定値を使うのは変数が未設定の場合だけ。設定値 `0` は既定判定を無効化するが、CPU モードを常に避けられるわけではない。host expert の推定量が `ram_budget_bytes` を超えると、`load_experts_tiered` が CPU モードへ切り替えて警告を出す。`HY4_RAM_BUDGET_GB`（未設定なら `STRATA_HY4_RAM_GB`）と `--ram-experts-gb` が RAM 予算に関係し、`--vram-experts-gb` は VRAM 予算を制限して host 側の量に影響する。`engine/src/hy4flash/run/hy4_gpu_model.hip.h:810-832,842-848,1424-1429`、`engine/src/hy4flash/run/hy4_main.hip.cpp:451-458,654-655`。
- pinned host arena の確保に失敗した場合も、指定値にかかわらず CPU モードで再試行する。`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1159-1172`。

## 実行時の詳細

読み取りは `load_gpu_model` のモデル読み込み時、全 expert の VRAM 常駐ができなかった後に行う。関数内やプロセス内の cache はなく、その時点で `getenv` を呼ぶ。通常の CLI 起動とサーバー起動はいずれも `load_gpu_model(..., true)` を呼ぶ。`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1267-1271,1497`、`engine/src/hy4flash/run/hy4_main.hip.cpp:649-659`、`engine/src/hy4flash/run/hy4_serve.hip.h:291-297`。

CPU モードでは host に置く expert を CPU tier にし、RAM 予算を超える冷たい expert は SSD tier に回す。CPU tier がある場合、実行側は `CpuExperts` を初期化し、GPU と CPU の expert 処理を組み合わせる。CPU モードでなければ host arena を pinned memory に確保し、GPU が読み取る。RAM 不足による自動切替後も、tier 表示ログは `RAM (CPU)` となる。`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1084-1110,1159-1174,1227-1255`、`engine/src/hy4flash/run/hy4_graph.hip.h:1552-1583,2466-2489`。

CLI の `--ram-experts-gb` / `--vram-experts-gb` は容量予算を調整するが、`HY4_CPU_EXPERTS` の読み取り値を直接置き換えない。`--ram-experts-gb` は `STRATA_HY4_RAM_GB` も設定する。`engine/src/hy4flash/run/hy4_main.hip.cpp:451-458,654-655`。

## ログと測定値

自動的に CPU モードへ切り替わる RAM 制約経路では、stderr に `[load] host experts %.1f GB exceed safe RAM budget %.1f GB (avail %.1f / %.1f GiB); auto-enabling 4-tier CPU + SSD cold-expert streaming\n` が出る。pinned arena 確保失敗時は `[load] pinned host arena %.2f GB failed (WDDM/commit limit); retrying with CPU-expert mode\n` が出る。単一 GPU の tiered loading 完了時は `[load] experts 4-tier: %llu static VRAM (%.2f GB) + %d adaptive VRAM slots (%.2f GB) = %.2f GB VRAM, %llu in %s (%.2f GB), %llu on SSD (%.2f GB), %.1f s\n` が出て、`%s` は `RAM (CPU)` または `pinned host (GPU)` となる。`engine/src/hy4flash/run/hy4_gpu_model.hip.h:847-848,1161-1174,1251-1255`。

tiered loading が失敗すると `experts: <理由>` を stderr に出してモデルロードは失敗する。通常 CLI は終了コード 1 を返し、サーバーは `ERR cannot load <model>` を返して終了コード 1 となる。`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1499-1501`、`engine/src/hy4flash/run/hy4_main.hip.cpp:659`、`engine/src/hy4flash/run/hy4_serve.hip.h:294-297`。Strata の資料にこの変数の性能測定値はない。

## 根拠

- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:1486-1501` — 値の読み取り、既定値、tiered loading 呼び出し、失敗報告。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:384-400` — 既定判定で使う CPU capability 判定。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:810-848,1084-1110,1159-1174,1227-1255` — RAM 予算、自動 CPU 切替、host/SSD tier、確保失敗 fallback、ログ。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1552-1583,2466-2489` — CPU expert の初期化と GPU/CPU 併用処理。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:451-458,649-659`、`engine/src/hy4flash/run/hy4_serve.hip.h:291-297` — CLI・サーバーの呼び出し経路。
