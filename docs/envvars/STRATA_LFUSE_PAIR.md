# `STRATA_LFUSE_PAIR`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。

## 役割

常駐 expert を使う verifier の shared expert 計算で、gate 行列と up 行列の積を一つの multi-matrix kernel launch にまとめる経路を許可します。単独では有効化されず、`STRATA_LFUSE` が有効で、verifier の resident 条件なども満たしたときだけ参照されます。CUDA/HIP 実装と SYCL 実装の両方に同じ制御があります。

## 値と判定

値全体を parse せず、環境変数の先頭文字だけを見ます。値が未設定なら有効、設定値の先頭文字が `0` なら無効、それ以外なら有効です。空文字も設定済みで先頭文字が `\0` のため有効です。たとえば `0`, `0abc` は無効、`1`, `true`, `false`, `2`, 空文字は有効です。空白や大文字小文字、数値としての妥当性は検査しません。

判定結果は関数内の `static const bool` に保存されます。最初にこの判定へ到達した後でプロセス環境を変更しても反映されません。コード上、判定関数が呼ばれるのは `lfuse_on(n)` が真のときに限られるため、実際の初回評価は対象となる verifier window 内です。

## 有効になる条件

`STRATA_LFUSE_PAIR` が有効でも、次の条件をすべて満たす場合にだけ pair launch が試されます。

- verifier の `ar_on()` が真、すなわち対象 stage の全 expert が VRAM resident で、resident-only 経路が停止されていない。
- `STRATA_LFUSE` が先頭文字 `1` で有効。
- native MoE combine が有効で、`STRATA_DEC_BATCH` が未設定または `atoi` の結果が 0 以外。
- verifier の window 行数 `n` が 2〜8。
- shared expert の native BF16 backend が有効。

さらに kernel 側の `native_mmvq_pair()` が対象を Q8_0（ggml type 8）、2〜8列、正の行列寸法、32要素境界の入力、未 packed の重みなどに限定しています。これらの条件を満たさない場合、同関数は `false` を返し、呼び出し元が gate と up の `native_mmvq()` を別々に実行します。従って環境変数が有効でも、全モデル形式・量子化で pair launch が使われるわけではありません。

## 実行時の詳細

CUDA/HIP と SYCL の `Verifier::record_window()` は `lfuse_on(n) && g_lfuse_pair()` の結果を `shared_expert_multi()` に bit 1 として渡します。`shared_expert_multi()` はその bit を `pair` として解釈し、両重みの型が等しい場合に `native_mmvq_pair()` を試します。pair kernel は一つの launch 内で gate と up の各出力行を計算します。対応条件を満たさなければ二つの `native_mmvq()` 呼び出しにフォールバックします。

この変数が無効でも shared expert 自体は引き続き計算され、gate/up の積が個別 launch になります。pair 経路の失敗は通常 fallback で処理され、環境変数専用のログはありません。pair kernel の起動後に backend エラーが発生した場合は、shared expert のエラーとして verifier のエラー文字列に伝播します。

この変数を読む本番実装は verifier と shared expert の CUDA/HIP/SYCL ソースです。通常の単一 token 経路や、resident 条件を満たさない経路にはこのスイッチの分岐はありません。`docs/DETAILS.md` に `STRATA_LFUSE_PAIR` 固有の説明や性能測定値は見つからなかったため、効果量は記載しません。

## 根拠

- `src/core/verify.cpp:133-134` — 値判定と static cache。
- `sycl/src/core/verify.cpp:71-73` — SYCL 側にも同じ判定。
- `include/strata/core/verify.hpp:389-395` — `ar_on()` は all-resident かつ `!ar_off_`。
- `src/core/verify.cpp:845,851-855,1531-1535` — batch 条件、pair 適用条件、shared expert へのフラグ伝達。
- `sycl/src/core/verify.cpp:825,836-840,1391-1395` — SYCL 側の同等条件とフラグ伝達。
- `src/kernels/cuda/shared_expert.cu:214-232` — bit の解釈、pair 試行、二つの積への fallback。
- `sycl/src/kernels/cuda/shared_expert.dp.cpp:313-330` — SYCL 側の同等処理。
- `src/kernels/cuda/native_mmvq.cu:2417-2441` — CUDA/HIP pair kernel の対象条件と dispatch。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:3602-3625` — SYCL 側の同等条件と dispatch。
