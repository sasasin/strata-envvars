# `--split-device`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（engine の root option。層分割を使う場合は `--serve` と `--layer-split` を併用） |
| オプション | `--split-device` |
| 別名 | なし |
| 値 | 後段ステージごとの可視 GPU デバイス番号をカンマ区切りで指定。例: `1,2` |

## 役割

`--layer-split` で分けたモデルの後段ステージを、どの可視 GPU で実行するか指定します。値の順序は後段ステージの順序に対応し、先頭 GPU（device 0）が最初の区間を実行します。省略時は次に列挙される可視デバイスが順に選ばれます。`--layer-split` が空なら、この値はステージ構成に使われません。

## 使い方

```sh
# serve モードで層境界 24 の後段を可視 GPU 1 に割り当てる
strata --serve --layer-split 24 --split-device 1

# 後段の2ステージを可視 GPU 1、2 に割り当てる
strata --serve --layer-split 24,36 --split-device 1,2

# 境界を自動決定し、後段ステージを可視 GPU 2、1 の順に割り当てる
strata --serve --layer-split auto --split-device 2,1
```

GPU 番号は Strata が見る可視デバイスの番号です。CUDA/HIP では通常 0 が先頭デバイスです。SYCL では後段に使えるのは device 0 と同じ backend の GPU です。

## 値と既定値

- 値は空でない10進整数のカンマ区切りです。空要素、負数、符号付き数値、非数字は受理されません。値の個数は、明示的な `--layer-split K[,K2..]` の K の個数と一致する必要があります。`--layer-split auto` ではこの個数照合は行われません（`engine/src/program/generate.cpp:4790-4801, 4840-4845`、SYCL: `engine/sycl/src/program/generate.cpp:2274-2285, 2317-2323`）。
- `--split-device` 自体の parser は次の argv 要素を文字列として受け取り、独自の数値変換や範囲検証をしません。値を省略すると `--split-device needs a value` を stderr に出して終了コード 2 です（CUDA/HIP: `engine/src/program/generate.cpp:3842-3847, 4065-4067`、SYCL: `engine/sycl/src/program/generate.cpp:1882-1887, 2058-2060`）。
- `--layer-split` 使用時にこの指定を省略すると、CUDA/HIP は device 1 から順に、SYCL は device 1 以降のうち device 0 と同じ backend の GPU を順に選びます。`--split-device` を複数回指定した場合は parser の後の値で前の値が置き換わります（CUDA/HIP: `engine/src/program/generate.cpp:4065-4067, 4803-4809`、SYCL: `engine/sycl/src/program/generate.cpp:2058-2060, 2287-2307`）。
- 1つの K に対する `--split-device 0` は、両ステージを同じ GPU に置く特別な指定です。device 0 は複数 K の後段デバイスとしては使えません（`engine/src/program/generate.cpp:4808-4809, 4843-4845`、SYCL: `engine/sycl/src/program/generate.cpp:2306-2307, 2320-2323`）。

## 実行時の動作

option は `Options::split_device` に文字列として保存されます。実行時に `--layer-split` が指定されている場合だけ CSV を整数列に解析し、その順に `split_devs` を構成します。後段 GPU ごとに `GpuStage` を作り、該当デバイスに切り替えて重みなどの stage resource を用意し、層の分割実行に使います（`engine/src/program/generate.cpp:4065-4067, 4783-4809, 4856, 13248-13267`、stage 作成: `engine/src/program/generate.cpp:3693-3708`）。

## 適用条件と副作用

- `--layer-split` は `--serve` が必要です。`--split-device` だけを指定しても、層分割の選択には使われません（`engine/src/program/generate.cpp:4786, 4803-4805`、SYCL: `engine/sycl/src/program/generate.cpp:2266, 2287-2288`）。
- 通常の複数 GPU 指定では device 番号は 1 以上、可視デバイス数未満で、重複できません。CUDA/HIP の検証はデバイス番号範囲と一意性を確認します。SYCL は加えて、指定先が GPU であり device 0 と同じ backend であることを確認します（`engine/src/program/generate.cpp:4840-4845`、`engine/sycl/src/program/generate.cpp:2317-2323`）。
- 明示的な `--layer-split K[,K2..]` では境界 K が 2 以上で昇順である必要があります。device リストとの個数不一致も不正です。いずれも layer split の診断を stderr に出し、終了コード 2 で失敗します（`engine/src/program/generate.cpp:4840-4853`、SYCL: `engine/sycl/src/program/generate.cpp:2317-2330`）。
- `STRATA_PRIMARY_DEVICE` が 0 以外の場合、CUDA/HIP の layer split は未対応として stderr に理由を出し終了コード 2 になります（`engine/src/program/generate.cpp:4768-4773, 4857-4863`）。SYCL 側の同環境変数との相互作用は、この調査では確認できませんでした。
- 1つの K と `--split-device 0` の同一 GPU 分割は、conversation parking が有効（cache MiB、slots、prompt cache がいずれも正数）の場合に拒否され、終了コード 2 になります（`engine/src/program/generate.cpp:4808-4813`、SYCL: `engine/sycl/src/program/generate.cpp:2306-2311`）。
- server の `split_serve` 構成で prefill/decode を別々の GPU に置く機能とは別です。その機能に渡す engine 引数では `--split-device` は禁止されています（`terminal/serve/split.py:37-45`）。

## 出力とエラー

- 値が欠けている場合は parser が stderr に不足を表示して終了コード 2 で終了します（`engine/src/program/generate.cpp:3844-3846`）。
- 値の書式、個数、デバイス範囲、重複などが layer split の条件を満たさない場合は、`--layer-split ... needs --serve ...` の診断が stderr に出て終了コード 2 になります（`engine/src/program/generate.cpp:4848-4853`、SYCL: `engine/sycl/src/program/generate.cpp:2325-2330`）。
- `--split-device` 自体には既定値を表示する専用出力や警告はありません。自動割当の実際の選択は `--layer-split` の処理に依存します。

## 根拠

- parser と値取得: `engine/src/program/generate.cpp:3842-3847, 4065-4067`、SYCL: `engine/sycl/src/program/generate.cpp:1882-1887, 2058-2060`。
- CSV 解析、既定割当、特別な device 0、範囲・重複・個数の検証と失敗: `engine/src/program/generate.cpp:4783-4856`、SYCL: `engine/sycl/src/program/generate.cpp:2263-2334`。
- 後段 GPU stage の生成と split 実行計画: `engine/src/program/generate.cpp:3693-3708, 13248-13267`。
- split-serve 側での併用禁止: `terminal/serve/split.py:37-45`。
- 利用者向け説明（補助資料）: `docs/MULTI_GPU.md:156`。
