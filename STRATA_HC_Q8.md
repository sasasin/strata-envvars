# `STRATA_HC_Q8`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

ネイティブ dense GGUF の hyper-connection（HC）投影について、verify window の読み取りに使う Q8_0 データを追加で GPU に読み込みます。CUDA/HIP の fused HC read は、通常の pack に格納された BF16 投影の代わりに GGUF の Q8_0 投影を使います。対象は各層の attention/FFN の down/up/inject 投影と、最終 mixer の `output_hc_down.weight` / `output_hc_up.weight` です。通常の読み取りとは重みと加算順が異なるため、計算結果が変わり得る opt-in の実験経路です（`src/core/native_dense.cpp:40-51`、`src/kernels/cuda/fused_gr.cu:1349-1356`）。

## 値と判定

| 設定値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| 先頭文字が `1`（例: `1`, `10`, `1anything`） | 有効 |
| その他（例: `0`, `true`, ` 1`） | 無効 |

数値 parse や文字列全体の比較はせず、`getenv()` の戻り値が null でなく、先頭文字が文字 `1` かを比較します。判定は `hc_q8_requested()` の関数内 static に保存されるため、最初に判定した後の環境変更は反映されません。判定関数は `NativeDense::load()` 中の補助ウェイト読み込みで呼ばれます（`src/core/native_dense.cpp:40-44,323-324`）。SYCL 側にも同じ判定があります（`sycl/src/core/native_dense.cpp:32-36,318-319`）。

## 有効になる条件

- `NativeDense::load()` が呼ばれる必要があります。生成経路では `o.native_dense_gguf` が空でない場合にロードし、`--native` が使われていて `--native-dense-gguf` が別途指定されていない場合は native shards がその入力に設定されます。通常の pack 読み込みだけではこの環境変数は使われません（`src/program/generate.cpp:2507-2519,3028-3035`）。
- 入力 GGUF に対象名の行列があり、型・shape が認識される必要があります。元から Q8_0 型（GGUF tensor type `8`）の行列をコピーします。追加の `STRATA_HC_Q8_INJECT=1` が有効なら、F32 型の `_inject.weight` も Q8_0 に変換してコピーします。`STRATA_HC_Q8_INJECT` も先頭文字が `1` の設定有無で判定されます。これを使わない場合、inject 行は Q8_0 read 内で pack の BF16 行を使います（`src/core/native_dense.cpp:45-51,323-347`; `src/kernels/cuda/fused_gr.cu:1377-1382,1435-1444`）。
- 行列の shape が canonical weight table の寸法と一致し、入力幅 `ne0` が 32 の倍数でなければロードはエラーになります。デバイス確保またはコピーに失敗しても `NativeDense::load()` はエラーを返します（`src/core/native_dense.cpp:329-347`）。
- CUDA/HIP の verify read は down と up の Q8_0 コピーが両方ある場合に Q8 カーネルを選びます。層ごとの HC 読み取りではこれらのポインターを `FusedGrArgs` に渡し、最終 mixer では両コピーに加えて native head がロード済みの場合に Q8 read を選びます。条件を満たさない箇所は既存経路を使います（`src/core/verify.cpp:1053-1072,1703-1724`; `src/kernels/cuda/fused_gr.cu:1855-1864`）。
- SYCL にも追加 Q8 コピーの読み込み処理はありますが、SYCL の `fused_gr_read_multi` は Q8_0 read を実装していないと明記されています。したがって SYCL ではこの設定でコピーとロード量ログが生じても、read は Q8_0 カーネルに切り替わりません（`sycl/src/core/native_dense.cpp:318-355,404-406`; `sycl/src/kernels/cuda/fused_gr.dp.cpp:1607-1625,1876-1883`）。

## 実行時の詳細

有効時、`NativeDense::load()` は対象の GGUF tensor ごとに Q8_0 用のデバイス領域を確保し、GGUF のバイト列をコピーして `WeightRef::hc_q8` に保持します。F32 inject を選んだ場合は各32値の最大絶対値から scale を作り、Q8_0 の block（半精度 scale 2 byte + int8 値 32 byte）へ変換します（`src/core/native_dense.cpp:53-87,336-347`）。

CUDA/HIP では `verify.cpp` が HC の down/up/inject Q8_0 ポインターを fused read に渡します。`fused_gr_read_multi()` は down と up が揃っていれば Q8 read kernel を起動し、揃わなければ通常経路へ進みます。最終 mixer も別条件で同じ Q8 read を使います。Q8 kernel の起動エラーは stderr に `fused_gr_read_multi q8: ...` を出し、プロセスを終了します（`src/core/verify.cpp:1053-1072,1703-1724`; `src/kernels/cuda/fused_gr.cu:1855-1864`）。

コピーされた Q8_0 投影の合計量は stderr に `strata: STRATA_HC_Q8=1: %.2f GiB of Q8_0 hyper-connection projections for the verify read` と表示されます。shape 不一致時の文言は `native dense (STRATA_HC_Q8): incompatible matrix <tensor名>`、アップロード失敗時は `native dense (STRATA_HC_Q8) upload <tensor名>` です。生成側はロード失敗を `strata generate: native dense projections: ...` として出力します（`src/core/native_dense.cpp:329-343,379-381`; `src/program/generate.cpp:3028-3033`）。

## 文書との照合・制限

`docs/STRIX_HALO.md` は `STRATA_HC_Q8=1` を gfx1151 向けの opt-in fast configuration に含め、GGUF 自身の Q8_0 HC 投影を使う設定として記載しています（`docs/STRIX_HALO.md:100-117`）。同文書の測定値は複数の設定をまとめた構成全体の結果であり、この環境変数単独の性能差とは読み取れません。`docs/UNSLOTH_Q4.md` は互換 pack で Q8_0 HC 投影を BF16 に丸める際の最大絶対誤差を記載していますが、これは `STRATA_HC_Q8` 単独の品質測定ではありません（`docs/UNSLOTH_Q4.md:91-105`）。

## 根拠

- `src/core/native_dense.cpp:40-51,323-347,377-381` — 値の判定、名前フィルター、追加コピー、失敗条件、ロード量ログ。
- `src/program/generate.cpp:2507-2519,3028-3035` — native dense GGUF の入力条件とロード呼び出し。
- `src/core/verify.cpp:1053-1072,1703-1724` — 層ごとの read と最終 mixer への Q8 ポインター設定。
- `src/kernels/cuda/fused_gr.cu:1349-1356,1377-1382,1855-1864` — Q8 read の数値経路、inject の既定、カーネル選択とエラー。
- `sycl/src/core/native_dense.cpp:32-43,318-355,404-406`; `sycl/src/kernels/cuda/fused_gr.dp.cpp:1607-1625,1876-1883` — SYCL でのコピー処理と Q8 read 未実装の差。
- `docs/STRIX_HALO.md:100-117`; `docs/UNSLOTH_Q4.md:91-105` — 利用例および互換 pack に関する説明。
