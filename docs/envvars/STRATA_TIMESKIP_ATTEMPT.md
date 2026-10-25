# `STRATA_TIMESKIP_ATTEMPT`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部依存の環境変数は対象外。

## 役割

Time-skip の各 revision command に、現在の試行番号を渡すための内部環境変数です。`strata timeskip run --revise-command ...` の実行経路で、Strata CLI が環境変数を設定します。通常のモデル実行設定ではありません。CLI の `--attempts` は試行回数の上限であり、各 revision command に渡るこの値は 1 から始まる個別の試行番号です。

## 値と判定

| 読み取り箇所 | 未設定 | 設定値の扱い | 空文字・不正値 |
|---|---|---|---|
| `strata_cli/cli.py` の起動側 | 既定値なし。各試行時に値を設定する | Python の整数 `attempt` を `str()` で10進文字列化して設定 | 親プロセスに同名変数があっても各試行の値で上書き |
| `integrations/harness/revise_once.py` | 文字列 `"1"` | 文字列のまま使い、数値変換・検証をしない | 空文字は空文字のまま一時ディレクトリ名と request ID に入る |
| `apps/host/server/timeskip-revise.mjs` | nullish coalescing により数値 `1` | JavaScript の `Number()` で変換 | 空文字や空白だけは `0`、数値化不能な文字列は `NaN`。後者は JSON 化で `null` になる |

CLI の `TimeSkipRun` は `range(1, max_attempts + 1)` の index を revision callback に渡します。CLI 引数経由では番号は正の整数で、0 回のとき revision command 自体が呼ばれません。外から両スクリプトを直接起動する場合の任意文字列に対する検証や範囲制限はありません。

## 有効になる条件

`strata timeskip run` に `--revise-command` が指定され、実際に1回以上の revision 試行が始まる場合に CLI が設定します。未指定なら revision callback は `None` を返し、環境変数を読む子プロセスは起動しません。試行回数の上限は CLI では `TimeSkipRun` に渡されて0以上に丸められます。App Host から起動する経路では `apps/host/server/timeskip.mjs` が指定値を 0〜10 に制限します。

## 実行時の詳細

試行ごとに `strata_control/time_skip.py` は index 付きの候補ディレクトリを作り、CLI はその候補ディレクトリを current working directory にして revision command を実行します。CLI は親環境を複製したうえで `STRATA_TIMESKIP_ATTEMPT` を試行 index の文字列に置き換えます。したがって、親プロセスの値は引き継がれず、各子プロセスで番号が更新されます。

Harness 用 `integrations/harness/revise_once.py` はこの文字列を一時 Harness home の `strata-revise-a{attempt}-` prefix と、Harness session の `requestId`（`timeskip-{attempt}`）に含めます。これは試行ごとの分離・識別に使われ、候補の採否はチェック処理が決めます。

アプリ内 assistant 用 `apps/host/server/timeskip-revise.mjs` は環境値を数値化して JSON request body の `attempt` に載せます。しかし、現行の `/api/internal/timeskip-revise` handler は `cwd` と `prompt` を使っており、`body.attempt` は参照していません。この経路では値は handler 以降の処理を変えません。ホストの内部 endpoint は内部 secret を検査し、候補フォルダーが Time-skip の state directory 配下にあることも確認します。

## 根拠

- `strata_cli/cli.py:357-363,1557-1572` — revise command の契約、各試行での環境設定・上書き、および起動条件。
- `strata_control/time_skip.py:422-449` — 1始まりの試行 index と候補 directory の生成。
- `apps/host/server/timeskip.mjs:426-436,446-455` — App Host の試行回数制限と起動引数。
- `integrations/harness/revise_once.py:84-105,129-136` — 未設定時の既定文字列、変換しない読み取り、一時領域と request ID での使用。
- `apps/host/server/timeskip-revise.mjs:14-29` — Node 側の既定値、`Number()` 変換、request body への格納。
- `apps/host/server/index.mjs:1164-1174,1188-1199` — 内部 endpoint の検証と、受信した `attempt` が現行処理で使われないこと。

`docs/DETAILS.md` にこの変数の記載はありません。性能や品質の測定値に関する主張はありません。
