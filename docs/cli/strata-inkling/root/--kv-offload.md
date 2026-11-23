# `strata-inkling --kv-offload`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（root） |
| オプション | `--kv-offload` |
| 別名 | なし |
| 値 | 値を 1 個取る。help の表記は `auto` / `on` / `off` |

## 役割

Inkling CUDA backend の global KV cache を GPU VRAM と mapped pinned host RAM のどちらに置くか、また VRAM 不足時に host RAM へ spill するかを指定します。索引上の `strata-inkling` は CUDA/HIP の入口ですが、現行ソースでこの設定を読み取って KV 配置に反映する実装は CUDA runner です。HIP や CPU backend では値を処理する箇所を確認できず、同じ効果は裏付けられません（`engine/src/inkling2/ink_main.cpp:426-427`、`engine/src/inkling2/ink_backend.h:150-168`、`engine/src/inkling2/cuda/ink_cuda_backend.cu:149,240`）。

## 使い方

```sh
# CUDA backend で serve を起動し、global KV の配置を自動選択する
strata-inkling --serve --native ./model.strata --kv-offload auto
```

`--kv-offload` は parser 上、`--bench` と `--serve` の使用例に記載されています。backend を作って実行する経路でも共通設定として渡されます（`engine/src/inkling2/ink_main.cpp:494-496,540-569`）。

## 値と既定値

- 値の既定値は `auto` です（`engine/src/inkling2/ink_backend.h:34`）。
- parser は次の引数を文字列として保存するだけで、`auto` / `on` / `off` の検証をしません。値を省略すると `missing value after --kv-offload` を stderr に出し、終了コード 2 で終了します（`engine/src/inkling2/ink_main.cpp:381-383,426-427`）。
- 同じオプションを複数回指定した場合は、引数走査中に値が上書きされ、最後の値が残ります（`engine/src/inkling2/ink_main.cpp:379-384,426-427`）。
- CUDA backend は値がちょうど `on` なら on、ちょうど `off` なら off、それ以外を auto 相当の 0 として扱います。したがって未知の値や空文字も明示的なエラーにはならず、auto 相当になります（`engine/src/inkling2/cuda/ink_cuda_backend.cu:149`）。help に示される値は `auto|on|off` です（`engine/src/inkling2/ink_main.cpp:494,496`）。

## 実行時の動作

CUDA backend は mode を runner に渡し、初期化時に VRAM と host RAM の利用可能量を見積もります。host RAM 側は OS 用に 2 GiB を差し引いた量から、256 token 単位で収まる最大 context を算出します（`engine/src/inkling2/cuda/ink_runner.cuh:1941-1969`）。

- `on`: host RAM の見積もりが 256 token 以上なら、global KV の GPU 側容量を 0、host 側を `max_ctx` とし、host 側に置きます。host RAM に収まらない場合はこの分岐を通らず、VRAM 配置・自動縮小の分岐へ進むため、`on` 指定だけで host 配置が保証されるわけではありません（`engine/src/inkling2/cuda/ink_runner.cuh:1971-2005`）。
- `auto`（および未知の値）: VRAM だけで `max_ctx` を確保できない場合、host RAM 見積もりが 256 token 以上なら VRAM/host の分割を設定します。分割時の VRAM 側は、VRAM 見積もりが 1024 token 以上ならその約 3/4 を 256 token 単位に切り下げ、残りを host 側に割り当てます。両方の容量で `max_ctx` を満たせない場合は `max_ctx` も縮小されます（`engine/src/inkling2/cuda/ink_runner.cuh:1978-2005`）。
- `off`: 初期配置で host KV を使わない分岐に入り、global KV を VRAM に配置します。VRAM 不足時の elastic spill も無効になります（`engine/src/inkling2/cuda/ink_runner.cuh:1996-2005,2283-2291`）。

