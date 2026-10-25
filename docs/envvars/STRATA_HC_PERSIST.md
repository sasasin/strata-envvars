# `STRATA_HC_PERSIST`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

HIP ビルドで verifier の hyper-connection read を、通常の複数 kernel による read から 80-block persistent kernel に切り替えます。kernel は列方向に分割した down projection と up projection を一つの launch 内で処理し、途中に二つの grid barrier を置きます。加算順は通常経路と異なるため結果は bitwise 一致しません。

この経路を試すのは verifier の read だけです。drafter の read は対象外です。`Verifier::init()` が各 GPU で初期化検査を呼び、検査を通った場合に限って後続の read で利用します（`src/core/verify.cpp:634-647,1228-1249`、`src/kernels/cuda/fused_gr.cu:2591-2599`）。

## 値と判定

環境変数の文字列全体は検証せず、C の `atoi()` で整数に変換します。空文字、数字で始まらない文字列は `0` 相当です。先頭の空白や符号の後の数字は変換され、数値以降の文字は無視されます。

| 値 | 判定 |
|---|---|
| 未設定、空文字、`0`、数字で始まらない値 | 無効 |
| `atoi()` の結果が 0 以外（例: `1`, `-1`, `2`, `3`, `1abc`） | 有効化を試みる |
| `atoi()` の結果がちょうど 3（例: `3`, `3abc`） | 有効化を試み、persistent kernel 内の部分和と二乗和を double で蓄積する参照モード |

有効判定と double 参照モード判定は別々の `static const` 値として初回評価時にキャッシュされます。したがって実行中に環境を変更しても再評価されません。`-3` のような負の非ゼロ値も機能を有効化しますが、double 参照モードにはなりません（`src/kernels/cuda/fused_gr.cu:2856-2873`）。

## 有効になる条件

値が有効でも、以下の条件を満たさない GPU や read は通常経路に戻ります。

- HIP コンパイル時だけ persistent 実装が存在します。非 HIP ビルドでは初期化関数は何もせず、read 関数は常に「未実行」を返します（`src/kernels/cuda/fused_gr.cu:2599,3029-3031`）。
- GPU ordinal が 0..63 の範囲で、warp size が 32 であることが必要です。
- gfx11 / gfx12 は barrier timeout に使う `s_memrealtime` がないため初期化時に無効化されます。
- 起動時検査で、その GPU 上に 80 block が常駐でき、1..8 token の各サイズについて結果が通常 read と許容範囲内で一致する必要があります。利用可能な最大 token 数はこの検査で決まります。timeout や結果不一致より大きい token 数では default の read を使います。
- read の `q8_down` または `q8_up` が非 null（`STRATA_HC_Q8` 経路）、あるいは対象 token のいずれかの `q8_mixed` が非 null（`STRATA_QFUSE` 経路）の場合は persistent read を使いません。

初期化では `cudaMalloc` による workspace 確保も必要です。warp size、gfx 世代、確保、数値検査、常駐検査で使えない場合は stderr に `strata hc: CUDA%d: STRATA_HC_PERSIST=1 is off here: ...` を出します。利用可能な場合は、GPU ごとに最大 token 数、timeout 数、default read との最大相対差を含む `strata hc: CUDA%d: STRATA_HC_PERSIST=1: ...` 行を出します（`src/kernels/cuda/fused_gr.cu:2877-3013`）。

## 実行時の詳細

初期化は `Verifier::init()` から呼ばれ、GPU ordinal ごとの `tried` フラグで一度だけ行われます。検査では決定的な乱数 seed で作った入力と BF16 重みを使い、各 token 数について通常 read と persistent read の出力を比較します。出力が有限で、最大相対差が `1e-4` 未満であることを要求します。検査時の barrier timeout は「その token 数では 80 block が同時常駐できない」として扱い、それより大きい token 数も有効にしません（`src/kernels/cuda/fused_gr.cu:2908-2912,2913-3013`）。

実行時の barrier は `s_memrealtime` を使い、待機が 2 秒を超えると abort flag を立てます。persistent read の起動関数は launch 後に実行済みとして caller に返るため、実行時 timeout が起きても通常 read へ戻る動作ではありません。kernel は未完成の出力を残し、abort flag がクリアされないままなら後続の persistent read も barrier で即時 abort します。通常の正常動作では発生しないとされる状態ですが、opt-in を測定用途に留める制約として既存の `docs/AMD_HIP.md` も記載しています（`src/kernels/cuda/fused_gr.cu:2618-2657,3016-3027`、`docs/AMD_HIP.md:547-549`）。

## 根拠

- 値の読み取り、static cache、整数 `3` の double モード: `src/kernels/cuda/fused_gr.cu:2856-2873`
- HIP 限定実装と非 HIP stub: `src/kernels/cuda/fused_gr.cu:2599,3029-3031`
- GPU ごとの初期化、適用条件、診断ログ、検査: `src/kernels/cuda/fused_gr.cu:2877-3014`
- persistent read の fallback 条件: `src/kernels/cuda/fused_gr.cu:3016-3027`
- verifier からの呼び出しと通常経路への fallback: `src/core/verify.cpp:634-647,1228-1249`
- 同梱資料の説明とgfx1030での測定条件: `docs/AMD_HIP.md:539-549`。資料では2枚のRX 6900 XT、ROCm 10.0、layer split の測定を報告しています。これは当該構成での値であり、他のRDNAカードの性能を示すものではありません。
