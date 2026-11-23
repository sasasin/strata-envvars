# `--ram-experts-gb`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（CUDA/HIP） |
| オプション | `--ram-experts-gb` |
| 別名 | なし |
| 値 | 浮動小数点数として解釈される値（RAM に置く expert の容量上限。実装は 1 GiB = 1,073,741,824 bytes として変換） |

## 役割

GPU に置ききれない Inkling expert のうち、ホスト RAM に常駐させる容量を上限指定します。CUDA/HIP backend は VRAM 配置を優先し、残った expert をこの上限まで RAM に置き、それ以外はモデルファイルからの cold/SSD streaming 対象にします。モデル全体が VRAM に収まり、SSD モードも指定されていない場合は全 VRAM 常駐経路が選ばれるため、この RAM 上限は使われません（`engine/src/inkling2/cuda/ink_runner.cuh:391-413`）。

## 使い方

```sh
# VRAM に入らない expert の RAM 常駐上限を 8 GiB にする
strata-inkling --native model.strata --ram-experts-gb 8

# RAM 常駐を無効にし、GPU と SSD streaming で配置する
strata-inkling --native model.strata --ram-experts-gb 0

# Serve モードでも同じ backend 初期化設定を渡す
strata-inkling --serve --native model.strata --ram-experts-gb 8
```

## 値と既定値

- 値は必須です。値が続かない場合、parser は `missing value after --ram-experts-gb` を stderr に出して終了コード 2 で終了します（`engine/src/inkling2/ink_main.cpp:379-383,435-436`）。
- parser は `std::atof` で変換し、正の値・ゼロ・負の値を個別に拒否する validation はありません。数値でない文字列も `atof` の結果として 0 になり、後述の 0 指定相当になります（`engine/src/inkling2/ink_main.cpp:435-436`）。
- 省略時の内部値は `-1.0` です。負の値は CUDA/HIP backend で自動容量扱いになり、利用可能 RAM などをもとに上限が決まります（`engine/src/inkling2/ink_backend.h:29-31`、`engine/src/inkling2/cuda/ink_runner.cuh:293-299`、`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1028-1051`）。
- `0` は RAM expert の常駐を許さない指定です。正の値は RAM 上限として扱います。複数回指定した場合、引数走査中に同じフィールドへ順次代入されるため最後の指定が残ります（`engine/src/inkling2/ink_main.cpp:379-384,435-436`）。

## 実行時の動作

parser は値を `BackendOpts::ram_experts_gb` に格納します。通常の生成・serve の backend 初期化、および bench / selfcheck 等の backend 初期化へこの設定が渡されます（`engine/src/inkling2/ink_main.cpp:101-117,130-144,546-569`）。CUDA backend は `opts.ram_experts_gb` を runner の `load` に転送し（`engine/src/inkling2/cuda/ink_cuda_backend.cu:197`）、HIP backend は同じ値から RAM budget を計算します（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1028-1032`）。

CUDA では、正値を bytes に変換して上限とし、未指定相当の負値では利用可能ホスト RAM から OS 用の余裕を差し引いて上限を推定します。取得した上限は cgroup の空き容量から予約分を差し引いた値でも制限されます（`engine/src/inkling2/cuda/ink_runner.cuh:293-299,437-457`）。HIP も正値を GiB から bytes に変換し、負値では Linux の `/proc/meminfo` の `MemAvailable` を使った安全上限を計算します。さらに cgroup 制限がある場合は予約分を差し引いて RAM 上限を抑えます（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1028-1059`）。

両 backend とも expert の配置では VRAM を先に試し、VRAM に入らない expert だけを RAM 上限内で RAM に置きます。上限を超える expert は cold/SSD 側になります（CUDA: `engine/src/inkling2/cuda/ink_runner.cuh:442-457`、HIP: `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1085-1098`）。

## 適用条件と副作用

- この文書の対象は索引上の `strata-inkling`（CUDA/HIP、`engine/src/inkling2/ink_main.cpp`）です。`strata-inkling-metal` と `strata-inkling-sycl` は別入口・別スコープで、同じオプションの登録は索引にありません（`docs/cli/README.md:1509-1547,1549-1592`）。
- `--ssd-experts` を併用すると RAM budget は 0 扱いとなり、正の `--ram-experts-gb` を指定していても RAM 常駐には使われません（CUDA: `engine/src/inkling2/cuda/ink_runner.cuh:293-295,441-457`、HIP: `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1028-1032`）。
- 値を `0` にした場合も CUDA は RAM 常駐を無効にし、必要な cold expert 用に pinned DMA ring と cold store を用意します（`engine/src/inkling2/cuda/ink_runner.cuh:441-457,478-505`）。
- 正値を指定しても VRAM に expert が収まれば RAM は使われません。RAM と SSD の割り当てはモデルの expert サイズ、VRAM 容量、ホスト RAM / cgroup の余裕に依存します。
- HIP は `.strata` モデルで VRAM と RAM に置けなかった expert があれば 512 MiB の ColdStore を試します。open に失敗した場合も ColdStore を開いた分岐に入らず、後続の expert 読み出しは直接読み出し経路を使います（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1235-1255,4129-4173`）。
- CPU backend でも同じ設定フィールドが使われます。CPU backend は指定量を cgroup-aware な byte 上限に変換し、expert を優先順に RAM へ preload します。上限外の expert がある場合は bounded cold-store ring を使い、open に失敗すると stderr に警告して直接読み出しへ fallback します（`engine/src/inkling2/ink_cpu_backend.cpp:231-243,244-287`）。

`--cpu` を付けると parser が CPU backend を選びます。この場合も `--ram-experts-gb` は同じ `BackendOpts` として渡され、上記 CPU backend の配置規則が使われます（`engine/src/inkling2/ink_main.cpp:477,564-565`）。

## 出力とエラー

オプション値自体に対する範囲エラーや警告は parser にありません。モデル/backend 初期化が失敗した場合、通常モードは `init: <理由>` を stderr に出し終了コード 1、serve モードはプロトコルの `ERR init: <理由>` を出して終了コード 1 になります（`engine/src/inkling2/ink_main.cpp:564-568`）。CUDA が SSD streaming を有効にした場合は配置数や ring 情報を stderr に出します（`engine/src/inkling2/cuda/ink_runner.cuh:502-512`）。

## 根拠

- `docs/cli/README.md:1509-1547` — `strata-inkling` の CUDA/HIP root scope と指定オプションの索引リンク。
- `engine/src/inkling2/ink_main.cpp:379-383,433-436` — 引数値の取得と `atof` による格納。
- `engine/src/inkling2/ink_backend.h:29-31` — backend option の既定値と RAM/SSD の意味。
- `engine/src/inkling2/cuda/ink_runner.cuh:293-299,391-413,437-457,478-512` — CUDA の自動/明示 RAM 上限、配置順、cold-store 経路と出力。
- `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1028-1059,1085-1098` — HIP の RAM 上限計算と配置。
- `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1206-1255,4129-4173` — HIP の RAM 配置後に残る expert の ColdStore 利用と読み出し。
- `engine/src/inkling2/ink_cpu_backend.cpp:231-287` — CPU backend の preload 上限・cgroup 制限・cold-store fallback。
- `engine/src/inkling2/ink_main.cpp:564-568` — backend 初期化失敗時の出力と終了コード。
