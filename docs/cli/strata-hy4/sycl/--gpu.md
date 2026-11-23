# `--gpu`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl` |
| オプション | `--gpu` |
| 別名 | なし |
| 値 | GPU の整数インデックス。ソースでは `atoi` で変換される |

## 役割

SYCL 版 Hy4 エンジンの主 GPU を指定する。通常のモデル実行と `--serve` の両方で同じ引数処理を通り、GPU キューと serve 設定の主 GPU に反映される。対象の実行ファイルは `strata-hy4-sycl` で、CUDA/HIP 版や Metal 版とは別の parser を持つ。

## 使い方

```sh
# 通常実行で GPU インデックス 1 を主 GPU にする
strata-hy4-sycl --gpu 1 --native SQ32.strata --engram Engram-Q8.strata --tokens ids.txt

# engine line protocol の serve 実行でも主 GPU を指定する
strata-hy4-sycl --serve --gpu 1 --native SQ32.strata --engram Engram-Q8.strata
```

複数 GPU の利用対象も指定する場合は [`--gpus`](--gpus.md)（別名 `--devices`）を参照。

## 値と既定値

- 値は必須。値が省略されると `ERR --gpu needs a value` を標準出力に出して終了コード 2 で終了する（`engine/src/hy4flash/sycl/sy_main.cpp:109-115`）。
- 引数は `atoi` で整数化される。数値として解釈できない文字列は `atoi` の結果 0 になる。`--gpu` 自体に範囲検証やエラー判定はない（`engine/src/hy4flash/sycl/sy_main.cpp:133-135`）。
- 省略時の内部インデックスは 0。負数を指定した場合も `gpu_arg >= 0` の選択処理には入らず、主 GPU は 0 のままになる（`engine/src/hy4flash/sycl/sy_main.cpp:95, 199-200, 206`）。
- 指定値が見えている GPU の数を超える場合、明示的な `ONEAPI_DEVICE_SELECTOR` がある実行では `Q()` が列挙 GPU 数に収まるようインデックスを上限補正する（`engine/src/hy4flash/sycl/sy_common.h:169-174`）。selector をこのプログラムが設定する経路では指定値を `ONEAPI_DEVICE_SELECTOR` に組み立てるため、実際に有効な device ordinal の範囲と解釈は SYCL runtime 側に依存する。

## 実行時の動作

parser は `--gpu` の値を `gpu_arg` に保存し、引数解析後、GPU キューやデバイス能力情報に触れる前に主 GPU を決める（`engine/src/hy4flash/sycl/sy_main.cpp:105-115, 133-135, 199-214`）。

- `ONEAPI_DEVICE_SELECTOR` が未設定なら、`HY4S_BACKEND=opencl` のときは `opencl:gpu:<N>`、それ以外は `level_zero:gpu:<N>` をプロセス環境に設定する。内部インデックスはこの経路では 0 に設定し直す。環境変数の設定には上書き指定を使う（`engine/src/hy4flash/sycl/sy_main.cpp:86-92, 206-210`）。
- `ONEAPI_DEVICE_SELECTOR` が既に設定されていればそれを保持し、`N` を内部の主 GPU インデックスにする。キュー作成時には列挙された GPU 配列の範囲へ clamp して、その device から SYCL queue を作る（`engine/src/hy4flash/sycl/sy_main.cpp:87, 211-213`; `engine/src/hy4flash/sycl/sy_common.h:169-174`）。
- 主キューは通常実行の計算に使われる。`--serve` では同じ値を serve options に渡し、起動時の load 状態表示にも `GPU<N>` として出す（`engine/src/hy4flash/sycl/sy_main.cpp:215-248`; `engine/src/hy4flash/sycl/sy_serve.h:309-312`）。

`HY4_GPUS` が設定されていると、その値は複数 GPU 指定の初期値になる。コマンドラインの `--gpus` / `--devices` はこれを置き換える。複数 GPU 指定が空でなければ `--gpu` の非負値が既定主 GPU として渡されるものの、CSV 指定では有効な ID の先頭が主 GPU になり、数だけを指定する形式ではその主 GPU を維持する（`engine/src/hy4flash/sycl/sy_main.cpp:94-95, 133-136, 199-205`; `engine/src/hy4flash/sycl/sy_common.h:115-151`）。`--gpus` の詳細と peer device への expert 配置は [同オプションの文書](--gpus.md) を参照。

## 適用条件と副作用

- 選択対象は実行環境の SYCL GPU デバイス。列挙時は `HY4S_BACKEND` に応じて Level Zero または OpenCL を優先し、同一カードの重複表示を避ける backend filter がある。優先 backend の device がない場合は列挙先頭 device の backend に fallback する（`engine/src/hy4flash/sycl/sy_common.h:94-112`）。
- `ONEAPI_DEVICE_SELECTOR` が未設定なら、プロセス内の同環境変数を書き換える。すでに設定されている場合は書き換えず、その selector の見えるデバイス群に対してインデックスを適用する。
- `HY4S_CPU_DEVICE=1` の場合、キュー生成は CPU selector を使い、`--gpu` の主 GPU 選択は実際のキュー選択を置き換えない（`engine/src/hy4flash/sycl/sy_common.h:165-174`）。
- `--gpu` だけでは peer GPU は追加されない。peer device の指定と expert 配置は `--gpus` / `--devices` または `HY4_GPUS` を使う（`engine/src/hy4flash/sycl/sy_main.cpp:94, 199-205, 304-309`; `engine/src/hy4flash/sycl/sy_peer.h:182-194`）。

## 出力とエラー

- 値がない場合は標準出力に `ERR --gpu needs a value` を出して終了コード 2（`engine/src/hy4flash/sycl/sy_main.cpp:109-115`）。
- 不正な数値文字列は 0 として扱われ、範囲外の単一 `--gpu` 値を CLI parser が拒否する経路はない。明示 selector 下ではキュー作成時に範囲内へ clamp される（`engine/src/hy4flash/sycl/sy_main.cpp:133-135, 206-213`; `engine/src/hy4flash/sycl/sy_common.h:169-174`）。
- 有効な `--gpus` CSV の各 ID が列挙範囲外の場合は、標準エラーに `[gpu] ignoring out-of-range device index ...` を出してその ID を無視する。これは `--gpu` 単独の validation ではなく、複数 GPU 仕様の処理である（`engine/src/hy4flash/sycl/sy_common.h:123-143`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:79-95` — SYCL 実行開始時の selector と `HY4_GPUS` 初期値。
- `engine/src/hy4flash/sycl/sy_main.cpp:105-115, 129-136` — 手書き parser、値取得、`atoi` 変換。
- `engine/src/hy4flash/sycl/sy_main.cpp:199-214` — 単一 GPU / 複数 GPU の選択と selector の設定。
- `engine/src/hy4flash/sycl/sy_main.cpp:215-248, 255-259` — serve 分岐と通常実行の GPU 能力取得。
- `engine/src/hy4flash/sycl/sy_common.h:85-112, 115-175` — 主 GPU の保持、backend による GPU 列挙、複数 GPU 指定の解釈、キューの device 選択。
- `engine/src/hy4flash/sycl/sy_serve.h:309-312` — serve 起動時の主 GPU 表示。
- `engine/src/hy4flash/sycl/sy_peer.h:182-194, 231-245` — peer GPU expert 初期化の条件と device index の利用。
