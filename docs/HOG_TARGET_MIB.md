# `HOG_TARGET_MIB`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

同梱ツール `tools/session_pressure_test.py` で、セッション保存時にホストの空き RAM を意図的に減らすための変数です。対象は SAVE/RESTORE の圧力試験のみで、Strata の通常実行ファイルやサーバー本体はこの名前を読みません。値は「確保後に残したい空き RAM」の MiB 数として使われます。

## 値と判定

| 値 | 動作 |
|---|---|
| 未設定、または空文字 | `os.environ.get()` が偽となり、確保処理を行わない |
| 非空の整数文字列 | `int()` で整数に変換し、指定値を MiB として確保量を計算 |
| 非空だが `int()` で変換できない値 | `ValueError` となり、試験スクリプトはその箇所で終了する |

確保量は `psutil.virtual_memory().available - int(HOG_TARGET_MIB) * 2**20` バイトです。確保量が正の場合だけ `bytearray` を作ります。0 以下なら RAM を確保せず、後続の SAVE 試験へ進みます。整数値に範囲制限や clamp はありません。負値では計算上の確保量が空き RAM より大きくなり得ます。大きすぎる確保で `MemoryError` 等が発生した場合の処理は実装されていません。

## 有効になる条件

`tools/session_pressure_test.py` を実行し、環境に非空の `HOG_TARGET_MIB` が設定されている場合だけ有効です。スクリプトはこの処理で `psutil` を import するため、変数を設定した実行では `psutil` が利用可能である必要があります。未設定または空文字ならこの import も行いません。

確保は SAVE の直前に試みられ、SAVE が失敗して `--session-save-reclaim` による bounded retry を行う場合も、その retry の間は確保した領域を保持します。一般の Strata 起動や別のツールへの伝播はありません。

## 実行時の詳細

スクリプトは `psutil.virtual_memory().available` から目標値をバイトに換算して差し引きます。正の差分を `bytearray` に割り当てた後、4096 バイトごとに先頭 1 バイトを書き込みます。これにより確保した領域の各ページに触れてから `eng.session_file("save", out_file)` を呼びます。SAVE の試行後、必要であれば bounded retry まで実行し、その後 `hog = None` として保持していた領域への参照を外します。スクリプトはその時点の利用可能 RAM を MiB 単位で `available now: ... MiB` と標準出力に表示します。

SAVE が失敗し、再試行後も保存できなかった場合は `NOSAVE` を表示して終了コード 2 で終了します。保存できた場合は他のセッションを実行してから RESTORE し、続きの token id が一致し、再利用 token 数が正であることを検査します。これらの SAVE/RESTORE 判定は試験スクリプトの結果であり、`HOG_TARGET_MIB` 自体の成功を示すログではありません。

この変数はスクリプト起動後、SAVE 直前に一度だけ読み取られます。実行中に環境値を変えても確保量は変わりません。確保したオブジェクトは SAVE 処理終了後に参照を外します。OS がそのメモリをいつ物理的に回収するかはこのスクリプトの範囲では規定されません。

## 根拠

- `tools/session_pressure_test.py:2-9` — ツールの SAVE/RESTORE 圧力試験の目的と実行方法。
- `tools/session_pressure_test.py:55-64` — 環境変数の有無判定、MiB からバイトへの計算、割り当てとページへの書き込み、利用可能 RAM の表示。
- `tools/session_pressure_test.py:65-86` — SAVE と optional な bounded retry、確保領域の参照解除、NOSAVE 時の終了。
- `tools/session_pressure_test.py:87-100` — RESTORE 後の token id と再利用数の試験判定。

`HOG_TARGET_MIB` の参照は上記の同梱ツール内のみで確認しました。`docs/DETAILS.md` を含むソース以外の文書に、この変数の追加説明は見つかりませんでした。
