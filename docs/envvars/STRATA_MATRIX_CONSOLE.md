# `STRATA_MATRIX_CONSOLE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

これは Strata 製品の実行設定ではなく、終了一連の動作を確認するテスト専用フックです。Windows で実コンソールが必要なライフサイクル matrix の2ケースを、pytest wrapper から実行するか skip するかを制御します。Strata 本体（CLI、サーバー、エンジン）のソースには、この名前を読む箇所はありません。

## 値と判定

wrapper は `os.environ.get("STRATA_MATRIX_CONSOLE")` の真偽値を調べます。文字列を parse せず、空でない値なら有効です。

| 環境値 | 判定 |
|---|---|
| 未設定 | 偽。該当 Windows ケースを skip |
| 空文字 | 偽。該当 Windows ケースを skip |
| `1` | 真。該当ケースを実行 |
| その他の非空文字列（例: `0`, `false`） | 真。該当ケースを実行 |

CLI 引数や別の環境変数との優先順位、数値変換、範囲制限はありません。wrapper が各ケースのテスト関数を実行するたびに環境を確認し、値を cache しません。

## 有効になる条件

- pytest wrapper `tests/terminal/test_lifecycle_matrix.py` を実行していること。
- `tests/terminal/lifecycle_matrix.py` が Windows と判定すること。
- シナリオ名が `serve-ctrl-c` または `serve-console-close` であること。
- 上記条件を満たす場合、環境値が空でないこと。

`serve-ctrl-break` は matrix 側では Windows 専用ですが、wrapper の `CONSOLE` 集合には含まれないため、この変数では skip されません。Windows 以外では `matrix.WINDOWS` が偽のため、この変数は wrapper の判定結果に影響しません。対象シナリオは matrix の適用可能性チェックも通る必要があります。

## 実行時の詳細

対象ケースで Windows かつ値が未設定または空文字の場合、`self.skipTest("needs a console window; set STRATA_MATRIX_CONSOLE=1")` を呼び、pytest 上で skip として観測されます。値が非空なら `matrix.run([name])[0]` を実行し、その結果の `ok` を assertion します。成功・失敗時の matrix 出力は `PASS <name>` / `FAIL <name>` です。

有効化されたシナリオは fake engine package を使う close-path matrix です。`serve-ctrl-c` は Windows の Ctrl+C を送り、`serve-console-close` はコンソール close を試みます。環境変数自体は子プロセスへ転送されたり、製品の終了処理を変更したりせず、pytest wrapper の skip 判定にだけ使われます。

## 根拠

- `tests/terminal/test_lifecycle_matrix.py:5-6` — 実コンソールが必要な Windows ケースと設定案内。
- `tests/terminal/test_lifecycle_matrix.py:13,21-26` — 対象ケース、環境値の真偽判定、skip 文、matrix 呼び出し。
- `tests/terminal/test_lifecycle_matrix.py:30-32` — 適用可能なシナリオだけをテストとして登録。
- `tests/terminal/lifecycle_matrix.py:729-737,752-759` — ケースの実処理、Windows 条件、適用可能性。
- `docs/CLOSING.md:73-77` — この pytest wrapper が終了一連の確認に使われることの説明（動作判定の根拠はテストコード）。
