# `DS4_DBG_GG`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

DeepSeek-V4.1 エンジンの GGML block type 用 CPU lane で、形式選択・活性値量子化・GGML の row dot に関する診断行を stderr に出します。計算方式や返り値を切り替える用途ではありません。対象名の直接参照は `src/dsv41/ds4_gg_cpu.cpp` の `dbg()` だけで、同ファイル内の複数箇所からこの関数が使われます。

## 値と判定

`std::getenv("DS4_DBG_GG") != nullptr` で判定します。値の文字列や数値は parse せず、環境変数が存在するかだけを見ます。

| 状態 | `dbg()` の結果 |
|---|---|
| 未設定 | 無効 |
| 空文字を設定 | 有効 |
| `0`、`false`、その他の任意の文字列を設定 | 有効 |

`dbg()` の結果は関数内の `static const bool` に保存されます。最初の呼び出し時に一度評価され、その後プロセス内で環境を書き換えても反映されません。

## 有効になる条件

この環境変数を読む実装は `STRATA_DSV41_TQ_CPU` が定義されたときだけコンパイルされます。CMake では `STRATA_BUILD_DSV41` が有効で、`STRATA_NATIVE_EXPERTS` が有効な場合に `strata-dsv41` へこの定義を付けます。`STRATA_BUILD_DSV41` は既定で OFF です。定義がないビルドでは同ファイルの stub 実装が使われ、`DS4_DBG_GG` は読み取られません。

実行時には、GGML block type の CPU lane が呼ばれた箇所に限って診断行が出ます。`ds4_iq_cpu.cpp` は GGML 型なら `gg_cpu_fmt` / `gg_cpu_quant` / `gg_cpu_gate_up` / `gg_cpu_down` に振り分けます。対応型でない経路、またはこの CPU lane を通らない処理には影響しません。

## 実行時の詳細

有効時の出力は以下です（値は実行時引数から埋め込まれます）。すべて `stderr` への `fprintf` で、条件を通ったときだけ出ます。

- `gg_cpu_fmt %d %d`: `gg_cpu_fmt` に渡された gate/down の型番号。
- `gg_cpu_quant act %d k %d`: 量子化する activation 型番号と要素数。
- `gg_cpu_quant: no cpu from_float, ref %p`: CPU の `from_float` 関数がないため参照実装へ進む場合のポインタ。
- `gg dots type %d n %d rows %d..%d nt %d`: GGML の row dot ループを実行する場合の型・次元・row 範囲・token 数。
- `ds4: CPU lane type %d: AVX2 rows differ from ggml-cpu's dot at %d tokens, not used`: AVX2 row の照合が不一致となった場合の警告。これは `DS4_DBG_GG` または別変数 `DS4_GG_VERBOSE` が設定されている場合に出ます。

AVX2/AVX-512 row 実装を選んで早期 return する dot 経路では、最後の `gg dots ...` は出ません。この変数によって CPU lane の選択、照合条件、数値結果が変わる分岐は見つかりませんでした。

## 根拠

- `src/dsv41/ds4_gg_cpu.cpp:46-48,74-84,140-143,217-232`: 設定有無の判定、static cache、診断出力と `DS4_GG_VERBOSE` との関係、row dot の実行経路。
- `src/dsv41/ds4_iq_cpu.cpp:760-777`: GGML 型を GGML CPU lane に振り分ける呼び出し。
- `src/dsv41/ds4_gg_cpu.cpp:284-295`: `STRATA_DSV41_TQ_CPU` がない場合の stub 実装。
- `CMakeLists.txt:797-811,833-836`: `strata-dsv41` のビルド条件、既定 OFF の説明、`STRATA_NATIVE_EXPERTS` によるコンパイル定義。
- `docs/DETAILS.md`: `DS4_DBG_GG` に関する説明は見つかりませんでした。
