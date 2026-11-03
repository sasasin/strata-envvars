# `DS4_LANE_CHECK`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DeepSeek-V4.1 用 `strata-dsv41` の PCIe lane 初期化時に、CPU lane と GPU lane で同じ expert を計算し、出力の一致度を stderr に出す診断フックです。通常の生成結果を切り替える設定ではありません。値が設定されていると、lane の計測クラスごとに最大 4 expert を比較します。`src/dsv41/ds4_model.cu:10420-10427,10591-10596,10645-10647,10661-10670`。

## 値と判定

| 環境の状態 | 判定 |
|---|---|
| 未設定 | lane 比較診断を呼ばない |
| 空文字を含む任意の設定値 | lane 比較診断を呼ぶ |

`std::getenv("DS4_LANE_CHECK") != nullptr` の有無だけを判定し、値を数値・真偽値として変換しません。したがって `0`、`false`、空文字も設定されていれば有効です。無効値扱い、範囲、clamp、CLI 引数や設定ファイルによる上書きはありません。`src/dsv41/ds4_model.cu:10595`。

## 有効になる条件

- 対象コードは CMake の `STRATA_BUILD_DSV41` が有効で、かつ `STRATA_HIP_GFX906` ではない場合に追加される `strata-dsv41` 実行ファイルの一部です。通常の `strata` 実行経路にこの読み取りはありません。`CMakeLists.txt:931-945`。
- lane の割り当ては GGUF モデルで、`moe_token_path` が有効、`sync_decode` でなく、`DS4_STREAM` または fallback の `STRATA_DS4_STREAM` が設定値として 0 にならない場合に進みます。未設定時は lane を割り当てないため診断も実行されません。`src/dsv41/ds4_model.cu:9711-9719,9753-9755`。
- モデル読み込み後の `lane_setup()` で PCIe lane の staging buffer が確保され、対応するレイヤー形式・expert 配置を持つクラスが作られる必要があります。対象レイヤーは `lane_layer_ok()` の条件（非 MTP、単一 GPU、MXFP4、expert 数など）を満たし、少なくとも 1 expert が VRAM 外にある必要があります。`src/dsv41/ds4_model.cu:10420-10427,9722-9725,9753-9784,10431-10450`。
- クラスの CPU/GPU lane 計測が成功し `C.cost.ok()` である場合にだけ診断を呼びます。計測失敗時は lane を CPU のみにするログが出て、そのクラスでは比較をしません。`src/dsv41/ds4_model.cu:10555-10596`。
- `DS4_STREAM`（または fallback の `STRATA_DS4_STREAM`）は lane 自体の割り当てを止める条件に関わりますが、`DS4_LANE_CHECK` の値判定を置き換えません。lane の計画が実際に一部 expert を stream するかどうかは別判定です。診断呼び出しは `C.stream` の算出後、`C.cost.ok()` を条件としているため、`C.stream == false` のクラスでも計測成功時には比較されます。`src/dsv41/ds4_model.cu:9711-9725,9753-9756,10591-10596`。

## 実行時の詳細

モデル初期化では `calibrate_paths()` の後、`one_gpu_plan()` の前に `lane_setup()` が呼ばれます。lane setup は利用可能な GPU ごと・形式ごとのクラスを計測し、各クラスの計測結果が有効なとき、環境変数の設定有無を読み直して `lane_check()` を実行します。static cache はなく、診断結果は環境変数へ書き戻されません。`src/dsv41/ds4_model.cu:3789-3793,10420-10427,10431-10450,10591-10596`。

比較用入力は `sin(0.71 * i)` を基礎に各 97 要素目へ 6 を加え、平均二乗値が 1 になるよう正規化します。クラス選択時に集めた CPU lane 側 expert のうち先頭 4 件までを使い、CPU の `cpu_experts()` 出力と、expert 1 個・weight 1 の GPU `moe_gate_up()` / `moe_down()` 出力を比較します。bit-identical な要素数、最大絶対差、CPU 出力最大値に対する最大相対差を stderr に出します。`lane_pull_cal()` が失敗した回は `n_bad` を増やして比較を続け、末尾に ` - a copy FAILED` を付けます。`src/dsv41/ds4_model.cu:10651-10707`。

出力形式は `ds4: lane check: ...: an expert on the CPU lane vs streamed to CUDA%d: ... bit-identical, max |diff| ...` です。この関数は `void` で、比較結果やコピー失敗数を生成処理の成否へ返しません。確認できる出力・失敗表示はこの stderr 行であり、この診断自体がプロセスを終了させる分岐はありません。`src/dsv41/ds4_model.cu:10647,10669-10708`。

比較対象となる GPU lane 計算の量子化経路は別設定 `DS4_IQ_Q8K` でも変わります。`src/dsv41/ds4_gguf.cu:267-276`。この環境変数の詳細は本書の対象外です。

## 根拠

- 環境変数の全ソース参照（実際の読み取りは 1 箇所）: `src/dsv41/ds4_model.cu:10595`。他の出現はコメントです（`src/dsv41/ds4_model.cu:9616,9623,10645-10646`）。
- 呼び出し順と lane 初期化: `src/dsv41/ds4_model.cu:3789-3793,10420-10427,10431-10450`。
- 比較条件、出力、コピー失敗表示: `src/dsv41/ds4_model.cu:10591-10596,10647-10708`。
- ビルド対象: `CMakeLists.txt:931-945`。
- `docs/DETAILS.md` および関連設計資料に、この変数の独立した説明や測定値は見つかりませんでした。
