# `STRATA_GR_UNFUSED`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

prefill の hyper-connection（HC）読み取りで、正規化した各行の FP32 値を別バッファに保存して使う経路を選びます。未設定または無効値では、正規化の行スケールと低精度画像を保存し、mix 側で `R * rs * norm_weight` を再計算します。有効値では `xn` に FP32 の正規化行を保存し、`gr_mix` がそれを読みます。CUDA/HIP 共通実装と SYCL 実装の双方にあります。ソースコメントはこの分岐を F-1 の A/B arm と呼びますが、通常利用者向けの CLI 引数や設定ではなく、prefill 内の環境変数フックです。`engine/src/prefill/prefill.cpp:1055-1059, 5102-5106, 5159-5164`、`engine/sycl/src/prefill/prefill.cpp:416-420, 3439-3442, 3502-3509`。

有効時、通常は再利用する次半分の正規化や層間融合を使わず、HC の書き戻し後に次の正規化を別に行う経路になります。FP32 の一時領域も追加で必要です。一方、変数が直接切り替えるのは prefill の内部計算経路です。生成・選択結果が同一になることをこの調査で実行確認したわけではありません。通常経路の再計算式と保存経路の値の式は、カーネル上ではどちらも `R * rs * w` の順です（`engine/src/prefill/kernels.cu:121-137, 139-158, 160-179, 344-364`）。

## 値と判定

両実装とも関数内 `static const bool` の初期化で `std::getenv` を一度呼び、値が存在し、かつ先頭文字が ASCII の `'1'` の場合だけ有効にします。文字列全体の parse、数値変換、空白除去、大文字小文字変換はしません。`engine/src/prefill/prefill.cpp:1056-1059`、`engine/sycl/src/prefill/prefill.cpp:417-420`。

| 条件（build / backend） | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| CUDA/HIP 共通 prefill 実装 | 無効（既定） | `1`, `10`, `1anything` | 空文字、`0`, `0anything`, `true`, `TRUE`, ` 1`, `-1` |
| SYCL prefill 実装 | 無効（既定） | `1`, `10`, `1anything` | 空文字、`0`, `0anything`, `true`, `TRUE`, ` 1`, `-1` |

未設定と空文字はいずれも無効です。`1` で始まる任意の文字列は残りを検証せず有効、その他は無効です。境界値としての数値範囲はなく、数値としての妥当性も検証しません。無効値に対する警告やエラー処理はありません（上記の判定箇所）。

## 有効になる条件

- Strata が CUDA/HIP または SYCL の prefill 実装を実行すること。変数の直接参照は `engine/src/prefill/prefill.cpp` と `engine/sycl/src/prefill/prefill.cpp` に限られます。decode の環境変数として読む実装は見つかりません。
- HC の read/mix 処理に到達すること。フラグは `Prefill` のバッファ carve と各 prefill 経路で参照されます（CUDA/HIP: `engine/src/prefill/prefill.cpp:2760-2769, 5102-5106, 5159-5164, 9303-9312`; SYCL: `engine/sycl/src/prefill/prefill.cpp:1662-1668, 3439-3442, 3502-3509`）。
- 別の環境変数との併用が必須という条件はありません。ただし `STRATA_PF_HC_REGION=1` が要求する HC scratch の共有領域利用は `!gr_unfused()` で抑止されます（CUDA/HIP `engine/src/prefill/prefill.cpp:2246-2254`）。`STRATA_HC_UPMIX` の upmix 分岐も `!gr_unfused()` を条件に含み、`STRATA_CVEC_FUSE` による control-vector 融合と次段への norm 融合も同様に抑止されます（CUDA/HIP `engine/src/prefill/prefill.cpp:5127-5130, 7662-7669`; SYCL `engine/sycl/src/prefill/prefill.cpp:3461-3463, 5392-5399`）。
- `STRATA_HC_REQ8` など別の重み・GEMM経路を使う場合も、同じ正規化・mix の分岐で `gr_unfused()` が判定されます（CUDA/HIP `engine/src/prefill/prefill.cpp:5091-5106, 9300-9312`）。

