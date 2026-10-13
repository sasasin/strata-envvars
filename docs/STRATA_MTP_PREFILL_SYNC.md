# `STRATA_MTP_PREFILL_SYNC`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数の動作は対象外。

## 役割

MTP drafter が prompt 処理中に draft layer の K/V を追いつかせる `MtpDrafter::prefill()` の同期方式を選びます。旧方式は `max_t_` 行以下の group ごとに mapped host memory へ入力を用意し、graph を実行して stream を同期してから次の group へ進みます。新方式（コードコメントの E-4）は入力レコードをまとめて device memory に upload し、group ごとの device copy と graph launch を同じ stream に積み、最後に必要な場合だけ同期します。対象はこの MTP prefill の処理経路であり、通常の target model の prompt 計算方式を切り替える変数ではありません。

## 値と判定

値は `std::atoi()` で変換され、結果が 0 以外なら旧方式を選びます。文字列全体の数値検証はありません。したがって未設定と同様に、空文字、`0`、数字で始まらない文字列は無効（0）です。`1`, `-1`, `1tail`, ` 1` は `atoi()` の結果が 0 以外となり有効です。`0tail` は 0 です。

| ビルド | 未設定時 | 設定時 |
|---|---|---|
| CUDA / SYCL（`STRATA_USE_HIP` なし） | 旧方式を使わない（E-4 を選択） | `atoi(value) != 0` なら旧方式、0 なら E-4 |
| HIP（`STRATA_USE_HIP` 定義） | 旧方式を使う | `atoi(value) != 0` なら旧方式、0 なら E-4 |

## 有効になる条件

- MTP drafter が使われ、その prompt chunk の draft K/V を `MtpDrafter::prefill()` が処理する場合に判定が関係します。単一 GPU の通常経路は先に `Prefill::draft_kv` を試し、そこで処理できない場合に drafter 自身の `prefill()` へ進みます。layer split では `STRATA_SPLIT_MTP_BATCH` による E-9 の opt-in がなければ、drafter 側の処理になります。E-9 が chunk を処理した場合、この環境変数の同期方式は使われません。
- 選択結果は `prefill()` 内の関数ローカル `static const bool` に一度保存されます。最初の呼び出しで評価された後にプロセス環境を書き換えても再評価されません。
- E-4 分岐は `n > 0` の場合に限られます。`n == 0` なら E-4 の一括 upload 分岐を通らず、group loop は実行されません。
- 旧方式は CUDA と SYCL の両実装で group ごとに同期します。E-4 は `sync=true` なら全 group の投入後に CUDA stream / SYCL queue を待ちます。`sync=false` ならそこで待たず、呼び出し元が同じ stream 上の後続処理で順序を保つ経路になります。旧方式の group ごとの同期は `sync` 引数にかかわらず行われます。

## 実行時の詳細

両実装とも `prefill()` の最初の実行時に環境変数を読みます。旧方式では group ごとに `capture_prefill()` を用い、各 group 分の `tok` / `step` / `pos` 情報を host mapped memory に詰めてから graph を launch し、直後に同期します。E-4 では全 `n` 行分の token / step / position record を作って device buffer に upload し、最大 `max_t_` 行ずつ device-to-device copy と `capture_prefill_dev()` の graph を投入します。処理対象外の古い cell（`cell0 + c + T <= first_needed`）はどちらの方式でも飛ばします。

E-4 の upload、buffer 確保、graph capture / launch、同期が失敗した場合は `false` を返し、`err` に `mtp prefill: ...` のエラーを設定します。旧方式でも graph capture、copy / launch、同期の失敗で同様に失敗します。この変数自体によるログ出力はありません。ソースコメントには HIP gfx1201 / ROCm 7.2.4 で E-4 が hang した試行と、旧方式では完了した試行が記録されていますが、これは実装コメントの報告であり、この調査で再測定した結果ではありません。

## 根拠

- `src/core/mtp.cpp:1130-1145` は事前確保と `capture_prefill_dev()` の準備、`:1148-1174` は読み取り、既定値、static cache、および E-4 選択条件を示します。
- `src/core/mtp.cpp:1174-1229` は一括 upload・device copy・graph launch と `sync` 分岐、`:1231-1253` は group ごとの mapped-memory 経路と同期を示します。
- `sycl/src/core/mtp.cpp:1322-1339,1347-1373,1373-1489,1491-1531` は SYCL 実装の同等処理を示します。
- `include/strata/program/draft_kv_plan.hpp:1-7,25-42` と `src/program/generate.cpp:8092-8120` は E-9 と drafter prefill の選択、および layer split の条件を示します。SYCL 側の単一 GPU fallback は `sycl/src/program/generate.cpp:7665-7670` にあります。
- `docs/DETAILS.md` と `docs/` 内にはこの環境変数固有の追加仕様や性能測定の説明は見つかりませんでした。
