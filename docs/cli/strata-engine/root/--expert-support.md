# `strata --expert-support`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン root。`generate` の後にも指定可能） |
| オプション | `--expert-support` |
| 別名 | なし |
| 値 | `GU,D,N_EMBD,N_FF`。2 個の ggml type ID と 2 個の正のサイズをカンマ区切りで指定 |

## 役割

指定した gate/up と down の ggml type ID、および expert の埋め込み幅・FFN 幅の組み合わせについて、このビルドの `native_expert_supported` 判定を問い合わせます。モデル推論の起動前に形式・サイズの対応可否を確認するための早期終了経路です。物理 GPU の有無や実行中のデバイス能力を問い合わせるものではありません（`engine/src/program/generate.cpp:3717-3720`）。

## 使い方

```sh
# ggml type ID 2/2、幅 2560/2560 の組み合わせを照会
strata --expert-support 2,2,2560,2560

# generate を明示する起動形でも、オプションをその直後に置ける
strata generate --expert-support 2,2,2560,2560
```

成功時は標準出力に `supported`、非対応時は `unsupported` を出します。

## 値と既定値

値は必須で、並びは `GU,D,N_EMBD,N_FF` です。`parse_i64_list` はカンマまたは空白類を区切りとして整数列を読み取り、整数は `0..2147483647` の範囲に限ります（`engine/src/program/generate.cpp:1552-1579`）。CLI 側では要素数がちょうど 4 個であること、`GU` と `D` が `0..255`、`N_EMBD` と `N_FF` が `1..1048576` であることを追加検証します（`engine/src/program/generate.cpp:3721-3729`）。従って空値、整数以外、負数、要素数違い、各範囲外は不正値です。省略時の既定値はありません。

## 実行時の動作

オプションは通常の生成オプション解析より前に検出されます。root では `argv[1]`、または `generate` を先頭に置く場合の `argv[2]` を調べ、値を検証してから `strata::kernels::native_expert_supported` を呼びます。判定結果を出力してその場で終了するため、通常のモデル読込・生成処理には進みません（`engine/src/program/generate.cpp:3665-3670, 3717-3734`）。

判定条件は backend 実装に依存します。CUDA/HIP の `engine/src/kernels/cuda/iq_kernels.cu` では、両 type の row/block 情報が有効で IQ type であること、対応するブロック幅で割り切れること、`N_EMBD` が 256 の倍数であること、および `N_FF * N_EMBD` が 256 の倍数であることを確認します（同ファイル `5806-5810`）。Metal 実装は IQ または TQ type を許し、対応ブロック幅と同じ 256 境界条件を確認します（`engine/metal/src/engine/iq_host.cpp:77-80`）。これは実装内の形式・寸法判定であり、装着 GPU の検出ではありません。

通常の native pack 起動でも、読み込んだ各 layer の expert format に対して同じ関数を呼び、非対応なら layer と type ID を標準エラーに出してモデル初期化を中止します（`engine/src/program/generate.cpp:5364-5375`）。`--expert-support` はこの判定関数への問い合わせだけを切り出しており、pack 内の形式を読み取るわけではありません。

オプションの値が複数回現れる場合の仕様は parser に定義されていません。早期走査で最初に一致した位置を処理して直ちに終了するため、後続の引数は処理されません（`engine/src/program/generate.cpp:3696-3734`）。

## 適用条件と副作用

`engine/src/program/generate.cpp` の早期引数処理で実装されています（`engine/src/program/generate.cpp:3665-3670, 3717-3734`）。この経路は通常の GPU 初期化より前に判定を返します（同ファイル `3717-3720`）。ただし main の共通前処理として stdout のバッファ設定と通常の I/O 優先度への復元は判定前に行われ、Linux の HIP build では NUMA scanner の設定処理も先に実行されます（同ファイル `3667-3678`）。判定分岐自体はファイル・ネットワーク・モデル・GPU に対する操作を行いません。SYCL 側の別 parser (`engine/sycl/src/program/generate.cpp`) には `--expert-support` の分岐がなく、この文書の対象は `strata-engine` 索引に記載された `engine/src/program/generate.cpp` の root parser です。

## 出力とエラー

- 対応あり: 標準出力 `supported`、終了コード `0`。
- 非対応: 標準出力 `unsupported`、終了コード `3`。
- 値の欠落または形式・個数・範囲不正: 標準エラー `--expert-support wants GU,D,N_EMBD,N_FF: two ggml type ids (0-255) and two sizes (1-1048576)`、終了コード `2`。

これらの出力と終了コードは分岐で直接指定されています（`engine/src/program/generate.cpp:3721-3733`）。

## 根拠

- `engine/src/program/generate.cpp:3665-3670` — エンジン main の入口。
- `engine/src/program/generate.cpp:3717-3734` — オプションの早期検出、入力検証、判定呼出し、出力、終了コード。
- `engine/src/program/generate.cpp:5364-5375` — native pack 起動時の各 layer の形式検証と失敗処理。
- `engine/src/program/generate.cpp:1552-1579` — 整数列の区切り・整数範囲・空列の扱い。
- `engine/src/kernels/cuda/iq_kernels.cu:5806-5810` — CUDA/HIP 側の形式・寸法判定。
- `engine/metal/src/engine/iq_host.cpp:77-80` — Metal 側の形式・寸法判定。

調査範囲は指定 commit のソース上の引数処理と `native_expert_supported` 実装です。同一 revision の CLI help は実行していません。SYCL 実装には当該引数分岐を確認できず、SYCL の使用可否は本オプションの説明対象外です。
