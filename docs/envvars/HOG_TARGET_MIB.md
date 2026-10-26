# `HOG_TARGET_MIB`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。調査対象リポジトリの作業ツリーは clean。Strata 本体の環境設定ではなく、同梱テストスクリプト専用の変数。

## 役割

`tools/session_pressure_test.py` が SAVE 処理の直前にホスト RAM を確保し、空き RAM を指定した MiB 数まで減らすためのテスト用設定です。SAVE がメモリ不足で拒否される条件を作る目的で使われます。通常の Strata 実行ファイルやサーバーが読む変数ではありません。

## 値と判定

| 値 | 動作 |
|---|---|
| 未設定または空文字 | Python の `os.environ.get()` が返す値は偽となり、メモリ確保処理と空き容量ログをスキップする。 |
| 空白以外の非空文字列 | `int()` で整数に変換し、指定 MiB 分の空き RAM を目標にする。 |
| 整数に変換できない文字列 | `ValueError` が処理されず、スクリプトは SAVE 処理に進む前に終了する。 |

`int()` は符号付き整数や前後の空白を受け付けます。`extra = available - target * 2**20` が正の場合だけ `bytearray(extra)` を確保します。`extra <= 0` なら確保は行わず、現在の空き RAM を表示します。値の範囲チェックや上限 clamp はありません。そのため、負数などを指定した場合には利用可能 RAM を大幅に超える確保を試みる可能性があり、`MemoryError` もこのスクリプト内では捕捉されません。

## 有効になる条件

- `tools/session_pressure_test.py` を直接実行すること。これは SAVE / RESTORE のラウンドトリップを試す同梱テストツールです。
- 非空値の場合は `psutil` が import できること。依存がなければ import エラーでスクリプトが終了します。
- 計算した `extra` が正であること。正でなければ RAM を確保しません。

## 実行時の詳細

スクリプトは先に会話を生成し、対象会話 D の出力を得た後、次ターン用の入力を作ります。その後にこの変数を評価し、条件に合えば `psutil.virtual_memory().available` を読み、空き容量と目標値の差を byte 単位で `bytearray` に確保します。確保した領域の各 4096 バイト境界で先頭バイトに `1` を書き込み、ページを実際に触ります。続けて空き RAM を MiB 単位で標準出力に表示し、`eng.session_file("save", out_file)` を呼びます。

SAVE の後、成功・失敗にかかわらず `hog = None` として確保領域への参照を外します。SAVE が失敗し、`--session-save-reclaim` が引数に含まれている場合は、その後で bounded retry を行います。スクリプトはプロセス起動後のこの位置で一度だけ環境を読みます。実行中の環境変更を再評価するループはありません。設定した子エンジンへの環境変数転送や上書きも、この変数についてはありません。

## 根拠

- `tools/session_pressure_test.py:2-10`: ツールの SAVE / RESTORE ラウンドトリップ目的と起動方法。
- `tools/session_pressure_test.py:48-64`: 対象会話生成後の読み取り、truthiness 判定、`int()` 変換、RAM 確保・ページ touch、空き容量ログ。
- `tools/session_pressure_test.py:65-87`: SAVE と任意の bounded retry、確保領域の解放、SAVE 失敗時の終了。
- ソース全体の `HOG_TARGET_MIB` 完全一致検索では、このファイル以外に参照は見つかりませんでした。`docs/DETAILS.md` に本変数の説明はありませんでした。
