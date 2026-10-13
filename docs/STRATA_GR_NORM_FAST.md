# `STRATA_GR_NORM_FAST`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

HIP backend の fused hyper-connection multi-token read で、ストリーム単位に分割した正規化 (`gr_norm_split_kernel`) を、レジスタ上で複数の float4 をまとめて読み書きする `gr_norm_split_fast_kernel` に切り替えます。どちらも `R` と `w_norm` から正規化済み `xn` および逆 RMS 値 `rs` を作ります。この変数が選ぶのはこの正規化カーネルだけで、down/up 射影の選択は別の処理です。

## 値と判定

HIP build では `std::atoi` の結果が 0 以外なら ON、0 なら OFF です。文字列全体の検証はなく、`atoi` が認識する先頭の数値部分で判定します。空文字や数値で始まらない文字列は 0 として扱われます。

| 環境変数 | HIP での結果 |
|---|---|
| 未設定 | GPU 世代ごとの既定値に従う |
| `0`、空文字、数値に変換できない値 | OFF |
| `1`、`-1`、`2` など `atoi` の結果が 0 以外 | ON |

明示値の判定結果は関数内の `static const int` に保存されるため、プロセス内で最初に判定された後に環境を書き換えても反映されません。未設定時は GPU 番号ごとの判定をキャッシュします。`cudaGetDevice` または `cudaGetDeviceProperties` に失敗した場合、またはデバイス番号が 0〜63 の範囲外の場合は OFF です。

CUDA build ではこの変数を読み取らず、常に OFF を返します。

## 有効になる条件

- HIP backend であること。CUDA backend は常に OFF です。
- 対象の hyper-connection read が fused multi-token 経路で実行されること。単一 token 用の `fused_gr_read` はこの判定を通りません。
- multi-token read が `kHcSplit` または `kHcStaged` variant を選ぶこと。variant が plain の場合は `norm_fast_on()` を呼びません。variant は `STRATA_HC_SPLIT` と `fused_gr_check()` のカードごとの検証結果で決まり、別の条件です。
- Q8 projection 経路、利用可能な `STRATA_GR_V3` 経路、または gfx906 で `STRATA_GR_SPLIT=1` の専用経路が先に選ばれた場合は、通常の `launch_multi` に到達せず、この変数の正規化切り替えは使われません。

未設定時の既定は HIP GPU のアーキテクチャ名が `gfx1200` または `gfx1201` なら ON、それ以外は OFF です。明示値を設定するとこの既定判定を置き換えるため、gfx12 以外でも ON を強制できます。コードにはその強制値が対象 GPU で動作可能かを事前に検査する分岐はありません。

## 実行時の詳細

`Verifier::init()` は初期化時に `fused_gr_check()` を呼び、GPU ごとに hyper-connection multi-token variant を確認します。実際に `fused_gr_read_multi()` が Q8、v3、gfx906 専用経路を選ばず `launch_multi()` に進み、variant が split/staged であると、`norm_fast_on()` の結果に応じて fast または標準の split norm kernel を起動します。

fast kernel はスレッドごとに最大3個の float4 を先にロードし、レジスタ内で和と重みとの積を計算してから、標準 kernel と同じ stream ごとの warp reduction、warp 部分和の集計、`rsqrtf` を行います。コードコメントでは標準 kernel と同じ演算順・結果を保ち、グローバルメモリへの一時書き込み後の再読み込みを省く設計と説明されています。ここではソース上の実装意図を記し、独立した性能やビット一致の測定結果は主張しません。

この環境変数に固有の有効化ログや警告はありません。kernel 起動後の CUDA/HIP エラーは通常の `fused_gr_read_multi` エラーハンドリングに渡り、エラー文字列を stderr に出して終了します。

## 根拠

- `src/kernels/cuda/fused_gr.cu:1006-1022` — 環境値の変換、HIP/CUDA 分岐、gfx12 の既定判定とキャッシュ。
- `include/strata/kernels/gfx_arch.hpp:36` — gfx12 判定が `gfx1200` / `gfx1201` に限られること。
- `src/kernels/cuda/fused_gr.cu:661-755` — 標準 split norm と fast split norm の処理。
- `src/kernels/cuda/fused_gr.cu:1030-1046,1121-1128` — split/staged variant の場合に norm kernel を選び、`STRATA_HC_SPLIT` から variant 要求を読むこと。
- `src/kernels/cuda/fused_gr.cu:1830-1962` — Q8、v3、gfx906 専用経路および通常 multi-token 経路の選択。
- `src/kernels/cuda/fused_gr.cu:2127-2169` — GPU ごとの variant 検証と選択。
- `src/core/verify.cpp:540-552` — verifier 初期化時の `fused_gr_check()` 呼び出し。

`docs/DETAILS.md` と `docs/AMD_HIP.md` はこの変数名を直接説明していません。挙動の根拠は実装コードです。
