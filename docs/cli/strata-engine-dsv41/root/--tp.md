# `--tp`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `maya-ds4`（DSv4.1 エンジン） |
| オプション | `--tp` |
| 別名 | なし |
| 値 | 整数 `N`。同時に各層を処理する GPU グループの幅として扱う |

## 役割

テンソル並列で各層の attention head、出力 projection、expert FFN を複数 GPU に分割する幅を指定します。`N > 1` ではグループ内 GPU が層の状態を共有し、分担した計算結果を合わせます。`--tp 1` はテンソル並列を使わず、層を GPU 間に配置する動作です（`src/dsv41/ds4_model.hpp:49-53`、`src/dsv41/ds4_model.cu:2170-2205`）。

## 使い方

```sh
maya-ds4 --pack /path/to/model/maya-ds4 --gpus 0,1,2,3 --ids 1,2,3 --tp 2
```

この例では選択 GPU を幅 2 のグループに分け、各層の行列計算をグループ内で分担するよう要求します。CLI の通常実行では `--pack` と `--ids` などの実行引数も必要です（`src/dsv41/ds4_main.cpp:87-93`、`src/dsv41/ds4_main.cpp:1282-1296`）。

## 値と既定値

- `N` の省略時は parser が `--tp needs a value` を stderr に出し、終了コード 2 で終了します（`src/dsv41/ds4_main.cpp:1202-1207`）。
- parser は `atoi` で整数変換し、`max(1, 値)` を保存します。0、負数、整数として読めない文字列は 1 になります。数値の後ろに文字がある場合は `atoi` が読めた整数部分を使います。独立した上限検証はありません。同じオプションを複数回指定すると、後の値が残ります（`src/dsv41/ds4_main.cpp:1200-1207`、`src/dsv41/ds4_main.cpp:1231`）。
- 省略時の初期値は 2 です（`src/dsv41/ds4_model.hpp:49-53`）。ただし最終的なグループ幅はモデル形式・幾何条件・選択 GPU により、要求した値より小さくなる場合があります。

## 実行時の動作

モデル読み込みで `--tp` を GPU グループの最大幅として使います。隣り合う選択 GPU は通常、総 VRAM 容量が同じもの同士でグループ化されます。要求幅が選択 GPU 全体と等しい場合は容量の異なる GPU も一つのグループに含め、その場合は最も容量の小さいメンバーが expert の配置可能量を制約します。末尾に幅未満のグループができると、そのメンバーは個別 GPU のグループになります（`src/dsv41/ds4_model.cu:1912-1916`、`src/dsv41/ds4_model.cu:1925-1944`）。したがって、指定値が GPU 数を超える場合も指定幅の並列実行が保証されるわけではありません。

GGUF pack で `N > 1` の場合、expert FFN 幅、quant block 幅、`DS4_TP_ALIGN`（未設定時 128）、head 数、output group 数で分割できるかを検査します。条件を満たさない間は幅を 1 ずつ下げ、要求値と異なる結果になれば `tensor parallel N -> 実効値` を stderr に出します（`src/dsv41/ds4_model.cu:1892-1910`）。この縮小処理の後、層の head・output group・FFN の分割条件を満たさない場合はモデル読み込みに失敗します（`src/dsv41/ds4_model.cu:2170-2181`、`src/dsv41/ds4_model.cu:2190-2216`）。

有効なテンソル並列幅が 1 より大きい場合、または `--threads` が `off` 以外の場合、モデルは parallel 経路を設定します。これは decode の GPU ごとの host thread と prompt の chunk 経路に関係します。なお、GGUF の適合処理後に実効幅が 1 になっても、prompt 判定には parser が保持する元の `--tp` 値が使われる分岐があります（`src/dsv41/ds4_model.cu:1917-1924`）。chunk の値と追加条件については [`--prefill-chunk`](--prefill-chunk.md) を参照してください。

## 適用条件と副作用

- モデル読み込み時に GPU 群と各層の分割を決める起動時オプションです。指定幅 1 より大きい場合は GPU 間で head、output projection、FFN の計算・データを分担し、モデル用の GPU 状態と通信処理を使います（`src/dsv41/ds4_model.cu:2163-2205`）。
- 実際に使える GPU は `--gpus` で指定した ID 群で、未指定なら検出された全 CUDA GPU です（`src/dsv41/ds4_model.cu:1870-1879`）。GPU がない場合 `Model::load()` は失敗します（同:1870-1874）。
- `DS4_TP_ALIGN` は GGUF の幅縮小条件に使われる環境変数です。また `DS4_WINDOWS` は `--tp` を含む prompt 並列経路の判定に関係します。本書では環境変数自体の仕様は扱いません（`src/dsv41/ds4_model.cu:1905-1907`、`src/dsv41/ds4_model.cu:1917-1924`）。
- 性能や必要 VRAM が指定値に比例する保証は、ソースからは確認できません。実機・モデルごとの性能は調査していません。

## 出力とエラー

- GGUF の分割幅が要求値から縮小された場合、その変更を stderr に表示します（`src/dsv41/ds4_model.cu:1908-1910`）。デバイスごとの説明出力には、グループ幅が 2 以上の場合 `tensor parallel <幅>, part <番号>` が含まれます（`src/dsv41/ds4_model.cu:4408-4432`）。
- 分割不能や CUDA 初期化などで `Model::load()` が失敗すると、CLI は `maya-ds4: <理由>` を stderr に出して終了コード 1 を返します（`src/dsv41/ds4_main.cpp:1289-1294`）。オプション値の不足は終了コード 2 です。未知のオプションも usage を表示して終了コード 2 になります（`src/dsv41/ds4_main.cpp:1266-1272`）。

## 根拠

- CLI usage と parser: `src/dsv41/ds4_main.cpp:85-94`、`src/dsv41/ds4_main.cpp:1200-1207`、`src/dsv41/ds4_main.cpp:1231`。
- 値の初期値とテンソル並列の説明: `src/dsv41/ds4_model.hpp:49-53`。
- GPU 選択、GGUF の幅調整、グループ構築、prompt/decode 経路: `src/dsv41/ds4_model.cu:1870-1879`、`src/dsv41/ds4_model.cu:1892-1944`、`src/dsv41/ds4_model.cu:2163-2216`。
- 結果表示と CLI のロード失敗処理: `src/dsv41/ds4_model.cu:4408-4432`、`src/dsv41/ds4_main.cpp:1289-1296`。
- 索引は `strata-engine-dsv41` の root option として掲載しています: [`docs/cli/README.md`](../../README.md)。

調査範囲: 指定 revision の parser と DSV41 モデル実装を確認しました。CLI の `--help` は実行していません。別 platform/build variant、Release 配布物、実機の GPU 挙動は確認していません。
