# `STRATA_WATCHDOG_S`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

serve エンジンがリクエスト処理中に進捗 heartbeat を失ったとき、エンジンを止めるまでの秒数を指定する。CUDA/HIP 側では既定値60秒、`0` なら watchdog thread を起動しない。正の値では進捗停止を検出すると stall report を stderr に出し、GPU wait を解放して `abort()` する。サーバーがエンジンを再起動できるようにする仕組みであり、生成の計算内容を変える設定ではない。実装は `engine/src/program/generate.cpp` の serve request loop にある（同ファイル:16261-16323）。SYCL には別実装がある（`engine/sycl/src/program/generate.cpp:9543-9571`）。

## 値と判定

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA/HIP の通常エンジン | 60秒 | 空でない10進整数を全体として読み、0〜604800。例: `0` は監視停止、`1`、`+5`、` 5`、`604800` は受理（正の値は秒数） | 空文字は unset と同じ60秒。`true`、`5s`、`0anything`、`-1`、末尾空白、604801、`long` 範囲外は拒否し既定60秒へ戻す |
| Intel Arc の SYCL エンジン | 60秒 | `atoi` の結果が正ならその秒数。例: `1`, `5s`, ` 5`, `+5` はそれぞれ1、5、5、5秒 | `0`、空文字、`true`、`abc`、`0anything`、負数は `atoi` の結果が0以下となり監視 thread を起動しない。数値変換の範囲外の値は `atoi` の仕様上、結果を断定できない |

CUDA/HIP 側の parser `watchdog_seconds` は `strtol(..., 10)` を使い、変換エラー、数字なし、文字列末尾の残り、負値、上限超過を拒否する。先頭空白や符号付き正数は `strtol` が許容し、末尾空白は全体 parse 条件に反するため拒否する。拒否時は `bad` を立て、呼び出し元が既定値を使う。未設定と空文字は通常値として拒否されるのではなく、既定値を返す。`engine/include/strata/core/watchdog_limits.hpp:16-29`、呼び出しは `engine/src/program/generate.cpp:16267-16275`。

SYCL 側は `getenv` が null の場合だけ60を使い、設定済みなら `atoi` を直接適用する。`atoi` は文字列全体の妥当性を検査しないため、数字以降は無視され、数字で始まらない文字列や空文字は0になる。正の値を上限604800に制限したり、無効値を警告したりする処理はこの経路にない（`engine/sycl/src/program/generate.cpp:9547-9550`）。

## 有効になる条件

- 変数は serve エンジンの起動時に読み込まれる。watchdog thread は `limit > 0` の場合だけ作られるため、CUDA/HIP では明示的な `0`、SYCL では `atoi` 結果0以下で停止する（`engine/src/program/generate.cpp:16276-16278`、`engine/sycl/src/program/generate.cpp:9548-9551`）。
- Intel Arc は `engine/CMakeLists.txt` の `STRATA_ENABLE_SYCL` による別 backend で、SYCL 固有の parser が使われる。同 CMakeLists は SYCL を Linux x86_64 用と記載する（`engine/CMakeLists.txt:23-31`、`engine/sycl/CMakeLists.txt:255`）。
- 監視対象は request 中の進捗である。アイドル中、または heartbeat が更新された場合は経過時間をリセットする。値の指定だけで watchdog の対象外となる standalone / 非 serve 経路に監視を追加するものではない（`engine/src/program/generate.cpp:16291`、`engine/include/strata/core/progress.hpp:3-7`）。
- CUDA/HIP では別変数 `STRATA_WATCHDOG_IO_S` がファイル tier 読み込み中の追加猶予を決める。未設定時は `STRATA_WATCHDOG_S` の10倍で、これより大きい間は読み込み活動が直近10秒以内にある場合に限って待機を続ける。これは通常の無進捗期限 `STRATA_WATCHDOG_S` 自体を変更しない（`engine/src/program/generate.cpp:16269-16271,16297-16310`）。SYCL 側にはこの追加猶予の読み取りはない。
- ブロッキングする session file 処理が `progress_allow` で期限を設定した場合、その期限までは watchdog が停止判定を保留する（`engine/src/program/generate.cpp:16311-16312`、`engine/include/strata/core/progress.hpp:25-27,71-75`）。
- この値を上書きする CLI 引数や設定ファイルは該当する読み取り・分岐にない。`getenv` を呼ぶ時点のプロセス環境が使われる。

