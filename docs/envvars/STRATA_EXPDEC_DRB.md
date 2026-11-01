# `STRATA_EXPDEC_DRB`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata リポジトリの作業ツリーは `main...origin/main` で変更なし。

## 役割

EXPDEC の down kernel で、1 block が処理する出力行数を指定します。gate/up 用の `STRATA_EXPDEC_RB` とは別の値です。`STRATA_EXPDEC_DRB` 自体は EXPDEC を有効にせず、down kernel の適用条件を満たさない経路では参照値があっても使われません。

## 値と判定

`env_int_or()` が環境変数を `std::getenv()` で読み、値が未設定または空文字なら既定値 `0` を返します。それ以外は `std::atoi()` で整数化します。全体の厳密な parse やエラー検査はありません。先頭の空白と符号を含む整数部分が変換され、数字以外から始まる文字列は `0` になり、整数の後ろの文字は変換に影響しません（例: `12xyz` は `12`、`xyz` は `0`）。

| 入力 | `g_expdec_drb` | down kernel での扱い |
|---|---:|---|
| 未設定、空文字 | 0 | 自動選択 |
| 数字以外から始まる値 | 0 | 自動選択 |
| 変換結果が 0 または負数 | その整数 | 自動選択（明示値として使う条件が `knob > 0`） |
| 正数 | その整数 | `rows per pass` の倍数に切り上げ、出力行数 `n_embd` を上限として使う |

正数のとき `rb = ceil(value / rpp) * rpp` を計算し、`rb > n_embd` なら `n_embd` に制限します。ここで down の `rpp` は `(256 / LANES) * R`、`LANES` は type 20（Q2_0）なら 8、それ以外の対応 type 42（IQ4_NL）なら 16 です。`R` は別変数 `STRATA_EXPDEC_DR` の値を 1/2/4 に正規化した値（既定 4）です。したがって DRB の正数がそのまま rows per block になるとは限りません。整数範囲外の入力に対する `atoi` の動作はコードで検査・規定されていません。

根拠: `src/kernels/cuda/iq_kernels.cu:4055-4059,4070-4075,4085-4095,4167-4174`。

## 有効になる条件

DRB が down kernel の block 行数に反映されるには、次の条件を満たして EXPDEC down 経路まで到達する必要があります。

- EXPDEC が有効で、旧 IQ MMVQ kernel が無効である。EXPDEC は `STRATA_EXPDEC` の有効判定で制御され、`STRATA_OLD_IQ_MMVQ` が有効だと down EXPDEC を使いません。
- down 側の EXPDEC が有効である。通常は `STRATA_EXPDEC_DOWN` が 0 なので down は既定で無効です。
- layout が対応する。down type 20 ではさらに `STRATA_EXPDEC_D20` が有効であること、また type 20 または 42、`n_ff == 32 * ED_HB`、`n_embd` が 128 の倍数かつ正数であることが必要です。
- CUDA 実装の `native_expert_grouped` の down 処理が EXPDEC より前の別経路で終了しないこと。`STRATA_EXP_LAYOUTS` が有効で、適切な `em0d` と layout 条件を満たすと LDS down kernel が先に実行されます。

以上の条件を満たさない場合は既定の down kernel 等へ進み、DRB による block 行数設定は使いません。文書 `docs/EXPERTDEC.md` も EXPDEC を opt-in、CUDA only と説明し、down は `STRATA_EXPDEC_DOWN=1` のときに限るとしています。

根拠: `src/kernels/cuda/iq_kernels.cu:3395-3400,4081-4083,4185-4192,6455-6490`; `docs/EXPERTDEC.md:1-4,31-34`。

## 実行時の詳細

`g_expdec_drb` は翻訳単位の global 変数初期化時に環境から一度読み込まれます。呼び出しごとの再読込や環境値の cache 更新はありません。Strata の公開 C++ API `native_expert_set_expdec_params()` は `down_rows_per_block >= 0` の場合にこの値を上書きできます（0 は自動選択、負数は現値を維持）。ソース内の通常実行経路からこの setter を呼ぶ箇所は確認できず、設定手段として確認できるのは環境変数と API です。専用 CLI 引数による優先順位はありません。

down EXPDEC が適用されると、`expdec_down_r()` が DRB と `STRATA_EXPDEC_DR` から計算した `rb` で grid を作り、`expdec_down_kernel` に渡します。最初に該当する role/type を処理すると stderr に、適用時は `strata expdec: CUDA%d down type ... expdec_down_kernel R ..., %d rows per block ...`、非対応時は `... not covered: the default kernel runs` の形式で出力します。DRB の不正値だけを理由にする警告、終了、fallback はなく、0/負値や数字以外は自動選択として処理されます。ログは role/type と taken 状態ごとに一度だけです。

根拠: `src/kernels/cuda/iq_kernels.cu:4072,4120-4127,4142-4147,4177-4192,6218-6226`。

## 根拠

- 候補名のリポジトリ全体検索では、実際の環境読み取りは `src/kernels/cuda/iq_kernels.cu:4072` の1か所でした。値の読み取り helper は同ファイルの `4056-4059` です。
- API setter と getter は `src/kernels/cuda/iq_kernels.cu:6218-6238`、宣言と field の説明は `include/strata/kernels/iq_kernels.hpp:119-131` にあります。
- EXPDEC down の有効判定・実行・fallback は `src/kernels/cuda/iq_kernels.cu:4081-4083,4185-4192,6484-6490`、前段で LDS kernel に分岐する条件は `6455-6467` です。
- 関連設計資料は `docs/EXPERTDEC.md:1-4,16-34,36-42` です。同資料の測定値は EXPDEC 全体の説明であり、この環境変数単独の性能効果を示すものではありません。
