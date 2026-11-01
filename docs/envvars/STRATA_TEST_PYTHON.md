# `STRATA_TEST_PYTHON`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata 側の作業ツリーは `## main...origin/main` で、未コミット変更はありません。外部ライブラリの環境変数は対象外。

## 役割

`apps/host/tests/timeskip-real.test.mjs` 専用の Python 実行ファイル指定です。Time-skip の実処理や通常の Strata 起動設定ではなく、Node のテストが Python を見つけて実行できるか確認し、Python を必要とするテストを実行する際のコマンドを決めます。リポジトリ全体の完全一致検索では、このテストファイルの 1 箇所だけが名前を参照します。本番コード、セットアップ、サーバー設定による読み取りは見つかりませんでした。

## 値と判定

| 状態 | 選択されるコマンド | テスト上の扱い |
|---|---|---|
| 未設定（`process.env.STRATA_TEST_PYTHON` が `undefined`） | Windows (`win32`) では `python`、それ以外では `python3` | そのコマンドで `--version` を実行し、終了 status が `0` の場合だけ Python 依存テストを実行 |
| 空文字 | 空文字 | `??` は空文字を既定値に置き換えない。空コマンドでの `--version` 実行は成功 status `0` にならず、Python 依存テストは skip される |
| その他の設定値 | 値全体を実行ファイル名として使用 | 数値化、trim、shell 分割、パス検証、バージョン文字列の検査はしない。`--version` の status が `0` でなければ skip |

設定値にコマンド引数を併記する構文はありません。値は `spawnSync(PYTHON, ['--version'], ...)` の第 1 引数にそのまま渡されます。無効な実行ファイルや非ゼロ終了は別の値への fallback ではなく、Python 依存テストの skip につながります。skip の理由文字列は `no python on this machine` です（`apps/host/tests/timeskip-real.test.mjs:15-16,55,87,98`）。

## 有効になる条件

- `apps/host/tests/timeskip-real.test.mjs` を Node のテストとして実行した場合にだけ参照されます。パッケージの `test` script は `apps/host/scripts/test.mjs` で、`node --test` にテストファイル群を渡します（`apps/host/package.json:27`, `apps/host/scripts/test.mjs:1-7,14`）。
- OS 条件は、未設定時の既定コマンド選択だけにあります。明示値は Windows / 非 Windows のどちらでも同じ方法で使用されます。
- `hasPython` はテストモジュールのトップレベルで計算されます。この結果で skip 条件が決まるため、同じ Node プロセスで後から環境変数を変えても再判定されません。
- CLI オプションや他の Strata 環境変数との優先順位はありません。明示値があれば OS 別の既定値より優先されます。

## 実行時の詳細

モジュール読み込み時に `PYTHON` を定数へ取り込み、ただちに `--version` を同期実行します。`status === 0` だけを確認し、出力内容は確認しません。`hasPython` が false のときも Python 非依存のテストは登録・実行され、Python を使う 3 件のテストだけが `skip: 'no python on this machine'` によって skip されます（`apps/host/tests/timeskip-real.test.mjs:15-16,55,87,98`）。

Python 依存テストでは同じ `PYTHON` 値を `createTimeSkip({ ..., python: PYTHON, ... })` に渡します。Time-skip 実装はこれを Python コマンドとして `strata.py` と CLI 引数に付けて spawn し、`PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`、`STRATA_TIMESKIP_DIR` を含む環境を子プロセスへ渡します（`apps/host/tests/timeskip-real.test.mjs:63,93,107`; `apps/host/server/timeskip.mjs:291-292,302-309,446-455`）。したがってこの変数が指定するのはテスト側の起動コマンドであり、Strata の本番コードが `STRATA_TEST_PYTHON` を読むことや、子の Python がこの変数名を解釈することを示す実装はありません。

Python 依存テスト内で起動に失敗すると、`timeskip.mjs` は `could not start the Time-skip command: ...` をエラーとして返します。`startDetached` を使うテストはその結果を `assert.ok(started.ok, JSON.stringify(started))` で検査するため、テスト失敗として観測されます（`apps/host/server/timeskip.mjs:457-462,477-482`; `apps/host/tests/timeskip-real.test.mjs:65-66,108-109`）。初回 `--version` の失敗自体は例外やログとして報告されず、上記の skip に使われます。

## 根拠

- `apps/host/tests/timeskip-real.test.mjs:14-16` — 環境変数の読み取り、OS 別既定値、同期 `--version` 確認。
- `apps/host/tests/timeskip-real.test.mjs:55,87,98` — Python が使えない場合に skip するテスト群。
- `apps/host/tests/timeskip-real.test.mjs:63,93,107` — 選択値を Time-skip helper に渡す箇所。
- `apps/host/server/timeskip.mjs:291-309,446-455` — 渡されたコマンドで `strata.py` を起動する実装と子プロセス環境。
- `apps/host/server/timeskip.mjs:337-361,457-482` — 起動エラー、終了結果、タイムアウト等の返却経路。
- `apps/host/package.json:27`, `apps/host/scripts/test.mjs:1-7,14` — テスト実行入口。
