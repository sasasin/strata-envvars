# `STRATA_DIAG_POOL`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CPU expert pool の `run_split_multi_native` にかかった時間と、worker / host の処理量を集計して診断行に出すためのフラグです。値は計算経路や結果を選択せず、タイミング取得とカウンター更新、診断出力を有効にします。読み取りは `engine/src/kernels/cpu/pool.cpp` の `diag_pool_on()` にあります（同ファイル:754-757）。

ヘッダーコメントは「measuring build only」としていますが、この環境変数判定や計測箇所を囲う build macro は当該実装にありません。したがって、コードが含まれるビルドであれば値によって診断処理が動きます。CPU pool の `run_split_multi_native` が呼ばれない経路では、この計測対象の集計は増えません（同ファイル:1559-1617、`engine/include/strata/kernels/cpu/pool.hpp`:455-463）。

## 値と判定

`std::getenv` の戻り値が null でないことに加え、最初の1文字が `'1'` かを比較します。文字列全体の数値変換や真偽値 parse はしません。空文字は設定済みでも無効です。大文字小文字や空白の正規化もありません（`engine/src/kernels/cpu/pool.cpp`:754-757）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `diag_pool_on()` の判定 | 無効 | 先頭が `1`：`1`, `10`, `1anything` | 空文字、`0`, `2`, `true`, `TRUE`, ` 1` |

CLI 引数や別の環境変数による上書き・fallback はこの判定にありません。`diag_pool_on()` の関数内 `static const bool` は初回呼び出し時に一度だけ初期化されるため、その時点の値がプロセス内で使われ続けます。初回評価後に環境を書き換えても反映されません（同ファイル:755-757）。

## 有効になる条件

- CPU expert pool のコードがビルドに含まれ、`diag_pool_on()` の初回評価時に環境変数の先頭文字が `1` であること（`engine/src/kernels/cpu/pool.cpp`:754-757）。
- `ExpertPool::run_split_multi_native` が少なくとも1回、正の `n` で呼ばれること。`n <= 0` は直ちに戻り、集計対象になりません（同ファイル:1559-1561）。
- mode 5 / 6 / 7 の phase / task 計測は各モードの経路でのみ行われます。`run_phase` は mode 5、6、7 に対して待機・phase 計時を集計し、worker task 時間は mode 5 以上で加算します（同ファイル:1117-1118、1337-1339、1467-1487）。`STRATA_POOL_DEP` 等で実行経路が変われば phase の内訳も変わりますが、この変数自体はその選択をしません（同ファイル:1568-1605）。
- OS、GPU backend、サーバーモード、モデル状態による追加の値判定はありません。値が無効でも CPU pool の通常処理と、登録済み pool 診断 callback 自体はこのフラグで無効化されません（同ファイル:917-918、1035-1038）。

## 実行時の詳細

有効時、native expert の multi-token 呼び出し全体を計時し、各分割 batch の数、expert 数、entry 数を加算します。mode 5 / 6 の行処理と mode 7 の依存 batch、quantization、worker の busy / wake / task counters をコード上の条件に応じて計測します（`engine/src/kernels/cpu/pool.cpp`:1117-1118、1337-1339、1467-1487、1559-1617）。

呼び出しごとに集計し、累計 2000 calls ごとに `running` の診断行を `stderr` に出します。pool の破棄時には calls が1以上なら `end` の行を出します。計測値は pool インスタンス内のカウンターに保持され、永続化や子プロセスへの転送はありません（同ファイル:1016-1033、1035-1037、1611-1617）。

## ログと測定値

出力は `stderr` の `strata diag-pool (running): ...`（2000 calls ごと）または `strata diag-pool (end): ...`（pool 破棄時）です。行には calls / batches / phases / experts / entries、worker 数、host の参加有無、NUMA slice 数、実行・待機・quantize・worker busy / wake などのミリ秒値と task 数が含まれます。出力文字列とフィールドは `engine/src/kernels/cpu/pool.cpp`:1025-1032、出力タイミングは同ファイル:1035-1037、1611-1617 にあります。

この環境変数について条件付きの測定結果を示す Strata 資料は確認できません。これらは実行時診断カウンターであり、速度向上や性能値を保証する記述ではありません。

## 根拠

- `engine/src/kernels/cpu/pool.cpp:754-757` — 環境変数の読み取り、先頭文字判定、初回呼び出し時の cache。
- `engine/src/kernels/cpu/pool.cpp:1117-1118, 1337-1339, 1467-1487` — worker と phase の計時条件。
- `engine/src/kernels/cpu/pool.cpp:1559-1617` — `run_split_multi_native` の計測・集計と定期出力。
- `engine/src/kernels/cpu/pool.cpp:1016-1037` — 診断行の形式と pool 破棄時出力。
- `engine/include/strata/kernels/cpu/pool.hpp:455-463` — 診断カウンターの説明と保持領域。
