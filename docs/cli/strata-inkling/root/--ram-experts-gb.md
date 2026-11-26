# `--ram-experts-gb`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（トップレベル） |
| オプション | `--ram-experts-gb` |
| 別名 | なし |
| 値 | GiB 単位の数値（`double`）。RAM に置く expert 重みの上限を指定する |

## 役割

モデルの expert 重みを GPU メモリに置けなかった場合に、ホスト RAM に常駐させる量を制限する。上限を超えた expert は、backend とモデル形式に応じて SSD からの読み出し対象になる。値は `--serve`、`--bench` のほか、トップレベルの直接実行にも共通の backend 設定として渡される。CPU backend でも参照される。

## 使い方

```sh
strata-inkling --bench --native model.strata --ram-experts-gb 8
```

この例は benchmark 実行時に RAM expert 上限を 8 GiB として起動する。値の指定自体はコマンドモードを限定しない。

## 値と既定値

- 引数が必要で、`std::atof` で `double` に変換される。オプションの後に値がなければ `missing value after --ram-experts-gb` を stderr に出して終了コード 2 で終了する（`engine/src/inkling2/ink_main.cpp:845-849,910-911`）。
- 既定値は `-1.0`。負値は各 backend の自動上限を選ぶ（`engine/src/inkling2/ink_backend.h:30-32`）。
- `0` は RAM 常駐を許さない指定。正値は指定 GiB を byte 上限に換算する。CUDA/HIP の換算は `2^30` byte/GiB、CPU backend は `cgroup_mem::gib_to_bytes` を使う（`engine/src/inkling2/cuda/ink_runner.cuh:296-303`; `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1090-1094`; `engine/src/inkling2/ink_cpu_backend.cpp:229-231`）。
- CLI に数値範囲や形式の検証はない。`atof` が数値として読めない文字列や空文字列を受け取ると `0` になり、0 の扱いへ進む。負の値も拒否されず自動上限として扱われる（parser: `engine/src/inkling2/ink_main.cpp:910-911`）。
- 同じ引数を複数回指定した場合、parser はその都度同じフィールドへ代入するため、最後に現れた値が残る（`engine/src/inkling2/ink_main.cpp:845-849,910-911`）。

## 実行時の動作

値は `BackendOptions::ram_experts_gb` に入り、backend のモデルロード時に expert の配置計画へ使われる。CUDA は backend から CUDA runner に値を転送する（`engine/src/inkling2/ink_cuda_backend.cu:227-232`）。

