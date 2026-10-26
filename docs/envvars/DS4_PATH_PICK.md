# `DS4_PATH_PICK`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

DeepSeek V4.1 の CUDA/HIP モデル読み込み時に行う、prompt の処理経路選択用の速度較正を止める変数です。較正では GPU への DMA、RAM から staging buffer への読み込み、可能な場合はディスク読み込み、CPU lane の expert 計算を計測します。この変数は flow と windows のどちらを直接選ぶものではありません。

## 値と判定

値は `std::atoi()` で整数変換され、結果が `0` なら較正をスキップします。変数が未設定ならこの判定に入らず、較正を試みます。

| 値 | 結果 |
|---|---|
| unset | 較正を試みる |
| `0`、空文字、数字で始まらない文字列 | `atoi` の結果が 0 となり、較正をスキップ |
| `1`、`-1`、`2tail` など、`atoi` の結果が 0 以外 | 較正を試みる |

`atoi` は文字列全体の厳密な検証をしません。先頭の空白と符号を許し、数字の後ろは無視します。たとえば `0tail` は 0 としてスキップし、`2tail` は 2 として較正します。オーバーフローする値の挙動はこの実装から保証できません。

根拠: `src/dsv41/ds4_model.cu:7795-7799`。

## 有効になる条件

環境変数によるスキップ判定より前に、次のいずれかに当たると較正関数は戻ります。

- chunked prompt path が無効（`chunk <= 0`）。
- `chunk_min` が既定の flow 最小値 `2` ではない。
- `DS4_CHUNK_MIN` が設定されている（値が何であっても）。

その後も、flow 用 chunk があるデバイスを見つけられない場合や、測定用の CPU-lane expert がない場合などは一部または残りの計測を行いません。測定が成立するには DMA・RAM copy・CPU 計算の各速度が正である必要があり、ディスク速度の取得は必須ではありません。

較正値に基づく経路選択を行うのは、別変数 `DS4_PICK` が文字列全体で `adaptive` と一致する場合だけです。未設定または別の値なら、経路選択は `DS4_PICK_MIN` による prompt 長の基準を使い、`DS4_PATH_PICK` が較正を許可しても選択方式は adaptive になりません。`DS4_PATH_PICK=0` も flow を強制しません。

根拠: `src/dsv41/ds4_model.cu:7795-7802,7919-7927,7990-7997`。

## 実行時の詳細

`calibrate_paths()` はモデル読み込み処理中、worker 起動後、store 初期化前に呼ばれます。したがって、環境変数はモデル読み込み時に評価されます。プロセス実行中に値を変更しても、読み込み済みモデルの較正結果はやり直されません。別モデルを読み込むときは再度関数が実行され、その時点の環境値で判定します。

未設定または `atoi` 結果が非ゼロの場合、較正は staging から GPU ring への転送、RAM から staging への job copy、cold expert のディスク read（条件を満たす場合）、CPU expert 計算を測ります。成立した計測値は `pm` に保存されます。verbose mode では stderr に `ds4: prompts through the flow or windows by this PC's speeds: ...` の行を出します。`atoi` 結果が 0 の場合、この較正とその行は実行されません。

`DS4_PICK=adaptive` で較正値が利用可能なとき、prompt feed は予測した flow と windows の時間および sampled page residency を見て経路を選びます。較正が無効・利用不可の場合、adaptive 分岐も flow を選ぶ既定経路に進みます（ただし呼び出し元で chunk 条件を満たす場合）。

根拠: `src/dsv41/ds4_model.cu:2811-2822,7795-7927,7990-8046,9360-9367`。

## 文書との照合

`docs/DETAILS.md` に `DS4_PATH_PICK` の説明は見つかりませんでした。ここでは HEAD の実装を根拠に記述しています。コードコメントにある性能測定値は実測を再確認していないため、この調査結果には転記していません。

## 根拠

- `src/dsv41/ds4_model.cu:7790-7802` — 較正関数と環境変数判定。
- `src/dsv41/ds4_model.cu:7805-7927` — DMA、RAM copy、disk、CPU lane の計測と verbose 出力。
- `src/dsv41/ds4_model.cu:2811-2822` — load 中の呼び出し位置。
- `src/dsv41/ds4_model.cu:7990-8046,9360-9367` — adaptive 経路判定と prompt feed での利用。
