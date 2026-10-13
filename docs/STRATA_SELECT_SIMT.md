# `STRATA_SELECT_SIMT`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の QSA（query selective attention）prompt 経路で、indexer query と pooled block のスコアを計算するカーネルを切り替えます。compute capability 8 未満では、既定の warp scorer の代わりに共有メモリを使う FP32 タイル scorer を使います。top-k による cell 選択そのものは同じ後続処理です。

この変数は CUDA 実装の `qsa_block_scores_tc()` 内だけで直接読み取られます。HIP ビルド側は `STRATA_SELECT_WMMA` を別途判定し、SYCL 移植版にもこの変数の読み取りはありません。CUDA prompt 経路でも `STRATA_SELECT_OLD` が設定されていると `qsa_block_scores_tc()` を呼ばず、通常の warp scorer を使います。

根拠: `src/kernels/cuda/qsa_select.cu:1118-1167`、`src/prefill/prefill.cpp:2760-2775`、`sycl/src/kernels/cuda/qsa_select.dp.cpp:1646-1698`。

## 値と判定

値を数値として parse せず、`getenv()` が返す文字列の先頭文字だけを調べます。比較は文字 `'1'` との完全一致です。

| 値 | `simt` 判定 | 挙動 |
|---|---:|---|
| 未設定 | 無効 | warp scorer に fallback |
| 空文字 | 無効 | warp scorer に fallback |
| 先頭文字が `1`（例: `1`, `10`, `1abc`） | 有効 | 条件を満たせば FP32 タイル scorer |
| その他（例: `0`, `true`, ` 1`, `2`） | 無効 | warp scorer に fallback |

判定結果は関数内の `static const bool` に保存され、同じプロセスでは最初の評価後に環境を書き換えても再評価されません。読み取りは CUDA device が capability 8 未満と判定された場合に限って行われます。

根拠: `src/kernels/cuda/qsa_select.cu:1141-1163`。

## 有効になる条件

すべての条件を満たした場合に限り、この変数が選択カーネルを切り替えます。

- CUDA ビルドであること。HIP の `__HIPCC__` 分岐は別の `STRATA_SELECT_WMMA` 判定を使います。
- prompt の QSA selection が `qsa_block_scores_tc()` を呼び出すこと。`STRATA_SELECT_OLD` が存在すると呼び出しが短絡され、warp scorer に進みます。
- indexer geometry が `idx_dim=128`, `idx_n_head=4`, `idx_block=4` で、query 数が `65535 * 16` 以下であること。geometry または query 数が合わないと同関数は `false` を返し、呼び出し元が warp scorer を使います。
- GPU の compute capability major が 8 未満であること。8 以上では TF32 tensor-core scorer に進むため、この変数は参照されません。
- 8 未満の GPU で、環境値の先頭文字が `1` であること。
- タイル grid の y 寸法が `65535` 以下であること。超える場合は `false` が返り、呼び出し元が warp scorer に fallback します。

`STRATA_QSA_WARP` が文字列全体で `1` または `select` のときは、CUDA device の cached major を `7` として扱う A/B 経路があります。この場合、実際の GPU が capability 8 以上でも上記の pre-sm_80 分岐に入り得ます。いずれも文字列比較は大文字小文字を区別します。

根拠: `src/kernels/cuda/qsa_select.cu:1121,1141-1167`、`src/prefill/prefill.cpp:2766-2775`。

## 実行時の詳細

CUDA prompt 処理は各 selection batch について `qsa_block_scores_tc()` を試し、`false` なら `qsa_block_scores()`（warp scorer）を呼びます。その後の `qsa_block_topk()` は両方のスコア経路で共通です。FP32 タイル scorer は 32 query × 64 block をタイル化し、各 indexer head の内積を ReLU して head ごとに足し合わせます。途中の tail block は別の tail kernel でスコア化されます。

この経路は既定の warp scorer と加算順序が異なるため、ビット単位の一致は保証されません。ソースはスコア差による近接順位の変化を許容する説明をしています。カーネル起動エラー時は stderr に `qsa_block_scores (simt): <CUDA error>` を出してプロセスを終了します。

設定方法について `docs/OLDER_GPUS.md` は、エンジン起動前に環境へ設定する方法と、モデル設定の `env` object に設定して再起動する方法を記載しています。CLI 引数による上書きは調査したコードにありません。

根拠: `src/prefill/prefill.cpp:2760-2775`、`src/kernels/cuda/qsa_select.cu:487-553,1163-1172`、`docs/OLDER_GPUS.md:111-124`。

## 文書・測定値との照合

`docs/OLDER_GPUS.md` の説明は、pre-sm_80 CUDA で tiled FP32 scorer を選び、warp scorer と加算順序が異なるというソースの記述と一致します。同資料には Quadro RTX 8000（sm_75）、CUDA 12.4、GCC 13、IQ3_S + MTP、最大 context 262144 などに条件を限った測定があります。BF16_TC を有効にした比較では 4,057 token prompt の 1,262 tok/s から 1,290 tok/s、32,057 token prompt では 1,416 tok/s から 1,501 tok/s へ変化したと記録されています。いずれも資料にある特定環境・設定の観測値で、一般的な性能保証ではありません。同資料は 131,072 context の合成 QSA scorer check で 256 query 全件の選択 ID が一致したとも記しますが、任意入力での同一選択を保証する結果ではありません。

## 根拠

- `src/kernels/cuda/qsa_select.cu:487-553` — FP32 tiled scorer の処理。
- `src/kernels/cuda/qsa_select.cu:1118-1196` — backend / capability / geometry / 環境値による dispatch と fallback。
- `src/prefill/prefill.cpp:2760-2775` — prompt selection の呼び出し元と `STRATA_SELECT_OLD` 条件。
- `sycl/src/kernels/cuda/qsa_select.dp.cpp:1646-1698` — SYCL/AMD 経路における別実装。
- `include/strata/kernels/qsa_select.hpp:26-37` — API と bitwise 差に関する説明。
- `docs/OLDER_GPUS.md:111-149` — switch の説明、設定例、測定条件と測定結果。
