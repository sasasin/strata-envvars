# `STRATA_LFUSE`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

verify window 内の共有 expert（shared expert）について、ゲート計算を router の行列積へ載せ、対応する場合は gate/up の重み行列積を一つの native MMVQ launch にまとめます。前者では共有 expert の出力への sigmoid・スケールを後段の MoE combine に移します。通常の shared expert 呼び出しや combine 自体を有効化するスイッチではなく、条件を満たす経路の融合を許可するスイッチです。

この環境変数は CUDA/HIP 側の `src/core/verify.cpp` と SYCL 側の `sycl/src/core/verify.cpp` で読まれます。読み取り結果は関数内の `static const bool` に保存されるため、各プロセスで最初に判定した後の環境変更は反映されません。

## 値と判定

値全体や数値としての妥当性は検査せず、`getenv()` が返す文字列の先頭文字だけを `'1'` と比較します。

| 環境値 | `g_lfuse()` |
|---|---:|
| 未設定 | OFF |
| 空文字 | OFF |
| 先頭文字が `1`（例: `1`, `10`, `1anything`） | ON |
| その他（例: `0`, `true`, ` 1`, `01`） | OFF |

大文字小文字・空白の除去、整数変換、無効値の警告や fallback はありません。根拠: `src/core/verify.cpp:70`, `sycl/src/core/verify.cpp:71`。

## 有効になる条件

`STRATA_LFUSE` が ON でも、`lfuse_on(n)` が真になるのは次の条件をすべて満たす verify group だけです。

- その group の層が all-resident 経路である（全 expert が VRAM resident で、`ar_off_` ではない）。
- native MoE combine が有効。
- `STRATA_DEC_BATCH` が有効。これは unset なら有効、設定時は `atoi(value) != 0` で判定される。
- group の行数 `n` が 2〜8。
- shared expert の native BF16 経路が有効（CLI 設定 `--native-bf16-extra` によって設定される）。

条件式は CUDA/HIP と SYCL で同じです（`src/core/verify.cpp:845,851-855`, `sycl/src/core/verify.cpp:825,836-840`）。all-resident は Verifier が持つ全 resident 状態と `ar_off_` で定義されます（`include/strata/core/verify.hpp:389-395`）。native MoE combine と native BF16 shared expert は CLI 解釈後にそれぞれ有効状態が設定され、初期値はどちらも false です（`src/program/generate.cpp:350-352,1864-1866,3050-3052`）。

## 実行時の詳細

ゲート融合は、`lfuse_on(n)` と補助スイッチ `STRATA_LFUSE_GATE` が有効な場合に router の重みと shared expert gate の重みを同じ multi-row BF16 GEMV に渡します。`STRATA_LFUSE_GATE` は unset なら ON、設定されていれば先頭文字が `0` の場合だけ OFF です。router の形状・native router 状態などが対応しない場合や fused GEMV が成功しない場合、router は通常の GEMV に戻り、ゲートは shared expert 側で計算されます（CUDA/HIP: `src/core/verify.cpp:1431-1448`; SYCL: `sycl/src/core/verify.cpp:1302-1319`）。

ゲート/up のペア融合は、`lfuse_on(n)` と `STRATA_LFUSE_PAIR` が有効な場合に `shared_expert_multi()` へペア融合 bit を渡します。補助スイッチは unset なら ON、先頭文字が `0` のとき OFF です。カーネル側では両重みの native type が一致し、`native_mmvq_pair()` が成功したときだけ一 launch にし、それ以外は gate と up の個別 `native_mmvq()` 呼び出しへ戻ります（`src/core/verify.cpp:1531-1536`, `src/kernels/cuda/shared_expert.cu:214-232`; SYCL: `sycl/src/core/verify.cpp:1390-1395`, `sycl/src/kernels/cuda/shared_expert.dp.cpp:315-336`）。

ゲートを router 側で計算できた group は、`shared_expert_multi()` がそのゲートによるスケールを省略し、後段の gated MoE combine が sigmoid と乗算を行います。router 側でゲートを用意できなければ通常の shared expert combine を使います（CUDA/HIP: `src/kernels/cuda/shared_expert.cu:241-264`, `src/core/verify.cpp:1652-1671`; SYCL: `sycl/src/kernels/cuda/shared_expert.dp.cpp`, `sycl/src/core/verify.cpp:1502-1515`）。

## 既定値と適用範囲

HIP エンジンは起動時に GPU 0 のアーキテクチャを調べます。gfx1151 では `STRATA_GFX1151_DEFAULTS` が unset、または先頭文字が `0` 以外なら、`STRATA_LFUSE=1` を含む既定スイッチ群を、各変数が未設定のときだけ設定します。`STRATA_GFX1151_DEFAULTS` の先頭文字が `0` なら群全体を設定しません。`STRATA_LFUSE` に空文字を含む何らかの値を既に設定している場合も、その値が保たれます。適用したスイッチ名は stderr にまとめて表示されます（`src/program/generate.cpp:2152-2158`, `src/core/arch_defaults.cpp:32-58,61-79`）。

この自動既定値は gfx1151 以外の AMD GPU と CUDA には適用されません。gfx12 の既定値テーブルにも `STRATA_LFUSE` は含まれません（`src/core/arch_defaults.cpp:14-30`）。SYCL の verify 実装にも環境変数による分岐はありますが、上記 HIP 起動時の arch-default 設定経路はありません。

`STRATA_LFUSE` 自体が KV append を切り替える実装箇所は確認できませんでした。Q8 KV の複数行 append は `STRATA_DEC_BATCH`、`STRATA_NO_BATCH_KV_STEP`、batch-recording などで選択されます（`src/core/verify.cpp:1263-1309`; SYCL は `sycl/src/core/verify.cpp:1128-1157`）。したがって `docs/STRIX_HALO.md` の「shared expert and the KV append」という表現のうち、KV append の起動削減をこの変数の直接効果とは扱いません。

## 文書との照合・ログ

`docs/STRIX_HALO.md:83-98` は gfx1151 で `STRATA_LFUSE` を既定有効にすること、および共有 expert / KV append 周辺の launch を減らすことをまとめています。実装では、gfx1151 の既定設定と shared expert の融合分岐を確認できました。一方、KV append の複数行化は別の分岐にあるため、上記のとおり分けて記述しました。同資料には gfx1151 の設定群について保守側の機材で出力が byte-identical とありますが、この調査ではその計測や再現性を検証していません。

`docs/INTEL.md:830-833` は Arc Pro B70 で `STRATA_LFUSE` を試したものの採用しなかったと記載しています。これは SYCL の同資料上の判断として参照し、性能値や他機材への一般化はしていません。環境変数による専用ログや警告はありません。gfx1151 で arch defaults が実際に値を設定した場合に限り、起動時の共通スイッチ一覧に `LFUSE` が現れます。
