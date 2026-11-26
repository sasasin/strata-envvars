# `STRATA_QSA_DUMP_LAYER`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

QSA の選択セルを `STRATA_QSA_DUMP` のファイルへ追記する診断用処理で、記録対象を QSA layer の番号で絞ります。通常の推論処理や選択結果を変える分岐ではなく、該当する QSA layer の選択 ID をホストへコピーしてダンプに記録するかどうかだけを変えます。読み取り箇所は CUDA/HIP 用 prefill 実装の `engine/src/prefill/prefill.cpp` です（同ファイル:5512-5523）。

## 値と判定

この値は `std::getenv` が返す文字列を `std::atoi` で `int` に変換します。文字列全体の妥当性検査、clamp、エラー処理はありません。unset は `-1` となり、`only < 0` の条件で全 QSA layer を対象にします。設定値が 0 以上なら、その番号と現在の QSA ordinal が一致する layer だけを対象にします（同ファイル:5515-5516）。

| 条件 | unset | 選択対象になる値の例 | 全 layer になる値の例 | 指定 layer に一致しない値の例 |
|---|---|---|---|
| CUDA/HIP prefill で `STRATA_QSA_DUMP` が設定されている | `-1` に相当し、全 QSA layer | `0`, `1`, `12`（対応する ordinal のみ） | `-1`, `-2`（負数はすべて全 layer） | `5`（ordinal 5 以外） |

空文字、数字以外で始まる文字列、空白だけの文字列は `atoi` により `0` になります。したがって、たとえば `""`、`true`、`0anything` は ordinal 0 を指定します。前後の空白や符号は `atoi` の整数変換規則に従い、数値の後ろにある文字列は検証されません。`+2tail` は 2、`-2tail` は負数として全 layer です。int の範囲を超える文字列は有効な入力として扱えず、変換結果は保証されません。なお `STRATA_QSA_DUMP` が unset ならこの変換自体が行われません（同ファイル:5512-5516）。

## 有効になる条件

- CUDA または HIP backend の GPU engine が必要です。CMake は CUDA/HIP の GPU engine 内で `src/prefill/prefill.cpp` を `strata_prefill` に含めます（`engine/cmake/strata_gpu_engine.cmake:6-9,478-488`）。
- `STRATA_QSA_DUMP` が設定されていなければ、layer filter を含む記録ブロックに入りません。空文字でも `getenv` は非 null なのでブロックに入りますが、その値でファイルを開けるとは限りません（`engine/src/prefill/prefill.cpp:5512,5520`）。
- プロンプト処理が QSA layer の該当箇所まで進み、`p0 + T > pos0 + n - last` を満たす必要があります。`last` は別変数 `STRATA_QSA_DUMP_LAST`（未設定時 4096）で決まり、この条件を満たさないチャンクは記録しません（同ファイル:5513-5516）。
- layer 番号はモデル全体の layer 番号でなく QSA layer の ordinal です。チャンク開始前にそれまでの QSA layer 数を数え、各 QSA layer の処理後に ordinal を増やしています（同ファイル:4594-4595, 5222-5225, 5575）。
- SYCL 用 `engine/sycl/src/prefill/prefill.cpp` にも `STRATA_QSA_DUMP` の記録処理がありますが、そこでは `STRATA_QSA_DUMP_LAYER` を読まず、layer による絞り込みもありません（`engine/sycl/src/prefill/prefill.cpp:3820-3843`）。この変数は SYCL 経路では効果がありません。
- この読み取り箇所に CLI 引数や設定ファイルとの優先順位処理はありません。

## 実行時の詳細

`STRATA_QSA_DUMP`、`STRATA_QSA_DUMP_LAST`、`STRATA_QSA_DUMP_LAYER` はブロック内 `static` として保持されます。各値は最初に該当箇所へ到達したときに評価され、その後プロセス内では再読込されません。初回に `STRATA_QSA_DUMP` が unset なら `dump` は null のままなので、実行中に環境を変更しても記録処理は有効になりません。初回に dump path が設定されていた場合も、layer 値を含む各値はキャッシュされ、後からの変更は反映されません（`engine/src/prefill/prefill.cpp:5512-5516`）。

条件に一致すると選択 ID をホストへコピーして stream を同期し、ファイルを append モードで開きます。開けた場合は `{qsa ordinal, p0, T, cap}` の 4 個の int32 header と `T * cap` 個の選択 ID を書き込みます。別変数 `STRATA_QSA_DUMP_STEPS` が設定されていれば、その後に step record も追記します（同ファイル:5516-5529）。この環境変数はこの記録対象の選択だけを変え、QSA の選択計算や後続 attention 計算の分岐には使われません。

## ログと測定値

この変数専用のログや測定値はありません。ファイルを開けなかった場合は `fopen` の失敗を検査せず、記録を飛ばします。`fwrite`、CUDA copy、stream 同期の戻り値もこのブロックでは検査せず、明示的な警告・エラー出力やエラー返却はありません（`engine/src/prefill/prefill.cpp:5517-5529`）。

## 根拠

- 読み取り、整数変換、ordinal filter、ダンプ処理: `engine/src/prefill/prefill.cpp:5512-5529`
- ordinal の開始値と QSA layer 判定: `engine/src/prefill/prefill.cpp:4594-4595,5222-5225,5575`; `engine/include/strata/core/geometry.hpp:88-90`
- CUDA/HIP 用 prefill target: `engine/cmake/strata_gpu_engine.cmake:6-9,478-488`
- SYCL 側に layer filter がないダンプ実装: `engine/sycl/src/prefill/prefill.cpp:3820-3843`
