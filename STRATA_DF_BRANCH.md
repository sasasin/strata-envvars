# `STRATA_DF_BRANCH`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

推測検証 (`Verifier`) が記録する CUDA graph の中で、同じレイヤー入力だけを読む一部の計算を追加 stream に分岐させる opt-in 設定。分岐先は GDN レイヤーの gate/beta と `z` の計算、および条件を満たす QSA レイヤーの query と indexer query である。通常の演算を別の値に置き換える設定ではなく、入力依存が独立した計算を並行して graph に記録する。既定値は無効。

## 値と判定

| 環境変数の状態・値 | `df_branch_` |
| --- | --- |
| 未設定 | 無効 |
| 空文字 | 無効 (`atoi("")` は 0) |
| 数値変換結果が 0 | 無効 |
| 数値変換結果が 0 以外 | 有効 |

読み取りは `Verifier::init` 中に一度行い、`std::atoi` の結果を `!= 0` で判定する。文字列全体の厳密な数値検証ではないため、先頭の空白や符号の後に数字があればその数値で判定し、数字の後ろの文字列は判定に影響しない（例えば `1x` は有効、`x1` は無効）。負の非ゼロ値も有効になる。初期化後の環境変更は保存済みの `df_branch_` を変えない。

有効時は共通の fork event、2組の side stream/event を作成する。これらの作成に失敗した場合は CUDA エラー状態を取得して `df_branch_` を無効に戻すため、分岐なしの経路へ進む。ここで専用の警告ログは出さない。

## 有効になる条件

各 `record_window` 呼び出しで、さらに以下をすべて満たすときにだけ `br` が有効になる。

- `df_branch_` が有効。
- `G == 1`。`G` は通常 1 だが、batch でない `split_` の `T >= 2` ウィンドウでは 2 となり、その場合は分岐しない。
- batch-rec 経路でない (`!batch_rec_`)。
- stage profiler が有効でない (`!prof_on_`)。profiler の stamp は主 stream `cs` に記録されるため、分岐経路と併用しない。

GDN レイヤーでは `br` が有効なら分岐を使う。QSA レイヤーでは追加条件として `qbr = br && qb` が必要である。`qb` は `STRATA_DEC_BATCH` が有効、ウィンドウ内の行数 `n > 1`、native QSA と native RoPE が有効、かつ KV cache が Q4 の場合には `STRATA_DF_QB_Q4` も有効であることを要求する。従って環境変数を有効にしても、これらの実行条件に合わない QSA 経路では通常の主 stream 処理となる。

## 実行時の詳細

fork は主 stream `cs` の直前までの処理を event に記録し、side stream にその event を待たせる。join は side stream の完了 event を記録し、主 stream に待たせる。この依存関係により、分岐処理は fork より前の主 stream 処理を待ち、join より後の主 stream 処理は分岐処理を待つ。これらの stream/event 操作は `record_window` 内で graph capture される。

レイヤー処理では次の用途に使われる。

- ウィンドウ入力の step/position のコピーを最初のレイヤー処理と並行して side stream 1 に載せる。
- GDN では、入力 `xm` からの gate/beta (`gdn_ab_multi`) と `z` (`native_mmvq`) を side stream 0/1 で実行する。主 stream は q/k/v 投影と convolution を進め、recurrence が gate/beta/z を読む前に両 side stream を join する。
- 条件を満たす QSA では、query 投影と query の norm/RoPE/回転を side stream 0、indexer query とその norm/RoPE を side stream 1 で実行する。indexer query は block score の計算前に、query は attention 前に join する。

コードコメントには Linux の open modules/GSP 構成で NVML query（例: `nvidia-smi`）がリクエスト間に入った際、分岐を使う stage の window が graph 内で停止した報告が記録されており、そのため既定で無効とされている。コメント記載の条件は 2x RTX 3090 と 2x RTX 2080 Ti で、Windows では未観測とされる。これは実装コメント内の過去報告であり、この調査で再現・測定した結果ではない。

## 根拠

- `src/core/verify.cpp:540-541, 746-757`: `Verifier::init` 内の環境変数読み取り、`atoi` 判定、分岐用 stream/event 作成と失敗時の無効化。
- `src/core/verify.cpp:826, 867-879`: graph window の記録、`br` の実行条件、fork/join の event 依存。
- `src/core/verify.cpp:885-899, 1117-1127, 1147-1161`: 入力コピーと GDN の並行処理、recurrence 前の join。
- `src/core/verify.cpp:1214-1241, 1324-1328, 1386-1392`: QSA query 分岐、`qbr` 条件に使う `qb`、block score/attention 前の join。
- `include/strata/core/verify.hpp:443-448`: 分岐状態と side stream/event の保持。
- `docs/DETAILS.md` および `docs/` 内に `STRATA_DF_BRANCH` の説明は見つからなかった。上記の挙動と制約は実装コードに基づく。