## 実行時の詳細

最初に `gr_unfused()` が呼ばれた時点で環境を読み、C++ の関数内 `static` に結果をキャッシュします。たとえば `carve` が `xn` を確保する条件として先に呼ぶ場合があります。以後の prefill 処理で再読込しないため、実行中に環境値を変更してもこのプロセス内の判定には反映されません（CUDA/HIP `engine/src/prefill/prefill.cpp:1056-1059, 2760-2769`; SYCL `engine/sycl/src/prefill/prefill.cpp:417-420, 1662-1668`）。別プロセスの起動や子プロセスへの転送をこのコードは行いません。

有効時の HC 読み取りでは `gr_norm` が `R` の各行を RMS 正規化し、`xn` に FP32 値を書きつつ、GEMM 用の低精度 `xn16`（必要な場合は低位部分も）を作ります。その後の down / inject 投影と gate/up 投影を経て、`gr_mix` が `xn` と gated 値から `mixed` を作ります。無効時は `gr_norm_rs` が行スケール `rs` と低精度 `xn16` を作り、`gr_mix_r` が `R`, `rs`, norm weight から同じ形の FP32 正規化値をその場で再計算して `mixed` を作ります（CUDA/HIP `engine/src/prefill/kernels.cu:121-179, 344-364`; 呼び分け `engine/src/prefill/prefill.cpp:5102-5106, 5155-5164, 9303-9312`; SYCL `engine/sycl/src/prefill/prefill.cpp:3439-3442, 3502-3509`）。

有効時は `carve` が `T * D` 個の FP32 を `xn` 用に確保します。`bytes_needed_impl` の ring-byte 計上経路も `gr_unfused()` が真なら同サイズを計上します（CUDA/HIP `engine/src/prefill/prefill.cpp:2766-2769, 3718-3738`; SYCL `engine/sycl/src/prefill/prefill.cpp:2451-2455`）。バッファを確保できない場合は通常の chunk 初期化失敗経路に入り、`prefill: device buffers for a chunk of ... tokens do not fit (...)` を `err` に設定して失敗を返します（CUDA/HIP `engine/src/prefill/prefill.cpp:2738-2746`）。

同フラグは HC 書き戻しを次半分の正規化と融合する判定も無効にします。CUDA/HIP では `fuse` が偽になり、後段の書き戻しは `gr_write_norm_rs` でなく `gr_write` になります（`engine/src/prefill/prefill.cpp:7662-7669, 9500-9512`）。SYCL でも同じ条件で `fuse` / `fuse_next` を止め、次層の norm 融合を避けます（`engine/sycl/src/prefill/prefill.cpp:4161-4168, 5392-5403`）。

## ログと測定値

この変数自体を理由に出す有効・無効ログ、警告、終了メッセージはありません。値が `1` 以外であることを報告するエラー経路もありません（読み取り箇所: `engine/src/prefill/prefill.cpp:1056-1059`; `engine/sycl/src/prefill/prefill.cpp:417-420`）。chunk のデバイスバッファ不足時は上記の一般的な prefill エラーが返ります。資料 `docs/DETAILS.md` にこの変数の動作や測定値に関する記述は見つかりませんでした。

## 根拠

- `engine/src/prefill/prefill.cpp:1055-1059` — CUDA/HIP 実装の値判定。
- `engine/src/prefill/prefill.cpp:2246-2254, 2760-2769, 3718-3738` — HC region の抑止、FP32 buffer の確保と sizing。
- `engine/src/prefill/prefill.cpp:5102-5106, 5127-5130, 5155-5164, 7662-7669, 9303-9312, 9500-9512` — HC 計算、upmix / 融合の分岐。
- `engine/src/prefill/kernels.cu:121-179, 344-364` — 正規化保存・再計算のカーネル。
- `engine/sycl/src/prefill/prefill.cpp:416-420, 1662-1668, 2451-2455, 3439-3442, 3461-3463, 3502-3509, 4161-4168, 5392-5403` — SYCL 実装と分岐。
