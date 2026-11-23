# `HY4_HOST_NEED_GB`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HIP Hy4 GPU モデルの tiered expert 読み込みで、自動算出する安全 RAM 予算から差し引く予約量（GB）を表す。`load_experts_tiered` はこの値を引いた RAM 予算と host experts の推定量を比較し、収まらないとき CPU + SSD cold-expert streaming に切り替える。expert の配置が VRAM に収まる通常の全 GPU 読み込みでは、この比較は実行されない（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:805-828, 842-848`; `engine/src/hy4flash/run/hy4_gpu_model.hip.h:1486-1502`）。

## 値と判定

| 条件 | unset | 設定時に使う値 | 無効・境界値 |
|---|---|---|---|
| `load_experts_tiered` の自動 RAM 予算経路 | `need = 0.0` GB | `atof` の変換結果（GB）を Windows / 非 Windows 別の総 RAM・空き RAM 予算からそれぞれ差し引く | 数値変換の検証、範囲制限、負値の拒否はない。空文字や数値で始まらない文字列は `atof` で `0` になる。数値に続く文字は終端検査をしないため無視される（例: `1.5junk` は通常 `1.5`）。`0` と `0anything` は差し引き 0、負値は予算を増やしうる |

この環境変数の読み取り自体は `getenv(...) ? atof(...) : 0.0` であり、空文字も「設定あり」ですが、変換結果は 0 です。大文字小文字・空白・数値全体の妥当性を別途検査しません（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:810-815`）。

通常のオフライン GPU 実行では、先に `plan_memory` が `HY4_HOST_NEED_GB` を `snprintf("%.2f", ...)` の計算値で設定し、`hy4_setenv` は Windows で `_putenv_s`、それ以外で `setenv(..., 1)` を使うため、呼び出し時点の利用者設定を上書きします。算出量は host KV、host embed、VRAM に置けない trunk、VRAM 容量に応じた bounce 予約、および固定 `0.35` GB の合計です（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:402-410, 515-543`）。

## 有効になる条件

- 実装は `engine/src/hy4flash/run/` の HIP 実装です。オフライン経路では `plan_memory` が実行されるため、外から設定した値は自動算出値に置き換わります（`engine/src/hy4flash/run/hy4_main.hip.cpp:613-649`）。
- `--serve` 経路は `plan_memory` を呼ぶ前に `hy4_serve_main` へ戻るため、この計画関数による書き戻しはありません（`engine/src/hy4flash/run/hy4_main.hip.cpp:544-611`）。tiered 読み込みに進み、かつ後述の RAM 予算が自動計算される場合には、起動時に引き継いだ値が使われます。
- `HY4_RAM_BUDGET_GB` が設定されていればその値、そうでなく `STRATA_HY4_RAM_GB` が設定されていればその値が優先され、`HY4_HOST_NEED_GB` は読まれません。設定有無で選ぶため、空文字でも上位変数が選ばれ、`atof("")` 相当の 0 GB に clamp されます（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:810-813`）。
- `--ram-experts-gb N` は `N >= 0` のとき `STRATA_HY4_RAM_GB` を設定します。`--ssd-experts` は `HY4_RAM_BUDGET_GB=0` と `STRATA_HY4_RAM_GB=0` を設定します。いずれも自動予算より優先されるので、この場合は対象変数が予算に影響しません（`engine/src/hy4flash/run/hy4_main.hip.cpp:451-465`）。
- いずれの環境変数による予算でも、`--ram-experts-gb` の非負 cap があれば最終予算はその値以下に制限されます（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:830-832`）。
- 値が予算に反映されても、GPU 全体へ expert を読み込めた場合は `load_experts_tiered` に入らず、host experts の予算比較もありません。tiered 経路で host experts 推定量が予算を超えた場合に限り、自動で CPU mode が有効になります（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1473-1502, 842-848`）。

## 実行時の詳細

`plan_memory` はオフライン経路で GPU の VRAM 状況、モデルの Section 1/4 サイズ、context、KV 方式、vision の有無などから host 側の見積もりを作り、環境へ書き込みます。tiered loading では `HY4_RAM_BUDGET_GB`、次に `STRATA_HY4_RAM_GB`、最後に自動計算を選びます。自動計算時は `HY4_HOST_NEED_GB` と `HY4_ENGRAM_CACHE_MIB`（未設定時は RAM 上限に応じた 128/256/512/850 MiB）、OS 別の予約量、vision の有無を考慮し、空き RAM が 0.5 GiB 以下なら空き RAM 側の制約を使わず、それ以外は総 RAM 側と空き RAM 側の小さい予算を採ります。最後に非負の `--ram-experts-gb` cap を適用します（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:805-832`）。

host experts 推定量が最終予算を超えて `cpu_mode` がまだ false の場合、`cpu_mode` を true にし、stderr に `[load] host experts %.1f GB exceed safe RAM budget %.1f GB (avail %.1f / %.1f GiB); auto-enabling 4-tier CPU + SSD cold-expert streaming\n` を出します。CPU mode が既に有効ならこのログは出ません。RAM 予約領域の `hipHostMalloc` に失敗した経路では、別の `[load] pinned host arena %.2f GB failed (WDDM/commit limit); retrying with CPU-expert mode\n` を出して tiered loader を CPU mode で再試行します（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:842-848, 1159-1174`）。

環境は各読み取り箇所で都度参照され、対象値を static cache するコードはありません。`plan_memory` の自動設定は現在のプロセス環境への書き込みで、子プロセスへの転送はこのコードにはありません。serve は計画関数を通らず、loader 内で設定値を読む場合の値は serve 起動時のプロセス環境に依存します（`engine/src/hy4flash/run/hy4_main.hip.cpp:544-611`; `engine/src/hy4flash/run/hy4_gpu_model.hip.h:405-410, 810-815`）。

## ログと測定値

対象値そのものの有効・無効を示す専用ログはありません。予算不足時の CPU + SSD 切替と pinned host arena 失敗時の再試行ログは上記のとおりです（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:842-848, 1161-1174`）。この変数について条件つきの測定値は確認できません。

## 根拠

- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:402-410, 515-543` — helper の環境設定方法と、オフライン計画での値の算出・書き込み。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:805-832` — 値の読み取り、予算優先順位、OS 別の自動予算、RAM cap。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:842-848, 1159-1174, 1486-1502` — tiered 経路での適用、ログ、再試行。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:451-465, 544-611, 613-649` — CLI による予算設定、serve とオフライン経路の違い、計画関数の呼び出し。
