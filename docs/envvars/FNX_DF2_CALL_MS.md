# `FNX_DF2_CALL_MS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

バッチデコードの次窓用ドラフト計画で、DFlash2 の最初のドラフトに見積もる追加時間（ミリ秒）を指定する。既定値は `2.5`。これは `RowOffer.first_ms` として行数プランナーのコスト計算に使われ、実際の待ち時間・タイムアウトや DFlash2 実行時間を設定する値ではない。プランナーがそのレーンに 1 個以上のドラフトを割り当てる場合にコストへ加算される。`FNX_BATCH_FIXED` で固定数を強制する場合はプランナーを通らないため、この値は割当数に影響しない（`engine/src/split/src/batch.cpp:291-305`、`engine/src/split/src/batch_plan.hpp:61-81,128-137`）。

## 値と判定

`fnx::env_num` が `std::getenv` で読み、有限の十進数として文字列全体を `strtod` で変換する。未設定なら既定値 `2.5`。設定された空文字は無効値。先頭文字が符号・小数点・数字のいずれでもない文字列、途中や末尾に余分な文字がある文字列、範囲外、非有限値は `std::runtime_error` になる。先頭・末尾の空白は受け付けず、`x` / `X` を含む値（16 進浮動小数点表記を含む）も拒否する。小数・指数表記および先頭の `+` / `-` は受理される。大文字小文字を区別する文字列スイッチではない。値の下限・上限や clamp はないため、負数やゼロも数値として通る（`engine/src/split/src/env.hpp:24-30,42-48`）。

| 条件 | unset | 設定時に数値として有効な例 | 無効な例 |
|---|---:|---|---|
| `env_num` の判定 | `2.5` | `0`、`1`、`-1`、`+0.5`、`1e2` | 空文字、`true`、`1x`、`0anything`、` 1`、`1 `、`nan`、`inf` |

数値として有効でも、負数・ゼロを含む値に対する範囲検査はない。DFlash2 が有効なバッチ経路で値が負数なら、プランナーに負の追加コストとして渡る。安全な範囲はソースで規定されていない（`engine/src/split/src/batch.cpp:291-305`）。

## 有効になる条件

- `sfnx` サーバーでは `--parallel` 相当の `a.batch` が 1 より大きく、`FNX_BATCH_DRAFTS` が `0` ではないときに `BatchDecoder` が作られる。`FNX_BATCH_DRAFTS` は未設定または `1` で MTP モード、`lookup` で lookup モード、`0` で無効（`engine/src/split/tools/sfnx.cpp:448-458`、`engine/src/split/src/engine_common.cu:1044-1052`）。
- 値がプランのコストに反映されるには、モードが MTP で、Engine に DFlash2 が attach され、`draft_next` が実行される必要がある。ソースでは `df2 = mtp && e_.df2_on()` と判定する（`engine/src/split/src/batch.cpp:262-266,330-332`）。
- DFlash2 が attach されていない場合、または `FNX_BATCH_DRAFTS=lookup` の場合、`first_ms` は `0` にされるため数値はプランには影響しない。ただし `draft_next` が初めて呼ばれれば値自体は解析されるので、無効な文字列はその場合もエラーになる（`engine/src/split/src/batch.cpp:265-266,291-293`）。
- バッチドラフトを無効にした場合、または `sfnx` の batch 数が 1 の場合、サーバーは `BatchDecoder` を生成せず、この環境変数を読む経路に入りません（`engine/src/split/tools/sfnx.cpp:451-458`）。`fnx_run bdecode` も `BatchDecoder` を使いますが、そこで attach されるのは MTP であり DFlash2 ではありません（`engine/src/split/tools/fnx_run.cpp:646-670`）。
- `FNX_BATCH_FIXED` が `-1`（既定）以外なら `draft_next` は各レーンの割当数を固定し、`choose_rows` によるコスト比較を行わない。このときこの値はドラフト数を決めないが、読み取り・数値検証は行われる（`engine/src/split/src/batch.cpp:291-301`）。

## 実行時の詳細

値は `BatchDecoder::draft_next` 内の関数ローカル `static const` として、最初にその行へ到達したとき一度だけ読み込まれる。以後の変更は同じプロセス内では反映されない。読み取りは `df2` の真偽を使ってコストを割り当てる直前に行われ、`df2` が偽でも省略されない（`engine/src/split/src/batch.cpp:262-293`）。

DFlash2 経路では、各レーンの `RowOffer.first_ms` に設定された値が、そのレーンに少なくとも 1 draft を計画した場合の見積もりコストとなる。これにより `choose_rows` / `plan_rows` が期待トークン数対見積もり時間を比較する。計画後の `draft_df2` は、ドラフト対象レーンの要求をまとめて `e_.df2_draft(rq)` に渡す。この値は呼び出しを遅延・中断させず、実際の経過時間は `last_draft_ms` 等の別の計測経路に記録される（`engine/src/split/src/batch.cpp:291-305,330-332,487-511`、`engine/src/split/src/batch.hpp:54-55`）。

## ログと測定値

この値専用の有効化ログや値の表示はない。`FNX_BATCH_TRACE` が有効なら `batch plan:` の行に各レーンのドラフト計画数などが stderr に出るが、`FNX_DF2_CALL_MS` の値自体は出力されない（`engine/src/split/src/batch.cpp:317-328`）。

設定値が不正な場合、helper は `FNX_DF2_CALL_MS: '<値>' is not a number` という例外を投げる（`engine/src/split/src/env.hpp:43-48`）。`sfnx` の実行中に発生すると、stdout の `ERR ...` と stderr の `sfnx: failed: ...` を出して終了コード 1 で終了する（`engine/src/split/tools/sfnx.cpp:1097-1102`）。`fnx_run` のトップレベルで捕捉される場合は stderr に `fnx_run: ...` を出して終了コード 1（`engine/src/split/tools/fnx_run.cpp:1364-1373`）。

`engine/src/split/src/batch.cpp:291` のコメントには既定見積もりの根拠として「one lane's drafter round (about 3 ms alone, overlapped between lanes)」とあるが、これはコードコメント上の目安であり、この調査で測定した値ではない。`docs/SPLIT_ENGINE.md:85` は DFlash2 用のテスター向けスイッチとして名前を挙げるだけで、この変数の値域や動作の詳細は記していない。

## 根拠

- 候補名の直接参照は `engine/src/split/src/batch.cpp:291` の 1 箇所。そこから `env_num` の parse 規則は `engine/src/split/src/env.hpp:24-30,42-48`。
- 適用条件、コストへの設定、固定割当、DFlash2 呼び出しは `engine/src/split/src/batch.cpp:262-305,330-332,487-511`、コスト計算は `engine/src/split/src/batch_plan.hpp:61-81,128-137`。
- サーバーの BatchDecoder 作成条件とエラー出力は `engine/src/split/tools/sfnx.cpp:448-458,1097-1102`。補助 `bdecode` 経路は `engine/src/split/tools/fnx_run.cpp:646-670,1364-1373`。
- 調査対象 revision は `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`。調査開始時の Strata 作業ツリーは `## main...origin/main` で、変更表示はなかった。
