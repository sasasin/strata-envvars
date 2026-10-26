# `DS4_PICK`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。Strata 所有ソースを調査。外部ライブラリや GPU driver が独自に読む環境変数は対象外。

## 役割

DeepSeek V4.1 (`dsv41`) のプロンプト処理で、chunked pass（flow）と16-token windowsのどちらを使うか選ぶ方式を切り替えます。`DS4_PICK=adaptive` のとき、計測した転送・CPU lane の速度、expert の常駐状況、過去の処理時間から両経路を見積もります。adaptive 以外では、プロンプト長を `DS4_PICK_MIN` のしきい値と比較する固定ルールを使います。

## 値と判定

環境変数は `pick_path()` の関数ローカル `static const bool` 初期化時に一度読みます。`std::strcmp(e, "adaptive") == 0` による文字列全体の完全一致で判定し、大文字小文字は区別します。

| `DS4_PICK` | 判定 |
|---|---|
| 未設定 | adaptive 無効 |
| `adaptive` | adaptive 有効 |
| 空文字、`Adaptive`、`1`、その他の文字列 | adaptive 無効 |

`adaptive` が有効でも、計測モデル `pm.on` が成立していなければ固定しきい値方式に戻ります。また、2048 tokens 以上は常に flow を選びます。

## 有効になる条件

- Strata の `dsv41` モデルの feed 経路であること。別の engine やモデルの経路にはこの読み取りはありません。
- chunked prompt 処理が使えること（`chunk > 0`）。feed は `n >= chunk_min` のときだけ `pick_path()` を呼び、満たさなければ windows を使います。
- adaptive の速度予測を実際に使うには `pm.on` が必要です。モデル load 時の `calibrate_paths()` は `chunk > 0`、`chunk_min == 2`、`DS4_CHUNK_MIN` が未設定で、flow chunk を持つ GPU と少なくとも2 staging slot がある場合に計測します。`DS4_PATH_PICK` の値を `atoi` した結果が 0 なら計測を省略します。測定した DMA、RAM-to-staging copy、CPU lane の速度がすべて正でなければ `pm.on` は true になりません。
- `DS4_PICK` が無効、または `pm.on` が false の場合、固定ルールは `DS4_PICK_MIN` の `prompt_flow_min()` を使います。`DS4_PICK_MIN` は未設定・空文字なら96、数値変換結果が1未満なら1に丸めます。

## 実行時の詳細

`calibrate_paths()` はモデル load 中に呼ばれます。flow の GPU transfer、RAM から staging への copy、可能なら cold expert の disk read、CPU lane の処理速度を測って予測値を初期化します。予測可能な状態で `DS4_PICK=adaptive` の場合、`pick_path()` は各層の CPU lane expert 数と profile、常駐ページのサンプルから flow / windows の仕事量を見積もります。過去に成功した prompt の実時間もサイズ区分ごとに更新し、後続選択の予測を補正します。常駐 expert の割合が90%以上なら、windows の予測が flow より少しでも速い場合に windows を選べます。90%未満なら、windows が flow の半分以下の時間と予測された場合に限り windows を選びます。

`Model::feed()` では選択結果により `forward_chunks()` または `feed_windows()` に進みます。`feed_mark()` も同じ選択関数を使います。`--verbose` のとき adaptive 判定の見積もりログとして `ds4: a prompt of ... tokens through ...` が stderr に出ます。chunk 有効時には固定しきい値の起動ログ `ds4: prompt path: the chunked pass from ... tokens, windows of 16 below` も stderr に出ます。

選択は prompt 長だけでなく、adaptive モードでは各 process の計測結果と実行履歴にも依存します。ソースコメントは flow と windows が異なる丸めをすることを記しているため、経路選択を変えた場合に prompt の数値結果が同一とは限りません。性能向上の一般的な保証はソースからは確認できません。

## 根拠

- `src/dsv41/ds4_model.cu:7990-7998` — `DS4_PICK` の完全一致判定、未有効時の固定しきい値経路、2048 tokens 上限、`pm.on` fallback。
- `src/dsv41/ds4_model.cu:7790-7803,7807-7819,7916-7920,2820-2824` — load 時の calibration 呼び出し、適用条件、計測と `pm.on` の設定、起動時のしきい値ログ。
- `src/dsv41/ds4_model.cu:8023-8046` — flow / windows の速度見積もり、RAM 常駐率を含む選択と verbose ログ。
- `src/dsv41/ds4_model.cu:8067-8082,8408-8415` — 成功した prompt の時間・選択数を使ったモデル更新。
- `src/dsv41/ds4_model.cu:9356-9383` — feed と feed_mark から選択結果が実際の prompt 処理経路に反映される箇所。
- `src/dsv41/ds4_pick_rule.hpp:18-27` — 固定方式の既定しきい値と `DS4_PICK_MIN` の変換・下限。
- `docs/DETAILS.md` — `DS4_PICK` 固有の性能測定記載は確認できず。性能値は記載していない。
