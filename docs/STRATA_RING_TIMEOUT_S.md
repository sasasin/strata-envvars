# `STRATA_RING_TIMEOUT_S`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL backend の検証 window が、GPU の layer doorbell（ring）を待つ時間を秒単位で指定します。実装コメントでは、既定20秒では初回に GPU kernel を JIT コンパイルするカード（例として Arc A750）で最初の window の開始に足りない場合があるため、この値で延長できると説明しています。

この環境変数を読むのは `sycl/src/core/verify.cpp` だけです。CUDA 側の `src/core/verify.cpp` は同じ種類の待機に固定20秒を使い、この環境変数を読みません。SYCL のパイプライン用 `Verifier::service()` にも別の固定20秒 timeout があり、この変数の対象外です。

## 値と判定

`std::atol()` で値を `long` に変換し、結果が1以上ならその秒数を採用します。それ以外は20秒に戻します。文字列全体の数値検証はせず、`atol()` が変換できる先頭部分を使います。

| 環境変数の状態・値 | 採用値 |
|---|---:|
| 未設定 | 20秒 |
| 空文字、数値に変換できない文字列、`0`、負数 | 20秒 |
| `1` 以上の整数文字列 | 変換後の秒数 |
| 数値の後ろに文字がある値（例: `30abc`） | 先頭の整数部分。例では30秒 |
| 数字より前に空白や符号がある値（例: ` 30`, `+30`） | `atol()` が変換した値。例では30秒 |

明示的な上限・clamp はありません。変換結果が正の `long` であればその値を使います。`atol()` の範囲外入力に対するエラー検査もありません。

根拠: `sycl/src/core/verify.cpp:209-216`。

## 有効になる条件

- SYCL backend を使うビルド・実行経路であること。SYCL の engine は `sycl/CMakeLists.txt:220-228` で `sycl/src/core/verify.cpp` を含みます。通常の CUDA engine は `CMakeLists.txt:472-478` で別の `src/core/verify.cpp` を含みます。
- GPU が doorbell を上げるまでホストが待つ経路であること。すでに doorbell が届いていれば timeout 判定は実行されません。
- all-resident など、layer ごとの host doorbell 待ちを行わない経路では、この待ち時間は適用されません。
- `Verifier::service()` のパイプライン経路は別実装で、`fl_since_ms_` からの経過時間が20,000 msを超えると timeout します。`STRATA_RING_TIMEOUT_S` は参照されません。

## 実行時の詳細

`strata_ring_timeout()` は関数内 `static const long` を初回呼び出し時に初期化します。通常の window 実行では、各 layer の `h_seq_` が期待値に達するまで spin wait し、その待ちが設定秒数を**超えた**場合に timeout とします。バッチ実行と `batch_poll()` にも同じ関数が使われます。初回の ring 待ちで timeout 関数が呼ばれた後は結果がプロセス内にキャッシュされ、環境変数を変更しても再読込しません。

timeout 時は検証処理がエラーを返し、GPU 側の待ちを最大5秒間解放・drain しようとします。エラー文字列は通常経路で `verify: timed out at layer N`、バッチ経路で `verify batch: timed out at layer N` です。通常経路で `STRATA_VERIFY_TRACE` が有効なら、timeout 前後の診断出力も行います。これらの後処理時間5秒は本変数では変わりません。

パイプライン用の `Verifier::service()` は `fl_since_ms_ > 20000.0` を独自に判定するため、`STRATA_RING_TIMEOUT_S` を大きくしてもそこは延長されません。

## 文書との照合

ソース内の実装コメントに既定20秒と、初回 JIT の起動がそれを超えうる旨があります。`docs/DETAILS.md`、`docs/INTEL.md`、`docs/A770_SPEED_SPEC.md`、`docs/TROUBLESHOOTING.md` を検索した範囲では、この環境変数の値や使い方を説明する記述は見つかりませんでした。性能値や実測効果は記載していません。

## 根拠

- `sycl/src/core/verify.cpp:206-216`: 既定値、`atol()`、1秒未満の fallback、関数内 static cache。
- `sycl/src/core/verify.cpp:2202-2249`: 通常の window の doorbell 待ちと timeout error。
- `sycl/src/core/verify.cpp:3173-3205`: batch run の doorbell 待ち。
- `sycl/src/core/verify.cpp:3412-3453`: `batch_poll()` の doorbell 待ち。
- `sycl/src/core/verify.cpp:3713-3769`: pipelined `service()` はこの環境変数を使わず固定20秒。
- `CMakeLists.txt:472-478`, `sycl/CMakeLists.txt:220-228`: CUDA と SYCL で異なる `verify.cpp` を engine に含める構成。
- `src/core/verify.cpp:2195-2229,2882-2905,3045-3061,3317-3337`: CUDA 側の対応する待ち時間は固定20秒。
