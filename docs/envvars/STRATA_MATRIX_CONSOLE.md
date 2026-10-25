# `STRATA_MATRIX_CONSOLE`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

これは Strata 本体や通常の `strata` 実行時の設定ではなく、Windows 上で端末ライフサイクルのテスト行列を一部実行するためのテスト用スイッチです。環境変数が設定されていると、実コンソールウィンドウを必要とする2ケースをスキップせず実行します。

## 値と判定

| 環境 | 動作 |
|---|---|
| Windows 以外 | この変数によるスキップ判定を行わない。 |
| Windows、対象2ケース、未設定または空文字 | `os.environ.get()` が偽となり、ケースを `skipTest` する。 |
| Windows、対象2ケース、空でない値 | 値の内容を parse せず真として扱い、ケースを実行する。 |
| Windows、その他のケース | この変数の値に関係なくケースを実行する。 |

したがって `1` が必須ではなく、例えば `0` や `false` も空でなければ有効です。大文字小文字や前後空白の検査、値の数値変換はありません。

## 有効になる条件

対象は `serve-ctrl-c` と `serve-console-close` の2シナリオで、かつ `matrix.WINDOWS` が真の場合だけです。テスト関数は実行前に環境を判定し、条件を満たさなければ「needs a console window; set STRATA_MATRIX_CONSOLE=1」の理由でスキップします。テストモジュールは POSIX/Windows 以外でもクラス全体をスキップします。

## 実行時の詳細

値は `tests/terminal/test_lifecycle_matrix.py` の各テスト関数が呼ばれるたびに `os.environ.get("STRATA_MATRIX_CONSOLE")` で参照されます。値を保持する static cache はありません。判定を通ると `matrix.run([name])` が該当シナリオを起動し、その結果の `ok` を unittest assertion で確認します。環境変数を Strata サーバーやエンジンの子プロセスへ渡す処理は、この判定箇所にはありません。

## 根拠

- `tests/terminal/test_lifecycle_matrix.py:1-6` は Windows の実コンソールを必要とするテストの説明。
- `tests/terminal/test_lifecycle_matrix.py:13,21-26` は対象シナリオ名、Windows 条件、未設定・空文字時の skip、設定時の実行を示す。
- HEAD 全体での `STRATA_MATRIX_CONSOLE` 完全一致検索では、直接参照は `tests/terminal/test_lifecycle_matrix.py:5,23-24` のみ。

この候補はテスト専用コードにのみ現れるため、通常利用者向けの Strata 機能を制御する環境変数としては確認できません。`docs/DETAILS.md` にこのテストスイッチの説明はありません。
