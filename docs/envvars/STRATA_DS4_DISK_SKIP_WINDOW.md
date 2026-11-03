# `STRATA_DS4_DISK_SKIP_WINDOW`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`STRATA_DS4_DISK_SKIP_AUTO` が disk skip を自動で止めるか判断する際に使う、cold share 集計窓の長さを指定します。単位はトークンです。値は集計窓の上限 `disk_skip_window × max(1, g.nl - disk_skip_from)` の計算に使われます。この変数だけでは expert を skip しません。また、通常の disk skip の重みしきい値を設定する変数でもありません。

対象コードは CMake オプション `STRATA_BUILD_DSV41` で別実行ファイル `strata-dsv41` に組み込まれる DeepSeek-V4.1 経路です。この build option は既定 OFF です。既存の `strata` 実行ファイル全般に適用される設定ではありません（`CMakeLists.txt:931-945`）。

## 値と判定

モデルオブジェクト構築時に `env_f("STRATA_DS4_DISK_SKIP_WINDOW", 32.0f)` で読み、戻り値を `int` に変換してから下限 4 を適用します。helper は環境変数が未設定なら既定値を返し、設定されていれば `std::atof` で変換します。この値を上書きする CLI 引数や設定ファイル経路は見つかりません（`src/dsv41/ds4_model.cu:1352,1442`）。

| 環境値 | `disk_skip_window` |
|---|---:|
| 未設定 | 32 |
| 空文字、数値に変換できない文字列、0、負値、4 未満 | 4 |
| `4` 以上の数値 | 小数部を `int` 変換で切り捨てた整数 |

`atof` による変換のため、文字列全体の厳密な数値検証やエラー報告はありません。数値の後ろに文字が続く入力も数値部分で変換されます。上限 clamp はコードにありません。設定値をプロセス起動後に変えても、既に構築されたモデルの値は再読み込みされません。

## 有効になる条件

この窓の値が自動停止判定に使われるには、次の条件が必要です。

- `STRATA_DS4_DISK_SKIP_W` が正の数に変換されること。未設定なら 0、負数は 0 に clamp されます。
- `STRATA_DS4_DISK_SKIP_AUTO` が 0 以外の数に変換されること。未設定なら 0 です。
- 対象 layer が MTP layer でなく、`disk_skip_from` 以上かつ `g.nl` 未満であること。
- `strata-dsv41` の route 処理が実行されること。

いずれかが満たされないと `skip_auto_tick()` は呼ばれず、この設定値は自動停止判定に使われません。AUTO が無効なら disk skip 自体は `STRATA_DS4_DISK_SKIP_W` と layer 条件で制御され、WINDOW はその skip 挙動を変えません。これらの変数の値判定と条件は `src/dsv41/ds4_model.cu:1397-1412,1441-1444,9460-9465,9511` にあります。

## 実行時の詳細

自動判定が有効な間、decode の CPU lane は対象 layer ごとに route 情報を集計します。実装コメント上、disk skip の対象は decode と draft の check で、prompt 経路は対象外です（`src/dsv41/ds4_model.cu:1391-1396,9385-9387`）。cold share の分母は、その route weight が `disk_skip_w × token の route weight 合計` 以上で、skip されず計算対象となる expert 数です。分子はそのうち CPU lane にあり、要求時に RAM にない expert 数です。lookahead が先読みして RAM に載せた expert は cold と数えないよう扱われます（`src/dsv41/ds4_model.cu:9460-9466,9483-9501`）。

集計レコードの `T` は処理中の route window の token 数です。`skip_auto_tick()` は ring にレコードを追加し、`disk_skip_window × max(1, g.nl - disk_skip_from)` に達した範囲を保つよう古いレコードを外します。`li == disk_skip_from` のときだけ累積 cold share を評価するため、この上限は `disk_skip_from` 以降の layer 数を掛けた集計量です（`src/dsv41/ds4_model.cu:1467-1488`）。

WINDOW は停止判定を直接行わず、集計対象の長さを変えます。自動判定は別途、skip 予算到達、cold share が 2% 以下、または cold share が少なくとも 5% 下がらない期間が settle 値に達した場合に skip を止めます（`src/dsv41/ds4_model.cu:1481-1488`）。その停止時は stderr に `ds4: DISK_SKIP auto: off after ...` を出します。decode の集計では実際に省略した expert 数も stderr に出力され、AUTO が動作した場合は最終状態と切り替え回数も表示されます（`src/dsv41/ds4_main.cpp:993-999,2811-2831`）。この変数自体の値を表示するログや、この値に起因する専用の終了・エラー経路は確認できません。

## 根拠

- `CMakeLists.txt:931-945` — DSV41 専用 build option と `strata-dsv41` ターゲット。
- `src/dsv41/ds4_model.cu:1352,1442` — env helper、既定値 32、int 変換、下限 clamp。
- `src/dsv41/ds4_model.cu:1397-1412,1441-1445` — 関連する skip 値と layer 開始値、自動判定の初期化。
- `src/dsv41/ds4_model.cu:1467-1488` — ring の保持上限と cold share による自動停止判定。
- `src/dsv41/ds4_model.cu:9460-9511` — 対象 layer の route skip と集計呼び出し。
- `src/dsv41/ds4_main.cpp:993-999,2811-2831` — decode / AUTO の観測ログ。

`STRATA_DS4_DISK_SKIP_WINDOW` の完全一致参照は上記 helper 呼び出しと、その説明コメントに限られます。Strata の文書には別の説明・測定値が見つからなかったため、挙動はソースコードだけを根拠に記載しています。
