# `STRATA_PYTHON`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Strata Terminal の起動スクリプトと App Host の Python resolver 経由で、Strata の Python プログラムを実行する interpreter を明示指定する。Terminal の `terminal/bin/strata`、`terminal/bin/strata.cmd`、`terminal/bin/strata-direct.ps1` は、値が空でなければ自動選択より優先し、その Python で `strata.py` を起動する。App Host の `python-resolver.mjs` では `STRATA_NATIVE_PYTHON` より優先して Python 子プロセスの command に使う。ただし packaged Control の子プロセス環境からはこの変数が除かれ、native-control の packaged 経路は Control 同梱 Python を直接使う。指定 interpreter のバージョンや依存パッケージを一律に検査する設定ではない。 (根拠: `terminal/bin/strata:45-49,142-147`; `terminal/bin/strata.cmd:16-32,42-44`; `terminal/bin/strata-direct.ps1:27-35,55-59`; `app/host/server/python-resolver.mjs:33-43`; `app/host/server/control-runtime.mjs:88-107`; `app/host/server/native-control.mjs:195-201`)

## 値と判定

| 読み取り経路 | 未設定または空文字 | 空でない値 | 値の検査 |
|---|---|---|---|
| POSIX Terminal (`terminal/bin/strata`) | 同梱 Python、PATH 等の候補を探索 | 指定値を最優先し、通常の実行ビット確認または `-c 'pass'` の起動で使えるか確認 | ファイルであることと起動可能性のみ。Python バージョン確認はしない |
| Windows cmd (`terminal/bin/strata.cmd`) | 同梱 runtime、venv、`py -3`、`python` の順に探索 | `if defined` で優先し、パスが存在すれば起動 | 存在確認のみ。Python バージョン確認はしない |
| Windows PowerShell (`terminal/bin/strata-direct.ps1`) | 同梱 runtime、venv、`py -3`、`python` の順に探索 | PowerShell の truthy 判定で優先し、パスが存在すれば起動 | `Test-Path` の存在確認のみ。明示値は起動テスト・バージョン確認をしない |
| App Host resolver (`app/host/server/python-resolver.mjs`) | `STRATA_NATIVE_PYTHON`、Control runtime、repo venv、OS 別候補へ進む | `env.STRATA_PYTHON || env.STRATA_NATIVE_PYTHON` の結果を command としてそのまま返す | 明示値の存在・起動・バージョン確認なし |

Terminal の POSIX / PowerShell / resolver は空文字を「指定なし」と扱う。cmd は `if defined` で判定するため、空値を設定した状態は通常の cmd 環境では未定義と同じく自動探索へ進む。App Host の resolver は文字列を変換せず、空白だけの文字列も非空として採用する。明示値に対して `STRATA_PYTHON="0"`、`true`、`false` などの特別な意味はなく、各ラッパーが interpreter のパス・コマンドとして扱う。 (根拠: `terminal/bin/strata:45-49`; `terminal/bin/strata.cmd:16-32`; `terminal/bin/strata-direct.ps1:27-35`; `app/host/server/python-resolver.mjs:33-43`)

## 有効になる条件

