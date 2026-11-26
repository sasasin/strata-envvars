# `STRATA_Q36_VERIFY`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Qwen3.6 専用 engine の decode 用最適化 kernel と、従来 kernel の結果を実行時に比較する診断スイッチ。新しい kernel が実際の activation で旧 kernel と一致するかを調べる用途で、未設定なら比較を行わない。検査対象は `q8_small`、`add_rms`、`shared_gu`、router/grouping、`moe_out` など、コードに比較経路がある箇所に限られる（[q36_engine.cu:2405-2425](../../../../Niko1221/Strata/engine/src/qwen35/q36_engine.cu)、[q36_engine.cu:2444-2454](../../../../Niko1221/Strata/engine/src/qwen35/q36_engine.cu)、[q36_engine.cu:2505-2523](../../../../Niko1221/Strata/engine/src/qwen35/q36_engine.cu)、[q36_engine.cu:2637-2645](../../../../Niko1221/Strata/engine/src/qwen35/q36_engine.cu)、[q36_engine.cu:2671-2695](../../../../Niko1221/Strata/engine/src/qwen35/q36_engine.cu)）。

この変数は生成結果を比較・選択するものではない。新 kernel の出力は通常どおり後続計算に使われ、旧 kernel の出力は比較用 scratch に計算される。比較不一致は記録・stderr 出力されるが、この変数の分岐自体は不一致を理由に生成を中断したり旧出力へ切り替えたりしない（[q36_engine.cu:2411-2424](../../../../Niko1221/Strata/engine/src/qwen35/q36_engine.cu)、[q36_engine.cu:2509-2523](../../../../Niko1221/Strata/engine/src/qwen35/q36_engine.cu)）。

## 値と判定

`Engine` のメンバー初期化時に `std::getenv("STRATA_Q36_VERIFY") != nullptr` だけで判定する。文字列の変換・比較はしないため、環境変数が存在すれば値が空でも有効。未設定だけが無効であり、`0`、`false`、`off` も有効になる（[q36_engine.cu:2405-2408](../../../../Niko1221/Strata/engine/src/qwen35/q36_engine.cu)）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| Qwen3.6 engine の全実行経路 | 比較しない | `1`、`true`、`false`、`0`、空文字など、設定されている値すべて | なし（値の内容は判定しない） |

## 有効になる条件

- GGUF の model family が `qwen35moe` と判定され、Qwen3.6 専用 `strata::qwen35::run` engine に入ること。他の model family はこの読み取り箇所を通らない（[generate.cpp:3804-3818](../../../../Niko1221/Strata/engine/src/program/generate.cpp)、[q36_engine.cu:1-3](../../../../Niko1221/Strata/engine/src/qwen35/q36_engine.cu)）。
- 検査対象 kernel 経路が選ばれること。最適化 kernel の検査は `fast_k` が true の場合だけ行う。`STRATA_Q36_OLD_KERNELS` が設定されると `fast_k` が false になり、`q8_small`、`add_rms`、`shared_gu`、route/group、`moe_out` の新 kernel 比較経路は使われない（[q36_engine.cu:2405-2407](../../../../Niko1221/Strata/engine/src/qwen35/q36_engine.cu)、[q36_engine.cu:2429-2431](../../../../Niko1221/Strata/engine/src/qwen35/q36_engine.cu)、[q36_engine.cu:2508-2509](../../../../Niko1221/Strata/engine/src/qwen35/q36_engine.cu)、[q36_engine.cu:2532-2535](../../../../Niko1221/Strata/engine/src/qwen35/q36_engine.cu)、[q36_engine.cu:2626-2629](../../../../Niko1221/Strata/engine/src/qwen35/q36_engine.cu)、[q36_engine.cu:2671-2675](../../../../Niko1221/Strata/engine/src/qwen35/q36_engine.cu)）。
- `--no-graph` を指定して eager launch にすること。既定では graph が有効で、単一 token decode は graph capture 内で `forward` を呼ぶ。一方、比較関数は stream 同期と device-to-host copy を実行する。Qwen3.6 の説明資料も `STRATA_Q36_VERIFY=1` と `--no-graph` の組み合わせを指定している（[q36_engine.cu:5344-5347](../../../../Niko1221/Strata/engine/src/qwen35/q36_engine.cu)、[q36_engine.cu:3612-3634](../../../../Niko1221/Strata/engine/src/qwen35/q36_engine.cu)、[q36_engine.cu:3707-3710](../../../../Niko1221/Strata/engine/src/qwen35/q36_engine.cu)、[q36_engine.cu:2411-2415](../../../../Niko1221/Strata/engine/src/qwen35/q36_engine.cu)、[docs/QWEN36.md:115-119](../../../../Niko1221/Strata/docs/QWEN36.md)）。
- `STRATA_Q36_VERIFY` による CLI 値や別環境変数との優先順位はない。CLI の `--no-graph` は比較を有効化せず、graph を切って比較経路を実行可能にする条件である（[q36_engine.cu:5346-5372](../../../../Niko1221/Strata/engine/src/qwen35/q36_engine.cu)）。

