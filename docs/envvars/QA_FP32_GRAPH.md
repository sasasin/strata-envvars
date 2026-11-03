# `QA_FP32_GRAPH`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

SYCL 版の standalone parity / timing プログラム `qsa_prompt_attn_parity` に、FP32 の旧 attention kernel を使った command graph の計測を追加します。Strata の通常の `strata` 実行ファイルやサーバーで推論経路を切り替える変数ではありません。変数名の全参照は `sycl/src/kernels/qsa_prompt_attn_parity.cpp:406` の読み取り 1 箇所だけです。

## 値と判定

| 値 | 判定 |
|---|---|
| 未設定 | command graph 計測を行わない |
| 設定あり（空文字を含む） | command graph 計測を行う |

`std::getenv("QA_FP32_GRAPH")` の null 判定だけを使います。文字列の内容、数値変換、大文字小文字、空白は検査しません。したがって `0`、`false`、空文字を含む、設定された値はすべて同じ扱いです。fallback や値域制限はありません。CLI 引数や別環境変数による上書きもありません。

## 有効になる条件

- SYCL parity target `qsa_prompt_attn_parity` をビルドして実行すること。SYCL CMake の `STRATA_SYCL_PARITY` は既定で `ON` で、この target は同 option のブロック内で作成・CTest 登録されます。
- プログラム内で `run()` が実行されること。`main()` は通常、int8 に加えて FP16 / Q4_0 等の各ケースを順に `run()` へ渡します。AMD HIP platform の条件や `--int8-only` によるケース選択はありますが、`QA_FP32_GRAPH` の分岐自体には OS、GPU 世代、build macro、モデル状態の追加判定はありません。

この判定は engine の実行経路には接続されていません。トップレベル CUDA parity target は `src/kernels/qsa_prompt_attn_parity.cpp` を使い、候補名を読むコードはありません。対象となる読み取りは SYCL 側のコピーに限られます。

## 実行時の詳細

`run()` の旧 kernel / 新 kernel / per-cell kernel の通常の比較と timing の後に環境変数を読みます。値が設定されている場合、SYCL の in-order queue で `old_run()` を 32 回記録し、graph を finalize します。その後 graph を 20 回 submit し、各回の `wait_and_throw()` 完了後に時間を記録します。最初の 5 回を除いた 15 回の per-call 時間をソートし、中央値を `DECODEGRAPH fmt=... ctx=... nq=... us=...` と stdout に出します。この計測は parity 比較結果や kernel 選択の条件を変更しません。

値は `run()` ごとに直接読み直され、static cache はありません。通常のプロセス環境は実行中に変わらないため、各 `run()` で同じ設定を判定します。未設定時は graph 計測の出力を追加しません。graph の記録・finalize・実行で失敗した場合のこの分岐固有の fallback や診断ログは実装にありません。API 呼び出しの失敗時に外部 SYCL runtime が示す動作は、この文書では Strata の挙動として扱いません。

## 根拠

- `sycl/src/kernels/qsa_prompt_attn_parity.cpp:406-428` — 設定有無の判定、32 回の `old_run()` 記録、20 回の graph 実行、初回 5 回を除いた中央値の stdout 出力。
- `sycl/src/kernels/qsa_prompt_attn_parity.cpp:266-270, 285-299, 451-452` — `old_run()` が旧 decode attention kernel を呼ぶこと、run の戻り値が parity 検査に基づくこと。
- `sycl/src/kernels/qsa_prompt_attn_parity.cpp:455-494` — CLI のケース選択と `run()` 呼び出し。
- `sycl/CMakeLists.txt:288-291, 413-418` — `STRATA_SYCL_PARITY` の既定値と parity executable / CTest 登録。
- `CMakeLists.txt:541-547` — CUDA parity target は別の `src/` ファイルを使うこと。
