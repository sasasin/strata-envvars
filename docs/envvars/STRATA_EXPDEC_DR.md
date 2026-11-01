# `STRATA_EXPDEC_DR`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

EXPDEC の down カーネルで、1 lane が担当する行数 `R` を指定します。ゲート/up の行数を指定する `STRATA_EXPDEC_R` とは別の設定です。`STRATA_EXPDEC_DR` は down カーネルのパラメーターであり、down 側の EXPDEC が無効なら処理に使われません。

## 値と判定

`env_int_or()` は環境値が未設定または空文字なら既定値 `4` を返し、それ以外は `std::atoi()` で整数化します。その後 `expdec_dr()` が整数 `1` と `2` だけをそのまま採用し、それ以外を `4` にします。文字列全体の厳密な数値検証はなく、`atoi` が読む先頭の数値部分が判定対象です。

| 環境値 | parse 後 | down の `R` |
|---|---:|---:|
| 未設定、空文字 | 既定値 4 | 4 |
| `1`、`1x`、`1.5` | 1 | 1 |
| `2`、`2x`、`2.5` | 2 | 2 |
| `0`、`3`、`-1`、`x` | それぞれ 0、3、-1、0 | 4 |

したがって不正文字列や範囲外の整数はエラーにならず、最終的に `R=4` へ戻ります。数値部分の後ろは検査されません（例: `2anything` は `2`）。`atoi` で `int` の範囲に収まらない値の結果は保証されません。

## 有効になる条件

- この値は `src/kernels/cuda/iq_kernels.cu` の EXPDEC down 分岐で参照されます。down EXPDEC 自体は `STRATA_EXPDEC` が有効で、旧カーネル指定 `STRATA_OLD_IQ_MMVQ` が無効であることが必要です。両フラグは未設定・空文字・先頭文字が `0` の値を無効、それ以外を有効とします。
- さらに `STRATA_EXPDEC_DOWN` が非ゼロで、down の型が既定では Q2_0（type 20）または IQ4_NL（type 42）である必要があります。IQ4_NL は `STRATA_EXPDEC_D20` も非ゼロの場合だけ対象です。形状条件は `n_ff == 32 * ED_HB`、`n_embd` が 128 の倍数かつ正数です。満たさないと down は既定カーネルへ進み、この値は使われません。
- `STRATA_EXPDEC_DR` の値による専用 CLI 引数は見つかりませんでした。内部 API `native_expert_set_expdec_params()` が `down_rows_per_lane > 0` を受け取ると環境値を上書きします。エンジン起動経路にこの setter を呼ぶ箇所はなく、リポジトリ内では `expdec_bench` が選択肢を渡します。

## 実行時の詳細

候補名の全参照を検索すると、環境から読む直接参照は `iq_kernels.cu` の初期化1箇所でした。共通の `env_int_or()` は同ファイル内の EXPDEC ノブ専用で、DR には文字列リテラルの名前を渡しています。値はカーネル翻訳単位のグローバル `g_expdec_dr` 初期化時に読み込まれ、`expdec_dr()` が 1/2/4 に正規化した値を down カーネル選択へ渡します。起動後の環境変更は再読み込みされませんが、上記の内部 setter で値を差し替えることはできます。

down EXPDEC が採用されると、`R=1/2/4` に応じたテンプレート版 `expdec_down_kernel` を選びます。ログは対象の role/type と taken 状態ごとに初回だけ stderr へ出力され、適用時は `strata expdec: CUDA%d down type ... expdec_down_kernel R %d ...` の形式です。対象外では `... not covered: the default kernel runs` が出ます。EXPDEC が無効、または旧カーネル指定時はこの判定関数から既定 down カーネルへ進み、EXPDEC のログは出しません。launch 後の CUDA エラーは `native_expert_grouped/down: <エラー文字列>` を stderr に出してプロセスを終了コード 1 で終了します。

## 根拠

- `src/kernels/cuda/iq_kernels.cu:4055-4059,4063-4075` — `env_int_or()` の未設定・空文字処理、`atoi`、既定値4、1/2以外を4とする正規化。
- `src/kernels/cuda/iq_kernels.cu:4081-4084,4185-4192` — down EXPDEC の型・shape・別ノブ条件と、失敗時に false を返す分岐。
- `src/kernels/cuda/iq_kernels.cu:4123-4148` — 初回ログ文言と down カーネルの `R` 報告。
- `src/kernels/cuda/iq_kernels.cu:4167-4183` — 正規化後の `R` による down カーネルの選択。
- `src/kernels/cuda/iq_kernels.cu:6216-6237` — EXPDEC とパラメーターを設定する内部 API。DR は setter の正値で置換される。
- `src/kernels/cuda/iq_kernels.cu:6484-6491` — down EXPDEC が使われない場合の既定カーネル経路と、launch 後の CUDA エラー確認。
- `src/kernels/cuda/iq_kernels.cu:38-40` — CUDA エラー文字列を stderr へ出し、終了コード 1 で終了する `check()`。
- `include/strata/kernels/iq_kernels.hpp:113-125`、`docs/EXPERTDEC.md:16-34,40-42` — EXPDEC が対象とする形式、down の opt-in 条件、ノブの説明。
- `src/kernels/expdec_bench.cpp:90,104-107` — ベンチマーク CLI の `d` 選択肢を内部パラメーター setter へ渡す箇所。エンジン本体の CLI オプションではありません。
