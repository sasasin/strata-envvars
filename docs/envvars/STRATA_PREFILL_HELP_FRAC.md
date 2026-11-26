# `STRATA_PREFILL_HELP_FRAC`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

layer split の単一 chunk prefill で、次段の idle GPU に渡して計算させる pinned expert の割合を指定する。値を設定すると chunk token 数に応じた既定割合を置き換える。環境変数だけでは機能は有効にならず、別の `STRATA_PREFILL_HELP` と MMQ 等の条件も必要。CUDA と SYCL の `Prefill::bind_stage_helper()` から使用される（`engine/src/prefill/prefill.cpp:3173-3195,3212-3219,3258-3267`、`engine/sycl/src/prefill/prefill.cpp:2060-2082,2085-2090,2158-2167`）。

## 値と判定

両 backend とも `std::getenv` の結果を `std::atof` に渡し、`std::clamp(..., 0.0, 1.0)` で範囲を制限する。未設定時だけ `-1.0` を sentinel にして、chunk 長 `T` から割合を計算する。空文字や数値に変換できない文字列は `atof` により 0 となり、範囲内の固定値として扱われる。数値文字列の後続部分は検査されず、`atof` が認識する数値接頭部が使われる（例: `0.2tail` は 0.2、`1tail` は 1）。`atof` は変換エラーを個別に報告しない（`engine/src/prefill/prefill.cpp:3187-3194`、`engine/sycl/src/prefill/prefill.cpp:2074-2081`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値・扱い |
|---|---|---|---|
| CUDA / SYCL 共通 | `f = min(0.45, 0.5 - T / 16384)`。`f >= 0.3` のとき `f`、それ未満は 0 | `atof` 結果を `[0,1]` に clamp した割合。例: `0.2` は 0.2、`1` や `2` は 1 | `0`、負値は clamp 後 0 で分担なし。空文字、`true`、`garbage` も `atof` 結果 0。`-0.1` は 0、`1.2` は 1。大文字小文字による文字列比較はない |

`atof` の結果が NaN の場合は比較で固定値として採用されず、unset と同じ `T` ベースの計算へ進む。無限大は clamp により 1 または 0 になる。`T` は `bind_stage_helper(T)` に渡された prompt chunk の token 数である（`engine/src/prefill/prefill.cpp:3187-3194,3258-3262`、`engine/sycl/src/prefill/prefill.cpp:2074-2081,2158-2162`）。

## 有効になる条件

- `STRATA_PREFILL_HELP` が設定され、`atoi` の結果が 0 以外であること。未設定、空文字、`0`、数字で始まらない値は opt-in にならない。この別変数も関数内 `static` に保存される（`engine/src/prefill/prefill.cpp:3176-3178,3212-3219`、`engine/sycl/src/prefill/prefill.cpp:2063-2065,2085-2090`）。
- 複数 GPU の layer split があり、各段に次段を helper として設定すること。呼び出し側は `multi_gpu && !stages.empty()` のとき各段で `set_stage_helper()` を呼ぶ（CUDA: `engine/src/program/generate.cpp:13155-13169`、SYCL: `engine/sycl/src/program/generate.cpp:7615-7627`）。
- CUDA では `STRATA_PF_OWN_ONLY` build の場合、この helper 経路は `set_stage_helper()` 内で直ちに無効化される（`engine/src/prefill/prefill.cpp:3217-3220`）。
- 対象段と helper 段が異なる有効 device 上にあり、MMQ plan があること（CUDA: `engine/src/prefill/prefill.cpp:3216-3219`、SYCL: `engine/sycl/src/prefill/prefill.cpp:2088-2090`）。
- prompt が単一 chunk であること。さらに `T >= stream_all_min()`、expert source があり、ring が `STAGE` より大きく、`fused_ring()` でないこと（CUDA: `engine/src/prefill/prefill.cpp:3258-3267,4295-4304`、SYCL: `engine/sycl/src/prefill/prefill.cpp:2158-2167,2744-2749`）。
- 対象段の全 layer が MMQ 対応であること。native pack の layer で fused native kernel が対応する場合はこの helper 分岐を使わない（CUDA: `engine/src/prefill/prefill.cpp:3263-3267`、SYCL: `engine/sycl/src/prefill/prefill.cpp:2163-2167`）。helper 段にも chunk 用の MMQ buffer、source、ring 等が必要（CUDA: `engine/src/prefill/prefill.cpp:3268-3273`、SYCL: `engine/sycl/src/prefill/prefill.cpp:2168-2173`）。
- `STRATA_PREFILL_HELP_FRAC=0` または割合が 0 以下なら helper binding は false となり、その prompt は通常の段単独処理に進む。条件不成立も同様に割合を適用しない。

