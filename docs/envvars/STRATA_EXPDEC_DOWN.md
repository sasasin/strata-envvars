# `STRATA_EXPDEC_DOWN`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

`STRATA_EXPDEC=1` で有効になる EXPDEC 最適化のうち、expert の down projection にも EXPDEC kernel を使うかを選びます。既定値は無効で、ゲート/up 側の EXPDEC には影響しません。down 側の候補は Q2_0 と IQ4_NL ですが、Q2_0 には別途 `STRATA_EXPDEC_D20` も必要です（`src/kernels/cuda/iq_kernels.cu:4062-4070,4081-4083`）。

## 値と判定

環境値は `env_int_or(name, 0)` が読み、空でない値を `std::atoi` に渡します。結果の整数が 0 なら無効、0 以外なら有効です（`src/kernels/cuda/iq_kernels.cu:4055-4059,4070`）。

| 環境値 | `g_expdec_down` | 判定 |
|---|---:|---|
| 未設定 | 0 | 無効 |
| 空文字 | 0 | helper が既定値 0 を返し、無効 |
| `0`、`00`、`junk` | 0 | 無効。`atoi` が先頭から整数に変換できない場合も 0 |
| `1`、`2`、`-1` | それぞれの整数 | いずれも 0 以外なので有効 |
| `1tail`、` 1x` | 1 | `atoi` が先頭の整数部分を読むため有効 |

文字列全体の妥当性検査や値域制限はありません。数値変換後の整数が 0 かどうかだけを使います。整数型に収まらない値の結果はこの実装で検証・制限されません。

## 有効になる条件

環境値が非 0 でも、次の条件を満たす down の呼び出しでだけ EXPDEC kernel が選ばれます。

- 全体の `STRATA_EXPDEC` が有効。CUDA ソースの `env_on` は unset・空文字・先頭が `0` の値を無効、それ以外を有効と判定します（`src/kernels/cuda/iq_kernels.cu:3395-3398,4061-4062`）。したがって、通常の `STRATA_EXPDEC=1` が必要です。
- `STRATA_OLD_IQ_MMVQ` が有効でない。この設定が有効だと EXPDEC の down 分岐から戻り、既定 down kernel に進みます（同:3399-3401,4185-4192）。
- `native_expert_grouped` の down 処理が EXPDEC 判定まで到達する。down の特別な LDS / AMD layout 経路が先に処理・return する場合は、この判定を通りません（同:6444-6484）。
- レイアウト条件を満たす。Q2_0（`d_type == 20`）では `STRATA_EXPDEC_D20` も非 0、IQ4_NL（`d_type == 42`）では追加フラグ不要です。どちらも `n_ff == 640`、`n_embd > 0` かつ 128 の倍数が必要です（同:4066,4081-4083）。

## 実行時の詳細

この値は CUDA kernel ソースのグローバル変数初期化時に読み込まれ `g_expdec_down` に保存されます。読み直しはなく、プロセス起動後の環境変更は反映されません。ソースには `native_expert_set_expdec_params` による上書き口もあり、`p.down >= 0` なら値を直接設定します。リポジトリ内でこの setter を使うのは `expdec_bench` で、通常の engine 経路では setter 呼び出しを確認できません（同:6216-6227、`src/kernels/expdec_bench.cpp:105-106`）。CLI 引数や別設定ファイルが環境変数より優先する通常 engine の経路は見つかりません。

条件を満たすと `expdec_down()` が down 用 EXPDEC kernel を起動し、満たさない場合は呼び出し元が既定 down kernel を選びます（同:4185-4192,6484-6491）。EXPDEC が有効で旧 kernel が無効な状態では、初めて遭遇した role/type ごとに stderr へ一度、選択結果を出します。適用時は `strata expdec: CUDA%d down type %d: expdec_down_kernel ...`、対象外なら `strata expdec: CUDA%d down type %d ... not covered: the default kernel runs` です。全体 EXPDEC が無効、または旧 kernel が有効なら、この down 判定関数はログを出さずに戻ります（同:4123-4147,4185-4192）。kernel 起動後は `check("native_expert_grouped/down")` でエラー確認します（同:6484-6491）。

この機能は `src/kernels/cuda/iq_kernels.cu` に実装されています。CMake の CUDA/HIP kernel target に同ファイルが含まれます（`CMakeLists.txt:412-416,456-505`）。一方、SYCL は移植済みの `sycl/src/kernels/cuda/iq_kernels.dp.cpp` を選択し、そのコピーに `STRATA_EXPDEC_DOWN` または EXPDEC 実装はありません（`sycl/CMakeLists.txt:107-126,237-246`）。したがって環境変数だけで SYCL 経路にこの down kernel が加わることはありません。

## ログと測定値

`docs/EXPERTDEC.md` は RTX 2080 Ti の 131k decode における down Q2_0 の測定を約 10%低速と記載し、既定 OFF の理由としています。同資料の測定条件は layer split（RTX 3060 / RTX 2080 Ti）、`--pipeline-windows 2`、Windows、96 verify windows です（`docs/EXPERTDEC.md:91-100`）。これは資料に記載された条件での測定値であり、他環境の性能を示すものではありません。

## 根拠

- 値の取得・変換と既定値: `src/kernels/cuda/iq_kernels.cu:4055-4073`
- EXPDEC down の型・寸法条件: 同 `:4081-4083`
- EXPDEC / 旧 kernel の判定、down kernel 選択: 同 `:4185-4192`
- 上書き API と bench 利用: 同 `:6216-6237`、`src/kernels/expdec_bench.cpp:105-106`
- engine の down dispatch と既定 kernel fallback: 同 `:6444-6491`
- down kernel と観測ログ: 同 `:2745-2785,4123-4147`
- 測定条件と結果: `docs/EXPERTDEC.md:91-100`