初期化後の elastic KV cache 成長時、`auto` / `on` 相当では VRAM に必要量を確保できず、かつ host 側がまだ割り当てられていない場合、global KV の末尾を mapped pinned host RAM に割り当てて spill します。`off` はこの処理の条件から除外されます（`engine/src/inkling2/cuda/ink_runner.cuh:2283-2341`）。

`--kv-dtype`（別名 `--kv`）は KV 1 token あたりのメモリ量に関係します。また自動 dtype 選択では `off` を VRAM 限定として扱い、GPU 容量・世代・context に応じて FP8 を選ぶ条件があります（`engine/src/inkling2/cuda/ink_cuda_backend.cu:149-168,170-181`）。`--max-context`、`--parallel`、GPU 選択や layer split も容量計算に関係します（同 `:148,170-198`、`engine/src/inkling2/cuda/ink_runner.cuh:1910-1968`）。

## 適用条件と副作用

- 効果が確認できるのは `make_default_backend` が CUDA backend を選択し、CUDA runner の初期化へ進む場合です。`--cpu` を指定すると CPU backend が選択されます。HIP / Metal / SYCL backend の現行実装には `kv_offload` を読む参照がなく、このオプションによる host KV offload 効果は確認できません（`engine/src/inkling2/ink_backend.h:150-168`、`engine/src/inkling2/ink_main.cpp:443-477`、`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:694-699`）。
- 自動・明示 offload は mapped pinned host RAM を確保します。CUDA runner は `cudaHostAlloc(..., cudaHostAllocMapped)` と `cudaHostGetDevicePointer` を使い、global KV の host 側領域を GPU から参照可能にします（`engine/src/inkling2/cuda/ink_runner.cuh:1876-1895,2035-2048`）。
- 初期 host KV 確保に失敗すると、警告を stderr に出し、その visit の host 領域を解放して GPU 側容量へフォールバックします（`engine/src/inkling2/cuda/ink_runner.cuh:2049-2056`）。elastic spill 時の host allocation が成立しない場合は spill 成功経路に入らず、容量拡張が失敗します（同 `:2289-2341`）。
- `--info`、`--export-tokenizer` の処理自体は backend 初期化へ進まないため、この値による配置効果はありません（`engine/src/inkling2/ink_main.cpp:544-546`）。

## 出力とエラー

- `on` の初期 host 配置では stderr に `[InkCUDA] Host KV Offload ON ...`、auto 分割では `[InkCUDA] Auto Host KV Offload ...` を出します（`engine/src/inkling2/cuda/ink_runner.cuh:1971-1995`）。
- elastic spill が発生すると stderr に配置 token 数を出します（`engine/src/inkling2/cuda/ink_runner.cuh:2322-2336`）。初期の mapped host allocation 失敗は警告を出して GPU 側へフォールバックします（同 `:2049-2056`）。
- オプションの値そのものに対する validation error はありません。未知の option 名は別経路で `unknown option: ...` を stderr に出して終了コード 2 になります（`engine/src/inkling2/ink_main.cpp:499-501`）。

## 根拠

- `engine/src/inkling2/ink_main.cpp:379-383,426-427`: 共通 parser が次の引数を `kv_offload` 文字列に保存する箇所。
- `engine/src/inkling2/ink_backend.h:17-38`: `BackendOpts` の既定値と設定フィールド。
- `engine/src/inkling2/ink_backend.h:150-168`: build backend 選択と CPU fallback。
- `engine/src/inkling2/cuda/ink_cuda_backend.cu:146-181,233-241`: CUDA backend における mode 変換、dtype/容量見積もりとの相互作用、runner への引き渡し。
- `engine/src/inkling2/cuda/ink_runner.cuh:1876-1895,1927-2009,2035-2056,2283-2341`: host memory mapping、初期配置、失敗時 fallback、実行中の elastic spill。
- `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:694-699`: HIP backend の初期化では `kv_dtype` を参照するが、`kv_offload` の参照は確認できない。
- `docs/cli/README.md:1509-1530`: tool ID と root scope、および指定オプションの索引リンク。索引は調査対象のソース根拠ではなく、配置確認に使用。
