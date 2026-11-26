# `STRATA_PAR_COUNTERS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

並列 batch の計測用カウンターを有効にする研究・診断用スイッチ。C++ engine は batch window、admission、pipeline drain などの集計を取り、batch が idle になったとき stderr に `strata par: ...` を出す。生成処理のスケジューリングや token 選択を切り替える設定ではない。サーバーの Python 側は空き slot を待った回数と待ち時間を累積し、batch 状態の `/v1/status` に `par_counters` として追加する。実装は `engine/include/strata/program/par_counters.hpp` の `strata::program::ParCounters` と `terminal/serve/server.py` にある（`engine/src/program/generate.cpp` が header を取り込み、GPU engine target に含める）。`engine/include/strata/program/par_counters.hpp:1-10,25-74`、`engine/src/program/generate.cpp:155,16831-16837`、`terminal/serve/server_parts/base.py:280`、`terminal/serve/server.py:5295-5306`、`engine/cmake/strata_gpu_engine.cmake:548-551`。

## 値と判定

数値や真偽値への変換はせず、両実装とも値全体を文字列 `"1"` と比較する。unset、空文字、`0`、`true`、`01`、`1anything`、前後に空白がある値、大文字小文字違いはいずれも無効。範囲・負数という数値判定はない。C++ は `ParCounters` オブジェクト生成時に `getenv` を一度呼び、Python は `base.py` の import 時に `os.environ.get` を評価する。どちらも実行中の環境変更を再読込しない。

| 判定箇所 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| C++ engine | `on_ = false` | `"1"` のみ | 空文字、`"0"`、`"true"`、`"01"`、`"1x"` など |
| Python serve | `False` | `"1"` のみ | 空文字、`"0"`、`"true"`、`"01"`、`"1x"` など |

C++ は `e != nullptr && e[0] == '1' && e[1] == '\0'`、Python は `os.environ.get("STRATA_PAR_COUNTERS") == "1"` で判定する。どちらも無効値を警告せず、無効状態として扱う。`engine/include/strata/program/par_counters.hpp:25-30`、`terminal/serve/server_parts/base.py:280`。

## 有効になる条件

- C++ 集計は engine の batch loop で `ParCounters` が生成され、その後 batch window が完了する経路でのみ値を使う。少なくとも batch window がなく idle になった区間では `flush` が何も出さない。`engine/src/program/generate.cpp:16831-16837,17469-17475,18358-18364`、`engine/include/strata/program/par_counters.hpp:52-54`。
- C++ 判定は engine プロセスの環境で行う。`terminal/serve/server.py` の `child_env` は親環境をコピーしてから config の `env` を反映するため、config の `env` に同名キーを指定すると子 engine 側の値を上書きできる。これは Python サーバー側の import 時判定には遡及しない。`terminal/serve/server.py:4007-4028`。
- Python の `par_counters` は `PAR_COUNTERS` が真で、かつ status 作成時に `engine.batch` が truthy の場合に限り `/v1/status` の live status へ含まれる。slot 待ち計数は slot が選ばれ、slot 待ち状態を抜けたときに加算される。`terminal/serve/server_parts/base.py:280`、`terminal/serve/server.py:2183-2202,5295-5306`。
- CLI 引数による有効化・無効化の分岐はない。サーバーや engine がすでに起動した後に親プロセスの環境だけを変更しても反映されない。server の `PAR_COUNTERS` は import 時、C++ は `ParCounters` 構築時の値を保持する。`terminal/serve/server_parts/base.py:280`、`engine/include/strata/program/par_counters.hpp:29-30`。

## 実行時の詳細

C++ 側は `on_` が false なら各計測 hook が即時 return する。true の場合、batch window ごとの行数・live slot 数、admission の prompt token 数と prompt 時間、pipeline control line 前の drain 時間や in-flight group 数などを host 側カウンターに加算する。pipeline 経路では `pc.on()` のときに in-flight group 数も数える。GPU 同期を追加する処理ではなく、header の説明では既存の待ち地点で時間を計測する。batch loop が全 slot idle になったタイミングで `flush` し、集計を stderr に書いた後カウンターを reset する。計測対象がないときは出力しない。`engine/include/strata/program/par_counters.hpp:3-10,32-74`、`engine/src/program/generate.cpp:18410-18424`、`engine/src/program/generate.cpp:17469-17475,18358-18364`。

Python 側は slot を取れず待ち始めた時刻 `admit_since` と、後に空き slot を取得した時刻との差を `queue_wait_s` に加算し、`queued` を 1 増やす。これは admission 中に control line を待った時間そのものではなく、空き slot を待っていた区間の集計である。status に含める値は `dict(self.par_counters)` のコピー。カウンターは server object の初期化で `{"queued": 0, "queue_wait_s": 0.0}` として作られ、以後の slot 待ち成功で累積する。`terminal/serve/server.py:1006-1015,2183-2202,5295-5306`。

## ログと測定値

C++ は batch loop が idle になり計測対象がある場合、stderr に `strata par: wall ...; windows ...; ...` の行を出す。expert 集計に対象差分がある場合は続けて `strata par experts: ...` を出す。`flush` 後に stderr を flush し、カウンターを reset する。`STRATA_PAR_COUNTERS` による警告・エラー・終了経路は実装にない。Python 側は `/v1/status` の live status に `par_counters` を追加するだけで、この変数によるログ出力はない。Strata の `docs/DETAILS.md` にこの変数固有の測定値は確認できない。`engine/include/strata/program/par_counters.hpp:52-75`、`terminal/serve/server.py:5302-5304`。

## 根拠

- `engine/include/strata/program/par_counters.hpp:1-10,25-90` — C++ 判定、計測項目、出力と reset。
- `engine/src/program/generate.cpp:155,16831-16837,17230-17231,17469-17475,18048-18054,18118-18122,18358-18364,18410-18424,23725-23729` — C++ の生成 loop と呼び出し位置。
- `engine/cmake/strata_gpu_engine.cmake:548-551` — `generate.cpp` を含む `strata` target。
- `terminal/serve/server_parts/base.py:280` — Python 側の環境値判定。
- `terminal/serve/server.py:1006-1015,2183-2202,4007-4028,5295-5306` — Python カウンターの初期化・更新・子環境・status への追加。
