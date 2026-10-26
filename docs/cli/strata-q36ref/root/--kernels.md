# `--kernels`

調査対象: Strata commit `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-q36ref` |
| コマンド | `strata-q36ref`（Qwen3.6 reference CLI） |
| オプション | `--kernels` |
| 別名 | なし |
| 値 | `strata` または `plain` |

## 役割

Qwen3.6 reference CLI の一部演算で使う kernel 経路を選びます。`strata` は既定値で、対象となる量子化行列積に Strata の native MMVQ、条件を満たす GDN 層に Strata の fused kernel、対応する router に Strata の native top-k を使います。`plain` はこのソース内の参照 kernel 経路を選びます（`src/qwen35/q36ref.cu:390-394,399-417,623-639,657-680`）。この executable は CMake の GPU backend build で定義される照合用 CLI です（`CMakeLists.txt:771-775`）。

## 使い方

```sh
strata-q36ref --model <model.gguf> --tokens <token-id,...> --kernels plain
```

値は1つ必要です。省略時は `strata` です。大文字小文字の変換や別名はありません。

## 値と既定値

- `strata`: parser の初期値です。`--kernels strata` と明示しても同じ経路です。
- `plain`: `g_strata` を false にし、後述する Strata native の分岐を選びません。

parser は `--kernels` の直後の値が `strata` または `plain` であることを検査します。不正値は `q36ref: --kernels strata or plain` を stderr に出して終了コード 2、値がない場合は `q36ref: --kernels needs a value` を stderr に出して終了コード 2 です。同じオプションを複数回指定すると、引数を順に読むため最後に指定した値が有効です（`src/qwen35/q36ref.cu:722-752`）。

## 実行時の動作

`strata` の場合、重み型が `Q8_0`、`Q4_K`、`Q5_K`、`Q6_K` の量子化 GEMV は Strata の `native_quantize_q8_1` と `native_mmvq` を通ります。他の重み型はこの native MMVQ 分岐に入りません（`src/qwen35/q36ref.cu:399-417`）。`plain` ではこの分岐を通らず、該当する量子化重みはこのファイルの GEMV kernel に渡されます（同 `src/qwen35/q36ref.cu:418-439`）。

GDN 層では、`strata` かつ state size `D == 128` かつ `ssm_d_conv == 4` のときに fused GDN kernel を使います。それ以外の条件、または `plain` ではこのファイルの convolution、GDN、gated norm kernel が使われます（`src/qwen35/q36ref.cu:623-639`）。router は `strata` かつ `native_router_topk_supported(n_expert, K)` が真の場合に native top-k を使います。条件外または `plain` では router 値を host にコピーし、CPU 側で softmax、top-k、重みの再正規化を行います（同 `src/qwen35/q36ref.cu:655-680`）。

両値とも `--act` との併用は可能です。ただし `--act` による活性値の Q8 化は `plain` の量子化重み経路でのみ作用し、`strata` では先に native Q8_1 変換へ進みます（`src/qwen35/q36ref.cu:399-427`）。

## 適用条件と副作用

このオプションは経路選択フラグです。`plain` を選んでも CUDA を使わなくなるわけではありません。state 初期化は両値で共通に実行され、activation scratch、CUDA stream、native Q8_1 buffer を確保します（`src/qwen35/q36ref.cu:558-575`）。GPU kernel 実行、モデルの GPU 常駐など、CLI 全体の実行条件も変わりません（同 `src/qwen35/q36ref.cu:1-7,775-804`）。

native 分岐の内部条件を満たさない演算は利用可能な plain/host 経路へ進みます。なお `strata` 経路で native GEMV に不連続な複数入力列が渡る場合は `q36ref: the native path wants contiguous input columns` を stderr に出して終了コード 1 となります（`src/qwen35/q36ref.cu:402-407`）。CUDA 呼び出しの失敗も共通の `CK` 処理で診断を stderr に出し終了コード 1 です（同 `src/qwen35/q36ref.cu:53-60`）。

## 出力とエラー

成功時に `--kernels` 固有の出力はありません。CLI は通常の生成 token ID を stdout に、処理時間などを stderr に出します（`src/qwen35/q36ref.cu:822-830`）。値の欠落・不正値は終了コード 2、前述の native 入力条件違反や CUDA 呼び出しエラーは終了コード 1 です。

## 根拠と調査範囲

- parser、既定値、入力検証: `src/qwen35/q36ref.cu:722-764`
- 量子化 GEMV の経路と native 入力条件: `src/qwen35/q36ref.cu:399-439`
- GDN、router の適用条件と fallback: `src/qwen35/q36ref.cu:623-680`
- 共通初期化と CUDA 資源確保: `src/qwen35/q36ref.cu:558-575`
- エラー処理、正常時出力: `src/qwen35/q36ref.cu:53-60,822-830`
- CMake target: `CMakeLists.txt:771-775`

同一 revision の既存 `strata-q36ref` バイナリは確認・実行していません。記述は checkout 内の parser、使用箇所、初期化処理、CMake 定義に基づきます。Release への同梱状況はこの調査では確認していません。