## 実行時の詳細

CUDA / SYCL とも `split_help_frac(T)` の関数ローカル `static` が環境値を初回評価時に一度読み、以後の prompt では値を再読込しない。初回評価はプロセス起動時ではなく、`bind_stage_helper()` が helper の存在等を確認して `split_help_frac()` に到達した時点。そこから先は、割合が正で chunk 条件を満たす場合だけ pinned expert の選別に使われる（CUDA: `engine/src/prefill/prefill.cpp:3187-3195,3258-3267`、SYCL: `engine/sycl/src/prefill/prefill.cpp:2074-2082,2158-2167`）。

prompt の expert 列挙で pinned かつ通常の helper cache 等により除外されていない expert に対し、割合を累積し、累積値が 1 以上になるたびにその expert を helper GPU の ring に割り当てて 1 を引く。そのため分担は割合に応じた間引きとなる。割合が 0 の場合は peer-streaming が有効にならない（CUDA: `engine/src/prefill/prefill.cpp:4641-4642,4673-4718`、SYCL: `engine/sycl/src/prefill/prefill.cpp:3090-3092,3145-3187`）。

分担対象の行は別 MMQ grouping で計算されるため、コードコメントは既定経路と bit-identical でないと説明する。prompt 出力全体の差や精度への影響を定量化する記述は、ここで確認した実装にはない（`engine/src/prefill/prefill.cpp:3173-3175`、`engine/sycl/src/prefill/prefill.cpp:2060-2062`）。

## ログと測定値

この変数の値や採用割合だけを表示するログは確認できない。helper 用 stream/event の初期化が失敗すると `set_stage_helper()` は `prefill: the layer split's prompt help (streams and events)` を返し、呼び出し側は `strata serve: <error> - stage <i> reads its prompts alone` と stderr に出して続行する（CUDA: `engine/src/prefill/prefill.cpp:3245-3253`、`engine/src/program/generate.cpp:13160-13165`；SYCL: `engine/sycl/src/prefill/prefill.cpp:2133-2148`、`engine/sycl/src/program/generate.cpp:7620-7625`）。chunk ごとの条件不成立は false を返して通常経路へ進み、専用の理由ログはない（CUDA: `engine/src/prefill/prefill.cpp:3258-3273,4303-4316`；SYCL: `engine/sycl/src/prefill/prefill.cpp:2158-2173,2747-2761`）。

実装コメントにある測定は 2x RTX 3090、UD-Q4_K_XL、各 PCIe 4.0 x16、P2P なしの条件で、固定割合 0.2 / 0.3 / 0.4 の順に prompt tok/s を記録している。1.5K token は 749 / 820 / 908（割合なし 675）、3K は 1335 / 1437 / 1328（割合なし 1262）、4K は 1622 / 1620 / 1440（割合なし 1609）、6K は 1811 / 1660 / 1471（割合なし 2038）、8K は 1895 / 1804 / 1663（割合なし 2230）。これはソースコメントに記載された測定値であり、別条件への一般化はできない（`engine/src/prefill/prefill.cpp:3180-3186`、`engine/sycl/src/prefill/prefill.cpp:2067-2073`）。

## 根拠

- `engine/src/prefill/prefill.cpp:3173-3195,3212-3220,3256-3273,4295-4316,4641-4718`
- `engine/sycl/src/prefill/prefill.cpp:2060-2082,2085-2090,2156-2173,2744-2761,3090-3092,3145-3187`
- `engine/src/program/generate.cpp:13155-13169`
- `engine/sycl/src/program/generate.cpp:7615-7627`
