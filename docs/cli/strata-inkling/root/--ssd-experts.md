# `strata-inkling --ssd-experts`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（root） |
| オプション | `--ssd-experts` |
| 別名 | なし |
| 値 | なし。expert の SSD cold-store 利用を有効にする真偽フラグ |

## 役割

GPU または RAM に載せきれない Inkling expert 重みを、`.strata` ファイルから bounded cold-store ring 経由で読む配置を選びます。CUDA の単一 GPU `.strata` 専用 loader では VRAM に収まる場合も全 expert を VRAM 常駐させる経路を避け、VRAM に入らない expert を RAM ではなく SSD 側に置きます。CPU/HIP では RAM 配置上限や GPU 容量と組み合わさって cold-store の有無が決まるため、全 expert が GPU に収まる場合まで SSD 読み込みを強制する指定ではありません。索引上は CUDA/HIP の `strata-inkling` root scope のオプションです。

## 使い方

```sh
# Inkling .strata モデルでベンチマークし、GPU/RAM に載らない expert を SSD 経由にする
strata-inkling --bench --native /models/inkling.strata --ssd-experts
```

`--ssd-experts` は値を取らず、`--native` のモデル指定などと併用します。parser はこのフラグを `BackendOpts` に設定し、通常の生成、serve、bench など backend 初期化へ進む処理で参照します（`engine/src/inkling2/ink_main.cpp:379-438,540-569`）。

## 値と既定値

- parser はオプションを見つけると `cfg.bopts.ssd_experts = true` とし、引数を消費しません。既定値は `false` です（`engine/src/inkling2/ink_main.cpp:433-439`, `engine/src/inkling2/ink_backend.h:29-32`）。
- 値の形式・数値範囲の validation はありません。値を後ろに付けてもこのフラグの値としては読まれず、別の引数として処理されます。未知の引数は `unknown option` を stderr に出して終了コード 2 になります（`engine/src/inkling2/ink_main.cpp:379-384,488-501`）。
- 同じフラグを複数回指定しても同じ `true` を再設定するだけです（`engine/src/inkling2/ink_main.cpp:437-439`）。

## 実行時の動作

