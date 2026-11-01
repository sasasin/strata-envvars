# `STRATA_PREFILL_LM_MARGIN_MIB`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

layer-major prefill の super-chunk 用 VRAM 適合判定で、空けておく VRAM 量を MiB 単位で指定します。指定値は予約量として差し引かれ、実際に割り当てる量やモデル重みの配置を直接指定するものではありません。layer-major prefill が選択され、`lm_prepare()` が super-chunk を準備する経路でだけ参照されます。候補一覧にはありますが、実際の読み取り箇所は `src/prefill/prefill.cpp` の `lm_margin_bytes()` にある `std::getenv()` 1 箇所です。

## 値と判定

| 状態 | 適用される余白 |
|---|---:|
| 未設定 | layer-major が既定で有効になった場合は 512 MiB、`STRATA_PREFILL_LAYER_MAJOR` などで明示的に有効にした場合は 96 MiB |
| 設定あり | `std::atoll()` の結果を MiB としてバイト換算した値。0 以上なら上記既定値を置き換える |
| 空文字 | `atoll("")` 相当で 0。明示値 0 として余白なし |
| 数字として読めない文字列 | `atoll()` は変換できないと 0 を返すため、余白なし |
| 数字に続く文字 | `atoll()` が先頭から読めた整数部分を使う。末尾全体の検証はない（例: `128junk` は 128 MiB） |
| 負数 | コードに範囲検査・clamp はない。負の値を 20 bit 左シフトしており、C++ では負の符号付き値の左シフトは未定義動作。結果を有効な負の余白として保証できない |

`std::atoll()` の結果を `int64_t` にしてから `<< 20` しています。大きすぎる入力の範囲検査や変換失敗の個別エラー処理もありません。変換後の値が 0 以上なら明示設定値を採用し、負なら `by_default` に応じた 512/96 MiB に戻す条件ですが、負数入力ではその前の左シフト自体が未定義動作です。根拠: `src/prefill/prefill.cpp:5925-5931`。

## 有効になる条件

この変数単独では layer-major prefill を有効にしません。layer-major が選ばれた後、super-chunk の VRAM 必要量から余白を引くために使われます。

- `STRATA_PREFILL_LAYER_MAJOR` が空でない場合、その値が `std::atoi()` で 0 以外なら明示的に有効、0 と解釈されれば無効です。空文字または未設定時は既定規則へ進みます。明示的に有効にした場合は `by_default=false` なので、この変数が未設定なら余白は 96 MiB です（`src/prefill/prefill.cpp:5894-5898,7238-7243`; `include/strata/core/sm120_series.hpp:112-120`）。
- `STRATA_PREFILL_LAYER_MAJOR` が未設定または空の場合の既定 ON は、HIP ではなく、`STRATA_DEFAULTS=026` でもなく、prompt path が 2 stage 以上である場合です。既定で ON になるこの経路では、余白は 512 MiB です（`src/prefill/prefill.cpp:7233-7243`; `include/strata/core/sm120_series.hpp:112-120`）。Metal の `Prefill::run()` は別の経路へ return するため、この CUDA/HIP 実装の判定には入りません（`src/prefill/prefill.cpp:7222-7237`）。
- 有効判定後も、画像 prompt、peer GPU、DFlash2 prompt taps、KVA、chunk 境界で yield する batch read、`--prefill-pipe`、一部の expert format/layout や必要 buffer 不足などでは `lm_prepare()` が layer-major を辞退します。これらの拒否経路では margin 値は super-chunk 適合判定に到達しない場合があります（`src/prefill/prefill.cpp:5971-5999,6010-6023`）。
- CLI 引数や別の環境変数が margin の数値を上書きする処理は見つかりません。`STRATA_PREFILL_LAYER_MAJOR` と `STRATA_DEFAULTS` は layer-major を選ぶ条件と未設定時既定 margin の区分に関係しますが、margin の明示値より優先されません。

## 実行時の詳細

`lm_margin_bytes()` 内の `static const int64_t explicit_v` は、layer-major super-chunk 準備で最初にこの関数を呼んだ時に一度だけ環境を読み取って cache します。そのため同一プロセス中に環境を書き換えても明示値は再読込されません。一方、未設定時の 96/512 MiB の選択は引数 `by_default` で呼び出しごとに決まり、layer-major が既定で有効だったか、明示的に有効化されたかで異なります（`src/prefill/prefill.cpp:5925-5931,6042`）。

`lm_prepare()` は `cudaMemGetInfo()` の free VRAM からこの余白を引いた `room` を計算し、候補 super-chunk の必要 VRAM が `room` 以下となる最大サイズを探します。`STRATA_PREFILL_LM_R` が VRAM 固定ならその配置で、host 固定なら pinned host 配置で fit を探します。auto の場合は全目標サイズが VRAM に収まる場合だけ residual rows を VRAM に置き、それ以外は pinned host 配置で fit を探します。余白を大きくして fit するサイズがなくなると、準備は `no VRAM for a super-chunk (<free> MiB free)` 理由で失敗し、layer-major の実行を辞退します（`src/prefill/prefill.cpp:6040-6062`）。

辞退理由は stderr に `strata prefill: layer-major off for this prompt: ...` と出ます。ただし既定で ON の経路で、理由が `a short prompt` の場合はこの行を抑制します。準備に成功した場合は layer-major 実行後に stderr へ super-chunk 数、最大サイズ、residual rows の配置、実行統計などを出します。margin 値そのものを表示するログはありません（`src/prefill/prefill.cpp:7160-7167,7245-7269`）。この失敗はここではプロセス終了ではなく chunk-major の `run_impl()` へ戻る fallback です（`src/prefill/prefill.cpp:7265-7271`）。layer-major 実行を開始した後の CUDA 同期エラー等は `err` に設定され `false` を返す経路がありますが、これは margin 設定固有の失敗ではありません（`src/prefill/prefill.cpp:7151-7157,7254-7263`）。

## 根拠

- 環境読み取り、`atoll()`、MiB 換算、未設定時既定値: `src/prefill/prefill.cpp:5923-5931`
- free VRAM からの差し引き、候補サイズ探索、fit 失敗理由: `src/prefill/prefill.cpp:6040-6062`
- layer-major の選択条件と `by_default` の伝播: `src/prefill/prefill.cpp:7233-7243`; `include/strata/core/sm120_series.hpp:112-120`
- 拒否条件: `src/prefill/prefill.cpp:5955-5999,6010-6023`
- 適合失敗後のログと chunk-major fallback: `src/prefill/prefill.cpp:7265-7271`
- 既存設計資料 `docs/DETAILS.md` にこの margin 変数固有の説明は見つかりませんでした。
