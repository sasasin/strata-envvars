# `BOTH_CONC`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`BOTH_CONC` は Strata の engine/server の動作を制御する設定ではなく、同梱の調査用ラッパー `tools/par/both.py` が負荷測定の並行数リストとして読む環境変数です。値は同ラッパーから `tools/par_load.py` の `--conc` CLI 引数へ渡され、W2 の closed-loop 負荷測定と、別 loader の負荷測定に使われます（`tools/par/both.py:8-15`）。

## 値と判定

| 状態・値 | 処理 |
|---|---|
| 未設定 | `os.environ.get()` の既定値 `8,16,32` を使います。 |
| 空文字 | 空文字のまま使います。空文字を既定値に置き換える処理はありません。 |
| 設定値 | `both.py` 自身は parse・trim・範囲検査をせず、文字列のまま `--conc` に渡します。 |
| 下流の変換 | `par_load.py` は `a.conc.split(",")` の各部分を Python `int()` に渡します。空要素や整数にできない要素は `ValueError` になります。空白や符号付きの整数表記は `int()` が受理します。 |
| 数値の範囲 | 正数か、上限があるかを検査する処理は見つかりません。0 や負数も変換自体は通りますが、測定として成立する保証はありません。 |

既定値と変換の根拠: `tools/par/both.py:9-11,15`、`tools/par_load.py:471-476,505-510`。`par_load.py` は通常の `--conc` 既定値 `1,2,4,8` を持ちますが、このラッパーは `--conc` を常に明示するので、その既定値は使われません。

## 有効になる条件

- `tools/par/both.py` が実行される必要があります。Strata の通常 CLI、engine、server が `BOTH_CONC` を読む箇所は確認できませんでした。
- 値が並行数に反映されるのは、下流の `par_load.py` が workload `w1` 以外を実行する場合です。`both.py` の sustained 側は `w2` を指定し、burst 側にも同じ値を渡します（`tools/par/both.py:11-15`）。`par_load.py` は `w1` だけ `--conc` を無視して `[1]` に固定します（`tools/par_load.py:510`）。
- `tools/par/recon3.py` 経由では、親プロセスの環境を複製した後 `BOTH_CONC=CONC` で上書きし、その時点のコードでは `CONC` は常に `8,16,32` です。したがって呼び出し元で設定した値はこの経路では優先されません（`tools/par/recon3.py:26,46,55-57`）。`both.py` を直接起動する場合は、環境値または未設定時の既定値が使われます。

## 実行時の詳細

`both.py` は起動時に `BOTH_CONC` を一度読み、同じ `conc` 文字列をまず `par_load.main()` の W2 closed-loop 測定へ渡し、次に `PA_LOAD` が指す別 loader のプロセスへ `--conc` として渡します（`tools/par/both.py:8-15`）。実行中に環境を変更して値を再読込する処理はありません。子プロセス起動時の環境は継承されますが、並行数については環境変数自体でなく明示的な `--conc` 引数が渡されます。

`par_load.py` はカンマ区切りの各整数を並行レベルとして反復し、各レベルの測定結果を標準出力へ表示します（`tools/par_load.py:298-321,510,525`）。無効な整数要素は `int()` 変換時に例外となります。変換可能でも、値が0以下の場合に `closed_loop()` へ空または負数相当の worker 数が渡り、記録配列が空のまま最大完了時刻を求めるなどして失敗し得ます（`tools/par_load.py:271-295`）。`both.py` は最初の `par_load.main()` の戻り値を検査せず、2番目の `subprocess.run()` も `check=True` にせず戻り値を検査しません。そのため下流処理の失敗をこのラッパー自身が終了コードへ伝える保証はありません（`tools/par/both.py:11-15`）。

直接起動時に `BOTH_CONC` が未設定なら既定値を使います。`recon3.py` 経由では `BOTH_CONC` を固定値で上書きします。CLI の `--conc` は `both.py` 自身にはありませんが、同ラッパーが下流 CLI に指定します。

## 根拠

- `tools/par/both.py:8-15` — 環境変数の読み取り、既定値、二つの loader への引き渡し。
- `tools/par/recon3.py:26,46,47-57` — `CONC` の設定、子プロセス環境での `BOTH_CONC` 上書き、ラッパー起動。
- `tools/par_load.py:471-510` — `--conc` 引数、引数解析後の文字列分割と整数変換、`w1` の特例。
- `tools/par_load.py:271-295,298-321,525-540` — worker 数の利用、測定ログ、ledger 保存と戻り値。
