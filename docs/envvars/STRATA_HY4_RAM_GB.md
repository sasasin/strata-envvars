# `STRATA_HY4_RAM_GB`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HY4 の HIP/CUDA GPU ローダーが expert を段階配置する際に、GPU に載らない expert のうちホスト RAM に置く量の予算（GiB）を指定する。予算を超える必要があると CPU expert モードへの切替条件になり、CPU モードでも収まらない cold tail はモデルファイル上に残す。GPU に expert 全量を配置できた場合、この変数を読む段階的ローダー自体が呼ばれない。読み取りは `engine/src/hy4flash/run/hy4_gpu_model.hip.h:792-833, 1420-1503`。

## 値と判定

段階的ローダーで `HY4_RAM_BUDGET_GB` が未設定のときだけ、この変数を `getenv` で参照する。値は `atof` で数値接頭辞を変換し、`std::max(0.0, ...)` で負数を 0 に丸める。文字列全体の妥当性検査や上限 clamp はない。空文字・数値で始まらない文字列は `atof` の結果が 0 となり、`1xyz` は 1 として扱われる。`0`、`0anything`、負数は 0、正の数はその値（例: `8`, `8.5`, `1e1`）となる。前後の空白は `atof` の変換規則に従い、大文字小文字の比較はない。根拠: `engine/src/hy4flash/run/hy4_gpu_model.hip.h:805-812`。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| HIP/CUDA の HY4 段階的 GPU ロード | 自動算出した RAM 予算 | `1`, `8.5`, `1e1` など、`atof` が正数に変換する値 | 空文字、`abc`, `0`, `0anything` は 0。負数も 0 に clamp |

## 有効になる条件

- `engine/src/hy4flash/run/hy4_gpu_model.hip.h` の HY4 GPU ローダー経路であること。モデルの Section 4（experts）全量が VRAM 予算内で GPU に載る場合は通常の全量ロードが選ばれ、この変数は読み取られない（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1434-1503`）。
- 全量ロードに失敗するか予算上全量を載せられず、`load_experts_tiered()` に進むこと（同 `:1450-1500`）。この関数は `with_experts` が真の `load_gpu_model()` から呼ばれる（同 `:1420-1421, 1499-1500`）。
- `HY4_RAM_BUDGET_GB` が設定されている場合は、空文字も含めてそちらを使うため、この変数は無視される。設定値は `atof` 後に 0 以上へ clamp される（同 `:810-812`）。
- CLI の `--ram-experts-gb N` は `atof(N)` が 0 以上なら環境に `STRATA_HY4_RAM_GB=N` を設定する。加えて CLI 値は `g.ram_experts_gb_cap` にも渡され、環境由来の予算をその値以下に制限する。CLI 値が負なら環境への設定も cap も行わず、既存の環境値が使われる（`engine/src/hy4flash/run/hy4_main.hip.cpp:367, 455-458, 654-659`; `engine/src/hy4flash/run/hy4_gpu_model.hip.h:830-832`）。ただし先に `HY4_RAM_BUDGET_GB` が設定されている場合は、CLI がこの変数を書いても読み取り優先順位は変わらない。
- `--ssd-experts` は `HY4_RAM_BUDGET_GB=0` と `STRATA_HY4_RAM_GB=0` を設定し、さらに `ram_experts_gb_cap=0` とするため、RAM 予算を 0 にする（`engine/src/hy4flash/run/hy4_main.hip.cpp:460-465`）。
- CPU expert モードでない初期経路でも、GPU 外に必要と見積もった expert 量がこの予算を超えると CPU + SSD cold-expert streaming を自動で有効にする（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:842-849`）。CPU モードではホスト expert が予算を超える分を rank の低温側から SSD 上に残す（同 `:1090-1110`）。
- 自動予算は OS ごとに空き RAM・総 RAM・`HY4_HOST_NEED_GB`・`HY4_ENGRAM_CACHE_MIB`・Vision 有無を使って算出される。この変数があるとその算出を置き換える。続けて `--ram-experts-gb` の cap があれば小さい方を採用する（同 `:813-832`）。
- 同名の環境変数読み取りは HIP/CUDA 共用の `.hip.h` にのみ見つかった。SYCL runner は `--ram-experts-gb` を引数として直接渡し（`engine/src/hy4flash/sycl/sy_main.cpp:103, 140-141, 304`）、この環境変数を読む箇所はない。Metal runner は `--ram-experts-gb` を未使用として警告する（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1603`）。

## 実行時の詳細

`STRATA_HY4_RAM_GB` 自体は `load_experts_tiered()` が呼ばれるたびに環境から読み、static cache しない。読み取り時点はモデルロード中である。既定値としての自動計算は、Windows では総 RAM に対する予約分と各種 headroom、Linux 等では別の予約率と headroom を差し引き、利用可能 RAM が取得できる場合は総量基準と空き量基準の小さい方を用いる（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:805-828`）。

