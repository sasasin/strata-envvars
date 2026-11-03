# `STRATA_ATTN_MERGE_ACTIVE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

SYCL 版 QSA decode attention の chunk 結合 kernel を選びます。有効時は各 query の実際の width に達するまでの active chunk だけを結合し、無効時は capacity から決まる全 chunk を従来の結合 kernel で処理します。Strata の SYCL 実装内の実行時制御です。

## 値と判定

環境値は `strata::bm_default_on()` が読みます。値全体の parse はせず、値が空でなければ先頭文字が `'0'` かどうかだけを見ます。空文字は未設定と同じくデバイス既定値にフォールバックします。

| 条件 | 有効 | 無効 |
|---|---|---|
| 未設定または空文字 | Battlemage デバイスで有効、それ以外は無効 | Battlemage 以外のデバイス |
| 空でない値を設定 | 先頭文字が `'0'` 以外なら有効（例: `1`, `true`, `false`, `2`, ` 0`） | 先頭文字が `'0'` なら無効（例: `0`, `0anything`） |

大文字小文字、空白の除去、数値としての妥当性、文字列の残りは検査しません。したがって `false` も明示的な有効値です。明示値はデバイス既定値を上書きし、CLI 引数との優先順位はありません。

## 有効になる条件

- 対象は `sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp` の SYCL QSA decode attention 実装です。環境変数を参照する helper を含むこの kernel ソースは SYCL build の `strata_kernels` に追加されています（`sycl/CMakeLists.txt:245-258`）。
- `qsa_decode_attn_batch()` の chunk 計算後、`n_q <= 8` のときだけ設定値に応じて active merge kernel を選びます。`n_q > 8` では設定が有効でも通常の merge kernel を使います（`sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:876-888,1072-1096`）。
- `qsa_decode_attn_batch_rows()` の通常の複数行経路は独自の row merge kernel を使い、ここではこの環境変数を確認しません（同ファイル `:1125-1129,1134-1145,1160-1167`）。ただし `STRATA_ATTN_RS` が `2` 以外、または `STRATA_ATTN_LANECELL=1` のときは同関数が各行を `qsa_decode_attn_batch()` に渡すため、その行ごとの呼び出しでは本変数の分岐が適用されます（同ファイル `:1134-1145`）。
- 未設定時の既定値は `intel_gpu_gen(d) == Battlemage` の場合だけ ON です。明示値はデバイス世代にかかわらず ON/OFF を指定します。Alchemist を含む Battlemage 以外は既定 OFF です（`sycl/include/strata/sycl_queue.hpp:159-166`）。

## 実行時の詳細

`merge_active_on()` 内の `static const bool` が最初の呼び出しで helper の結果をキャッシュします。以後、プロセス内で環境変数を変更しても再評価されません。また `d` もその初回評価時の値で判定されるため、複数デバイスを使うプロセスでは最初に呼び出されたデバイスの既定判定が共有されます（`sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:680-683`）。

有効経路の merge kernel は `steps` から各 query の width を読み、`ceil(width / CHUNK)` と `n_chunks` の小さい方までを結合対象とします。`CHUNK` は 64 cells です。通常経路の merge kernel は `0..n_chunks` を走査し、未使用 chunk は `-FLT_MAX` の最大値を使って除外します（同ファイル `:23,590-619,621-678`）。この選択自体に環境変数固有のログや警告はありません。QSA decode への呼び出し経路は `sycl/src/core/layer.cpp:1306-1312` にあります。

Strata の `docs/INTEL.md:518-548` は Battlemage 向け decode controls の一つとして本変数を挙げ、表の説明を「bounded batched QSA decode で active chunk だけを merge」としています。同資料の性能値は複数 control と build option をまとめた条件での測定で、当該変数単独の効果を示す値ではないため、ここでは個別の性能向上値を記載しません。

## 根拠

- 候補名のソース参照は `sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:681` の一箇所で、`bm_default_on` を介して `std::getenv(name)` を呼びます。同名の他の読み取り箇所はありません。
- 値の解釈と Battlemage 既定値: `sycl/include/strata/sycl_queue.hpp:159-166`。
- キャッシュと kernel 選択条件: `sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:680-683,1072-1096`。
- active chunk の範囲と通常 merge の処理: 同ファイル `:590-678`。
- row batch の通常経路と単行 fallback: 同ファイル `:1125-1167`。
- QSA decode の呼び出し例: `sycl/src/core/layer.cpp:1306-1312`。
- build 対象: `sycl/CMakeLists.txt:245-258`。