## 実行時の詳細

値はエンジンの serve 起動処理で watchdog thread を作る前に一度読み取られ、thread に値で渡される。関数内 static cache やリクエストごとの再読み取りはないため、起動後に環境を書き換えてもそのプロセスの監視期限には反映されない（CUDA/HIP: `engine/src/program/generate.cpp:16265-16278`; SYCL: `engine/sycl/src/program/generate.cpp:9547-9552`）。

thread は1秒ごとに heartbeat と busy 状態を確認する。進捗がない状態が設定秒数続き、明示的な block allowance 内でもない場合、CUDA/HIP はファイル tier 読み込み猶予も判定したうえで停止処理に入る。標準の期限に達した時点で読み込み猶予中なら、`STRATA_WATCHDOG_IO_S` の総期限まで待つことがある。SYCL はファイル tier の追加判定をせず、設定期限後に stall report を出して停止する（CUDA/HIP: `engine/src/program/generate.cpp:16287-16321`; SYCL: `engine/sycl/src/program/generate.cpp:9552-9569`）。

停止時には `release_gpu_waits(stderr)` と stderr flush の後 `std::abort()` が呼ばれる。サーバー側が再起動するという説明はソースコメントにあるが、ここで確認したのは engine 内の abort 経路までである（`engine/src/program/generate.cpp:16313-16321`、SYCL: `engine/sycl/src/program/generate.cpp:9563-9569`）。

## ログと測定値

CUDA/HIP では拒否された値があれば `strata serve: STRATA_WATCHDOG_S is not a whole number of seconds (0 to 604800): using 60 s` を stderr に出す。`STRATA_WATCHDOG_IO_S` も無効の場合は両名を出し、両方無効の場合の末尾は ` (and 10 x that for the file tier)` となる（`engine/src/program/generate.cpp:16272-16275`）。

期限超過時は CUDA/HIP で `strata serve: no progress for ... s during a request (...) - stopping the engine so the server starts it again (issue #29)`、SYCL では同文の末尾に ` (issue #29)` が付かない文を stderr に出す。続けて stall report を出力し、GPU wait を解放して abort する（上記各 backend の停止箇所）。正常値や unset の設定自体を通知するログはない。

`docs/DETAILS.md:1544` は既定期限を「2 minutes」と記載するが、現行 CUDA/HIP と SYCL の実装はいずれも未設定時60秒であり、記述が食い違う。設定一覧 `docs/SETTINGS.md:355` は NVIDIA/AMD と Intel Arc を対象として掲載しているが、parser の backend 差は説明していない。性能測定値は該当なし。

## 根拠

- `engine/include/strata/core/watchdog_limits.hpp:16-29` — CUDA/HIP 用の全体 parse、範囲、既定値 fallback。
- `engine/src/program/generate.cpp:16261-16323` — CUDA/HIP 側の読み取り、IO allowance、監視、ログと abort。
- `engine/sycl/src/program/generate.cpp:9543-9571` — SYCL 側の `atoi`、監視、ログと abort。
- `engine/include/strata/core/progress.hpp:3-7,25-27,61-75` — heartbeat と block allowance。
- `engine/CMakeLists.txt:23-31`、`engine/sycl/CMakeLists.txt:255` — SYCL backend の分離と対象 platform。
- `docs/DETAILS.md:1544`、`docs/SETTINGS.md:355` — 実装と照合した Strata 資料。
