# `STRATA_GDN_REC_WARP`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の実験ビルドで、Volta (compute capability 7.0) 上の GDN prompt recurrence に使うカーネルを選びます。unset または整数変換結果が 0 なら従来の pipelined recurrence、値が `2` なら依存 FMA chain を4分割したカーネル、それ以外の非0値なら warp 内 reduction を使うカーネルです。変数名に `WARP` とありますが、値 `2` は別の chain-split カーネルを選びます。

## 値と判定

実装は値を `std::atoi` に渡します。空文字だけは変換前に 0 とされます。文字列全体の妥当性は確認せず、`atoi` が先頭の空白と符号の後から読める整数部分を使います。そのため `2tail` は 2、`1tail` は 1、`0tail` や `word` は 0 になります。数値の範囲検査や clamp はありません。

| 値・状態 | 判定と選択（有効条件を満たす場合） |
|---|---|
| unset、空文字、`atoi` 結果が 0 | warp recurrence を選ばず、通常の dispatch に進む。既定では pipelined kernel だが、`STRATA_GDN_PIPELINE`、`STRATA_GDN_CHUNKED` など通常 dispatch 側の条件が適用される。 |
| `atoi` 結果が `2`（例: `2`, `+2`, `2tail`） | 4 accumulator chain-split kernel。積和の合算順序が変わるため FP32 レベルで従来版と異なり、bit-exact ではない。 |
| その他の非0整数（例: `1`, `-1`, `3`） | sync-free warp-reduction kernel。ソースコメントは従来の pipelined recurrence と bit-exact としている。 |

## 有効になる条件

- `STRATA_EXPERIMENTAL_SM60` を有効にした CUDA ビルドであること。通常配布の CUDA build ではこの dispatch はコンパイルされず、この変数は読み取られません。CMake ではこの設定を Pascal / Volta 向けの実験 build と説明しています。
- 実行デバイスの compute capability が 7.0 であること。`gdn_chunk_available()` が runtime capability 70 の場合だけ true を返し、その結果は `static` に一度だけ保存されます。別の capability ではこの変数が非0でも warp recurrence に入りません。
- `T > 0` で、`STRATA_GDN_REC_HEADS` が設定されていないこと。後者は値に関係なく「設定されているか」で判定され、初回評価結果が static に保存されます。
- `STRATA_GDN_CHUNK` が同じ呼び出しで chunked recurrence を選んでいないこと。`STRATA_GDN_CHUNK` は呼び出しごとに読み直され、chunked が選ばれると `STRATA_GDN_REC_WARP` の値にかかわらず warp recurrence 分岐は使われません。chunked が選ばれても `T < 64` なら chunk kernel 自体は起動せず通常 recurrence に戻ります。

warp 分岐に入らないときの通常 dispatch は `STRATA_GDN_PIPELINE`、CUDA の `STRATA_GDN_CHUNKED`、`STRATA_GDN_REC_HEADS` などの設定でも変わります。これらは `STRATA_GDN_REC_WARP` の parse 値そのものを変えません。

この実験 dispatch は `__HIPCC__` では使われません。CUDA の通常 build や非Volta GPU、上記の抑止条件では、処理は serial / 通常 recurrence など後続の既存 dispatch に進みます。

## 実行時の詳細

環境変数は `gdn_recurrence_variant()` の呼び出しごとに `getenv()` し、`atoi` で判定します。プロセス中の環境変更は次の recurrence 呼び出しで反映されます。一方、Volta 判定と `STRATA_GDN_REC_HEADS` の判定は初回呼び出し時の `static` 値です。

`2` のときは、従来 pipelined kernel の2本の積和 chain を各4 accumulator に分割した kernel を起動します。各 accumulator の部分和をまとめるため、FP32 の加算順序が変わります。それ以外の非0値では、8列を warp が担当し、row group の reduction を shuffle で行う kernel を起動します。こちらは従来 kernel と同じ演算順序を保ち、同期 barrier を使わない実装です。どちらの経路も recurrence の後に `gdn_out_norm_kernel` を起動します。

環境変数に由来する専用ログや警告はこの実装箇所にはありません。

## 文書・測定値との照合

`docs/NVIDIA_V100.md` は `STRATA_GDN_REC_WARP=2` を V100 の opt-in chain-split とし、recurrence の +6–9% を contributor の測定値として記載しています。同文書は測定が contributor によるもので maintainers によるものではないと説明しています。ソースのコメントも +6–9% と記載し、FP32 レベルで summation order が異なることを明記しています。測定条件の詳細は同資料の該当表にないため、ここでは性能値を他環境へ一般化しません。`STRATA_GDN_REC_WARP=1` の bit-exact sync-free variant については、同じ資料が測定上遅かったため bitwise control として残したと記しています。

## 根拠

- `src/prefill/kernels.cu:435-480` — warp-reduction kernel と計算順序。
- `src/prefill/kernels.cu:641-704` — chain-split kernel と演算順序の差。
- `src/prefill/kernels.cu:2666-2703` — compile guard、値の読み取り、dispatch、chunked recurrence との優先関係、後続 norm。
- `src/prefill/kernels.cu:2611-2614` — `STRATA_GDN_REC_HEADS` による serial 選択。
- `src/prefill/gdn_chunk.cu:523-529` — HIP / build 条件と runtime capability 70 の判定。
- `CMakeLists.txt:181-219,707-718` — 実験 build の説明と prefill source の構成。
- `docs/NVIDIA_V100.md:93-105` — V100 opt-in switch と contributor 測定値。
