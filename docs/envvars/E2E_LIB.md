# `E2E_LIB`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

同梱の E2E スクリプト `apps/host/scripts/agent-lost-e2e.mjs` で使うライブラリフォルダーのパスです。スクリプトが自分で `serve/server.py` を起動する経路に限り、この値をサーバー設定の `lib_dirs` とサーバープロセスの `LD_LIBRARY_PATH` に渡します。Strata の通常の CLI やエンジンが `E2E_LIB` という名前を直接読む実装は見つかりませんでした。

## 値と判定

| 状態 | スクリプトの値 | 結果 |
|---|---|---|
| 未設定 | `join(HOME, 'agentlost/eng')`。`HOME` は環境の `HOME`、未設定なら空文字 | 既定のライブラリフォルダーを使う |
| 空文字を明示 | 空文字のまま | fallback しない。`lib_dirs` に空文字を入れ、サーバープロセスの `LD_LIBRARY_PATH` も先頭が区切り文字になる形で設定する |
| その他の設定値 | 文字列をそのまま使う | 数値変換、真偽値判定、trim、範囲検査はしない |

読み取りは共通 helper `env(name, fallback) => process.env[name] ?? fallback` によります。したがって未設定 (`undefined`) だけが fallback になり、空文字は設定値として残ります。ライブラリパス自体に対するスクリプト側の存在確認はありません。

## 有効になる条件

`E2E_BASE_URL` が空文字または未設定で、スクリプトが既存サーバーではなく新しい `serve/server.py` を起動する場合にだけ `E2E_LIB` を読みます。`E2E_BASE_URL` が空でない場合は既存サーバーを使うため、`E2E_LIB` は参照されず、そのサーバーのライブラリ環境も変更しません。

また、`STRATA_HARNESS_DIR` が未設定ならスクリプトは `E2E_LIB` を読む前に `STRATA_HARNESS_DIR is not set` を stderr に出して終了コード 2 で終了します。`E2E_LIB` は必須パス検査の対象ではありません。スクリプトは `E2E_ENGINE`, `E2E_PACK`, `E2E_GGUF1`, `E2E_GGUF2`, `E2E_MTP` のパスだけを `existsSync` で確認し、不足時は `missing: <path>` を出して終了コード 2 で終了します。

## 実行時の詳細

新規サーバー経路では、値を JSON 設定の `lib_dirs: [lib]` に格納し、同時にサーバープロセスの環境の `LD_LIBRARY_PATH` を `${lib}:${既存値または空文字}` にします。設定 JSON の `lib_dirs` はサーバーの `child_env()` で `Path(d).is_dir()` を満たす要素に絞られ、Linux 等では子エンジン用 `LD_LIBRARY_PATH` の先頭に追加されます。空文字は `Path('')` が現在の作業ディレクトリを指すため、通常はこのディレクトリ検査を通り、空のパス要素として残ります。Windows ではサーバー側の共通処理は `PATH` を対象にしますが、この E2E スクリプト自身は起動環境に常に `LD_LIBRARY_PATH` を設定しています。

値の変更はスクリプト起動時に `lib` を決め、JSON と子プロセス起動環境を作る際に反映されます。リクエストごとの再読み込みや、実行中の環境変更を再評価する処理はありません。`lib_dirs` が存在しないディレクトリを指す場合、サーバーの `child_env()` はその要素を除外します。一方、スクリプトが起動するサーバー自身には `LD_LIBRARY_PATH` の値が渡されます。

`E2E_LIB` 固有のログや警告はありません。スクリプトがサーバーの準備完了を得られなかった場合は `the engine did not become ready` を stderr に出し、終了処理でコード 4 を指定しますが、この結果が `E2E_LIB` に起因するとはコードから判定できません。

## 根拠

- `apps/host/scripts/agent-lost-e2e.mjs:29-35` — `env` helper、`HOME` と `E2E_BASE_URL` の決定。
- `apps/host/scripts/agent-lost-e2e.mjs:44` — Harness 環境の検査と終了コード 2。
- `apps/host/scripts/agent-lost-e2e.mjs:58-66` — 既存サーバー分岐、`E2E_LIB` の読み取りと既定値、必須パス検査からの除外。
- `apps/host/scripts/agent-lost-e2e.mjs:67-78` — `lib_dirs` 設定、サーバープロセスの `LD_LIBRARY_PATH`、`serve/server.py` 起動。
- `apps/host/scripts/agent-lost-e2e.mjs:86-93` — サーバー準備待ちと失敗時の終了コード 4。
- `serve/server.py:4054-4057,4085-4089` — 子エンジン環境の構築、存在する `lib_dirs` の選別とライブラリ検索パスへの追加。
- `serve/server.py:9139-9142,1151-1154` — `child_env()` で環境を作り、環境を渡してエンジン子プロセスを起動。
