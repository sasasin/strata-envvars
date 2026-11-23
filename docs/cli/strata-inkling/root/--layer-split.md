# `strata-inkling --layer-split`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（トップレベル） |
| オプション | `--layer-split` |
| 別名 | なし |
| 値 | 文字列。`auto` またはカンマ区切りの正の整数。CUDA 実装には `off`、`none`、`ep2` の特別値もある |

## 役割

複数 GPU で Inkling のモデル層を GPU ごとの連続した段（pipeline stage）に分ける方式を選び、必要に応じて層の分割点を指定します。分割が有効なときは各段が担当する層を保持し、通常の2 GPU expert-parallel（EP2）とは別の経路になります（`engine/src/inkling2/cuda/ink_runner.cuh:835-887`, `992-999`, `1084-1088`）。

## 使い方

```text
strata-inkling --serve --native model.strata --gpus 2 --layer-split auto
strata-inkling --bench --native model.strata --gpus 2 --layer-split 16,8
strata-inkling --serve --native model.strata --gpus 3 --layer-split 8,8,8
```

ヘルプは `--bench` と `--serve` の形式で `auto|K1,K2,...` を案内しています。オプション自体はトップレベル parser で共通に処理され、モデルをロードする各モードへ backend options として渡ります（`engine/src/inkling2/ink_main.cpp:472-473`, `488-496`, `564-572`; `engine/src/inkling2/cuda/ink_cuda_backend.cu:194-200`）。

## 値と既定値

- 値は必須です。値を省略すると parser の `next()` が `missing value after --layer-split` を stderr に出し、終了コード `2` で終了します（`engine/src/inkling2/ink_main.cpp:379-383`）。
- 省略時の backend 値は空文字列です（`engine/src/inkling2/ink_backend.h:25`）。空値は明示的な layer-split 指定として扱われません。
- `auto` は利用可能 VRAM をもとに層数を自動配分します。数値列は GPU 段数分の正の整数として読み取られた場合に手動配分として使われます（`engine/src/inkling2/cuda/ink_runner.cuh:1001-1025`）。
- parser は値の形式を検証せず、文字列をそのまま保存します（`engine/src/inkling2/ink_main.cpp:472-473`）。CUDA 実装は各カンマ区切り部分に `atoi` を適用し、正の値だけを列に加えます。正の数として読めない部分やゼロ以下の部分は捨てられます（`engine/src/inkling2/cuda/ink_runner.cuh:1002-1011`）。
- 読み取った正の数の個数が GPU 段数と一致しなければ、値が `auto` でなくても自動 VRAM 配分に進みます。一致していて合計がモデルの物理層数と異なる場合は、比率に応じて再スケールされます（`engine/src/inkling2/cuda/ink_runner.cuh:1013-1060`）。したがって、文字列が不正でも必ずエラーになるわけではありません。

## 実行時の動作

CUDA backend は受け取った値を `load_from_model_file` に渡します（`engine/src/inkling2/cuda/ink_cuda_backend.cu:194-200`）。2 GPU 以上が選ばれている場合、空でない通常値（`auto` を含む）は pipeline layer-split を明示したものとして扱われます。`auto` または手動数値列により `ls_active` になると、モデルの物理層を段に割り当て、各 GPU にその段が所有する trunk tensor を配置します（`engine/src/inkling2/cuda/ink_runner.cuh:835-887`, `992-999`, `1075-1134`）。

`auto` や手動列ではない値 `off`、`none`、`ep2` は layer-split を抑止し、2 GPU の EP2 経路を選ばせます（`engine/src/inkling2/cuda/ink_runner.cuh:838-855`, `857-870`）。これらの値はヘルプの選択肢には記載されていません。

## 適用条件と副作用

- layer-split の選択処理は CUDA のモデルローダーに実装されています。2 GPU 以上で有効になり、GPU 段は選択 GPU の順に作られます。1 GPU の場合、指定値だけで複数段にはなりません（`engine/src/inkling2/cuda/ink_runner.cuh:796-829`, `838-887`）。
- `--gpus` / `--devices` は使用 GPU 数または GPU 番号リストを設定し、layer-split の段数と順序に影響します（`engine/src/inkling2/ink_main.cpp:445-469`; `engine/src/inkling2/cuda/ink_runner.cuh:796-829`）。
- オプションが空のときも CUDA 実装は2 GPU 構成を自動判定します。3 GPU 以上、異なる compute capability、VRAM 容量差が15%超、Windows、または2 GPU 間で P2P が使えない場合に layer-split を選びます。その他の2 GPU 構成では EP2 を使います（`engine/src/inkling2/cuda/ink_runner.cuh:835-870`）。
- 自動配分は各 GPU の空き VRAM、安全余裕、層ごとの expert サイズを参照します。後段に割り当てる層はその GPU の VRAM に全て収まるよう制限され、割り当て数がゼロの後段 GPU は外されます（`engine/src/inkling2/cuda/ink_runner.cuh:1026-1075`）。
- `--cpu` を指定すると `make_default_backend` は CPU backend を選ぶため、ここで説明した CUDA 層分割処理は適用されません（`engine/src/inkling2/ink_backend.h:150-163`; `engine/src/inkling2/ink_main.cpp:564-568`）。
- GPU の能力・VRAM 情報を照会し、layer-split が有効なら GPU 間 P2P 能力を調べます。モデル trunk の tensor を各 stage GPU に転送・配置するため、VRAM 使用量と GPU 間通信に影響します（`engine/src/inkling2/cuda/ink_runner.cuh:820-829`, `872-887`, `1089-1134`）。

## 出力とエラー

- 2 GPU 構成で P2P が使えず自動的に layer-split を選ぶ場合、stderr に自動選択のメッセージを出します（`engine/src/inkling2/cuda/ink_runner.cuh:857-863`）。
- オプション値自体に対するエラー出力や終了コードは実装されていません。CUDA backend の初期化失敗は `init: <理由>` を stderr に出して終了コード `1` になります（serve モードでは `ERR init: <理由>` をプロトコル出力します）（`engine/src/inkling2/ink_main.cpp:564-568`）。

## 根拠

- parser と値の保存: `engine/src/inkling2/ink_main.cpp:379-383`, `472-473`
- 値の既定状態: `engine/src/inkling2/ink_backend.h:17-26`
- CUDA backend への引き渡し: `engine/src/inkling2/cuda/ink_cuda_backend.cu:194-200`
- GPU モード選択と自動判定: `engine/src/inkling2/cuda/ink_runner.cuh:835-887`
- 手動値の読取、自動配分、段への割当: `engine/src/inkling2/cuda/ink_runner.cuh:992-1088`
- 初期化と失敗時の出力: `engine/src/inkling2/ink_main.cpp:564-572`

## 調査範囲と制約

対象 revision は作業開始時点の `73d4f4196c25a65e02f6b9ef25d354826ce55105`、作業ツリー状態は `## main...origin/main` でした。調査対象は索引に記載された CUDA/HIP 入口 `engine/src/inkling2/ink_main.cpp` と、layer-split を使う CUDA backend / runner です。実行バイナリによる `--help` 確認、build、GPU 実行、テストは行っていません。HIP backend がこの option をどう扱うか、ここで示した CUDA loader の動作からは確認できないため、説明を CUDA 実装に限定しました。
