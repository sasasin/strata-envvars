# `STRATA_EXE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`STRATA_EXE` は Strata 本体の一般設定ではなく、会話キャッシュ等を検証する3つのテストスクリプトが起動するエンジン実行ファイルを差し替えるために読みます。利用箇所は `tools/batch_groups_cache_test.py`、`tools/cancel_park_test.py`、`tools/session_pressure_test.py` です。これらは設定 JSON の `exe` を既定にし、選んだパスと設定由来の引数を `serve.server.StrataEngine` に渡します。

## 値と判定

3スクリプトとも `os.environ.get("STRATA_EXE", cfg["exe"])` を使います。文字列の parse、空白除去、パス検証、既定値への fallback はこの式にはありません。

| 状態 | 選ばれる実行ファイル |
|---|---|
| 未設定 | 設定 JSON の `exe` |
| 空文字を設定 | 空文字列（`cfg["exe"]` には戻らない） |
| その他の設定値 | その文字列をそのまま使用 |

値は各スクリプトのトップレベルで `StrataEngine` を作る時に一度読み取られます。プロセス起動後の環境変更を再読する処理はありません。CLI 引数はエンジンに渡す別の引数リストであり、`STRATA_EXE` の実行ファイル選択を上書きする処理は見つかりませんでした。

## 有効になる条件

対象3スクリプトを実行した場合に限り、この選択が行われます。Strata の `serve/server.py`、C++/GPU エンジン本体、`setup.py` には `STRATA_EXE` の参照がありません。したがって、この名前を Strata サーバー/CLI の一般設定やエンジン内部設定として扱う根拠はありません。

## 実行時の詳細

スクリプトは選択した文字列を `StrataEngine(exe, ...)` に渡します。`StrataEngine` はこれを起動時の実行ファイルとして保存し、ログが有効なら `[strata] ... engine started: {exe} --serve ...` を記録してから、`[exe, "--serve", *args]` を子プロセスとして起動します。子プロセス環境は呼び出し側の `child_env(cfg)` が作り、元の環境をコピーした後、構成値等を適用します。エンジン側で `STRATA_EXE` を読んで別の実行ファイルへ切り替える処理は確認できませんでした。

指定パスを起動できない場合、`StrataEngine` の `popen` 呼び出しが `OSError` を再送出します。プロセスが起動しても `READY` を返さない、または準備前に終了した場合は、起動再試行条件を満たす場合を除き `EngineDied` を送出します。これはテストハーネスが選択した実行ファイルの起動結果であり、`STRATA_EXE` 自体についての警告やエラー文ではありません。

## 根拠

- `tools/batch_groups_cache_test.py:21-33` — 設定 JSON を読み、`STRATA_EXE` を `cfg["exe"]` の fallback 付きで取得して `StrataEngine` に渡す。
- `tools/cancel_park_test.py:22-31` — 同じ選択。設定 JSON の `args` と `STRATA_EXTRA_ARGS` は別に渡す。
- `tools/session_pressure_test.py:20-30` — 同じ選択。設定 JSON の `args` と `STRATA_EXTRA_ARGS` は別に渡す。
- `serve/server.py:1017-1024,1039-1042,1057-1062,1074-1084` — `exe` を起動情報・BUILD.json の照合・ログに用い、`[exe, "--serve", *args]` を起動する。起動時の `OSError` は再送出する。
- `serve/server.py:1085-1153` — `READY` 待ち、準備前終了時の条件付き再試行と `EngineDied` 経路。
- `serve/server.py:3747-3760` — 子プロセス環境は `os.environ` のコピーから構成され、設定の `env` が値を上書きできる。
- `rg -n --hidden --glob '!.git/**' 'STRATA_EXE'` の全参照は上記3テストスクリプトのみ。候補索引 `docs/envvars/000_envvers.md:763-765` には `STRATA_EXE` が列挙されていますが、本体設定ではなくテストハーネス専用の参照でした。
