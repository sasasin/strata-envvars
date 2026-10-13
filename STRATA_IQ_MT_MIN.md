# `STRATA_IQ_MT_MIN`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数の意味は対象外。

## 役割

CPU 上で native expert の複数 token 用 IQ カーネルを使い始める最小 token 数を決めます。主な対象は gate/up 行の IQ multi-token kernels で、IQ4_NL の down 行にも同じ閾値があります。既定値 `2` では token が1個のとき ggml-cpu の dot 経路に残り、`1` 以下なら対応する Strata multi-token kernel を1 token から選べます。

この切り替えは CPU 側の演算経路を変えます。IQ の単一 token と複数 token の計算で丸めが異なるため、verify window の draft 数など、同じ expert を共有する token 数が違うと greedy 出力が変わり得ます。`1` にすると対応 kernel の計算を1 token から揃え、draft 数による差を避ける意図です。通常の model/backend 全体の設定ではなく、native expert が CPU で実行される場合の kernel 選択用です。

## 値と判定

値は文字列比較ではなく `std::atoi` で整数へ変換されます。値の全体を検証せず、整数変換の後ろに続く文字列も無視します。unset のときは `2` です。空文字や先頭が数値でない文字列は `atoi` の結果 `0` になり、負数も clamp されません。

| 環境値 | 判定結果 | 対応する kernel 選択への影響 |
|---|---:|---|
| unset | 既定値 `2` | token 数 `nt >= 2` で multi-token kernel 候補になる |
| `1`, `1abc` | `1` | `nt >= 1` で候補になる |
| `0`, 空文字, `abc` | `0` | 正の `nt` すべてで候補になる |
| `-2` | `-2` | 正の `nt` すべてで候補になる |
| `3`, `3tail` | `3` | `nt >= 3` で候補になる |
| 空白または数値で始まる値 | `atoi` の変換規則に従う | 変換された整数と `nt` を比較する |

`atoi` の変換失敗と空文字はどちらも `0` になります。大文字小文字の判定はありません。正の閾値の上限・下限チェックや clamp はありません。

## 有効になる条件

この値は、Strata が native expert 対応 (`STRATA_NATIVE_EXPERTS`) 付きでビルドされ、モデルの native expert を CPU pool が実行するときに関係します。native expert 機能を含めないビルドでは、本番の `native_expert.cpp` は選択経路に入りません。通常の GPU expert kernel、FP16 等の非 native expert 経路にはこの閾値は適用されません。

`native_gu_rows()` では、閾値に加えて token 数、format 対応、CPU ISA の条件を満たす必要があります。

- AVX-512 対応形式なら、AVX-512 が利用可能で `STRATA_NO_IQ512` が unset の場合に AVX-512 kernel が候補です。
- AVX2 対応形式なら、AVX-512 CPU ではなく、AVX2 が利用可能で `STRATA_NO_IQ256` が unset の場合に AVX2 kernel が候補です。
- AVX1 用の対応形式では、AVX2 がなく AVX1 が利用可能で `STRATA_NO_IQ128` が unset の場合に AVX1 kernel が候補です。この gate/up 経路にも `nt >= mt_min` が掛かります。
- いずれの条件も満たさなければ ggml-cpu の `vec_dot` へ fallback します。非対応形式もここへ進みます。

`native_down_rows()` でこの閾値が直接使われるのは IQ4_NL の AVX2 multi-token down kernelです。AVX2 対応、`nt >= mt_min`、かつ `STRATA_NO_IQ4NL` が unset の場合に選ばれます。Q5_1/Q8_0 の down kernel は別の `STRATA_KQ256` 条件と `nt >= 2` で選択され、AVX2 用 Q2_0 down kernel (`q2_native_kernels`) も専用経路を通るため、この変数の閾値では制御されません。AVX1 down kernel の分岐にも `mt_min` 条件はありません。

## 実行時の詳細

本番での読み取り箇所は `src/kernels/cpu/native_expert.cpp` にあります。`native_gu_mt_min()` は `STRATA_IQ_MT_MIN` のポインターと `atoi` 結果を function-local `static` に保持し、gate/up の kernel 選択で使います。`native_down_rows()` は別の function-local `static` で同じ名前を読み、IQ4_NL down kernel に使います。どちらも各関数で最初に評価された結果をプロセス内で再利用します。したがって、読み取り後に環境を変更しても、その選択値は再評価されません。2箇所は初回評価が独立しています。

`STRATA_IQ_MT_MIN` が unset の場合に限り、`STRATA_IQ3S_MT1` が設定され、AVX2 はあるが AVX-512 はなく、IQ256 gather 条件も満たす CPU では、IQ3_S の gate/up 閾値を `1` にする別の opt-in 分岐があります。`STRATA_IQ_MT_MIN` を明示すると、この IQ3_S 上書き分岐は使われません。これは設定値の内容ではなく、`getenv(...) != nullptr` という設定有無で判定されます。

この環境変数自体について、本番コードはログや警告を出しません。コード上の効果は CPU native expert の kernel 分岐です。`tools/batch_test.py` は `--mt-min` 引数を engine 用環境辞書へ渡し、既定の引数値は文字列 `1`、空文字ならその変数を辞書に追加しません。ただしこれは同梱比較ツールの挙動であり、engine 本体の既定値は未設定時の `2` です。

診断実行ファイル `native_expert_parity` は、起動時にこの変数が未設定なら自身のプロセス内で `1` を設定してから parity を調べます。設定済みの値は変更しません（`src/kernels/native_expert_parity.cpp:528-544`）。`iq_avx2_parity` は現在値を出力します（`src/kernels/cpu/iq_avx2_parity.cpp:528-545`）。これらは診断実行ファイル固有の挙動で、engine 本体の既定値を変えるものではありません。

## 文書との照合

`docs/DETAILS.md` は、既定の `2` では一 token と複数 token で CPU の IQ expert rows の丸めが異なり得ること、`STRATA_IQ_MT_MIN=1` で対応する multi-token kernel を全 group に使うことを説明しています。同資料の測定記載は Ryzen 7600（AVX-512）の IQ3_S decode で `-1..-3%`、その他の対象モデルは同じとしています。これはその記載条件の測定値であり、他 CPU・モデルや設定での性能はこの調査では確認していません。実装条件は上記の通り format・ISA ごとに制限され、「すべてのCPU演算に一律適用」されるものではありません。

## 根拠

- `CMakeLists.txt:1210-1218,1267-1305` — native expert build option と CPU kernel source の登録。
- `src/kernels/cpu/native_expert.cpp:115-132` — gate/up の閾値、既定値、IQ3_S の unset 時 override。
- `src/kernels/cpu/native_expert.cpp:134-197` — gate/up の token 閾値、ISA・format 判定、ggml-cpu fallback。
- `src/kernels/cpu/native_expert.cpp:199-231` — down 行の独立した閾値読み取りと、IQ4_NL、KQ、AVX1、ggml-cpu 各経路。
- `src/kernels/cpu/pool.cpp:629-663` — CPU pool から native gate/up/down row kernel を呼ぶ箇所と Q2_0 専用分岐。
- `tools/batch_test.py:81-98` — 比較ツールの `--mt-min` と engine 用環境辞書。
- `src/kernels/native_expert_parity.cpp:528-544`, `src/kernels/cpu/iq_avx2_parity.cpp:528-545` — parity 診断実行ファイルによる既定値設定と値の表示。
- `docs/DETAILS.md:97-108` — 目的、設定上の説明、測定値および再現性条件に関する記載。
