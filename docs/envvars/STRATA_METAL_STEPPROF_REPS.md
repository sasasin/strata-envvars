# `STRATA_METAL_STEPPROF_REPS`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。

## 役割

Metal backend の step profiler が、decode window の dispatch prefix を反復計測する回数を指定します。これは計測用設定で、通常の生成処理に対する常時の実行制御ではありません。値を設定しただけでは profiler は起動せず、`STRATA_METAL_STEPPROF` で指定した window 長などの条件を満たす必要があります（`metal/src/engine/window.cpp:1468-1471,1878-1893`）。

## 値と判定

`stepprof()` の呼び出しごとに `std::getenv("STRATA_METAL_STEPPROF_REPS")` を調べます。未設定なら 5、設定されていれば値を `std::atoi` で変換し、`std::max(1, ...)` により最低 1 回にします（`metal/src/engine/window.cpp:1878`）。

| 環境値 | `reps` | 判定 |
| --- | ---: | --- |
| 未設定 | 5 | 既定値 |
| 空文字 | 1 | `atoi` が 0 を返し、下限値になる |
| `0`、負の整数 | 1 | 0 または負値を下限値に丸める |
| 正の整数 | その整数 | 反復回数として使う |
| 数字で始まる文字列（例: `3x`） | 数字部分 | `atoi` が先頭の数値部分を変換する |
| 数字で始まらない文字列 | 1 | `atoi` が 0 を返し、下限値になる |

文字列全体の妥当性検査、上限値、範囲エラー処理はありません。変換可能範囲を超える文字列の `atoi` の結果はこのコードで別途検証・処理されません（`metal/src/engine/window.cpp:1878`）。

## 有効になる条件

この変数は Metal の `Window::stepprof()` だけで参照されます。実際の呼び出しには、同じ window 実装の cached-window 分岐で次の条件が必要です。

- `STRATA_METAL_STEPPROF` の整数変換結果が今回の token 数 `Tn` と一致する。
- window に head がある。
- `seen2` を増やした結果が `STRATA_METAL_STEPPROF_AT` の整数変換結果と一致する（未設定時の既定値は 20）。
- `stream_` が false。

`STRATA_METAL_STEPPROF` と `_AT` は function-local `static const int` として初回評価時にキャッシュされます。一方、`_REPS` は profiler に入るたびに読み直されます。そのため `_REPS` だけを設定しても呼び出し条件を満たさなければ効果はなく、実行中の値変更は以後の profiler 呼び出しから反映されます。この変数の値に応じた別の platform 分岐は確認されません（`metal/src/engine/window.cpp:1447-1471,1878`）。

## 実行時の詳細

Profiler は最初に dispatch 全体を 40 回実行して GPU を warm up し、続いて全体を 15 回計測して中央値を基準時間にします。その後、各 `reps` pass で全体を 5 回実行して pass の基準を取り、空 prefix と各 barrier group までの prefix を実行します。prefix の時間は `reps` 回分をソートし、中央要素を採用します（`metal/src/engine/window.cpp:1879-1893`）。このため値を大きくすると prefix 計測の反復と GPU 実行が増えます。

結果は `stderr` に `strata metal stepprof:` で始まる pass ごとの時間、window 全体と prefix chain の時間、part ごとの時間・dispatch 数・group 数・推定 weight bytes などを出力します（`metal/src/engine/window.cpp:1879-1890,1939-1953`）。Strata はこの環境変数に対する無効値の警告や専用終了経路を設けていません。prefix 実行中に外部の GPU/runtime エラーが起きた場合の詳細は、この環境変数の読み取り箇所だけからは特定できません。

## 根拠

- `metal/src/engine/window.cpp:1464-1472` — cached window での profiler 呼び出し条件と、関連する `STRATA_METAL_STEPPROF` / `_AT` の一度だけの読み取り。
- `metal/src/engine/window.cpp:1816-1818,1878-1893` — 計測関数、`_REPS` の既定値・変換・下限、および反復と中央値の計算。
- `metal/src/engine/window.cpp:1939-1953` — `stderr` の集計ログ。

`STRATA_METAL_STEPPROF_REPS` の完全一致参照は上記の実装と実装コメントに限られ、別の env helper や動的な名前渡し経路は確認されませんでした。`docs/DETAILS.md` に本変数固有の追加説明は見つかりませんでした。