- Terminal ラッパーを通じて起動すること。指定値が使える場合は同梱 runtime や PATH 上の Python より優先される。POSIX では指定先がファイルで起動可能である必要があり、失敗すると自動候補への fallback はせず、`strata: STRATA_PYTHON=... is not executable` を stderr に出して失敗する。Windows cmd / PowerShell は指定先の存在を確認し、存在しない場合は各々 `strata: STRATA_PYTHON=... does not exist` を stderr に出して終了コード 5 で終わる。 (根拠: `terminal/bin/strata:39-49`; `terminal/bin/strata.cmd:29-32,46-48`; `terminal/bin/strata-direct.ps1:30-34`)
- Terminal の自動探索で使われる Python 3.10 以上の確認は PATH 等の候補に対するもので、明示指定した interpreter には適用されない。POSIX は `serve` / `bench` 起動時に必要パッケージを別途検査し、不足なら interpreter のパスを含む案内を stderr に出して終了コード 5 とする。 (根拠: `terminal/bin/strata:65-85,123-140`)
- App Host の resolver では、非空の `STRATA_PYTHON` が `STRATA_NATIVE_PYTHON` に優先する。指定値が使われるのは resolver の呼び出し元がその戻り値で Python 子プロセスを起動する経路である。明示指定値が起動不能でも resolver は代替 interpreter を選び直さず、起動側で失敗する。 (根拠: `app/host/server/python-resolver.mjs:33-43`; 呼び出し例 `app/host/server/index.mjs:800-805`; `app/host/server/native-control.mjs:190-201`)
- Packaged App Host の Control 子プロセスは `controlEnvironment` が子環境から `STRATA_PYTHON` と `STRATA_NATIVE_PYTHON` を除去する。packaged native-control 経路も `control.control.python` を使う。そのため、この環境変数は Control の子プロセス interpreter を差し替えない。 (根拠: `app/host/server/control-runtime.mjs:88-107`; `app/host/server/native-control.mjs:195-201`)

## 実行時の詳細

Terminal の各ラッパーは起動のたびに環境変数を読み、選んだ Python で `strata.py` と元の引数を実行する。POSIX は `exec "$PY" "$APP/strata.py" "$@"` でプロセスを置き換える。指定値がある場合、POSIX は起動確認として `-c 'pass'` を実行するが、その後にバージョンを照会しない。Windows cmd / PowerShell はパスの存在確認後に本体を起動する。 (根拠: `terminal/bin/strata:45-49,90-102,142-147`; `terminal/bin/strata.cmd:16-32,42-44`; `terminal/bin/strata-direct.ps1:27-59`)

App Host resolver は `resolvePython()` の呼び出し時に環境値を参照し、選択結果を module-level `Map` に保存する。cache key に `STRATA_PYTHON`、`STRATA_NATIVE_PYTHON`、repo、Control interpreter、platform を含むため、同一 key では選択結果を再利用し、環境値が異なれば別 key になる。fallback 判定 (`source: 'fallback'`) は cache しない。App Host の server index は module 初期化時に一度 `resolvePython()` を呼んで `PYTHON` として保持する。一方 native-control の `python()` は呼び出し時に resolver を呼ぶ。実行中に環境を変えた場合、すでに保持した `PYTHON` には反映されず、後続 resolver 呼び出しは新しい値または該当 key の cache を使う。 (根拠: `app/host/server/python-resolver.mjs:31-56`; `app/host/server/index.mjs:800-805`; `app/host/server/native-control.mjs:190-201`)

## ログと測定値

POSIX Terminal は明示値を起動できない場合に stderr へ `strata: STRATA_PYTHON=<値> is not executable` を出す。Windows cmd は存在しない場合に `strata: STRATA_PYTHON=<値> does not exist`、PowerShell も同じ文言を出して終了コード 5 とする。指定 interpreter の起動後に発生する Python のエラーは通常の子プロセス出力・終了コードとしてラッパーから返る。App Host resolver 自体には明示値の妥当性を示すログはない。性能測定値は該当しない。 (根拠: `terminal/bin/strata:47-49`; `terminal/bin/strata.cmd:46-48`; `terminal/bin/strata-direct.ps1:30-34,58-59`; `app/host/server/python-resolver.mjs:33-43`)

## 根拠

- `terminal/bin/strata:39-49,90-102,123-147` — POSIX の設定値判定、失敗時出力、子プロセス起動。
- `terminal/bin/strata.cmd:16-32,42-48` — Windows cmd の優先順位、存在確認、起動・失敗処理。
- `terminal/bin/strata-direct.ps1:27-59` — PowerShell の優先順位、存在確認、起動・失敗処理。
- `app/host/server/python-resolver.mjs:31-56` — App Host の値選択、優先順位、cache。
- `app/host/server/index.mjs:800-805` — server index 初期化時の resolver 呼び出し。
- `app/host/server/native-control.mjs:190-201` — source / packaged native-control の interpreter 選択と子環境。
- `app/host/server/control-runtime.mjs:88-107` — Control 子環境から本変数を除去。
