# `HY4_KV_DEVPOS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Hy4-Flash ランナーで、疎層KVキャッシュとIndexPool状態をVRAM上に保持する位置数の上限を指定する。値を超える位置まで必要になると、キャッシュ一式を pinned host memory に移す。未設定または `atoi` の結果が0以下なら、この上限による早期移行は起きず、`max_ctx` またはVRAM不足時の移行に従う。対象コードは `strata-hy4` の CUDA/HIP 実装で、Metal/SYCL版ではこの変数の読み取りは見つからなかった。`STRATA_BUILD_HY4` は既定でOFFであり、CUDAまたはHIPを有効にしてビルドした場合にこの実装が含まれる（`engine/CMakeLists.txt:846-852,884-889`）。

## 値と判定

`Runner::init` は `getenv` が返す文字列を `atoi` に渡す。環境変数が未設定なら0、空文字や数字で始まらない文字列も `atoi` の結果は0となる。先頭の空白・符号の後にある数字列を整数化し、数値に続く文字は検査しないため、例として `4096tail` は4096、`0anything` は0、`-4096` は負値となる。大文字小文字による判定はない。`kv_dev_limit > 0` の場合だけ上限判定に使われるため、0と負値は上限なしと同じ扱いである（`engine/src/hy4flash/run/hy4_graph.hip.h:1596-1608,2795-2802`）。

| ビルド・状況 | unset | 設定時に上限として有効になる値 | 上限として無効になる値 |
|---|---|---|---|
| `strata-hy4` のCUDA/HIPランナー | 0。正の上限なし | `atoi` の結果が正の整数。例: `4096`, `8192`, `4096tail` | `atoi` の結果が0以下。例: 空文字、`0`, `0anything`, `true`, `-1` |

`atoi` による変換で、全体の数値妥当性検査や範囲クランプはない。正の値が `max_ctx` より大きくても値自体は保持されるが、実際の伸長先は `max_ctx` 以下になる（同ファイル `:1599,2798-2801`）。

## 有効になる条件

- `strata-hy4` を使うこと。ビルドは `STRATA_BUILD_HY4=ON` かつ CUDA または HIP が必要で、CMake上Metal/SYCLは別実装である（`engine/CMakeLists.txt:846-852`）。
- CLI実行とサーバーモードはいずれも `plan_memory` の後に `Runner::init` を呼び、この値を読む（`engine/src/hy4flash/run/hy4_main.hip.cpp:648-659,692-705`; `engine/src/hy4flash/run/hy4_serve.hip.h:291-316`）。
- 正の値が上限として効くには、`kv_is_host` でないことと、伸長先 `target` が上限より大きくなることが必要。`HY4_KV_HOST` のビット0が立つ場合は `kv_is_host` となり、初期化時から疎層KVをhost側に置くため、このVRAM上限による伸長制御は使われない（`engine/src/hy4flash/run/hy4_graph.hip.h:1598-1608,2795-2802`）。
- メモリ計画時、必要VRAMの見積りが不足し、`HY4_KV_HOST` 自体が未設定で、算出可能な `dev_pos` が4096以上かつ `max_ctx` 未満、さらに trunk がVRAMに残る場合は、Strataが計算した値で `HY4_KV_DEVPOS` を上書きする。これは利用者が指定済みでも同じである。条件を満たさない場合はこの代入がなく、既存値が初期化で使われる（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:515-528`）。
- `HY4_KV_HOST` が設定されていると、値が空文字や `0` でも `getenv` の存在判定により自動 `dev_pos` 設定経路を止める。後段の `atoi` では空文字は0になるため、この場合はhost強制ビットが立たず、手動の `HY4_KV_DEVPOS` があれば別途読み込まれる（同ファイル `:520-530`; `engine/src/hy4flash/run/hy4_graph.hip.h:1598-1601`）。

## 実行時の詳細

メモリ計画はモデル初期化前にCLI側（`hy4_main.hip.cpp:648-659`）またはサーバー側（`hy4_serve.hip.h:291-295`）で実行される。計画関数は条件に応じて環境変数を設定し、続いて `Runner::init` が `HY4_KV_DEVPOS` を読み `kv_dev_limit` に保存する。プロセス起動時に一度読むだけのグローバルcacheではなく、Runnerごとの初期化時に読み、その後の伸長処理は保存済みフィールドを参照する。初期化後の環境変更はそのRunnerには反映されない（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:520-528`; `engine/src/hy4flash/run/hy4_graph.hip.h:1437,1596-1608,2795-2802`）。

初期の疎層KV領域は、正の `kv_dev_limit` が `max_ctx` より小さい場合にはその値までに制限される。後の `kv_grow_to` は必要サイズからステップ単位で `target` を算出し、`target > kv_dev_limit` ならVRAM伸長をせず `kv_spill_to_host()` に移る。VRAM空き容量が不足して伸長できない場合も同じ移行経路を使う。移行では疎層KVとIndexPoolを pinned host memory に確保・コピーし、`kv_is_host` をtrueにして以降の伸長を止める（`engine/src/hy4flash/run/hy4_graph.hip.h:1602-1609,2795-2818,2767-2793`）。

## ログと測定値

自動計画で `dev_pos` が設定された場合、stderrに `[plan] growable KV: up to %ld positions stay in VRAM, moves to pinned host memory if context exceeds that` が出る。上限到達またはVRAM不足で移行した場合は `[runner] sparse KV + IndexPool moved to pinned host memory (%d positions, %.2f GB, %.2f s)` が出る。上限までVRAM上で伸長できた場合は `[runner] sparse KV + IndexPool grew in VRAM: %d -> %d positions (%.2f GB total, %.1f ms)` が記録される。手動値がそのまま使われる場合に専用の有効・無効ログはない（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:564-566`; `engine/src/hy4flash/run/hy4_graph.hip.h:2793,2855-2856`）。

## 根拠

- `engine/CMakeLists.txt:846-852,884-889` — ビルド条件とCUDA/HIPソースの選択。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:515-535` — VRAM見積り、値の自動算出・設定、および `HY4_KV_HOST` との関係。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1596-1623` — 値の読み取り、上限による初期KVサイズ決定、host/VRAM配置。
- `engine/src/hy4flash/run/hy4_graph.hip.h:2767-2802,2808-2818,2820-2856` — host移行、上限超過判定、VRAM伸長とログ。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:648-659,692-705`; `engine/src/hy4flash/run/hy4_serve.hip.h:291-316` — CLIとサーバーの計画・Runner初期化経路。
