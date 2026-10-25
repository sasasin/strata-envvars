# `STRATA_EXPDEC_MINBLK`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

CUDA の EXPDEC grouped expert kernel が使う「1ブロックあたりの行数」を自動で決めるとき、計算上残るブロック数の最低目安を指定します。EXPDEC の有効化自体や、カーネルが対象レイアウトを処理するかは制御しません。ゲート/アップ投影では常に EXPDEC が選ばれた場合に使われ、down 投影では down 用 EXPDEC も有効になり対象レイアウトに合う場合に使われます。

## 値と判定

`src/kernels/cuda/iq_kernels.cu` の `env_int_or()` が環境変数を読み、`std::atoi()` で変換します。

| 環境変数の状態 | `g_expdec_minblk` |
|---|---:|
| 未設定 | 800 |
| 空文字 | 800 |
| 整数として読める文字列 | 先頭の整数。先頭空白と符号は `atoi` の規則で処理され、数字以降の文字列は変換を止める。例: `12tail` は 12、`-3` は -3 |
| 空白・符号の後に数字がない文字列 | 0 |

値全体の検証や範囲制限はありません。0 や負数もそのまま使われます。範囲外の文字列を `atoi` で変換した結果は C/C++ の仕様上保証されないため、ここでは有効値として扱いません。

## 有効になる条件

この値は `expdec_rows_per_block()` の自動決定分岐でのみ参照されます。ゲート/アップ用の `STRATA_EXPDEC_RB`、down 用の `STRATA_EXPDEC_DRB` が正数なら、その値から行数を決めるため、この下限値は参照されません。該当する `_RB` / `_DRB` が未設定、空、0、または負数なら自動決定に進みます。

自動時の初期行数 `rb` は、ゲート/アップでは `16 * R`、down では `(256 / lanes) * R` です。`R` はそれぞれ `STRATA_EXPDEC_R` / `STRATA_EXPDEC_DR` の判定後の値です。`cap` は `cap_groups > 0` なら `cap_groups`、そうでなければ 1 です。次の倍の行数にしたときも

`ceil(nrow / (2 * rb)) * cap >= STRATA_EXPDEC_MINBLK`

を満たす間、`rb` を2倍します。ループは `2 * rb <= nrow` の間に限られます。したがって小さい値（0や負数を含む）では可能な範囲まで行数を大きくし、大きい値では初期行数から増えないことがあります。これは推定上の起動ブロック数に対する分岐であり、実際にその数のブロックが常に同時実行されることを保証する設定ではありません。

## 実行時の詳細

値は CUDA translation unit のグローバル変数初期化時に一度読み込まれます。実行中に環境を変更しても再読込されません。内部 API `native_expert_set_expdec_params()` に `min_blocks > 0` を渡す呼び出しは値を上書きできますが、調査対象リポジトリでこの setter を呼ぶのは `expdec_bench` だけでした。ヘッダーは各パラメーターを環境変数または既定値から読むものと説明しています。この上書きは正数に限られます。

通常の engine 経路では、EXPDEC 自体が `STRATA_EXPDEC` で有効になり、旧 IQ MMVQ kernels が無効で、レイアウトが対応する場合にだけカスタム kernel へ進みます。`STRATA_EXPDEC` は `env_on()` により、unset・空文字・先頭文字 `0` なら無効、それ以外は有効です。ゲート/アップの対応条件は形式番号 16/17/18/21/22、`n_embd == 2560`、正の `n_ff` が64の倍数です。down はさらに `STRATA_EXPDEC_DOWN` が有効であること、形式番号20（かつ `STRATA_EXPDEC_D20` が有効）または42、`n_ff == 640`、正の `n_embd` が128の倍数であることが必要です。条件を満たさない場合は呼び出し元が既定 kernel を起動します。

EXPDEC がレイアウトに合うと、初回の (役割, 形式) ごとに stderr の `strata expdec: ...` 行に選択された kernel と行数が出ます。このログは `STRATA_EXPDEC_MINBLK` の生の値自体は表示しません。`docs/EXPERTDEC.md` は自動行数決定の基準を説明していますが、特定値の性能差は記載していません。

## 根拠

- 環境読み取り、既定値800、グローバル初期化: `src/kernels/cuda/iq_kernels.cu:3933-3953`。
- 手動行数と自動決定の式、下限条件: `src/kernels/cuda/iq_kernels.cu:3963-3973`。
- gate/up と down の行数決定呼び出し: `src/kernels/cuda/iq_kernels.cu:3976-3983,4045-4052`。
- EXPDEC レイアウト条件と旧 kernel / EXPDEC 有効判定: `src/kernels/cuda/iq_kernels.cu:3955-3961,4029-4044,4063-4065`。
- `env_on()` の値判定と grouped expert 呼び出し元: `src/kernels/cuda/iq_kernels.cu:3273-3276,5200-5205,5262-5268`。
- setter の上書き条件、ベンチ用 API の注記: `src/kernels/cuda/iq_kernels.cu:5022-5042`, `include/strata/kernels/iq_kernels.hpp:106-120`; setter の呼び出しは `src/kernels/expdec_bench.cpp:105-106`。
- 設計概要: `docs/EXPERTDEC.md:23-28`。
