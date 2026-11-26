# `NATIVE_BENCH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

この変数は通常の Strata 推論エンジンの設定ではなく、SYCL 版の単体診断プログラム `native_expert_parity` に追加の GPU grouped-expert 計測を行わせるスイッチである。プログラムはまず1レイヤー分の通常の CPU/GPU parity 計算を行い、その後この変数が設定されていれば、同じ expert blob を使った固定サイズの grouped 呼び出しを計時して標準出力に表示する。通常の parity 判定や推論時の expert 選択を変更する分岐ではない（`engine/sycl/src/kernels/native_expert_parity.cpp:291-321,347-368`）。

`native_expert_parity` ターゲットは `STRATA_NATIVE_EXPERTS` が有効な SYCL ビルドで追加される。一般の Strata 実行ファイルに対して設定しても、このソースにある計測処理は実行されない（`engine/sycl/CMakeLists.txt:683-688`）。

## 値と判定

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| SYCL `native_expert_parity` | 計測を行わない | 値の内容を問わず、環境変数が存在すれば計測する（例: `1`、`0`、`false`、空文字） | なし。設定値の内容を検査しない |

判定は `std::getenv("NATIVE_BENCH") != nullptr` のみで、数値・真偽値への変換、文字列全体や先頭文字の比較、空白の除去はない。したがって `NATIVE_BENCH=` の空文字や `NATIVE_BENCH=0` も有効であり、未設定だけが無効である（`engine/sycl/src/kernels/native_expert_parity.cpp:321`）。

## 有効になる条件

- `STRATA_NATIVE_EXPERTS` を有効にしてビルドし、SYCL ターゲット `native_expert_parity` を実行する必要がある。通常の Strata 推論プロセスに同名変数を設定しても、ここで説明する処理経路には入らない（`engine/sycl/CMakeLists.txt:683-688`）。
- プログラムの引数・入力が有効なレイヤー処理に到達し、CPU/GPU parity 計算が完了する必要がある。GGUF に対象レイヤーの expert tensor がない場合や形式がサポートされない場合は、そのレイヤーを表示して失敗数を増やし、`continue` するため、計測分岐には到達しない（`engine/sycl/src/kernels/native_expert_parity.cpp:114-129,317-321`）。
- 通常の入力は GGUF shard と任意のレイヤー番号で、レイヤー番号を省略すると既定の `{0, 1, 2, 3, 20, 47}` を処理する。`--synthetic` 入力も同じレイヤー処理に進むため、この分岐の対象になる（`engine/sycl/src/kernels/native_expert_parity.cpp:81-92,97-114`）。
- 計測条件は環境変数以外に CLI 引数や別の環境変数で上書きされない。計測は固定して `G=10` expert groups、各 group `E=4` entries、`iters=20` 回とし、各 group の blob は同じレイヤー blob の複製である（`engine/sycl/src/kernels/native_expert_parity.cpp:321-347`）。

## 実行時の詳細

変数は各レイヤーについて GPU parity 計算と結果コピーが終わった直後に読み取られる。値を static 変数などに cache しておらず、レイヤーごとに `getenv` を再評価する（`engine/sycl/src/kernels/native_expert_parity.cpp:317-321`）。

設定されている場合は、同一 blob を10個の device allocation に複製し、40 entries の group 情報・scratch・出力領域を確保する。warm-up として grouped kernel を1回呼び出して wait した後、同じ呼び出しを20回行い、最後に queue を wait する。経過した host wall-clock 時間を20で割って1レイヤー呼び出しあたりのミリ秒を出し、`G * blob.size()` をその時間で割った値も表示する。従って、この環境変数が増やすのは診断プログラム内の追加計測であり、生成 token や推論結果を選ぶ処理ではない（`engine/sycl/src/kernels/native_expert_parity.cpp:321-359`）。

## ログと測定値

各計測対象レイヤーについて標準出力に次の形式を表示する。数値は実行時に計測され、固定の性能値ではない（`engine/sycl/src/kernels/native_expert_parity.cpp:349-355`）。

```text
          GPU grouped: 10 experts x 4 entries: <ms> ms per layer call  (<GB/s> GB/s of expert bytes)
```

通常の parity 結果も引き続き表示され、失敗があれば最終行 `native_expert_parity: <n> failures` の後に終了コード 1、失敗がなければ 0 を返す。引数不足は usage を標準エラーに出して終了コード 2。対象 tensor がないレイヤーや非対応形式は個別の標準出力メッセージと失敗数に反映され、計測をスキップする（`engine/sycl/src/kernels/native_expert_parity.cpp:81,121-129,363-372`）。計測分岐固有の警告・エラー文はない。

`docs/A770_SPEED_SPEC.md:631-642` は `NATIVE_BENCH=1` での計測例を記載し、Coder IQ1_M / A770 のレイヤー別値を示す。ソースは `=1` を要求せず設定有無だけを確認し、実行時の数値を計測するため、ここでは資料の値を一般的な性能保証として扱わない。

## 根拠

- `engine/sycl/src/kernels/native_expert_parity.cpp:317-321` — SYCL parity 計算後の設定有無判定。
- `engine/sycl/src/kernels/native_expert_parity.cpp:321-359` — 固定の計測形状、warm-up、反復、時間算出、出力。
- `engine/sycl/src/kernels/native_expert_parity.cpp:81-129,363-372` — CLI、入力不備のスキップ、最終失敗数と終了コード。
- `engine/sycl/CMakeLists.txt:683-688` — `STRATA_NATIVE_EXPERTS` による診断ターゲットのビルド条件。
- `docs/A770_SPEED_SPEC.md:631-642` — ソース中の計測経路と照合した、特定条件の資料上の測定例。