## 実行時の詳細

値はモデルをロードした後に作られる `Engine E` のメンバー初期化で一度読み取られ、`verify_k` に保持される。比較条件ごとに同じ環境変数を再読込することはないため、engine の実行中に環境を変更しても反映されない（[q36_engine.cu:2405-2408](../../../../Niko1221/Strata/engine/src/qwen35/q36_engine.cu)、[q36_engine.cu:5458-5467](../../../../Niko1221/Strata/engine/src/qwen35/q36_engine.cu)）。

比較時は stream を同期し、新旧の device buffer を host vector にコピーし、`memcmp` で bit 単位に比較する。不一致時は最初に異なる要素の index、件数、new/old の数値と bit pattern を出力する。Router と grouping のように専用比較処理を使う箇所もある。検査は追加の kernel 実行、同期、host copy を伴うため、通常実行より診断処理が増える（[q36_engine.cu:2411-2424](../../../../Niko1221/Strata/engine/src/qwen35/q36_engine.cu)、[q36_engine.cu:2586-2621](../../../../Niko1221/Strata/engine/src/qwen35/q36_engine.cu)）。

このスイッチが設定されると、短い batch の router 経路で router と shared-expert gate をまとめた `router_ext` projection を使う条件も外れる（`!verify_k` が必要）。したがって検査時にはその router 経路も通常時と異なる（[q36_engine.cu:2895-2901](../../../../Niko1221/Strata/engine/src/qwen35/q36_engine.cu)）。

## ログと測定値

不一致時は stderr に `strata-q36 VERIFY MISMATCH ...` を出す。一般的な比較では各比較名につき先頭 3 件まで不一致詳細を出し、終了時に `strata-q36 VERIFY: <comparisons> comparisons, <mismatches> mismatches` と比較名ごとの不一致数を出力する。grouping 比較は別経路で、全体の不一致が先頭 20 件まで `strata-q36 VERIFY MISMATCH group ...` と出る（[q36_engine.cu:2417-2423](../../../../Niko1221/Strata/engine/src/qwen35/q36_engine.cu)、[q36_engine.cu:2618-2621](../../../../Niko1221/Strata/engine/src/qwen35/q36_engine.cu)、[q36_engine.cu:5528-5534](../../../../Niko1221/Strata/engine/src/qwen35/q36_engine.cu)）。

比較処理の CUDA API 呼び出しは `CK` 経由であり、API エラー時はそのエラーハンドリング経路に入る。不一致自体については mismatch を数えるだけで、停止や旧 kernel への fallback はない（[q36_engine.cu:2411-2424](../../../../Niko1221/Strata/engine/src/qwen35/q36_engine.cu)）。

Qwen3.6 の説明資料は、実 activation で旧 kernel と bitwise 比較する利用例を記載している。ここでは資料の性能測定値をこの診断変数の効果として扱わない（[docs/QWEN36.md:115-127](../../../../Niko1221/Strata/docs/QWEN36.md)）。

## 根拠

- `engine/src/qwen35/q36_engine.cu:2405-2424` — 判定、比較処理、不一致ログ。
- `engine/src/qwen35/q36_engine.cu:2444-2695` — 個別の kernel 比較経路。
- `engine/src/qwen35/q36_engine.cu:2895-2901` — verify 有効時に変わる router 経路。
- `engine/src/qwen35/q36_engine.cu:5344-5372,5458-5467,5528-5534` — CLI の graph 既定値、engine 初期化、終了時レポート。
- `engine/src/program/generate.cpp:3804-3818` — model family による専用 engine 選択。
- `docs/QWEN36.md:115-119` — 文書中の使用例と `--no-graph` 指定。
