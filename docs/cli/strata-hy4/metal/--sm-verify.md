# `strata-hy4-metal --sm-verify`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal） |
| オプション | `--sm-verify` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

小さい行数の線形演算で、通常の row-blocked GEMV カーネルの代わりに `simdgroup_matrix` を使う `linear_sm` カーネルを選択します。名前に「verify」とありますが、このフラグ自体は二つのカーネルの結果を比較・検証する処理を追加せず、A/B 用のカーネル選択を切り替えます。

## 使い方

```sh
# Metal runner でモデルと token 列を処理し、対象となる小 M 線形演算で linear_sm を選択する
strata-hy4-metal --model model.strata --tokens tokens.txt --sm-verify
```

## 値と既定値

- 値は不要で、指定すると内部フラグが `true` になります。省略時は `false` です。parser の初期値とフラグ登録は `engine/src/hy4flash/metal/hy4_metal_main.cpp:1490-1491,1504-1544` にあります。
- 値の範囲検証はありません。繰り返し指定しても同じ真偽値を設定するだけです。値を後置すると値を消費しないため、後置トークンは別引数として扱われます。
- `--model` がない場合は usage を stderr に出して終了コード 2 になります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1611-1614`）。

## 実行時の動作

parser が設定したフラグは `Runner::sm_verify` に渡されます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1747-1749`）。線形演算を選ぶ `Runner::lin()` は、まず MPP GEMM 条件、次に Q8ROW 専用経路を判定し、その後 `M >= mm_min` の GEMM を選びます。それらに該当しない場合に限り、`--sm-verify` が有効で `1 <= M <= 8` かつ重み形式が 4、5、6、8 のとき `linear_sm_<形式>` を dispatch します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:482-510`）。既定の `mm_min` は 16 です（同 `:326-327`）。

この条件を満たさない小 M 演算では、`lin2` が有効かつ同じ形式条件を満たせば `linear_skr_*` が選ばれ、それ以外は `linear_sk_*` になります。したがって `--mm-min` を 1〜8 以下に下げて M がその閾値以上になると GEMM 分岐が先に選ばれ、このフラグによる切替は起きません。`--no-lin2` は `linear_skr_*` の fallback を無効にしますが、対象条件での `linear_sm_*` 選択には影響しません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:501-510,1527-1544,1729-1732`）。

カーネルは `hy4_lin2.metal` で `linear_sm_4`、`linear_sm_5`、`linear_sm_6`、`linear_sm_8` として登録されています（`engine/src/hy4flash/metal/hy4_lin2.metal:56-60,125-133`）。同カーネルは小 M の行列積を `simdgroup_matrix` の積和で計算します（同 `:78-123`）。

## 適用条件と副作用

- 対象は `strata-hy4-metal` の Metal runner です。CUDA/HIP の `strata-hy4`、SYCL の `strata-hy4-sycl` には、この文書の parser・カーネル選択条件は適用しません（`docs/cli/README.md:1358-1362,1452-1455`）。
- `Runner::lin()` を通る線形演算のうち、M と重み形式の条件を満たすものが対象です。形式 4/5/6/8 以外、M が 1〜8 の外、Q8ROW、または先行する MPP/GEMM 分岐に入る演算では、このフラグは `linear_sm` を選びません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:487-509`）。
- このフラグ独自のファイル・ネットワーク操作やログ出力は parser・選択処理にありません。通常の GPU dispatch は発生します。Metal 初期化失敗時は `init: ...` を stderr に出して終了コード 1 になります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1762-1765`）。

## 出力とエラー

フラグの受理や `linear_sm` 選択を知らせる専用メッセージは確認できません。未認識引数は stdout に `ERR unknown flag ...`、stderr に `unknown arg ...` を出して終了コード 2 になります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1603-1609`）。この経路における GPU カーネル実行後の失敗表示・終了コードは、当該フラグ固有のものとしては確認できません。

## 根拠

- parser の初期値・登録: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1490-1491,1504-1544`
- `Runner` への値の受け渡し: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1747-1749`
- MPP/Q8ROW/GEMM と small-M カーネル選択の優先順: `engine/src/hy4flash/metal/hy4_metal_main.cpp:482-510`
- `linear_sm` の実装と形式別 kernel 名: `engine/src/hy4flash/metal/hy4_lin2.metal:56-60,78-123,125-133`
- 索引のツール ID・Metal scope・作成予定リンク: `docs/cli/000_cli_tools.md:11`、`docs/cli/README.md:1358-1362`

調査対象の Strata checkout は開始時に `main...origin/main` で未コミット変更がありませんでした。
