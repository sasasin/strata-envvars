# `HOG_TARGET_MIB`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-26 時点）。

## 役割

この名前を読むのはエンジン本体ではなく、単一バグ検証用の `session_pressure_test.py` だけである。このスクリプトは SAVE の試行前にホストの空き RAM を指定値付近まで消費するための補助設定として使う。Strata のサーバーや CLI の設定ではなく、生成・保存のエンジン動作を直接変更する環境変数ではない。スクリプトは SAVE / RESTORE のラウンドトリップ検証を行う（`tools/research/tools/live-probes-2026-10/README.md:3,13`、`tools/research/tools/live-probes-2026-10/session_pressure_test.py:2-9,57-66`）。

## 値と判定

Python の `os.environ.get("HOG_TARGET_MIB")` の真偽値で有効化を判定し、真の場合だけ同じ環境変数を `int(...)` に渡す。未設定と空文字は無効で、値が文字列 `"0"` でも空でないため有効化される。整数変換は Python の `int` による10進整数変換であり、前後空白や符号は受け付ける。小数・単位付きの文字列など整数に変換できない値は `ValueError` になる。数値範囲の検査や clamp はない（`tools/research/tools/live-probes-2026-10/session_pressure_test.py:57-60`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| live probe のスクリプト | 分岐を実行しない | `1`、`0`、`-1`、` 32 `（空でなく `int` 変換可能） | 空文字（分岐しない）。`1.5` や `32MiB` は分岐に入り、その後 `ValueError` |

## 有効になる条件

- `tools/research/tools/live-probes-2026-10/session_pressure_test.py` を起動すること。通常の Strata エンジン起動だけではこの値を読み取らない（同ファイルの全参照は `:57,59`。候補名の全体検索でも他の参照はない）。
- 値が空でないこと。空でない値が `int` に変換できない場合は、SAVE より前に未処理例外となる。
- 確保するサイズ `psutil.virtual_memory().available - int(value) * 2**20` が正であること。0 以下ならメモリ確保をせず、SAVE 試行へ進む（同ファイル `:58-66`）。

この変数について CLI 引数や別の環境変数との優先順位はない。probe の設定ファイルや `STRATA_EXTRA_ARGS` が設定するエンジン引数とは別に、probe 自身が参照する（同ファイル `:20,28-30,57-59`）。

## 実行時の詳細

スクリプトは SAVE 前に環境変数を読み取る: まず設定値の真偽を確認し、真なら空き RAM を MiB に換算した目標値を引いて確保量を計算する。確保量が正ならそのサイズの `bytearray` を作り、4096 バイトごとに1を書き込んでから、現在の空き RAM を `available now: %d MiB` として標準出力へ出す。確保量が正でない場合にもこの表示は行う。値の読み取りはこの処理時点の2回で、値をキャッシュしたり、環境変数を変更して再評価したりする仕組みはない（同ファイル `:57-64`）。

確保したバッファは SAVE の試行または bounded retry の後、`hog = None` で参照を外す（同ファイル `:65-82`）。SAVE が拒否されると `SAVE: refused` と理由を最大300文字表示し、`--session-save-reclaim` が引数にあれば同じ engine で bounded retry を試す。なお、空き RAM の取得値とメモリ確保は probe プロセス側で行う処理であり、環境変数をエンジン子プロセスへ転送する処理ではない（同ファイル `:57-82`）。

## ログと測定値

有効な（空でない）値なら、確保量が正かどうかにかかわらず `available now: <整数> MiB` を標準出力へ出す。空文字または未設定ならこの行は出ない。整数変換失敗や `bytearray` 確保失敗は SAVE の `try` 節より前で起きるため、スクリプトは通常の Python 例外終了経路に入り、`SAVE: refused` の表示対象にはならない（`tools/research/tools/live-probes-2026-10/session_pressure_test.py:57-70`）。測定値の記載はない。

## 根拠

- `tools/research/tools/live-probes-2026-10/session_pressure_test.py:2-9,57-100` — probe の目的、値判定、メモリ確保、SAVE / retry / 終了表示。
- `tools/research/tools/live-probes-2026-10/README.md:3,13` — 単一バグ用 live probe としての位置づけ。
- `docs/DETAILS.md:928-943` — session save の RAM 判定、reclaim、サーバーが返す失敗分類。`HOG_TARGET_MIB` の意味を説明する資料ではなく、probe の対象機能との照合にのみ参照。
