# `STRATA_INK_GGUF_MT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

CUDA の Inkling-2 MoE dispatcher が、GGUF expert の gate/up と down に使う DP4A kernel の compile-time `MAX_M` を選ぶ調整用環境変数。`MAX_M` は各 expert の active token 列を処理するループのまとまり幅で、選択肢は 1 / 2 / 4 / 8 / 16。router の top-8 選択や expert の選択条件はこの変数では変更しない。実装は `launch_ink_moe_dispatch_only` 内の `info.has_gguf` 分岐にある（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:3812-3827,3834-3859`）。

## 値と判定

`std::getenv` で取得し、未設定でなければ `std::atoi` で整数に変換する。文字列全体の妥当性検査や clamp はない。空文字・数値で始まらない文字列・変換結果 0 は 0 として扱われる。`atoi` のため、先頭空白や符号は変換規則に従い、数値の後ろに文字が続いても数値部分が使われる（例: `4tail` は 4）。`true` / `false` は整数として解釈されず 0 になる。正の値でも 1 / 2 / 4 / 8 以外は専用分岐に一致せず、最後の 16 分岐を使う。範囲外の整数文字列に対する `atoi` の結果はこのコードで検査・規定していない（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:3826-3827,3834-3843,3849-3859`）。

| 条件 | unset / 変換結果が 0 以下 | 正の設定値 |
|---|---|---|
| `M == 1` | 1 | 値にかかわらず 1（環境値より優先） |
| `M != 1` かつ `M <= 128` | 2 | 1 / 2 / 4 / 8 はその値、それ以外（例: 3）は 16 |
| `M > 128` | 16 | 1 / 2 / 4 / 8 はその値、それ以外（例: 3）は 16 |

ここでいう正の設定値は `atoi` の変換結果。したがって `-1` は既定値側、`0anything` と空文字も 0 側になる。`M` はこの呼び出しで処理する token 数。明示設定が有効でも、`M == 1` の場合は必ず 1 が選ばれる。

## 有効になる条件

- CUDA の Inkling-2 MoE 実装を通り、対象 layer の `InkLayerMoeInfo.has_gguf` が true であること。GGUF format の gate/up code を検出した layer でこのフラグが立つ（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:3588-3595,3812-3814`; `engine/src/inkling2/cuda/ink_runner.cuh:1522-1529`）。
- `launch_ink_moe_dispatch_only` が実行されること。通常の `launch_ink_moe` から呼ばれるほか、runner の peer GPU 経路や hybrid 経路からも呼ばれる（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:3864-3884`; `engine/src/inkling2/cuda/ink_runner.cuh:3460-3486`; `engine/src/inkling2/cuda/ink_hybrid.cuh:2505-2520,2720-2731`）。
- GGUF expert 分岐に入らない layer では読み取り箇所まで到達しないため、値は使われない。HIP 側の同名変数の読み取りは対象 commit の全参照検索では見つからず、設定登録 JSON の backend 表記だけから HIP での効果は断定できない。
- `STRATA_INK_Q80_TC` は別に Q8_0 expert を tensor core 経路へ振り分ける判定を行う。GGUF group 幅の分岐を上書きする CLI 引数や設定ファイル読み取りはこの実装にはない（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:3828-3859`）。

## 実行時の詳細

変数の値は関数内 `static const int gg_mt` の初期化時に一度読み取られ、そのプロセス内では再読込されない。初期化は `info.has_gguf` 分岐に初めて入ったときに行われるため、それ以降にプロセス環境を変更しても反映されない。各呼び出しでは `M == 1` を先に判定し、それ以外なら正の `gg_mt`、または `M <= 128` の 2 / `M > 128` の 16 を `gmt` に設定する。`gmt` に応じて gate/up と down の両方で `<1>`, `<2>`, `<4>`, `<8>` のいずれかを起動し、それ以外は `<16>` を起動する（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:3826-3859`）。kernel 側では `MAX_M` ごとに active token 群を進め、末尾の不足分は `min(MAX_M, cnt - k0)` で処理する（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:892-904,944-961`）。

この選択は GGUF expert の gate/up 活性と down の重み付き出力を計算する kernel specialization に適用される。ソースは、この環境変数による全モデルでの数値同一性を保証する記述をしていない。

## ログと測定値

この変数専用の値表示、無効値警告、エラー終了分岐はない。0 以下や非数値文字列は既定値選択へ進み、正の未対応値は `<16>` kernel 分岐へ進む（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:3826-3843,3849-3859`）。

ソースコメントには、UD-Q4_K_XL の Q8_0 4 layer、64 slots で、group 幅 16 の所要時間が RTX 5090 / A6000 / RTX 4090 でそれぞれ 14.1 / 30.9 / 17.9 ms、幅 2 が 8.0 / 19.9 / 12.7 ms、8 slots では同等と記録されている。これはコメントに記載された測定値であり、測定方法や試行回数は同コメントにないため、他の条件へ一般化しない（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:3823-3825`）。

## 根拠

- 読み取り、整数変換、`M` による既定値と優先順位、kernel 分岐: `engine/src/inkling2/cuda/ink_moe_cuda.cuh:3812-3859`
- GGUF format フラグの定義と設定: `engine/src/inkling2/cuda/ink_moe_cuda.cuh:3588-3595`; `engine/src/inkling2/cuda/ink_runner.cuh:1522-1529`
- group 幅が処理単位となる loop: `engine/src/inkling2/cuda/ink_moe_cuda.cuh:864-915,917-965`
- 呼び出し経路: `engine/src/inkling2/cuda/ink_moe_cuda.cuh:3864-3884`; `engine/src/inkling2/cuda/ink_runner.cuh:3460-3511`; `engine/src/inkling2/cuda/ink_hybrid.cuh:2505-2520,2720-2731`