- **CUDA**: 正値では指定上限まで、GPU に入らない expert を RAM に割り当てる。負値では利用可能ホスト RAM から OS 用の余裕（2〜4 GiB相当の規則）を差し引いた量を上限にし、取得できない場合は上限なしとして扱う。`0` または `--ssd-experts` 指定時は RAM expert を割り当てず、SSD-only tier を使う。SSD-only のとき、正値は pinned DMA ring のサイズにも使われ、256 MiB 以上 2 GiB 以下に制限される。非正値では ring は 512 MiB（`engine/src/inkling2/cuda/ink_runner.cuh:296-303,448-468,534-568`）。
- **HIP**: 正値は RAM 上限に使われる。`0` と `--ssd-experts` は RAM 上限 0。負値で `--ssd-experts` がない場合、Linux は `/proc/meminfo` の `MemAvailable`、Windows は `GlobalMemoryStatusEx` 等から得る利用可能量を元に OS 用余裕を差し引く。さらに CUDA/HIP/CPU では cgroup に制限がある場合、利用可能 cgroup メモリから最大 2 GiB または 1/8 の予約分を差し引いた上限で抑える。GPU にも RAM にも収まらない HIP expert は Strata 形式なら ColdStore 経由、その他の形式では読み直し・再変換経路となる（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1090-1133,1136-1170,1172-1209,1372-1392`）。
- **CPU**: 正値は cgroup 上限でさらに抑えられ、負値は初期値の上限なしで expert を読み込む。ただし cgroup の利用可能量が取れ、制限中なら同じ予約規則で抑えられる。上限未満しか preload できない場合は ColdStore を開いて SSD streaming を使う。明示的な `--ssd-experts` と `--ram-experts-gb 0` の場合は preload を 0 にする。ColdStore を開けなければ警告を出し、直接読み出しへ fallback する（`engine/src/inkling2/ink_cpu_backend.cpp:226-260,270-296`）。

配置対象の優先順は model の `vram_load_order` に従う。CUDA は GPU、RAM、SSD の順に容量内へ配置し、HIP も GPU 群の後に RAM を割り当てる（`engine/src/inkling2/cuda/ink_runner.cuh:453-468`; `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1136-1170`）。

## 適用条件と副作用

- `--ssd-experts` との相互作用は backend ごとに異なる。CUDA/HIP は同オプションがあると RAM 上限を 0 として扱う。CPU では `--ssd-experts` だけで必ず preload を 0 にするのは `--ram-experts-gb` が 0 以下の場合であり、正値なら上限分を preload し、残りを cold storage 対象にできる（`engine/src/inkling2/cuda/ink_runner.cuh:296-303,452`; `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1090-1095`; `engine/src/inkling2/ink_cpu_backend.cpp:246-259`）。
- expert データを RAM に読み込むため、実際の常駐量は指定値以下となり、個々の expert のサイズや配置順にも左右される。CUDA/HIP は計画上の expert body を読み込み、CUDA は host arena、SSD-only 時は pinned ring を確保する（`engine/src/inkling2/cuda/ink_runner.cuh:524-568,574-620`; HIP: `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1343-1372`）。
- CPU と HIP は cgroup メモリ制限を考慮する。CUDA の自動上限は `ink_ram_available_bytes()` の値に依存する。OS・backend ごとの利用可能メモリ取得の詳細は各実装で異なる。
- この option の不正値に対する専用エラーや clamp は確認できない。`NaN` や無限大を渡した場合の容量換算結果は本調査では規定せず、利用値として案内しない。

## 出力とエラー

- 値欠落時は parser が stderr にエラーを出して終了コード 2（上記「値と既定値」参照）。未知の option も stderr に `unknown option`、終了コード 2 となるが、この option の値検証エラーはない（`engine/src/inkling2/ink_main.cpp:845-849,910-911,985-987`）。
- CPU ColdStore の初期化失敗時は stderr に `cold store open failed` を出し、直接読み出しを続ける（`engine/src/inkling2/ink_cpu_backend.cpp:270-284`）。
- GPU backend のモデルロード・メモリ確保・expert 読み出しが失敗すると backend の `init` が失敗し、通常起動では `init: <理由>` を stderr に出して終了コード 1 となる（`engine/src/inkling2/ink_main.cpp:1086-1090`; CUDA の確保失敗例: `engine/src/inkling2/cuda/ink_runner.cuh:524-530,558-560`）。具体的な失敗条件は GPU driver、空きメモリ、モデル、ColdStore 初期化結果に依存する。

## 根拠

- `engine/src/inkling2/ink_main.cpp:845-849,910-911` — 引数取得、欠落値処理、`atof` による parser 代入。
- `engine/src/inkling2/ink_backend.h:30-32` — 既定値と `--ssd-experts` の設定。
- `engine/src/inkling2/cuda/ink_runner.cuh:296-303,448-468,534-568` — CUDA の RAM 上限、配置、SSD-only ring。
- `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1090-1133,1136-1170,1372-1392` — HIP の上限計算、配置、常駐数と streaming。
- `engine/src/inkling2/ink_cpu_backend.cpp:226-260,270-296` — CPU の cgroup-aware 上限、preload、ColdStore と fallback。
- `engine/src/inkling2/ink_cuda_backend.cu:227-232` — CUDA runner への option 転送。
- `engine/src/inkling2/ink_main.cpp:1086-1090` — backend 初期化失敗の出力と終了。

調査範囲: 現行 checkout の Strata ソースを確認し、GPU 実行や build は行っていない。Linux/Windows の各メモリ取得 API が実行環境で返す値、実機での実メモリ消費量、性能差は未測定。
