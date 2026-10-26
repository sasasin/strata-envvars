# `DS4_BENCH_WIN`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

DeepSeek V4.1 の i-quant GPU ベンチマーク `ds4_iq_test --bench-big` で、expert ごとの group に含める entry 数を指定します。これは `tests/dsv41/iq_expert_test.cpp` にあるベンチマーク専用のフックです。同名の読み取りはこの一箇所だけで、エンジンの `strata-dsv41` や通常の Strata 実行コードからは参照されません。

## 値と判定

`bench_big()` が呼ばれた時点で `std::getenv()` により設定有無を調べ、設定されていれば `std::atoi()` で整数変換します。変換結果は 1〜16 に clamp されます。

| 環境変数の状態・値 | `NW` | ベンチ経路 |
|---|---:|---|
| unset | 0 | token 経路（`plan_ptr` を設定） |
| 空文字 | 1 | window 経路（`grp_ptr` を設定） |
| 数値として 1〜16 | その値 | window 経路 |
| 数値として 0 または負数 | 1 | window 経路 |
| 16 より大きい数値 | 16 | window 経路 |
| 数字で始まらない文字列 | 1 | `atoi()` が 0 を返すため window 経路 |

`atoi()` は文字列全体の厳密な検証をしません。先頭の空白と符号を許容し、数値の後ろに文字があっても数値部分を使います（例: `4tail` は 4）。設定値が空文字または数値に変換できない文字列でも、変数自体が設定済みなので clamp 後の `NW` は 1 です。

## 有効になる条件

- `ds4_iq_test` をビルドできる構成が必要です。CMake では `STRATA_BUILD_DSV41=ON` かつ `STRATA_HIP_GFX906` ではない場合に DeepSeek engine 関連ターゲットが追加され、`STRATA_NATIVE_EXPERTS` の条件内で `ds4_iq_test` が定義されます。
- この変数を読む `bench_big()` は、実行時に `--bench-big` を指定したときだけ呼ばれます。通常の `ds4_iq_test` parity 確認、`--bench`、`--bench-light` などには作用しません。
- `NW == 0` のときは `plan_ptr` に layer の plan を設定し、`iq::gate_up()` / `iq::down()` に group size 1 を渡します。`NW > 0` のときは `grp_ptr` と group 境界・entry index を設定し、同じ呼び出しに group size `NW` を渡して window 経路を測定します。window 経路でも1 groupあたりの expert 数は `NE=6` です。
- `NW` は読み取り後、ベンチ関数の配列サイズ、group 境界、GPU出力バッファサイズ、kernel 呼び出しに使われます。プロセス内で static cache されず、`bench_big()` ごとに読み取ります。プロセス起動後に環境を書き換えるケースは、このテストコードでは扱っていません。

この変数を設定してもモデル推論や通常の実行時処理は切り替わりません。`DS4_BENCH_ACTIVE` は別のベンチ用変数として plan の空 entry を作る用途で読み取られますが、その詳細はこの文書の対象外です。

## 実行時の詳細

`bench_big()` は、6 experts 分のデータを繰り返し配置した合成 working set を作り、gate/up と down の処理を分けて GPU event で計測します。`NW` が正なら1 expert group あたり `NW` entries を構成し、その値に応じた grouped-entry (`grp_ptr`) 経路を反復します。未設定なら既存の token plan (`plan_ptr`) 経路です。測定行は `big ... gate/up ... down ...` の形式で標準出力へ出ます。これはベンチ測定値であり、通常推論の速度や結果を示すものではありません。

`docs/DETAILS.md` と `docs/DEEPSEEK41.md` を確認しましたが、`DS4_BENCH_WIN` の説明や測定値は見つかりませんでした。したがって性能上の比較・効果は記載していません。

## 根拠

- `tests/dsv41/iq_expert_test.cpp:224-249` — `bench_big()` のworking set、変数の parse/clamp、entry 数と group 境界の構築。
- `tests/dsv41/iq_expert_test.cpp:252-273` — `NW` に応じた token/window 経路の選択、kernel 呼び出し、標準出力の計測結果。
- `tests/dsv41/iq_expert_test.cpp:330-359` — `--bench-big` から `bench_big()` を呼ぶ CLI 経路。
- `CMakeLists.txt:797-801,845-883` — DeepSeek engine 条件と `STRATA_NATIVE_EXPERTS` 配下の `ds4_iq_test` ターゲット。
