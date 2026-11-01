# `E2E_ENGINE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`apps/host/scripts/context-e2e.mjs` が実エンジンを使うコンテキスト E2E 実行で、起動する Strata 実行ファイルのパスを指定します。アプリ本体の通常起動設定ではなく、この手動実行スクリプト専用です。スクリプトのコメントは `node scripts/context-e2e.mjs` による実行を案内し、エージェント README も実エンジン実行の場所としてこのスクリプトを挙げています（`apps/host/scripts/context-e2e.mjs:3-16`, `apps/host/server/agent/README.md:148-155`）。

## 値と判定

| `E2E_ENGINE` の状態 | `ENGINE` の値 | ローカルエンジン起動モードでの結果 |
|---|---|---|
| 未設定 | `C:\\Users\\AI-Server\\Desktop\\Strata\\GitHub\\wt-023-int\\build-cuda\\strata.exe` | この既定パスを存在確認し、無ければ `missing: <パス>` を stderr に出して終了コード 2 |
| 空文字 | 空文字のまま | 空パスを存在確認し、通常は `missing: ` を stderr に出して終了コード 2 |
| 空でない任意の文字列 | その文字列をそのまま使用 | 対象パスの存在確認後、サーバー設定の `exe` として渡す |

読み取り helper は `process.env[name] ?? fallback` です。従って未設定（`undefined`）だけが既定値に置き換わり、空文字は既定値になりません。文字列の trim、形式検証、正規化、値域変換はこのスクリプトでは行いません。読み取りはモジュール評価時に一度行い `const ENGINE` に保持されます。実行中の環境変更を再読込する処理はありません（`apps/host/scripts/context-e2e.mjs:25-34`）。

## 有効になる条件

- スクリプトを実行し、`E2E_BASE_URL` が未設定または空文字の場合にローカル起動経路となります。この経路では `STRATA_HARNESS_DIR` が設定されている必要があり、未設定なら `STRATA_HARNESS_DIR is not set` を stderr に出して終了コード 2 です。続けて `ENGINE` とモデルファイルの存在、および空き RAM を確認します（`apps/host/scripts/context-e2e.mjs:36-49`）。
- `E2E_BASE_URL` が空でない場合は既存サーバー接続経路です。`ENGINE` とモデルファイルの存在確認をせず、Python サーバーも起動しません。`ENGINE` は設定 JSON に書かれますが、この経路ではその JSON をサーバーへ渡さないため実行に使われません（`apps/host/scripts/context-e2e.mjs:36-37,47-49,55-61,78-80,87-92`）。
- ローカル経路では `ENGINE` が一時 JSON の `exe` に設定されます。スクリプトは `serve/server.py --engine strata --config <一時設定>` を起動します。サーバーは設定 JSON を読み込み、`cfg["exe"]` を実行ファイルとして選びます。絶対パスでなければ設定の `cwd` を基準に絶対化し、通常の単一エンジン経路では `[exe, "--serve", *args]` として起動します（`apps/host/scripts/context-e2e.mjs:55-61,78-80`; `serve/server.py:9074-9078,9186-9194,9246-9251,9273-9279,1074-1084`）。このスクリプトが記述する既定値は Windows の絶対パスです。

## 実行時の詳細

この変数の値は Node.js プロセス開始時に読み取られ、ローカル経路では JSON の `exe` フィールドへ転送されます。Python サーバー側が `E2E_ENGINE` 自体を読み直すのではなく、その JSON 設定値を使用します。Node.js から Python サーバーへの環境は `process.env` の複製を基に作られ、`PATH` と `STRATA_DATA_DIR` を上書きしますが、`E2E_ENGINE` はそのまま継承されます（`apps/host/scripts/context-e2e.mjs:25-28,55-61,78-80`）。

ローカル経路で指定パスが存在しない場合、プロセス起動前に `missing: ${f}` を stderr に出して終了コード 2 になります。存在しても起動できない場合は Python サーバー側の起動が `OSError` となり、スクリプトは `/health` の応答を待ちます。準備完了にならなければ末尾のサーバー出力とともに `the engine did not become ready:` を stderr に出し、終了処理で終了コード 4 にします（`apps/host/scripts/context-e2e.mjs:47-49,78-95`; `serve/server.py:1077-1084`）。起動できた場合、サーバーのログには `engine started: <exe> --serve ...` が記録されます（`serve/server.py:1057-1062`）。その後スクリプトは `/health` と `/v1/models` を使って準備状態とモデル名を表示し、4 シナリオを走らせます（`apps/host/scripts/context-e2e.mjs:87-98,126-182`）。

## 根拠

- 候補一覧: `docs/envvars/000_envvers.md:349`。
- 環境値の読み取り、既定値、定数への保持: `apps/host/scripts/context-e2e.mjs:25-34`。
- モード選択、事前検査、一時設定への格納、Python サーバー起動: `apps/host/scripts/context-e2e.mjs:36-61,78-95`。
- 実エンジン E2E としての位置付け: `apps/host/scripts/context-e2e.mjs:3-16`, `apps/host/server/agent/README.md:148-155`。
- サーバー設定読込と `exe` 解決、起動: `serve/server.py:9074-9078,9186-9194,9246-9251,9273-9279,1057-1084`。

候補名のソース全体検索では実際の参照は `apps/host/scripts/context-e2e.mjs:28` の一箇所でした。`env` helper の定義と全呼び出しも確認し、この helper は環境値を `process.env` から取得しています。外部ライブラリや GPU driver が読む変数として扱う根拠はありません。
