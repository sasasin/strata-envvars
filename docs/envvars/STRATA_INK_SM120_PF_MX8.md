# `STRATA_INK_SM120_PF_MX8`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

CUDA の Ink MoE で、Blackwell SM120 系の MX8 gate/up 重みを読む際に、重みデータの L2 prefetch 命令へ渡す窓幅（bytes）を指定する。値 `1` は `128` bytes として扱われ、未設定時は `0`、つまりこのカーネルからの prefetch は無効。設定は出力値やルーティングを直接選択せず、重みデータへの prefetch 要求を変える。読み取りと値の正規化は `mx8_pf_env()`、要求の発行は `k_moe_mx8_tc` が行う（`engine/src/inkling2/cuda/ink_moe_fp4_sm120.cu:980-988, 595-608`）。

## 値と判定

`mx8_pf_env()` の初回呼び出しで `std::getenv` から文字列を取得し、設定されていれば `std::atoi` で先頭の整数を変換する。文字列全体の妥当性検査はないため、数値の後ろの文字は無視される。未設定なら `0`。変換結果 `x` は `x == 1` なら `128`、`x >= 32` なら `32` の倍数へ切り下げ、その他なら `0` になる（`engine/src/inkling2/cuda/ink_moe_fp4_sm120.cu:982-988`）。

| `atoi` の結果 | カーネルへ渡す値 | 例 |
|---|---:|---|
| 未設定 | 0 | unset |
| 1 | 128 | `1`, `1anything` |
| 32 以上 | 32 の倍数へ切り下げ | `32` → 32、`63` → 32、`128` → 128 |
| それ以外 | 0 | 空文字、`0`、`0anything`、`2`〜`31`、負数、先頭が数値でない文字列 |

`atoi` のため先頭空白や符号は整数変換の規則に従い、大文字小文字の比較はありません。範囲外の数値文字列に対する独自の検査やエラー処理もありません。空文字は「設定あり」ですが `atoi` の結果が 0 なので無効です。数値の後ろを検査しない例として `128junk` は 128、`1junk` は特例により 128 になります（同 `:984-986`）。

## 有効になる条件

- CUDA Ink の MoE dispatch が実行され、`force_exact_dec` が false、トークン数 `M >= 24`、かつ `sm120::available()` が true であること。dispatch はこの条件で SM120 Tensor Core 経路を選ぶ（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:3678-3680`）。
- SM120 カーネルが利用可能であること。`available()` は CUDA Runtime 12.8 未満または `CUDART_VERSION` 未定義なら false を返し、それ以外でも選択中の device の capability が `ink_cap_sm120` を満たし、該当カーネルの binary version が 120 以上であることを確認する（`engine/src/inkling2/cuda/ink_moe_fp4_sm120.cu:942-956`）。この translation unit は別ターゲットとしてビルドされ、CUDA architecture リストから 120/121 を `120a`/`121a` に変換する（`engine/src/inkling2/cuda/CMakeLists.txt:40-49`; `engine/src/inkling2/cuda/ink_sm120a.cmake:1-19`）。
- device kernel の実装本体は `__CUDA_ARCH__` が 1200 以上 1300 未満の場合に定義される `INK_SM120_DEV` で guard される（`engine/src/inkling2/cuda/ink_moe_fp4_sm120.cu:46-50, 502-503`）。
- dispatch 対象に MX8 expert があること（`info.has_mx8`）。該当時に MX8 活性値を量子化し、gate/up と down のカーネルを呼ぶ（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:3724-3738`）。各 MX8 kernel は処理する expert の該当コードが `FMT_MX8` でなければその work item を飛ばす（`engine/src/inkling2/cuda/ink_moe_fp4_sm120.cu:540-548`）。
- 値が正規化後に 32 bytes 以上であること。0 の場合は `if (pf ...)` が成立せず prefetch を発行しない（`engine/src/inkling2/cuda/ink_moe_fp4_sm120.cu:595-608`）。
- この変数が有効にするのは gate/up のみ。down カーネルの起動引数には値ではなく `0` が渡されるため、この変数では down の prefetch は有効にならない（同 `:1018-1024`）。
- SM120 経路を選ばない場合（たとえば `M < 24`、`force_exact_dec` が true、または device/build 条件不成立）はこの環境変数の値はカーネルへ渡らず、別の MoE 経路が選ばれる（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:3678-3680, 3724-3740`）。

## 実行時の詳細

値は `mx8_pf_env()` の関数内 `static const int` に保存される。環境変数はそのプロセスでこの関数が最初に呼ばれたとき一度だけ読み取られ、以後の変更は反映されない（`engine/src/inkling2/cuda/ink_moe_fp4_sm120.cu:982-988`）。CLI 引数や別の環境変数との優先順位・上書きはこの設定処理にはない。

正規化後の値は MX8 gate/up kernel の引数 `pf` になる。各 work item で MX8 expert と有効な行数を確認した後、各 weight row について `uj == 0` のスレッドが `wrow_p`（MX8 重み本体）から `min(pf, ROWS_K)` bytes の L2 prefetch を要求し、処理ループ中も `pf / 32` ステップごとに次の窓を要求する。窓の末尾は `ROWS_K` を超えない。gate/up の `ROWS_K` は `kInkHidden`、down は `kInkInter` だが、down には `pf=0` が渡るため本変数による要求はない。スケール配列 `wrow_s` への prefetch 要求もこの MX8 kernel にはない（`engine/src/inkling2/cuda/ink_moe_fp4_sm120.cu:503-505, 554-557, 595-608, 1018-1024`）。

## ログと測定値

この環境変数の値、無効値、prefetch の有効化を報告する Strata 側のログやエラー処理は見当たらない。値は上記の変換後そのままカーネル引数に使われる。対象環境変数に結び付いた測定値は、参照した Strata の資料・実装箇所では確認できなかった。

## 根拠

- `engine/src/inkling2/cuda/ink_moe_fp4_sm120.cu:982-988` — 環境変数の唯一の読み取り箇所、変換、static cache。
- `engine/src/inkling2/cuda/ink_moe_fp4_sm120.cu:595-608, 1009-1024` — MX8 kernel 内の prefetch と gate/up のみへの引き渡し。
- `engine/src/inkling2/cuda/ink_moe_fp4_sm120.cu:942-956` — CUDA Runtime、device capability、binary version による利用可否。
- `engine/src/inkling2/cuda/ink_moe_cuda.cuh:3678-3680, 3724-3738` — MoE dispatch 条件と MX8 経路。
- `engine/src/inkling2/cuda/CMakeLists.txt:40-49`; `engine/src/inkling2/cuda/ink_sm120a.cmake:1-19` — SM120 専用 translation unit と architecture 対応。
