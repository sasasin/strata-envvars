# `STRATA_GR_V3`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA/HIP の fused hyper-connection（GR）多 token read で、既定の multi read の代わりに v3 の down/up 2 カーネル経路を選ぶ実験用スイッチです。v3 は down projection を row group・stream・必要なら列半分に分割し、各部分の値と二乗和を作ってから up カーネルで合成します。計算の加算順が既定経路と異なるため、結果は bitwise 同一とは限りません。

通常の生成経路では Verifier が fused GR を選んだ場合に `fused_gr_read_multi()` を呼びます。関数の API は最大8 tokenをまとめる read で、fused GR 対応形状は `n_embd=2560, hc=4, hc_lr=320` です。環境変数の実処理は CUDA/HIP 実装と SYCL port にあります。CPU の `gr_parity` 実行ファイルにも同名の読み取りがありますが、これは比較テストの許容差を選ぶためのもので、CPU 本番演算を切り替える設定ではありません。

## 値と判定

製品経路では `std::getenv()` の文字列を `std::atoi(v) != 0` で判定します（`v == nullptr` は無効）。文字列全体の厳密な数値 parse ではなく、`atoi` が数値として読める先頭部分を変換します。

| 値 | 判定 |
|---|---|
| 未設定 | 無効（既定の read） |
| 空文字 | 無効（`atoi("") == 0`） |
| `0`、`00`、`0junk`、数値に変換できない文字列 | 無効 |
| `1`、`2`、`-1`、` 1tail` など、`atoi` の結果が0以外 | 有効 |

大文字小文字による解釈や範囲 clamp はありません。CUDA/HIP と SYCL の製品関数では判定結果を関数内の `static const bool` に保存するため、各プロセスで最初に `fused_gr_read_multi()` がこの判定に到達した後の環境変更は反映されません。Q8 専用経路はこの判定より前に実行して戻るため、そこでは本変数を読みません。

## 有効になる条件

値が有効でも、次の条件を満たす場合だけ v3 が実行されます。

- fused GR の multi read 経路に入り、Q8 down/up の専用経路に入らないこと。
- 使用デバイスの共有メモリ条件を満たすこと。
- CUDA/HIP 実装ではデバイス ID が `0..63` の範囲にあること。

CUDA/HIP 実装はデバイスごとに分割方式を一度決め、最大 token 数で必要な共有メモリ（`8 * 2560 * sizeof(float)`、80 KiB）を確保でき、必要な kernel attribute 設定も成功した場合だけ `split=1` を選びます。必要量の半分（40 KiB）以上だが80 KiB経路を使えないカードでは `stderr` に `strata: STRATA_GR_V3=1 needs the two-half split on this card, which fails its checks (#375): the default read is used` と出し、既定経路に戻ります。半分未満、またはデバイス ID が範囲外なら、同じく既定経路ですがこの警告は出しません。コードには `split=2` 用の launch もありますが、現在の CUDA/HIP の選択分岐は `split=2` を設定しません。

SYCL port ではデバイスの local memory size を上限として調べます。値が0以下なら判定上の上限を48 KiBにします。80 KiB以上なら `split=1`、40 KiB以上80 KiB未満なら前述の二分割チェック警告を出して既定経路、それ未満なら警告なしで既定経路です。SYCL port の選択分岐も `split=2` を設定しません。デバイス index が `0..63` 外の場合も v3 を選びません。

したがって有効値を設定しても全 GPU で v3 が実行されるわけではありません。条件に合わない場合は通常の `launch_multi()` 系経路へ進みます。別環境変数 `STRATA_GR_SPLIT` は gfx906 向けの別経路であり、`STRATA_GR_V3` の値判定を置き換えません。

## 実行時の詳細

`src/core/verify.cpp` は fused GR 対応レイヤーの read 用引数を作り、`fused_gr_read_multi()` を呼びます。CUDA/HIP 実装はまず引数を検査し、Q8 専用経路の対象でなければ `STRATA_GR_V3` を判定します。v3 が選ばれると、down カーネルが部分結果と stream ごとの二乗和を scratch に書き、続く up カーネルがそれらを使って残りの read を計算します。CUDA/HIP では launch error があれば `stderr` に `fused_gr_read_multi v3: <CUDA error>` を出して `exit(1)` します。SYCL 実装にも down/up の二つの kernel submission があります。

既定経路と summation order が異なるため、精度上の差はコードコメント上も明記されています。`src/kernels/gr_parity.cpp` と `sycl/src/kernels/gr_parity.cpp` の比較テストは、本変数が有効だと既定経路の中間 workspace `lo` の比較を外し、他の出力を相対許容差 `2e-6` で比較します。このテスト側の読み取りも一度だけ評価されます。

## 文書との照合

`docs/INTEL.md` は B70 上の測定として `STRATA_GR_V3=1` の decode 値が既定 port より4〜6%低かったと記し、同設定を opt-in のままにしています。記載された比較条件（Coder 19 / 2,184-token prompts、IQ2_XS 19）に限る報告であり、他の機種・モデルでの性能を示すものではありません。`docs/DETAILS.md` には本変数の説明は見つかりませんでした。

## 根拠

- `include/strata/kernels/fused_gr.hpp:50-60` — fused GR の対応 API、multi read の token 上限と引数。
- `src/core/verify.cpp:1053-1073` — Verifier が引数を作って multi read を呼ぶ箇所。
- `src/kernels/cuda/fused_gr.cu:456-464,468-520` — CUDA/HIP v3 kernel の方式と共有メモリ要件。
- `src/kernels/cuda/fused_gr.cu:1830-1962` — 値の判定、Q8 経路の先行、デバイス別選択、警告、fallback、kernel launch。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:1607-1669,1718-1735` — SYCL port の判定、local memory 条件、fallback と kernel submission。
- `src/kernels/gr_parity.cpp:340-360`、`sycl/src/kernels/gr_parity.cpp:485-505` — parity 比較専用の同名参照と許容差。
- `docs/INTEL.md:542-544` — B70 の限定された decode 比較と opt-in の記述。
