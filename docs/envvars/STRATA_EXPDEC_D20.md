# `STRATA_EXPDEC_D20`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `main...origin/main` で、変更表示はありませんでした。外部ライブラリの挙動は対象外です。

## 役割

EXPDEC の down 投影カーネルを IQ4_NL 形式にも使うための追加スイッチです。この変数だけでは EXPDEC も down 投影への適用も有効になりません。EXPDEC 自体が有効で、別変数 `STRATA_EXPDEC_DOWN` も非ゼロの場合に、IQ4_NL down を EXPDEC の対象に加えます。条件を満たさない場合は従来の down カーネルへ進みます（`src/kernels/cuda/iq_kernels.cu:4066,4081-4083,4185-4192,6484-6489`）。

## 値と判定

共通 helper は、値が未設定または空文字なら既定値を返し、それ以外は `std::atoi` の戻り値を使います。既定値は `0` です。全体の文字列検証や範囲検査はなく、判定側は `g_expdec_d20` がゼロかどうかだけを見ます（`src/kernels/cuda/iq_kernels.cu:4056-4059,4066,4081-4083`）。

| 設定値 | helper の結果 | IQ4_NL down 条件での扱い |
|---|---:|---|
| 未設定、空文字 | `0` | 無効 |
| `0`、`false`、数値で始まらない文字列 | `0` | 無効 |
| `1`、`2`、`-1`、`1suffix` | 非ゼロ | 有効候補 |

`atoi` は数値として読める先頭部分を変換するため、`1suffix` は `1`、`false` は `0` です。先頭空白や符号も `atoi` の規則で処理されます。変換失敗をエラーにせず、文字列全体が真偽値かどうかも確認しません。整数範囲外の入力に対する値はこのコードで規定されていません（`src/kernels/cuda/iq_kernels.cu:4056-4059`）。

## 有効になる条件

IQ4_NL down で EXPDEC が選ばれるには、すべての条件が必要です。

- 標準の grouped expert down dispatch に到達すること。`native_expert_grouped` の別の先行経路が条件に合うとそこで処理を終え、EXPDEC の down 選択まで進みません（`src/kernels/cuda/iq_kernels.cu:6267-6278,6298-6321,6484-6491`）。
- `STRATA_EXPDEC` が有効で、`STRATA_OLD_IQ_MMVQ` が有効でないこと。`STRATA_EXPDEC` の判定 helper は未設定・空文字・先頭が `0` の値を無効とし、それ以外を有効とします（`src/kernels/cuda/iq_kernels.cu:3395-3401,4060-4062,4185-4188`）。
- `STRATA_EXPDEC_DOWN` の `atoi` 結果が非ゼロであること。未設定・空文字の既定値は `0` です（`src/kernels/cuda/iq_kernels.cu:4070,4081-4083`）。
- down の型が IQ4_NL（コード上の type `20`）で、`STRATA_EXPDEC_D20` の `atoi` 結果も非ゼロであること。形状は `n_ff == 32 * ED_HB`（`ED_HB` は 20、すなわち 640）かつ `n_embd > 0` で 128 の倍数である必要があります（`src/kernels/cuda/iq_kernels.cu:2451-2453,4081-4083`）。

Q2_0（type `42`）は `STRATA_EXPDEC_DOWN` と形状条件で対象になり、`STRATA_EXPDEC_D20` は判定に使われません。対象形式・形状に合わない場合は EXPDEC down を使いません（`src/kernels/cuda/iq_kernels.cu:4081-4083,4190-4192`）。

## 実行時の詳細

`g_expdec_d20` は翻訳単位の初期化時に `env_int_or` を呼ぶグローバル変数です。したがって通常のエンジンではプロセス開始時に一度読み、その後の環境変更では更新されません。公開 API `native_expert_set_expdec_params` は `down_iq4_nl >= 0` の場合にこの値を上書きできますが、エンジン本体からの呼び出しは見つかりませんでした。確認できた呼び出しは `expdec_bench` です（`src/kernels/cuda/iq_kernels.cu:4066,6218-6226`; `src/kernels/expdec_bench.cpp:105-106`）。

この変数専用の警告や終了経路はありません。EXPDEC が有効で、標準 down dispatch が実行された場合、形式・形状が対象外なら `expdec_note` がその down type の `not covered: the default kernel runs` を stderr に一度出します。対象になれば `strata expdec: CUDA%d down type 20: expdec_down_kernel ...` を stderr に一度出します。EXPDEC 自体が無効、旧 kernel が有効、または別の先行経路の場合、この判定・ログには到達しません。kernel 起動後の runtime error は共通の `check("native_expert_grouped/down")` 経由で stderr に出てプロセスを終了します（`src/kernels/cuda/iq_kernels.cu:4120-4147,4185-4192,6484-6491`; `src/kernels/cuda/iq_kernels.cu:38-41`）。

`STRATA_EXPDEC` は初回使用時に遅延評価される一方、この変数は翻訳単位の初期化時に読む点が異なります（`src/kernels/cuda/iq_kernels.cu:4060-4066`）。また、HIP gfx12 向け architecture defaults は `STRATA_EXPDEC=1` を既定設定に追加し、ユーザーが既に設定した値は維持します。これは `STRATA_EXPDEC_D20` を設定するものではなく、down 用の `STRATA_EXPDEC_DOWN` も別途必要です（`src/core/arch_defaults.cpp:27-53,167-180`; `src/program/generate.cpp:3383-3400`）。

Strata の `docs/EXPERTDEC.md` は EXPDEC を CUDA 専用と説明し、IQ4_NL down の micro-bench は 0.95–1.07 倍で利得なしと記しています。これは資料に記載された測定の説明であり、本調査では実行・再測定していません（`docs/EXPERTDEC.md:1-4,86-87`）。一方、CMake は `iq_kernels.cu` を CUDA または HIP の GPU target に含め、HIP backend は `src/*.cu` を HIP 言語としてコンパイルします。また gfx12 向け architecture defaults は `STRATA_EXPDEC=1` を追加します。このため「CUDA 専用」という資料の説明と現行 build/source の対応には差があります（`CMakeLists.txt:412,456-506`; `cmake/hip_backend.cmake:123-130`; `src/core/arch_defaults.cpp:27-53,167-180`; `src/program/generate.cpp:3383-3400`）。

## 根拠

- 直接参照と整数 helper: `src/kernels/cuda/iq_kernels.cu:4056-4059,4066,4081-4083`。
- down dispatch、ログ、fallback: `src/kernels/cuda/iq_kernels.cu:4120-4147,4185-4192,6484-6491`。
- setter と初期化時期: `src/kernels/cuda/iq_kernels.cu:4060-4066,6218-6226`; `src/kernels/expdec_bench.cpp:105-106`。
- 関連する既定値・backend build・資料: `src/core/arch_defaults.cpp:27-53,167-180`; `src/program/generate.cpp:3383-3400`; `CMakeLists.txt:412,456-506`; `cmake/hip_backend.cmake:123-130`; `docs/EXPERTDEC.md:1-4,32-42,86-87`。
