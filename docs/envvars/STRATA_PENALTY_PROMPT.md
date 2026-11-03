# `STRATA_PENALTY_PROMPT`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

繰り返し・頻度・存在ペナルティの履歴窓に、プロンプトを含めるかを切り替えます。既定では現在の返答側だけを数えます。値が有効なら従来の方式に戻り、プロンプトと返答を合わせた直近 `penalty_last_n` トークンを数えます。この変数自体はペナルティを有効化せず、係数や履歴長も設定しません。

Strata 所有ソースで値を読む箇所は、CUDA 系の通常生成 `src/program/generate.cpp`、SYCL 生成 `sycl/src/program/generate.cpp`、Qwen 3.6-35B-A3B 用 CUDA エンジン `src/qwen35/q36_engine.cu` です。候補名のその他の出現はコメント、文書、テスト、または helper 宣言です。

## 値と判定

共通 helper は環境変数文字列の先頭文字だけを検査します。`'1'` で始まる値だけが有効で、文字列全体の parse はありません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効（既定の reply-only 窓） |
| 空文字 | 無効 |
| `1`, `10`, `1anything` | 有効 |
| `0`, `true`, ` 1`, その他 `'1'` で始まらない値 | 無効 |

大文字小文字、空白、数値としての妥当性は検査されません。無効値への警告や fallback エラーはありません。根拠: `include/strata/kernels/sampler.hpp:94-104`、`sycl/include/strata/kernels/sampler.hpp:69-79`。

## 有効になる条件

- プロセスに組み込まれた上記生成経路で、repeat / frequency / presence のいずれかのペナルティと正の `penalty_last_n` が使われると、変更された履歴窓が効果を持ちます。ペナルティ係数が既定の無効値である、または履歴長が 0 の場合、この変数だけを設定してもペナルティ処理は始まりません。通常生成ではリクエスト値を `req_sp` に設定し、`penalty_last_n` は 0 未満を 0 にしてから履歴長上限で制限します（`src/program/generate.cpp:17138-17150,17180-17189`、SYCL は `sycl/src/program/generate.cpp:11068-11090`）。
- Qwen 3.6-35B-A3B 経路では、リクエストの `penalty_last_n`、`penalty_repeat`、`penalty_freq`、`penalty_present` が別途サンプリング設定です（`src/qwen35/q36_engine.cu:3453-3462`）。履歴長 0 または全係数が無効なら環境変数による履歴範囲変更は実際のペナルティを生じさせません (`include/strata/qwen35/sampling.hpp:13-17,24-35`)。
- 通常生成の継続リクエストでは、既定の reply-only 窓は `pen_from` で元の返答開始位置まで戻されることがあります。プロンプトを数えるモードではその調整をしません（`src/program/generate.cpp:17432-17437,18932-18936`; SYCL は `sycl/src/program/generate.cpp:11228-11232,12497-12501`）。
- 読み取り箇所に OS や backend 固有の値判定分岐はありません。各バイナリに該当生成ソースが含まれるかはビルド経路によります。

## 実行時の詳細

通常生成は最初にこの設定を必要とするリクエストに到達した時点で読み、関数内の `static const bool` に保持します。同じプロセスの後続リクエストや batch slot もこの判定を共有し、実行中に環境値を変更しても再評価しません（`src/program/generate.cpp:17180-17189`; SYCL の対応箇所: `sycl/src/program/generate.cpp:11084-11091`）。Qwen エンジンも生成処理で同じ形式の static 値として保持します（`src/qwen35/q36_engine.cu:3570-3575`）。

通常生成では helper が返す値に応じて、履歴の開始位置を prompt 全体の先頭（旧方式）または decode 開始時の prompt 末尾（既定方式）にします。その履歴と各 verify row の token を `penalty_rows` で行ごとに組み立て、sampler に渡します（`include/strata/kernels/sampler.hpp:100-124`; `src/program/generate.cpp:17433-17437,18442-18451`; SYCL は `sycl/src/program/generate.cpp:11228-11232,12103-12114`）。履歴が変わることで、設定済みの penalty が適用される token が変わります。CUDA sampler は履歴中にある token の logit に repeat / frequency / presence の補正を行います（`src/kernels/cuda/sampler.cu:87-99,308-316`）。

Qwen 3.6-35B-A3B では有効時にプロンプト全体を初期履歴にし、既定時には空でないプロンプトの最終 token だけを初期履歴にします。その後、生成した token を履歴に追加して sampling します（`include/strata/qwen35/sampling.hpp:24-45`; `src/qwen35/q36_engine.cu:3570-3574,3618-3633`）。

この環境変数に由来するログ、警告、終了・失敗経路は実装されていません。値の不正形式も無効判定になるだけです。通常生成では penalty が有効なのに sampler に履歴が渡らない場合は別途 stderr に `sample_tokens: penalty_last_n ... needs a history ...` を出して終了しますが、環境値がその失敗を直接起こす分岐はありません（`src/kernels/cuda/sampler.cu:1260-1268`）。

## 根拠

- 環境値の直接読み取り: `src/program/generate.cpp:17187`, `sycl/src/program/generate.cpp:11089`, `src/qwen35/q36_engine.cu:3573`。
- 共通の先頭文字判定と履歴開始位置: `include/strata/kernels/sampler.hpp:94-104`, `sycl/include/strata/kernels/sampler.hpp:69-79`。
- Strata の説明との照合: `docs/DETAILS.md:560-566` は既定の reply-only 窓と `STRATA_PENALTY_PROMPT=1` による旧窓を説明しています。ここでは測定値を記載していません。
