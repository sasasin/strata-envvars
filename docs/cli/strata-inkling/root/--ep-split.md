# `strata-inkling --ep-split`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（トップレベル） |
| オプション | `--ep-split` |
| 別名 | なし |
| 値 | 数値として変換される値 `F`。backend 採用時の範囲は `0.1`〜`0.9` |

## 役割

2 GPU の Expert Parallelism（EP）で、GPU 1 側へ優先配置する expert の割合を指定する。たとえば `0.65` は expert を GPU 1 に優先割当てする比率を 65% とする。ただし VRAM の空き容量、backend、CUDA のマルチ GPU モード選択によって実際の配置は変わり、割合どおりになる保証はない（`engine/src/inkling2/ink_backend.h:17-25`; `engine/src/inkling2/cuda/ink_runner.cuh:1218-1251`; `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1064-1088`）。

## 使い方

```sh
strata-inkling --native model.gguf --gpus 2 --ep-split 0.65
```

2 GPU を使う指定と組み合わせる。`--ep-split` 単独では GPU 数を増やさない（`engine/src/inkling2/ink_main.cpp:443-472`; `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:602-615`）。

## 値と既定値

- 既定値は `0.5`（`engine/src/inkling2/ink_backend.h:22-25`）。
- parser は次の引数を `std::atof` で変換し、CLI 側では書式・範囲のエラーを検査しない。数値として読めない通常の文字列は `0` になり、空文字も `0` として扱われる。backend は受け取った値を `0.1`〜`0.9` に clamp するため、たとえば `0` や `2` はエラーにならず、それぞれ `0.1`、`0.9` として扱われる。NaN など非有限値を入口で拒否する処理は確認できず、その場合の配置値はここで確定できない（`engine/src/inkling2/ink_main.cpp:470-472`; `engine/src/inkling2/cuda/ink_runner.cuh:819`; `engine/src/inkling2/ep_dual_gpu.cu:732-735`; `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:578-580`）。
- 同じオプションを複数回指定すると、引数走査中に都度代入されるため最後の値が残る（`engine/src/inkling2/ink_main.cpp:379-384,470-472`）。値を省略すると `missing value after --ep-split` を stderr に出して終了コード `2` で終了する（同 `:381-383`）。
- `IK2_EP_SPLIT` が空でない有効値（`atof` の結果が厳密に `0 < v < 1`）を持つ場合、CLI 値の後で環境変数が適用され、CLI 指定を上書きする。無効値は無視され、CLI 値または既定値が残る。詳細は [`IK2_EP_SPLIT`](../../../envvars/IK2_EP_SPLIT.md) を参照（`engine/src/inkling2/ink_main.cpp:505-509`）。

## 実行時の動作

parser は値を `BackendOpts::ep_split` に保存する。通常生成、serve、selfcheck、bench、KLD 評価、参照 logits 出力では、その設定を含む `BackendOpts` で backend を初期化する（`engine/src/inkling2/ink_main.cpp:470-472,544-569`; `engine/src/inkling2/ink_backend.h:17-25,150-168`）。`--info`、tokenizer export、version、help は backend 初期化前に終了するため、このオプションの分割効果はない（`engine/src/inkling2/ink_main.cpp:385-398,488-498,544-549`）。

CUDA と HIP の EP backend は、clamp 後の比率を使い expert ごとに決定的な hash で GPU 1 への優先配置を決める。容量が足りなければ GPU 0 またはホスト RAM へ回るため、実配置数は指定比率と一致しないことがある（`engine/src/inkling2/cuda/ink_runner.cuh:1218-1251`; `engine/src/inkling2/ep_dual_gpu.cu:926-958`; `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1064-1088`）。

CUDA backend では、既定値付近（入力値と `0.5` の差が `0.001` 未満）で GPU 1 の空き VRAM が GPU 0 より 512 MiB 超多い場合、内部比率を空き容量比に基づき最大 `0.625` まで調整する（`engine/src/inkling2/cuda/ink_runner.cuh:1173-1177`）。

## 適用条件と副作用

- EP の比率として効果を持つのは、GPU backend が選択され、少なくとも 2 GPU の EP が有効な場合。`--cpu` や単一 GPU では GPU 間の分割は行われない（`engine/src/inkling2/ink_backend.h:150-168`; `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:602-615`）。
- HIP backend は `--gpus` 等で複数 GPU が要求され、2 台以上が見えると EP2 を初期化する（同 `:602-615,681-683`）。
- CUDA backend で 2 GPU 以上を使うとき、layer-split の明示指定、3 台以上、異なる GPU 世代、VRAM 容量差が 15% 超、Windows などの条件により Pipeline Layer-Split が選ばれる場合がある。EP2 ではないモードでは `--ep-split` による EP 配分をしない（`engine/src/inkling2/cuda/ink_runner.cuh:835-870`）。
- CUDA/HIP が選択されるかはビルド時の backend と `--cpu` 指定に依存する。既定 backend はビルド定義に応じて CUDA、HIP 等を選び、`--cpu` は CPU backend を選ぶ（`engine/src/inkling2/ink_backend.h:131-168`）。
- EP2 初期化では複数 GPU の device、stream や expert 用領域を使う。P2P が使えない場合に pinned-host 経由へ fallback する経路もある（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:616-682`; CUDA の選択は `engine/src/inkling2/cuda/ink_runner.cuh:854-870`）。

## 出力とエラー

値の不正を理由とした parser エラーはなく、backend 側で clamp される。backend 初期化に失敗すると通常実行では stderr に `init: <理由>` を出して終了コード `1`、serve では `ERR init: <理由>` を出して終了コード `1` となる（`engine/src/inkling2/ink_main.cpp:564-568`）。CUDA/HIP の EP 初期化が成功した場合、ロード情報に `ep_split` の採用値が表示される（`engine/src/inkling2/ep_dual_gpu.cu:1064-1068`; `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1324-1330`）。

## 根拠

- `engine/src/inkling2/ink_main.cpp:379-384,470-472`: トップレベル parser、値変換、値省略時の終了。
- `engine/src/inkling2/ink_main.cpp:505-509`: `IK2_EP_SPLIT` の後勝ち適用と有効範囲判定。
- `engine/src/inkling2/ink_backend.h:17-25,150-168`: 既定値、設定フィールド、backend 選択。
- `engine/src/inkling2/cuda/ink_runner.cuh:835-870,1173-1177,1218-1251`: CUDA のモード選択、既定値時の調整、EP 配置。
- `engine/src/inkling2/ep_dual_gpu.cu:732-735,926-958`: CUDA EP backend の clamp と GPU 優先配置。
- `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:578-580,602-615,1064-1088`: HIP の clamp、EP2 条件、expert 配置。
