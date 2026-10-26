# `--act`

調査対象: Strata commit `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-q36ref` |
| コマンド | `strata-q36ref`（Qwen3.6 reference CLI） |
| オプション | `--act` |
| 別名 | なし |
| 値 | `q8` または `f32` |

## 役割

`--kernels plain` で量子化重みの行列ベクトル積を行うとき、入力活性値を 32 要素ごとの Q8 相当値に丸めるか、元の FP32 値のまま使うかを選びます。既定値 `q8` は llama.cpp の量子化行列積で使われる activation rounding に合わせる目的です。`strata-q36ref` は CMake の GPU backend build で作られる照合用 executable です（`CMakeLists.txt:771-775`）。

## 使い方

```sh
strata-q36ref --model <model.gguf> --tokens <token-id,...> --kernels plain --act f32
```

`--act` は値を1つ取ります。`--kernels plain` を指定しない場合、既定の `strata` kernel 経路が選ばれ、このオプションは受理されますが、活性値の Q8 化設定には使われません。

## 値と既定値

- `q8`: 既定値です。32 要素ごとに絶対値最大値 `amax` を求め、`d = amax / 127`、`q = roundf(x / d)` として `q * d` を後段へ渡します。`amax == 0` のグループは `q = 0` とします（`src/qwen35/q36ref.cu:367-384`）。
- `f32`: `--kernels plain` の量子化重み経路で活性値の変換を行わず、入力 FP32 値をそのまま使います（`src/qwen35/q36ref.cu:418-426`）。

値の大文字小文字変換や別名はありません。値が欠落すると `q36ref: --act needs a value` を stderr に出して終了コード 2、`q8` / `f32` 以外の値では `q36ref: --act q8 or f32` を stderr に出して終了コード 2 です（`src/qwen35/q36ref.cu:727-732,754-758`）。同じオプションを複数回指定した場合は、引数を順に読むため最後の値が残ります（同 `src/qwen35/q36ref.cu:725-758`）。

## 実行時の動作

parser の初期値は `g_act_q8 = true` で、指定値に応じてこのフラグを設定します（`src/qwen35/q36ref.cu:386-388,754-758`）。処理への適用は、重み型が `Q8_0`、`Q4_K`、`Q5_K`、`Q6_K` のいずれかで、かつ `--kernels plain` が選択されている場合に限られます。該当時に `q8` なら活性値を変換してから自前 GEMV kernel に渡し、`f32` なら変換を飛ばします（`src/qwen35/q36ref.cu:399-427`）。F32、F16、BF16 の重みではこの変換分岐に入りません（同 `src/qwen35/q36ref.cu:401-402,428-435`）。

既定の `--kernels strata` では、量子化重みの経路が `--act` の分岐より先に Strata の `native_quantize_q8_1` と `native_mmvq` を実行して戻ります。そのため `--act f32` を指定しても、この経路の活性値はネイティブ処理側で Q8_1 化されます。従って `--act` でこの変換を切り替えられるのは `--kernels plain` の経路です（`src/qwen35/q36ref.cu:390-417`）。

## 適用条件と副作用

Q8 変換は実行時に GPU kernel `k_act_q8` で行われ、初期化時に用意された 65,536 個の `float` の scratch buffer を使います（`src/qwen35/q36ref.cu:371-388,571-574`）。plain 経路で変換対象となる入力要素数（複数選択時は `n * sel`）が 65,536 を超えると、`q36ref: activation scratch too small` を stderr に出して終了コード 1 で終了します（`src/qwen35/q36ref.cu:418-423`）。この上限検査は `q8` の変換分岐内でのみ実行され、`f32` では行われません。

## 出力とエラー

このオプション自体は成功時にメッセージを出しません。値の欠落・不正値は上記の通り終了コード 2 です。scratch buffer 超過時は plain 経路で終了コード 1 です。GPU kernel 起動エラーなどは共通の `CK` 経路から stderr にエラーを出し、終了コード 1 になります（`src/qwen35/q36ref.cu:53-60,428-440`）。

## 根拠と調査範囲

- parser、既定値、値チェック: `src/qwen35/q36ref.cu:386-388,722-764`
- Q8 rounding と plain / native の経路分岐: `src/qwen35/q36ref.cu:367-427`
- scratch buffer の確保と上限エラー: `src/qwen35/q36ref.cu:418-423,571-574`
- CMake executable 定義: `CMakeLists.txt:771-775`

同一 revision の既存 `strata-q36ref` バイナリは確認・実行していません。記述は checkout 内の parser、使用箇所、CMake 定義に基づきます。Release への同梱状況はこの調査では確認していません。
