# `STRATA_RUNS`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

この変数は Strata エンジンの設定ではありません。コミット済みのコミュニティ benchmark runner `bench/results/2026-10-04-community-2x-rtx3060/bench.py` が、各 prompt target に対して実行する non-streaming benchmark の回数を指定します。通常の Strata 起動コードではこの名前を読み取っていません。

## 値と判定

Python の `int(os.environ.get("STRATA_RUNS", "3"))` で、スクリプトの import 時に一度整数へ変換します。

| 環境変数の状態 | 結果 |
|---|---|
| 未設定 | 文字列 `"3"` を変換し、既定値 3 回 |
| 整数として変換できる文字列 | 変換した整数を使用。符号や前後の空白を含む整数表記も Python `int()` の規則で受け付ける |
| 空文字または整数として変換できない文字列 | import 時に `ValueError`。`main()` は実行されない |
| 0 または負の整数 | 値の検証・clamp はない。non-streaming の `range(1, RUNS + 1)` が空になり、non-streaming request は実行されない |

浮動小数点表記（例: `2.5`）は整数変換できずエラーになります。値を読み直す処理はなく、実行中に環境を書き換えても反映されません。

## 有効になる条件

`STRATA_RUNS` を読むのは、上記の日付付き benchmark runner と、同じ内容の `bench-0.1.39.py` だけです。Strata の engine/server、setup、通常の CLI 実行経路に同名の読み取りはありません。したがって benchmark runner を使わない場合、この変数による Strata 本体への効果はありません。

## 実行時の詳細

runner は `TARGETS` の各値について `i = 1` から `RUNS` まで non-streaming request を送ります。`RUNS` は結果 metadata の `protocol.runs_per_target` にも記録されます。`STRATA_TTFT` が有効な場合に target ごとに追加される streaming TTFT request は別ループで1回ずつ実行されるため、`STRATA_RUNS` では回数が変わりません。

## 根拠

- `bench/results/2026-10-04-community-2x-rtx3060/bench.py:16-28,40-48` — runner の任意環境変数一覧、既定値、import 時の変換。
- `bench/results/2026-10-04-community-2x-rtx3060/bench.py:202-205,223-248` — metadata への記録、target ごとの non-streaming ループ、別個の streaming TTFT ループ。
- `bench/results/2026-10-04-community-2x-rtx3060/bench-0.1.39.py` は上記 `bench.py` と同じ Git blob（`b6a7dff17ad3f939b69f2dfae330957e92d1fd74`）。

この変数はベンチマーク runner 内に限られ、エンジンの環境変数としての読み取り箇所は確認できません。性能値や測定結果については、この調査では主張しません。
