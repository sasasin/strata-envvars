# `STRATA_MTP_BATCH_F16`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。

## 役割

prompt 中の MTP drafter の K/V を prompt 側のバッチ処理で作る経路（`Prefill::draft_kv`、E-9）で、Q8_0 MMQ projection を選ばず native GEMM projection にするスイッチです。環境変数が有効な場合も drafter の重みは Q8_0 のままで、FP32 の中間入力を FP16 に変換して native projection に渡します。対象は通常の prompt prefill における drafter の `fc_embedding`、`fc_hidden`、attention の K/V projection です。通常の本体モデルの projection や decode 中の drafter 処理を切り替える変数ではありません。

## 値と判定

CUDA と SYCL の各 `Prefill::draft_kv` にある関数内 `static const bool` で、環境変数の値を最初の1文字だけで判定します。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（先頭文字が `\0`） |
| 先頭文字が `1` | 有効。`1`, `10`, `1anything` など |
| それ以外 | 無効。`0`, `true`, `2`, 空白で始まる値など |

文字列全体の比較、数値変換、大文字小文字の処理はありません。判定結果は各 backend のプロセス内で初回にこの関数が判定箇所まで到達したときに static cache され、後から環境値を変えても更新されません。

根拠: `src/prefill/prefill.cpp:1386-1388`、`sycl/src/prefill/prefill.cpp:1345-1347`。

## 有効になる条件

この変数は、`Prefill::draft_kv` のバッチ処理が呼ばれ、MMQ を使える条件でのみ projection の方式を変えます。具体的には、`STRATA_MTP_BATCH` でバッチ経路を無効にしていないこと、prompt scratch やモデル・drafter tensor が揃うこと、drafter と prefill が同じ device にあること、K/V mode・embedding などの前提を満たすことが必要です。これらを満たさず関数が先に decline した場合、`STRATA_MTP_BATCH_F16` の値は読まれず、バッチ経路が可能なら通常の `mtp.prefill(...)` に進みます。

単一 GPU の prompt 経路は MTP 使用時に `draft_kv` を試します。layer split では CUDA の `STRATA_SPLIT_MTP_BATCH` が有効で、さらに split 側に必要な GGUF 形式の embedding がある場合に限り試行されます。SYCL の prompt callback も MTP 使用かつ単一 GPU の条件で試します。

さらに、環境変数が unset/無効でも `mmq::built()` が false、または Q8_0 projection の寸法が `mmq::fits()` を満たさない場合は Q8 MMQ を選ばず、native GEMM になります。この場合 `STRATA_MTP_BATCH_F16` を有効にしても、その分岐に関する追加の切り替えはありません。

根拠: `src/prefill/prefill.cpp:1346-1358,1386-1388`、`sycl/src/prefill/prefill.cpp:1305-1317,1345-1347`、`src/program/generate.cpp:8092-8106,12474-12480`、`sycl/src/program/generate.cpp:7665-7670`。

## 実行時の詳細

バッチ関数は `q8 = !f16_only && mmq::built() && mmq::fits(Q8_0, Nn) && mmq::fits(Q8_0, KV)` と決めます。`STRATA_MTP_BATCH_F16` の先頭が `1` なら `f16_only` が true になり、MMQ 条件を満たしても `q8` は false です。`q8` が false のとき、embedding と hidden の正規化出力を `to_f16` で FP16 に変換し、projection lambda は `m.gemm.native(x16, Q8_0, w, ...)` を呼びます。K/V projection も同じ native 分岐を使います。無効値で MMQ が利用可能かつ寸法適合なら、代わりに中間入力を Q8_0 に量子化して `m.mmq_ctx->run(...)` を呼びます。

この経路で計算された K/V は drafter の K/V cache に append されます。失敗や前提不足でバッチ処理が decline すれば呼び出し側が drafter 自身の prefill 経路へ fallback します。コードはこの環境変数自体について専用のログやエラーを出しません。generate/serve の snapshot 検証ログ等は別の環境変数に依存します。

CUDA と SYCL の判定および projection 選択は同じ形です。資料 `docs/DETAILS.md` にはこの変数固有の説明や性能測定値を確認できなかったため、効果・性能はソースの分岐以上には述べません。

根拠: `src/prefill/prefill.cpp:1386-1388,1432-1441,1468-1487`、`sycl/src/prefill/prefill.cpp:1345-1347,1395-1405,1444-1469`、`src/program/generate.cpp:12474-12480`、`docs/DETAILS.md`。
