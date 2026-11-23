# `HY4_VCACHE_FRAC`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

単一 GPU の tiered expert loading で、expert 用 VRAM 予算のうち adaptive VRAM expert cache 用に確保する割合を指定する。割合を差し引いた予算で固定 expert を配置し、残りで可変サイズの cache slot を作る。値が cache 動作を有効にするのではなく、CPU expert mode や hybrid runner などの条件が別途必要である。実装は `load_experts_tiered` にある HIP/CUDA 共用コードである（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:792-793,850-874`）。

## 値と判定

単一 GPU (`ng == 1`) の tiered loading でだけ参照し、`getenv` が非 NULL なら `atof` の結果を `[0.0, 1.0]` に clamp する。空文字も「設定あり」として `atof("") == 0` になり、未設定時の自動値には進まない。`atof` は厳密な文字列検証をせず、数値として読める先頭部分を変換するため、例のように後続文字があっても拒否されない。変換結果が 0 以下なら clamp 後 0、1 以上なら 1。`dyn_frac > 0.01` の厳密な条件があるため、値が `0.01` 以下では動的 slot の割合計算に入らない（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:850-874,1074-1083`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `ng == 1` | 初期値は `1.0`。CPU mode で RAM 不足がある場合は overflow から `0.25..1.0` を計算し、それ以外で条件を満たす場合は混合量子化の expert サイズ条件により `0.35` にする | `0.02`、`0.5`、`1`。負値は `0` に clamp、1 超は `1` に clamp | 空文字、`0`、`0.01`、`-0.5`、`abc` は最終的に 0 または `0.01` 以下となり slot 不使用。`0.5junk` は先頭数値 `0.5` として変換 |
| `ng > 1` | `dyn_frac = 0.0` | 該当なし | 値の有無にかかわらず単一 GPU 用動的 cache 割合の判定をしない |

値の形式・全体一致・大文字小文字を検査せず、空白や数値の後ろの文字を明示的に拒否しない。変換不能な文字列は `atof` により 0 相当となる。`NaN` などの非有限表記に対する値の扱いは C ランタイムの `atof` と clamp 演算に委ねられ、アプリケーション側に専用検証はない。CLI 引数による同名の上書きはなく、環境変数が存在すると自動計算より優先される（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:850-864`）。

## 有効になる条件

- `load_gpu_model(..., with_experts=true)` が expert 全量を VRAM に載せる経路を使わず、`load_experts_tiered` に到達する必要がある。全量が VRAM に載ると、この変数は読まれない（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1420-1437,1485-1502`）。
- `g.peer_devs` が空で、単一 GPU（`ng == 1`）である必要がある。`--gpus` / `--devices` で複数 GPU を指定した場合は割合分岐が無効になる（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:800,850-865`; `engine/src/hy4flash/run/hy4_main.hip.cpp:404-405,516-539,657-659`）。
- `cpu_mode` が true である必要がある。これは `HY4_CPU_EXPERTS` が設定されていれば `atoi(...) != 0`、未設定なら RAM 使用量や CPU 能力から決まる。`HY4_VCACHE_FRAC` は CPU mode 自体を有効化しない（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1486-1499`）。
- `dyn_frac > 0.01`、`max_body_sz > 0`、`vram_budget >= 2 * max_body_sz` が必要である。さらに固定配置後に残る tier 非 VRAM expert から slot サイズが決まり、hybrid runner の `hyb` が成立しなければ runtime cache 初期化は戻る（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:869-874,1074-1083`; `engine/src/hy4flash/run/hy4_graph.hip.h:717-724,1582-1584`）。
- `0.01` 以下を設定すると動的 slot は割り当てない。設定が未設定なら自動割合が使われ、CPU mode・RAM 不足・expert サイズ分布の条件によって値が決まる（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:854-864`）。

## 実行時の詳細

値は expert を tier 分けする `load_experts_tiered` の呼び出し中に読み、プロセス起動時に一度だけ保存する static cache はない。通常の実行では expert loading 時に値が決まり、推論中に環境を変更しても既存の割当は変わらない。pinned host arena の割当失敗時は CPU mode で同関数を再試行するため、その再試行時にも値を読み直す（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:850-874,1157-1172`）。

最初に `vram_budget * dyn_frac` から動的枠の目安を出し、残りを固定配置向け予算にする。その後、固定 expert の実配置量 `vb` と、tier 非 VRAM expert の最大 blob サイズに基づき `dyn_slots` を再計算するため、実 slot 数・bytes は指定割合そのものの単純な積ではない。GPU 割当が失敗した場合は確保できた分までに `actual_dyn` を縮め、残りの RAM/SSD tier 構成で続行する。`HY4_RESERVE_GB` が正値なら GPU が UMA でない場合にその予約分へ達する前で slab 確保を止める（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:866-874,1073-1083,1113-1144`）。

runtime 初期化では cache slot を高 rank 優先で resident CPU expert から pre-populate し、その後の routing に応じた promote / eviction に使う。`HY4_VCACHE_FRAC` 自体は expert の選択や routing の値を変えず、slot の容量を通じて resident にできる数を変える。初期化される条件は `hyb` が成立し、slot 数と slot bytes が正であること（`engine/src/hy4flash/run/hy4_graph.hip.h:717-779,865-885`）。

## ログと測定値

- tiered load 完了時は `[load] experts 4-tier: ... static VRAM ... + ... adaptive VRAM slots ...` の行に実際に割り当てた slot 数・容量が出る（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1250-1255`）。
- runtime cache 初期化に進んだ場合は `[vcache] pre-populated %d/%d adaptive VRAM slots ...` が stderr に出る（`engine/src/hy4flash/run/hy4_graph.hip.h:747-779`）。
- slab の `hipMalloc` が失敗した場合はその箇所でエラーを捨ててループを止め、確保済み slot 数で処理を続けるため、当該失敗専用の警告は出ない（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1127-1143`）。
- pinned host arena が失敗すると `[load] pinned host arena ... failed ...; retrying with CPU-expert mode` を出して再試行する。再試行も失敗した場合は呼び出し側で `experts: <理由>` を stderr に出してモデルロードを失敗させる（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1157-1172,1499-1501`）。
- `docs/DETAILS.md` の expert cache 説明は別系統の `--expert-cache` と通常エンジン設定についてであり、この HY4 固有割合の値域や動作を説明する資料は確認できなかった（`docs/DETAILS.md:439-455`）。ここでは測定値を記載しない。

## 根拠

- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:792-874` — 値の読取、未設定時の計算、clamp と枠算出。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:1073-1144` — slot サイズ、割当、VRAM 予約と確保失敗。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:1420-1502` — 全量ロードと tiered load の選択、CPU mode の優先順位。
- `engine/src/hy4flash/run/hy4_graph.hip.h:717-779,1582-1584` — hybrid 条件、cache 初期化、pre-populate ログ。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:361-405,516-539,647-659` — `HY4_GPUS` と `--gpus` / `--devices` による GPU 構成、load 呼び出し。
