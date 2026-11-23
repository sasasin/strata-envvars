# `--gpus`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP runner、トップレベル） |
| オプション | `--gpus` |
| 別名 | `--devices` |
| 値 | GPU ordinal の CSV（例: `0,1`）、または区切りなしの整数。厳密な数値検証はない |

## 役割

実行に使う GPU を指定し、複数 GPU を選んだ場合は主 GPU と peer GPU に分けます。HY4 の MoE expert を各 GPU に配置して実行する経路に渡されます。`strata-hy4` の serve と通常実行の両方で使われます。

## 使い方

```sh
# GPU 0 を主 GPU、GPU 1 を peer GPU として使う
strata-hy4 --model model.strata --gpus 0,1 --tokens prompt.txt

# 見えている GPU のうち先頭 2 台を選ぶ（カンマなしの 2 は台数として解釈）
strata-hy4 --model model.strata --gpus 2 --tokens prompt.txt

# serve に同じ GPU 選択を渡す
strata-hy4 --serve --model model.strata --gpus 0,1
```

## 値と既定値

- 起動時の初期値は環境変数 `HY4_GPUS` の値です。コマンドラインで `--gpus` または `--devices` を指定すると、その値で置き換わります。同じオプションを複数回指定した場合も最後の値が残ります（`engine/src/hy4flash/run/hy4_main.hip.cpp:361,375-384,404`）。
- `--gpus 0,1` のようにカンマを含む値は、各部分を `atoi` で整数化した GPU ordinal のリストです。最初の ordinal が主 GPU、残りが peer GPU になります。同じ peer ordinal は重複除去され、主 GPU と同じ ordinal は peer から除かれます（`engine/src/hy4flash/run/hy4_main.hip.cpp:516-541`）。
- カンマを含まない値は `atoi` で整数化されます。値が 2 以上で、HIP のデバイス数取得が成功し 2 台以上見えていれば、ordinal `0` から `min(値, 見えている台数)-1` までを選びます。それ以外は値そのものを単一 GPU の ordinal として扱います。したがって `--gpus 1` は「1 台」ではなく ordinal 1 の指定です（同 `:518-526`）。
- 数値形式・範囲の事前 validation はありません。`atoi` が数値として読めない部分を `0` にするため、誤記が GPU 0 に解釈される場合があります。無指定または空文字列なら `--gpu` の値（既定 `-1`）があればそれを主 GPU にし、なければ GPU 0 が主 GPU です（同 `:360-361,514-516`）。
- 値を省略すると parser の `nxt()` が stdout に `ERR --gpus needs a value`（指定した表記に応じた option 名）を出し、終了コード 2 で終了します（同 `:377-383,404`）。
- 空の CSV 要素、負数、存在しない ordinal も独自のエラーにはなりません。選ばれた主・peer ordinal が無効なら後続の HIP API 呼び出しが失敗し、`HCK` は stderr に HIP error を出して終了コード 3 で終了します（同 `:543`; `engine/src/hy4flash/run/hy4_gpu_model.hip.h:27-34,886-890`）。

## 実行時の動作

1. parser が `--gpus` / `--devices` の値を保持し、GPU ordinal リストを構成します。主 ordinal は `--gpu` の値より `--gpus` の非空値が優先します。その後 `hipSetDevice` で主 GPU を選択します（`engine/src/hy4flash/run/hy4_main.hip.cpp:403-405,514-543`）。
2. 通常実行では選択 GPU の情報を取得し、peer GPU のメモリ情報も読み取ってメモリ計画に使います。モデル読み込みに主 GPU と peer ordinal を渡します（同 `:617-621,640-659`）。serve 実行でも `ServeOpts` に同じ主・peer GPU を渡します（同 `:555-577`）。
3. 複数 GPU の場合、expert residency 処理が各 GPU の空き VRAMから予約量を差し引き、expert を主 GPU と peer GPU の VRAM に配分します。ログには各 GPU の配置量が出ます（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:798-803,886-895,1145-1155,1256-1262`）。推論時には peer 側で expert を実行し、その部分結果を主 GPU に集約します（`engine/src/hy4flash/run/hy4_graph.hip.h:1503-1548`; 同 `:1118-1155`）。
4. 主 GPU と peer GPU の peer access が使えない場合、または P2P probe に失敗した場合は pinned host memory を介する転送経路に fallback します。P2P 転送が使える場合は peer copy を使います（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:896-934`; `engine/src/hy4flash/run/hy4_graph.hip.h:1131-1153`）。

## 適用条件と副作用

- この parser は CUDA/HIP 共通の `engine/src/hy4flash/run/hy4_main.hip.cpp` にあります。複数 GPU の peer expert 経路は CUDA または `HY4_HIP_PEERS` 有効時にコンパイルされます。HIP 側では `HY4_HIP_PEERS` の既定値が `1` です（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:676,877`; `engine/src/hy4flash/run/hy4_gpu.h:324-330`）。
- GPU の選択により GPU コンテキスト、VRAM、peer transfer 用の device buffer / stream が使われます。P2P 不可時は pinned host bounce buffer も確保されます（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1145-1155`; `engine/src/hy4flash/run/hy4_graph.hip.h:1514-1542`）。
- `--mpi-experts` を含む distributed build では `--serve` 以外、`--gpus` / `HY4_GPUS` が非空、または `--gpu` が 0 より大きい場合に併用条件エラーとなります（`engine/src/hy4flash/run/hy4_main.hip.cpp:508-512`）。

## 出力とエラー

- GPU 名・空き/総 VRAM は stderr に表示されます（`engine/src/hy4flash/run/hy4_main.hip.cpp:617-621`）。peer GPU の予約不足、P2P fallback、expert 配置量、multi-GPU 実行開始も stderr にログされます（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:892-895,1256-1262`; `engine/src/hy4flash/run/hy4_graph.hip.h:1545-1548`）。
- 値の形式そのものを拒否する validation 経路は確認できませんでした。無効 ordinal など HIP API の失敗は `HCK` 経由で stderr に HIP error を出し、終了コード 3 になります（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:27-34`）。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:361,401-405` — `HY4_GPUS` 初期値、`--gpus` と `--devices` の parser 定義。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:514-543` — scalar / CSV の解釈、重複除去、`--gpu` との優先順位、主 GPU の選択。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:555-577,617-659` — serve への引き渡しと通常実行のモデル読み込み経路。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:798-803,876-935,1145-1155,1256-1264` — peer GPU の VRAM 予算、P2P 検出、GPU への配置、ログ。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1118-1155,1503-1548` — peer 実行・部分結果転送と pinned host fallback。
- `engine/src/hy4flash/run/hy4_gpu.h:324-330` — HIP peer 経路の既定 compile flag。

調査制約: この文書は `strata-hy4` CUDA/HIP parser の実装に基づきます。実機 GPU や各 backend のビルド構成は実行確認していません。索引記載の parser パスは現行 checkout に存在せず、実際には `engine/src/hy4flash/run/hy4_main.hip.cpp` を確認しました。
