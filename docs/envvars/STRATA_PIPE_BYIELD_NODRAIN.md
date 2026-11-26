# `STRATA_PIPE_BYIELD_NODRAIN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

サーバーのバッチ・パイプライン処理で `BYIELD` 制御行を受け取ったとき、処理中の group を drain してから行を処理する通常経路を省くスイッチ。値が有効で対象経路に入ると、`BYIELD` は drain を行わず、その後の制御行処理で破棄される。対象行が `BYIELD` 以外なら drain 条件はこの変数では変わらない（`engine/src/program/generate.cpp:18415-18423,18459-18464`）。

## 値と判定

`pipe_byield_nodrain_env()` が `std::getenv` で値を取得し、値が設定されていて先頭文字が `'0'` でなければ有効とする。文字列全体の parse や真偽値変換はしない。空文字列は先頭が NUL で `'0'` ではないため有効。`0`、`01`、`0anything` は無効で、`1`、`true`、`false`、先頭に空白がある ` 0` は有効。大文字小文字・数値としての妥当性は判定しない（`engine/src/program/generate.cpp:481-487`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `generate.cpp` の判定 | off | 空文字、`1`、`true`、`false`、` 0` | `0`、`01`、`0anything` |

## 有効になる条件

- `--batch` が正数で、`--batch-groups` の解決値が 1 より大きく、`n_pipe` が 1 より大きいこと。`n_pipe` は GPU stage 数に 1 を加えた値で、この条件で `piped` が true になる（`engine/src/program/generate.cpp:17529-17533`）。
- メインループが `batch_on()` または `piped && pipe_inflight()` の入力処理に入り、`BSTOP ` で始まらない行を検査すること。`BYIELD` の場合に限り drain を省略する（`engine/src/program/generate.cpp:18410-18423`）。
- `--batch` / `--batch-groups` はパイプライン経路を決めるが、値判定に対する CLI 引数の上書きや別環境変数との優先順位はない（同: `1024-1026,4046-4048,17529-17533,18417-18418`）。
- 変数自体には OS、GPU 世代、モデル状態を検査する分岐がない。実際の適用範囲は上記の `piped` 経路に限られる（同: `17529-17533,18417-18418`）。

## 実行時の詳細

値は `pipe_byield_nodrain_env()` 内の関数ローカル `static const bool` に保存され、初回呼び出し時に一度だけ取得される。呼び出しは `piped` かつ `BSTOP ` 以外の入力行について drain 条件を調べる箇所にあるため、プロセス起動時とは限らず、最初にその条件を通った時点でキャッシュされる。以後の環境変更は反映されない（`engine/src/program/generate.cpp:481-487,18417-18418`）。

通常は `pipe_drain()` が group の in-flight がなくなるまで `pump(false)` を行い、最後に `pmtp_settle()` する。これが失敗した場合、メインループは `1` を返す。スイッチが有効で入力行が `BYIELD` で始まると、この呼び出しを通らず、次の分岐で `BYIELD` を処理して `continue` する（同: `18397-18401,18417-18423,18459-18464`）。このため、当該 `BYIELD` に対する drain と、その drain に伴う失敗終了経路が省かれる。

## ログと測定値

`STRATA_TRACE` が設定されていると `BYIELD` 分岐で stderr に `strata trace: BYIELD dropped, %d groups in flight` を出す。これは `BYIELD` を処理したときの in-flight group 数であり、変数の有効・無効を示す専用ログではない。drain を実行した経路では `STRATA_TRACE` により drain 時間のログも出るが、drain を省略した `BYIELD` ではそのログ処理を通らない（`engine/src/program/generate.cpp:18419-18431,18459-18463`）。

Strata の `docs/BATCHING.md:115-127` は、このスイッチを「pipelined batch に届いた BYIELD を group drain なしで破棄」と記載しており、実装と一致する。同節にこの変数単独の測定値はないため、速度・出力への影響は記載しない。

## 根拠

- `engine/src/program/generate.cpp:481-487` — 環境変数の読み取り、値判定、static cache。
- `engine/src/program/generate.cpp:17529-17533` — パイプライン batch の成立条件。
- `engine/src/program/generate.cpp:18397-18401,18410-18423` — drain の動作、入力経路とスキップ条件。
- `engine/src/program/generate.cpp:18459-18464` — `BYIELD` の破棄と trace ログ。
- `docs/BATCHING.md:115-127` — スイッチの説明と測定記載の照合。