RAM 予算は `gib_to_bytes()` で GiB を 2^30 倍して byte 数にし、GPU 予算を超えてホスト側に必要な容量の判定に使う（`engine/src/hy4_gpu_model.hip.h:834-849`; 変換定義: `engine/include/strata/platform/cgroup_mem.hpp:187-190`）。CPU モードでホスト expert が予算を超えると、expert directory の rank-major 順に低温側 expert を tier 3 として残し、ファイルから必要時に読む構成にする（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1090-1110`）。通常の pinned-host 配置に失敗した場合はログを出し、CPU モードを指定して同じ関数を再実行するため、その再呼び出しでも値を読み直す（同 `:1157-1172`）。

## ログと測定値

この値の読み取りや採用だけを示す専用ログはない。非 CPU モードから予算超過で CPU + SSD に切り替わる場合は、stderr に `[load] host experts %.1f GB exceed safe RAM budget %.1f GB (avail %.1f / %.1f GiB); auto-enabling 4-tier CPU + SSD cold-expert streaming` を出す（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:845-848`）。CPU モードでホスト expert が予算を超える場合は `[load] RAM budget %.1f GB for the host experts (%.1f GB wanted): %llu experts (%.2f GB, the coldest ranks) stay on the SSD` を出す（同 `:1097-1110`）。pinned host arena の確保失敗時は `[load] pinned host arena %.2f GB failed (WDDM/commit limit); retrying with CPU-expert mode` を出す（同 `:1161-1172`）。この変数に関する測定値は Strata の資料に見つからなかった。

段階的ロード自体が失敗すると stderr に `experts: <理由>` を出してロード失敗を返す。通常 CLI はモデルロード失敗で終了コード 1 になり、server 経路は `ERR cannot load <model>` をプロトコル出力して終了コード 1 を返す（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1499-1501`; `engine/src/hy4flash/run/hy4_main.hip.cpp:658-659`; `engine/src/hy4flash/run/hy4_serve.hip.h:293-297`）。

## 根拠

- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:805-832` — 環境変数の優先順位、数値変換、既定予算、CLI cap。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:842-849, 1090-1110` — CPU + SSD 切替条件と cold tail の扱い。
- `engine/include/strata/platform/cgroup_mem.hpp:187-190` — 予算 GiB から byte 数への変換。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:1420-1503` — expert GPU 全量ロードと段階的ロードの選択。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:455-465, 654-659` — `--ram-experts-gb` / `--ssd-experts` の設定とモデルへの cap 受け渡し。
- `engine/src/hy4flash/run/hy4_serve.hip.h:268-295` — サーバーモードでの cap 受け渡しとロード呼び出し。
- `engine/src/hy4flash/sycl/sy_main.cpp:140-141, 304`、`engine/src/hy4flash/metal/hy4_metal_main.cpp:1603` — 他 backend での別経路。
