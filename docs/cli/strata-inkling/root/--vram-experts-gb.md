# `strata-inkling --vram-experts-gb`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（root） |
| オプション | `--vram-experts-gb` |
| 別名 | なし |
| 値 | GiB 単位の浮動小数点数。専門家重みの VRAM 予算上限としてバイト数へ換算される |

## 役割

Inkling の CUDA/HIP 実行で、モデルの専門家重みを GPU VRAM に置く予算を指定する。指定値を超える専門家は、利用可能な RAM または SSD を使うハイブリッド配置へ回る。自動予算でロードできる重み量を抑えたい場合に使う。

## 使い方

```sh
# ベンチマーク時の専門家重み用 VRAM 予算を最大 8 GiB にする
strata-inkling --bench --native MODEL.strata --vram-experts-gb 8
```

同じ root オプションは `--serve`、通常の生成、`--selfcheck`、`--kld-eval`、`--dump-ref` のようにバックエンドを初期化する経路でも共通設定に入る。`--info` と `--export-tokenizer` はバックエンド初期化より前に処理され、この値を消費しない（`engine/src/inkling2/ink_main.cpp:544-572`）。

## 値と既定値

- 値は必須で、`std::atof` で `double` に変換される。値を省略すると `missing value after --vram-experts-gb` を stderr に出して終了コード 2 で終了する（`engine/src/inkling2/ink_main.cpp:381-384,433-434`）。
- 既定値は `-1.0`。0 未満は自動予算を使う分岐に入り、0 以上は指定値を使う（`engine/src/inkling2/ink_backend.h:17-31` および以下の backend 実装）。
- parser に範囲検証はない。値を繰り返すとループ内の代入により最後の値が残る（`engine/src/inkling2/ink_main.cpp:379-384,433-434`）。不正な数値文字列について Strata 独自の拒否処理は確認できない。

## 実行時の動作

parser は値を `BackendOpts::vram_experts_gb` に格納し、CUDA/HIP backend のモデルロードへ渡す（`engine/src/inkling2/ink_main.cpp:433-434`; `engine/src/inkling2/cuda/ink_cuda_backend.cu:194-199`）。バイト換算は 1 GiB = 1,073,741,824 bytes。

- **CUDA**: 0 以上なら専門家配置の GPU 予算をこの上限で抑える。単一 GPU の通常経路では自動で見積もった空き VRAM 予算と指定上限の小さい方を使う（`engine/src/inkling2/cuda/ink_runner.cuh:385-396,429-437`）。複数 GPU の Layer Split では各 stage の予算を個別に上限値で抑え、Expert Parallel では各 GPU の予算を個別に抑えるため、複数 GPU 合計の上限ではない（同 `:1194-1201,1220-1234`）。
- **HIP**: 0 以上なら主 GPU の専門家予算を指定値に置き換える。二枚目の GPU を使う場合は、その GPU で算出した予算と指定値の小さい方を使う（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:975-988,1011-1021`）。
- 予算に収まらない専門家は CUDA の配置計画で RAM 側へ回り、`--ram-experts-gb` / `--ssd-experts` の設定に応じて SSD 経路も使う（`engine/src/inkling2/cuda/ink_runner.cuh:435-457`）。GPU 側の予算がさらに必要な staging buffer を確保できない場合、ロードは失敗し得る（同 `:461-466`）。
- `--vram-reserve-mib` は CUDA の KV・作業領域等に対する最低予約量を調整し、VRAM 専門家予算の算定にも影響する。これは専門家予算上限とは別設定（`engine/src/inkling2/cuda/ink_cuda_backend.cu:182-198`; `engine/src/inkling2/cuda/ink_runner.cuh:385-396`）。

## 適用条件と副作用

`strata-inkling` の parser は CUDA/HIP 用 root parser である。通常の backend 選択はビルドされた CUDA、EP-CUDA、HIP の順で行い、`--cpu` を指定した場合は CPU backend を選ぶため VRAM 予算は GPU 専門家配置には適用されない（`engine/src/inkling2/ink_backend.h:150-168`; `engine/src/inkling2/ink_main.cpp:476-477,564-568`）。Metal と SYCL は索引上別ツール ID・別 parser の対象であり、この文書の適用範囲外。

指定値が小さい場合、専門家の配置先が RAM/SSD に変わり、必要な GPU staging buffer を確保できずモデル初期化が失敗することがある。値は VRAM 全体の上限ではなく専門家重み用の予算で、KV cache・trunk・作業領域の予約と合わせて GPU メモリ使用量が決まる（`engine/src/inkling2/cuda/ink_runner.cuh:385-396,429-466`; `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:975-1009`）。

## 出力とエラー

CUDA のロード成功時は専門家の GPU / host 配置数を含む `[InkCUDA] Loaded ...` 行を stderr に出す（`engine/src/inkling2/cuda/ink_runner.cuh:1558-1571`）。バックエンド初期化失敗時、通常経路は `init: <理由>` を stderr に出して終了コード 1、serve 経路は `ERR init: <理由>` をプロトコル出力して終了コード 1（`engine/src/inkling2/ink_main.cpp:564-568`）。具体的な GPU allocation エラー文は失敗箇所によって異なり、上記 staging 不足では loader が理由文を設定する（`engine/src/inkling2/cuda/ink_runner.cuh:461-466`）。

## 根拠

- `engine/src/inkling2/ink_main.cpp:379-384,433-434` — root parser、値必須処理、`atof` による格納。
- `engine/src/inkling2/ink_backend.h:17-31,150-168` — `-1.0` の既定値と CUDA/HIP/CPU backend 選択。
- `engine/src/inkling2/cuda/ink_cuda_backend.cu:182-199` — CUDA での予約量算定とモデル loader への値の転送。
- `engine/src/inkling2/cuda/ink_runner.cuh:385-396,429-466,1194-1234,1558-1571` — CUDA の上限適用、複数 GPU ごとの予算、RAM/SSD 配置・失敗・出力。
- `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:975-988,1011-1021` — HIP の主 GPU・peer GPU 予算への適用。
- `engine/src/inkling2/ink_main.cpp:544-572` — backend を使わない早期モードと、モデルロード／初期化エラーの出力。
