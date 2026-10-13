# `STRATA_EXPERT_V2K`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリが読む環境変数の動作は対象外。

## 役割

CUDA/HIP の native grouped expert decode で、対応する形式と寸法の expert に S27 カーネル列を選びます。対象は gate/up が Q4_K または Q5_K、down が Q5_1 または Q8_0、`n_embd == 2560`、`n_ff == 640` の組です。通常経路に代わり、grouped gate/up、SwiGLU と Q8_1 量子化、grouped down を同一 stream に順番に launch します。コードコメントでは UD-Q4_K_XL 向けの実験経路とされています。

## 値と判定

CUDA/HIP 実装は `getenv()` の結果の先頭文字だけを見て、`'1'` なら有効にします。文字列全体の比較や数値変換は行いません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| `1`、`10`、`1anything` | 有効 |
| `0`、`true`、` 1`、その他先頭文字が `1` でない値 | 無効 |

判定は `native_expert_grouped()` 内の `static const bool` に保存されますが、先行する S26 分岐が成立するとそこで return するため、その呼び出しではまだ評価されません。S26 分岐を通らなかった最初の呼び出しで評価され、その後はプロセス内で更新されません。したがって、初回評価後に環境を書き換えても反映されません。gfx1151 向け既定値テーブルには `STRATA_EXPERT_V2` はありますが `STRATA_EXPERT_V2K` はなく、この変数を Strata が自動的に設定するコードは確認できませんでした。

## 有効になる条件

- `native_expert_grouped()` が呼ばれ、環境値が有効であること。リモート expert、peer expert、verify の grouped native 経路から呼び出されます。
- レイアウトが `gu_type` 12（Q4_K）または13（Q5_K）、`d_type` 7（Q5_1）または8（Q8_0）、`n_embd == 2560`、`n_ff == 640` に一致すること。型番号と形式名は GGUF reader の対応表にあります。
- この分岐より前にある `STRATA_EXPERT_V2` の S26 条件に一致しないこと。S26 条件に一致した場合はそちらが先に実行されて return するため、`STRATA_EXPERT_V2K` は評価されません。
- CUDA/HIP の `src/kernels/cuda/iq_kernels.cu` 実装を使うこと。条件不一致、変数無効、または別の実装経路なら既存 grouped expert 経路へ進みます。

SYCL では S27 カーネルをビルドせず、切り替えにも使いません。grouped expert 関数の初回呼び出し時に、この変数または `STRATA_EXPERT_V2` のいずれかが先頭文字 `1` なら、stderr に一度 `note: STRATA_EXPERT_V2 / STRATA_EXPERT_V2K are AMD-only experiments, ignored on SYCL` と出します。

## 実行時の詳細

S27 は expert group 内で複数行を処理し、入力側の Q8_1 activation rows を共有領域に置く構成です。対応する形式ごとに S27 の weight load/apply 処理を使い、gate/up の後に既存の融合 SwiGLU + Q8_1 カーネル、続いて down カーネルを同じ stream に launch します。最後に `check("native_expert_grouped (v2k)")` でカーネル起動エラーを確認します。

対応するレイアウト内で `STRATA_TSUM` も先頭文字 `1` なら、S27 の gate/up と down の両方で transposed butterfly の warp sum を選びます。これは S27 分岐内で初回に評価・キャッシュされます。`STRATA_TSUM` が無効なら通常の warp sum を使います。

## 文書との照合

`docs/UNSLOTH_Q4.md` は UD-Q4_K_XL の routed experts を、gate/up は通常 Q4_K（一部 Q5_K）、down は通常 Q5_1（一部 Q8_0）と記載しています。これは S27 分岐が扱う型の組と一致します。同資料はモデルを experimental としていますが、`STRATA_EXPERT_V2K` 自体の有効値、適用条件、性能値は説明していません。ソースコメントにある bitwise 一致の記述は実装コメント上の主張として扱い、この調査では harness や実機で再検証していません。

## 根拠

- `src/kernels/cuda/iq_kernels.cu:2348-2354` — S27 の対象形式、処理構造とコメント上の bitwise 一致の説明。
- `src/kernels/cuda/iq_kernels.cu:2420-2472,2475-2557,2566-2644` — Q5_1/Q8_0 の処理と grouped S27 gate/up・down カーネル。
- `src/kernels/cuda/iq_kernels.cu:2647-2663` — S27 カーネル列、TSUM の有無による launch 選択。
- `src/kernels/cuda/iq_kernels.cu:3451-3492` — 値のキャッシュ、S26 との順序、形式・寸法条件、TSUM 分岐、fallback。
- `include/strata/artifact/gguf_reader.hpp:63-78` — 型番号 7/8/12/13 と Q5_1/Q8_0/Q4_K/Q5_K の対応。
- `src/core/remote_experts.cpp:313-323`, `src/core/peer_experts.cpp:235-245`, `src/core/verify.cpp:1577-1587` — 呼び出し元の grouped native 経路。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:3099-3102,5052-5074` — SYCL での未移植、無視、note 出力。
- `src/core/arch_defaults.cpp:32-57` — gfx1151 の既定値一覧。`STRATA_EXPERT_V2K` は含まれない。
- `docs/UNSLOTH_Q4.md:1-12` — UD-Q4_K_XL の実験扱いと expert weight 形式。