- **CUDA 単一 GPU の `.strata` v1.1:** CUDA loader は `ssd_experts == false` のとき、expert section 全体が VRAM の予算内なら全量 VRAM 常駐の高速経路を使います。このフラグを指定するとその経路を選ばず、expert ごとに VRAM、RAM、SSD の順で配置する tiered 経路へ進みます。SSD 指定時は RAM expert 上限が 0 となり、VRAM 予算に収まらない expert は SSD-only として数えられます（`engine/src/inkling2/cuda/ink_runner.cuh:391-413,429-457`）。
- SSD-only expert があれば loader は `.strata` 内の Section 4 expert のオフセット・サイズ等を cold-store descriptor に登録し、4 reader の cold store と CUDA pinned-memory ring を開きます。SSD 状態を stderr に表示します（`engine/src/inkling2/cuda/ink_runner.cuh:478-512`）。ring は既定の `--ram-experts-gb` が 0 以下なら 512 MiB、正値なら 256 MiB 以上 2 GiB 以下の式で決まります（同 `:491-494`）。
- **HIP:** `ssd_experts` または `--ram-experts-gb 0` は expert の RAM 配置上限を 0 にします。GPU に配置できなかった expert は RAM tier に入りません。Strata 形式で GPU/RAM に載らない expert が残ったときに 512 MiB cold store を開きます（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1028-1033,1064-1098,1235-1255`）。
- **CPU:** expert が RAM に載りきらない場合、またはこのフラグが指定された場合に cold SSD を必要と判定します。`--ram-experts-gb` が 0 以下なら preload を 0 とし、512 MiB の LRU ring を設定します。正値ならその RAM cap を使いつつ ring 分を差し引いて preload する場合があります（`engine/src/inkling2/ink_cpu_backend.cpp:231-265`）。
- CUDA の `load_from_model_file` が上記 cold-store loader に委譲するのは、形式が Strata で、単一 GPU 要求（peer GPU なし、GPU 数 1 以下、layer split 指定なし）の場合です（`engine/src/inkling2/cuda/ink_runner.cuh:770-794`）。それ以外の CUDA 経路は別の配置処理となり、SSD cold-store を開く処理は確認できません。したがって `--ssd-experts` を GGUF/HF safetensors や CUDA multi-GPU 経路で SSD 専用配置として扱えるとは言えません（同 `:1182-1251,1303-1314`）。
- `--ram-experts-gb` は配置との相互作用があります。特に CUDA/HIP は本フラグ指定で RAM expert cap を 0 にしますが、CPU backend は正の RAM 上限なら一部 preload を残す実装です。CUDA ring サイズも値に応じて変わります（`engine/src/inkling2/cuda/ink_runner.cuh:293-299,437-457,491-494`; `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1028-1033`; `engine/src/inkling2/ink_cpu_backend.cpp:234-263`）。

## 適用条件と副作用

- このオプションは parser 上では複数の実行モードから受理されますが、`--info` や tokenizer export は backend 初期化より前に終了するため expert の配置には到達しません。通常生成・serve は共通の backend init を通り、bench 等は別 handler から同じ `BackendOpts` を渡します（`engine/src/inkling2/ink_main.cpp:544-569`。bench handler 呼び出しは `:549`）。
- cold-store は指定したモデルファイルを読み取り専用で開きます。Windows は `FILE_FLAG_NO_BUFFERING` を試し、失敗時に buffered open へ fallback します。POSIX は `O_DIRECT` を試し、失敗時に通常の read-only open を試します（`engine/src/inkling2/ink_cold_store.hpp:67-129`）。キャッシュ pool は CUDA では pinned memory、CPU/HIP では通常の pool として確保されます（CUDA の allocator は `engine/src/inkling2/cuda/ink_runner.cuh:495-504`; cold-store の pool 確保は `engine/src/inkling2/ink_cold_store.hpp:131-155`）。
- すべての expert を SSD に移すフラグではありません。CUDA/HIP は VRAM に入る expert を引き続き GPU に置きます（CUDA `engine/src/inkling2/cuda/ink_runner.cuh:441-457`; HIP `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1064-1098`）。

## 出力とエラー

- CUDA は cold-store の open が失敗すると loader が `false` を返します。cold-store はファイルを開けない場合や ring allocation 失敗時に `err` を設定します（`engine/src/inkling2/cuda/ink_runner.cuh:502-504`; `engine/src/inkling2/ink_cold_store.hpp:99-107,115-123,140-155`）。通常の起動経路では backend init 失敗を `init: <error>` として stderr に出し、終了コード 1 になります（`engine/src/inkling2/ink_main.cpp:564-568`）。
- CPU は cold-store open 失敗時に理由を stderr に出し、エラーをクリアして direct reads に fallback します（`engine/src/inkling2/ink_cpu_backend.cpp:285-289`）。HIP は cold-store open 成功時の状態表示を確認できますが、失敗時の分岐はこの箇所で別エラーを返さず、その後の実読み込み処理も含めて一般的な失敗時出力はここから一律には特定できません（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1235-1255`）。

## 根拠

- `engine/src/inkling2/ink_main.cpp:433-439` — parser が値なしフラグとして `BackendOpts` に設定。
- `engine/src/inkling2/ink_backend.h:29-32` — `vram_experts_gb`、`ram_experts_gb`、`ssd_experts` の既定値。
- `engine/src/inkling2/cuda/ink_runner.cuh:391-457,478-512,770-794` — CUDA 単一 GPU Strata 経路の tier 判定、cold-store 起動、経路条件。
- `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1028-1098,1235-1255` — HIP の RAM cap、expert 配置、Strata cold-store 条件。
- `engine/src/inkling2/ink_cpu_backend.cpp:231-301` — CPU の RAM preload、cold-store 条件と失敗時 fallback。
- `engine/src/inkling2/ink_cold_store.hpp:67-155` — read-only/direct open、fallback、ring 確保と open error。
