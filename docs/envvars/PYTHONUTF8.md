# `PYTHONUTF8`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、`git status --short --branch` に未コミット変更の表示はありません。

## 役割

Strata は `PYTHONUTF8` の既存値を設定として読み取って分岐するのではなく、Windows の CLI ランチャーとホストアプリの Python 子プロセス環境に `1` を明示設定します。Windows ランチャーのコメントは、Python のテキスト処理を UTF-8 にして、キリル文字などを含むフォルダー名を扱えるようにする意図を記しています（`START-HERE.bat:5-6`、`bin/strata.cmd:9-10`、`bin/strata.ps1:53-54`）。この文書は Strata が設定・引き渡す事実を記録するもので、Python ランタイム内部の環境変数処理は説明対象外です。

## 値と判定

Strata 所有の実行コードに `PYTHONUTF8` の取得、文字列比較、数値変換、未設定・空文字の判定は見つかりません。見つかった本番コードは、いずれも値を文字列 `'1'` に設定して Python プロセスを起動します。

| 起動経路 | 呼び出し元の `PYTHONUTF8` | 子プロセスに渡す値 |
|---|---|---|
| `START-HERE.bat` / `bin/strata.cmd` | 未設定、空文字、その他の値 | `1` に設定してからランチャー経由で Python を実行 |
| `bin/strata.ps1` | 未設定、空文字、その他の値 | Python の選択後、実行直前に `1` を設定 |
| ホストの Python 子プロセス | `process.env` 由来の値があればそれを含む | 環境オブジェクトで `PYTHONUTF8: '1'` を後から指定する経路では `1` に上書き |

したがって利用者が親プロセス側で指定した値を Strata が解釈・尊重する設定ではありません。`apps/host/server/timeskip.mjs:455` は `extraEnv` を `PYTHONUTF8` 設定の後に展開しますが、実際の呼び出し元 `apps/host/server/index.mjs:1160-1165` が追加するのは `STRATA_HOST_URL` と `STRATA_INTERNAL_SECRET` だけで、`PYTHONUTF8` は上書きしません。値に範囲・境界・無効値という概念や、Strata 内の fallback はありません。

## 有効になる条件

- `START-HERE.bat` と `bin/strata.cmd` は Windows バッチランチャーです。`setlocal` の後で `PYTHONUTF8=1` を設定し、後続の Python 起動に引き継ぎます（`START-HERE.bat:4-6,36-55`、`bin/strata.cmd:8-10,34-44`）。`START-HERE.bat` は `.venv` または同梱 Python で `setup.py` を実行するほか、必要なら Python を検出・導入して `.venv` を作ります（同 `:venv`, `:bundled`, `:run`）。
- PowerShell ランチャーも Windows 用です。Python が選べない場合は `PYTHONUTF8` を設定する行より前にエラー終了します。選択できた場合は実行直前に `1` を設定し、`strata.py` を呼び出します（`bin/strata.ps1:25-51,53-57`）。
- ホストアプリの source-checkout サーバー、Control CLI、installer、Time-skip、tuning、native-control の子プロセス環境にも設定があります（下記「実行時の詳細」）。これらの経路では `process.env` 等を展開した環境オブジェクトに `'1'` を明示指定します。
- Strata コード中に、OS/backend/build macro/model 状態によって `PYTHONUTF8` の設定値を切り替える分岐は見つかりません。ホスト側の child process ごとに別の環境項目や実行条件はありますが、`PYTHONUTF8` 自体は固定値です。

## 実行時の詳細

Windows の `START-HERE.bat` と `bin/strata.cmd` は `setlocal` のスコープ内で設定し、Python 起動を含む後続処理へ渡します。`START-HERE.bat` は `setup.py` を実行し（`START-HERE.bat:44-55`）、`bin/strata.cmd` は `strata.py` を実行して Python の終了コードを返します（`bin/strata.cmd:42-44`）。PowerShell 版は Python 実行ファイルを選択した後に環境変数を設定し、`strata.py` を呼び出して、その `$LASTEXITCODE` を返します（`bin/strata.ps1:25-57`）。

ホストアプリでは次の Python 子プロセス環境を構築します。

- source-checkout サーバー環境は `process.env` を元にし、`PYTHONUTF8='1'` と `PYTHONIOENCODING='utf-8'` 等を設定します。native-control はその環境で `serve/server.py` を起動します（`apps/host/server/control-runtime.mjs:82-85`、`apps/host/server/native-control.mjs:387-390`）。
- Control 用環境は親環境を複製し、一部の Python 関連変数を削除した後、`PYTHONUTF8='1'` を含む固定値を設定します。Control CLI と installer の起動にもこの環境が使われます（`apps/host/server/control-runtime.mjs:88-111,124-130`、`apps/host/server/native-control.mjs:106`）。
- Time-skip の通常・detached CLI、tuning CLI は親環境を展開した後に `PYTHONUTF8='1'` を指定します（`apps/host/server/timeskip.mjs:302-310,446-455`、`apps/host/server/index.mjs:839-844`）。
- native-control の source-checkout autotuner と管理ジョブも、`process.env` を展開してから `'1'` を設定します。packaged autotuner は `controlEnvironment()` を使います（`apps/host/server/native-control.mjs:53-55,408-414`）。

これらの環境オブジェクトは子プロセスの起動時に渡されます。Strata 親プロセス内でこの変数を cache したり、リクエストごとに読み直したりする処理はありません。検索範囲で、この設定そのものを知らせるログ、警告、終了・失敗経路は確認できません。ランチャーや子プロセスには独立した起動エラー・終了コード処理がありますが、それらを `PYTHONUTF8` の値による結果とは判断できません。

## 根拠

- Windows ランチャーで固定値を設定し、Python を起動: `START-HERE.bat:4-6,36-55`; `bin/strata.cmd:8-10,34-44`; `bin/strata.ps1:25-57`。
- ホストのサーバー・Control・Time-skip・tuning・native-control 子プロセス環境: `apps/host/server/control-runtime.mjs:82-111,124-130`; `apps/host/server/native-control.mjs:53-55,106,387-390,408-414`; `apps/host/server/timeskip.mjs:302-310,446-455`; `apps/host/server/index.mjs:839-844,1160-1165`。
- 候補一覧: `docs/envvars/000_envvers.md:524`。候補名の完全一致検索では、上記の本番箇所はすべて設定・子プロセスへの引き渡しです。Strata が親環境から値を読み取る本番箇所は見つかりませんでした。このため、候補一覧は「Strata が利用者設定を読み取る環境変数」という意味では不正確です。
- `tools/test_cyrillic_paths.py:34-50` はテスト用子プロセスの環境に値を設定しランチャー内の文字列を確認します。`bench/results/2026-10-09-community-rtx-3060-0141/scripts/strata_bench_run.py:302` はベンチマーク記録用スクリプトで環境辞書に値を設定します。いずれも通常実行コードにおける環境変数の読み取り根拠としては使用していません。
- `docs/DETAILS.md` および他の設計資料に、この環境変数の追加の挙動説明は見つかりませんでした。
