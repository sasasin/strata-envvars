# `STRATA_DRAFT_TIMING`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

プロンプト処理中に draft layer の K/V をバッチ生成する経路で、drafter の待ち時間とバッチ処理時間を計測し、標準エラーに出します。CUDA と SYCL の `Prefill::draft_kv()` に実装されています。通常の drafter 自身の逐次 prefill を含む、すべての draft 処理を計測する変数ではありません。

## 値と判定

値の内容は parse せず、`std::getenv("STRATA_DRAFT_TIMING") != nullptr` で設定有無だけを判定します。

| 状態 | timing |
|---|---|
| 未設定 | 無効 |
| 空文字を含む、何らかの値が設定済み | 有効 |

値が `0`、`false`、任意の文字列でも設定済みなら有効です。無効になるのは未設定の場合だけです。判定値は関数内の `static const bool` に保存されるため、関数内で最初にこの判定箇所へ到達した後の環境変更は反映されません。

根拠: `src/prefill/prefill.cpp:1418`、`sycl/src/prefill/prefill.cpp:1381`。

## 有効になる条件

この変数自体はバッチ経路を有効化しません。`Prefill::draft_kv()` が呼ばれ、K/V の状態、device、scratch 容量などの適用条件を満たしてバッチ処理が最後まで成功した場合に、計測ログを出します。関数が適用不可として早期 return した場合や、処理エラーで失敗した場合は成功ログを出しません。呼び出し側は適用不可の場合に drafter 自身の `mtp.prefill()` へ進む経路を持ちます。

通常の `generate` の prompt path と server の chunk 処理から呼ばれます。server では `draft_kv::plan()` がバッチ経路を選ばない場合や、複数 GPU 等で条件を満たさない場合には、この計測箇所へ到達しないことがあります。詳細は `src/program/generate.cpp:8092-8120,12469-12480`、SYCL server は `sycl/src/program/generate.cpp:7665-7670`。

## 実行時の詳細

有効な場合、CUDA 実装は計測開始前に `cudaStreamSynchronize(m.cs)`、SYCL 実装は `m.cs->wait()` を行ってから `mtp.idle(err)` の所要時間を計り、その後のバッチ処理時間と関数全体の経過時間を計ります。CUDA の先行同期の戻り値はこの箇所では判定されません。SYCL では `wait()` を実行します。

成功時の stderr 出力は両実装で同じ形式です:

```text
strata draft kv: <n> cells from <cell0> (first needed <cell0+r0>), batch <B>: drafter idle <ms_idle> ms, the batches <batch_ms> ms, all <total_ms> ms
```

このフックは同期と計時、ログ出力を加えます。バッチ計算の選択条件や drafter の K/V 計算そのものを変更する分岐には使われません。成功経路では既存の `mtp.ms_prefill` にも `t0` からの経過時間が加算されます。

根拠: CUDA `src/prefill/prefill.cpp:1418-1422,1501-1509`、SYCL `sycl/src/prefill/prefill.cpp:1381-1385,1483-1502`。

## 文書との照合

`docs/DETAILS.md` には speculative drafting や draft layer の説明がありますが、`STRATA_DRAFT_TIMING` の説明は見つかりませんでした。性能値をこの変数の効果として示す資料も確認できていません。

## 根拠

- CUDA 読み取り、同期、時刻区間: `src/prefill/prefill.cpp:1418-1423`。
- CUDA 成功時の累積時間とログ: `src/prefill/prefill.cpp:1501-1509`。
- SYCL 読み取り、同期、出力: `sycl/src/prefill/prefill.cpp:1381-1386,1483-1502`。
- 呼び出し側と fallback: `src/program/generate.cpp:8092-8120,12469-12480`、`sycl/src/program/generate.cpp:7665-7670`。
