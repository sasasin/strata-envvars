# `HY4_RESERVE_GB`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HY4 GPU モデルの読み込みで、ホット expert を VRAM に配置する予算から差し引く予約量を GiB で指定する。モデル読み込み中に動的 KV-cache の VRAM slab を追加確保する経路でも、同じ量を空き容量として残す。値は expert の配置量と動的 KV-cache の配置量に作用し、モデル重みや token 選択を直接変更する処理はこの変数の参照箇所にはない（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1125-1142,1404-1429`）。

通常の CLI 起動とサーバー起動は、モデルを読む前に `plan_memory` を呼ぶ。環境変数が未設定なら同関数が計画値を設定し、その後 `load_gpu_model` が読む。CLI では `engine/src/hy4flash/run/hy4_main.hip.cpp:648-659`、サーバーでは `engine/src/hy4flash/run/hy4_serve.hip.h:291-295`。この変数に対応する専用 CLI 引数は見つからなかった。

## 値と判定

環境からの文字列は `getenv` で取得し、数値化は `atof`。全体の厳密な数値検証やエラー処理はない。`atof` は先頭の空白と符号を含む数値部分を変換し、後続の非数値文字列を検証しない。例えば `2.5` と `2.5GiB` はどちらも数値部分の 2.5、`abc` と空文字は 0 になる。大文字小文字の判定はない。未設定と空文字は異なる扱いになる（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:545-562,1125-1126,1404-1425`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値・扱い |
|---|---|---|---|
| `plan_memory` から通常起動（HIP/CUDA 共通コード） | 予約値を計算し、小数第 2 位までの文字列で環境に設定 | 数値として変換される値。負値も拒否されず、後段の expert 予算を増やし得る | 空文字・数値に変換できない文字列は 0 として読み込まれるが、設定済みなので自動計算値で置き換わらない。数値の後ろの文字列は検証されない |
| `load_gpu_model` の expert 配置 | 直接この関数へ未設定で到達した場合の既定値は 6.0 GiB。ただし確認した CLI / server の入口は先に `plan_memory` を呼ぶ | `atof` の値を GiB として空き VRAM から差し引く | 数値不正・空文字は 0。負値は clamp されず、差し引きが加算になる |
| `load_gpu_model` の動的 KV slab 追加確保 | 0 GiB | `max(0.0, atof(value))` を GiB から byte に換算。正値なら slab 追加後の空き VRAM をその分残す | 空文字・数値不正・負値は 0 GiB。UMA GPU では予約 byte 自体を 0 にする |

自動計算は `plan_memory` が見積もった作業領域、KV、workspace、cuBLAS、DFly、prefill scratch、条件付き vision / peer graph、GPU の安全余裕を合算して GiB 換算し、`%.2f` で設定する。KV 予約は host mask、growable KV、GPU 容量などで変わる。Windows では `wddm_vram_floor_gb` の容量別値、それ以外では別の容量別値が使われる（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:413-431,434-439,515-559`）。

## 有効になる条件

- `HY4_RESERVE_GB` の読み取り箇所は Hy4-Flash の GPU model 実装にあり、通常の CLI と server の起動時の `plan_memory` / `load_gpu_model` の経路で参照される（`engine/src/hy4flash/run/hy4_main.hip.cpp:648-659`、`engine/src/hy4flash/run/hy4_serve.hip.h:291-295`）。
- 通常の expert 配置では、`HY4_EXPERT_VRAM_GB`、なければ `STRATA_HY4_VRAM_GB` が設定されていると、その値で expert budget を置き換えるため、`HY4_RESERVE_GB` の expert 配置への効果は上書きされる。peer GPU がない場合は CLI の `--vram-experts-gb` cap がさらに `min` で適用される。host-mapped trunk の場合は expert budget を 0 にする（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1420-1433`、CLI から cap を設定する箇所は `engine/src/hy4flash/run/hy4_main.hip.cpp:451-453,648-655`）。
- `STRATA_HY4_DISTRIBUTED` で expert shard を読む経路は通常の expert placement 分岐より前に入り、空き VRAM から `HY4_RESERVE_GB`（値が未設定なら 6.0 GiB）を引いた budget を shard loader に渡す。失敗時は `experts: <理由>` を出して読み込み失敗を返す（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1400-1409`）。
- 動的 KV slab への適用は `!gpu_is_uma()` のときに限られる。UMA GPU ではこの予約による slab 停止判定を行わない（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1125-1133`）。
- 自動値の計算はモデルの最大 context、chunk、GPU 容量・空き容量、multi-GPU / peer、vision、draft の有無、KV 設定などを使う。これらが変われば未設定時の自動値も変わる（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:434-439,452-510,545-562`）。

## 実行時の詳細

`plan_memory` は `getenv("HY4_RESERVE_GB")` が null の場合だけ自動値を計算し、`hy4_setenv` で同一プロセスの環境へ設定する。Windows では `_putenv_s`、それ以外では `setenv(..., 1)` を使う。null でなければ既存文字列を保持するため、空文字でも自動値を作らない（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:405-411,545-563`）。

値は static cache されない。計画時と `load_gpu_model` 内の expert / KV 確保時にそれぞれ `getenv` し、読み込み時点のプロセス環境を変換する。確認できた CLI / server の入口では計画とモデルロードが起動時に連続して行われ、リクエストごとに計画をやり直す呼び出しはない（`engine/src/hy4flash/run/hy4_main.hip.cpp:648-659`、`engine/src/hy4flash/run/hy4_serve.hip.h:291-307`）。

通常の expert loading では free VRAM から予約 byte を引いた値が expert budget となる。全 expert 領域がその budget に収まれば全体を確保し、収まらないか確保に失敗すれば tiered loading に進む。tiered loading では budget が host / SSD に置く expert 量にも影響する。負の予約値では budget が増え、値が未設定で直に読み込まれた場合は 6 GiB を引く（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1420-1459,1486-1502`）。

動的 KV-cache の確保では、非 UMA GPU で各 slab を確保する前に空き VRAM を確認し、`空き <= slab サイズ + 予約 byte` なら追加を止める。VRAM 確認に成功した場合の判定であり、`hipMemGetInfo` が失敗した場合はこの条件を通らず slab 確保を試す。実際に確保できた slot 数に `dyn_slots` を更新する（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1125-1143`）。

## ログと測定値

計画時は stderr に `[plan] ... reserve %s GiB` を出す。表示値は計画後の環境文字列で、自動生成した値またはユーザー指定値を示す。全 expert の GPU 確保失敗では `[load] full expert hipMalloc (...) failed; falling back to tiered loading`（CUDA build の分岐では `cudaMalloc`）を出して tiered loading に進む。tiered loading が失敗すると `experts: <理由>` を出してモデルロードが失敗する。予約値だけを理由とする専用警告やエラーは確認できなかった（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:564-565,1450-1459,1473-1481,1499-1502`）。

## 根拠

- 全参照と自動設定、計画ログ: `engine/src/hy4flash/run/hy4_gpu_model.hip.h:403-411,545-565`
- 動的 KV-cache の予約判定: `engine/src/hy4flash/run/hy4_gpu_model.hip.h:1125-1143`
- distributed / 通常 expert budget、他設定による上書き、tiered fallback: `engine/src/hy4flash/run/hy4_gpu_model.hip.h:1400-1409,1420-1459,1486-1505`
- CLI と server の計画・ロード順: `engine/src/hy4flash/run/hy4_main.hip.cpp:648-659`、`engine/src/hy4flash/run/hy4_serve.hip.h:291-307`
