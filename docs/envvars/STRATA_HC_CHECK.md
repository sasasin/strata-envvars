# `STRATA_HC_CHECK`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

SYCL backend の verifier 初期化時に、hyper-connection multi read の split/staged 実装を plain read と比較する自己検査を有効にする opt-in フラグ。値の内容ではなく `getenv` が null かどうかだけで判定する。CUDA/HIP 共通実装にはこの名前の読み取りがない。SYCL の検査は結果を `g_variant` に保存して選択内容をログに出すが、現行ソースでは `fused_gr_variant()` の呼び出し元がなく、通常の SYCL read 経路もこの結果を参照しない。そのため、通常の生成 read の実装を切り替える設定とは確認できない。`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:2124-2125,3794-3842`、`engine/sycl/src/core/verify.cpp:624-638`。

## 値と判定

| 条件 | unset | 設定ありの例 | 判定 |
|---|---|---|---|
| SYCL の `fused_gr_check()` が未検査デバイスで呼ばれる | plain を保存して return。自己検査・ログなし | 空文字、`0`、`1`、`true`、`0anything` を含め、環境値が存在すれば検査を続行 | 文字列比較・数値変換・大文字小文字判定はない。`std::getenv(...) == nullptr` の有無だけで判定する。`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3804-3819` |

この変数自身に既定値や無効値の fallback はない。未設定時は検査を省略して plain を選ぶ。設定済みの場合に検査する候補は別変数 `STRATA_HC_SPLIT` で決まり、未設定・空文字・`2`・その他の文字列は staged、先頭文字が `1` なら split、先頭文字が `0` なら plain となる。`STRATA_HC_SPLIT` は先頭文字だけを見ており、たとえば `1x` は split、`0anything` は plain。`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:2115-2121,3814-3827`。

## 有効になる条件

- このコードは SYCL backend の `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp` にある。通常の CUDA/HIP 実装 `engine/src/kernels/cuda/fused_gr.cu` に `STRATA_HC_CHECK` の読取はなく、同名設定による検査 opt-in は確認できない。`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3804-3813`、`engine/src/kernels/cuda/fused_gr.cu:4732-4812`。
- SYCL の `Verifier::init()` が呼ばれ、その時点で現在デバイスの検査が未完了であること。デバイス ID が 0..63 の範囲外、または `g_variant[dev] > 0` の場合は、環境変数を読む前に return する。`engine/sycl/src/core/verify.cpp:624-638`、`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3804-3813`。
- 検査を実際に起動するには `STRATA_HC_CHECK` が設定済みで、かつ `STRATA_HC_SPLIT` が plain を指定しないことが必要。`STRATA_HC_SPLIT` が先頭 `0` の場合、検査をせず plain を保存して戻る。未設定なら `STRATA_HC_CHECK` の有無にかかわらず plain を使う。`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:2115-2121,3810-3827`。
- CLI 引数、モデルの値、または別設定で `STRATA_HC_CHECK` を上書きする処理は見つからない。検査開始後の GPU メモリ確保・kernel 実行が失敗すれば、選択結果が plain へ fallback する場合がある。`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3576-3604,3760-3789,3821-3834`。

## 実行時の詳細

`Verifier::init()` は現在デバイスを設定した後 `fused_gr_check()` を呼ぶ。検査はデバイスごとに `g_variant[64]` へ結果を保持し、すでに正の値があるデバイスでは以降の呼び出しをスキップする。未設定時は plain を保存するため、そのプロセス内で後から環境を変えても再評価されない。`engine/sycl/src/core/verify.cpp:633-638`、`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:2124-2125,3804-3813`。

opt-in された検査は seed `20260930` の疑似乱数による重み・入力を用い、token 数 1..8 と pending write の有無について plain と split/staged の `lo`、`rs`、inject、mixed、`R` の出力をビット単位で比較する。single-token read と plain も比較対象に含む。`STRATA_HC_SPLIT` が staged を許可すれば staged を優先し、通らなければ split、split も通らなければ plain を保存する。上限が split の場合は split を優先し、失敗時は plain にする。`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3572-3590,3683-3726,3730-3784,3821-3827`。

検査結果は `g_variant` に格納され、`fused_gr_variant()` は保存値を返す関数として定義されている。ただしソース全体で呼び出し元は見つからず、通常の `fused_gr_read_multi()` は別の SYCL read 実装を直接実行する。このため `STRATA_HC_CHECK` による検査・ログの発生は確認できるが、それが通常の生成で使う read variant を変更するとは言えない。`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3139-3169,3794-3802`。

## ログと測定値

- `STRATA_HC_CHECK` 未設定なら `g_variant` に plain を保存して無言で return する。`STRATA_HC_SPLIT` が plain 指定の場合は `strata hc: CUDA%d: the hyper-connection read runs as the plain one (STRATA_HC_SPLIT=0)` を stderr に出す。`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3810-3819`。
- 検査を起動できなかったときは `strata hc: CUDA%d: the check of split/staged could not run (%s)`、候補が不一致なら `strata hc: CUDA%d: the %s read differs from the plain read on this card - not used: %s`、選択後には `strata hc: CUDA%d: the hyper-connection read runs as %s%s` を stderr に出す。ここで `CUDA%d` は SYCL ソースに記述されたログ文字列である。`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3828-3841`。
- 自己検査中に `sycl::exception` が送出される経路では `exc.what()` とファイル・行番号を stderr に出し `exit(1)` する。`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3786-3789`。
- 性能測定値はこの変数の説明資料・対象ソースから確認できないため記載しない。

## 根拠

- `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:2115-2125` — `STRATA_HC_SPLIT` の値規則とデバイス別の選択状態。
- `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3572-3789` — SYCL 自己検査の対象、比較、失敗理由と exception 終了経路。
- `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3794-3842` — 選択状態、`STRATA_HC_CHECK` の有無判定、fallback とログ。
- `engine/sycl/src/core/verify.cpp:624-638` — verifier 初期化からの呼び出し。
- `engine/src/kernels/cuda/fused_gr.cu:4732-4812` — CUDA/HIP 実装の確認範囲。同ファイルに `STRATA_HC_CHECK` の読取はない。
