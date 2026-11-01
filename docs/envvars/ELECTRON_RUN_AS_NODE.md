# `ELECTRON_RUN_AS_NODE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata の通常の実行コードがこの環境変数を読み、動作を切り替える箇所は見つかりませんでした。確認できた実装上の用途は、統合 E2E ハーネスが `dsh` エージェントを起動するとき、親プロセスの環境からこの名前を取り除くことだけです。したがって、この文書は Strata 製品の環境変数設定ではなく、当該ハーネスの子プロセス環境の処理を記録します。

## 値と判定

ハーネスは `os.environ` を辞書にコピーし、そのコピーに対して `env.pop("ELECTRON_RUN_AS_NODE", None)` を実行します。変数の値を比較・変換せず、存在しても値は利用しません。未設定の場合も、空文字やその他の値で設定されている場合も、子プロセスへ渡す辞書にはこのキーが残りません。元の `os.environ` は変更されません。

## 有効になる条件

この処理は `integrations/harness/tool_flow_e2e.py` の `start_agent()` が呼ばれた場合に限られます。同関数は環境をコピーして `DSH_HOME` を設定し、`dsh --profile ... --patch ... --port ... --no-open` を起動します。値に基づく条件、OS/backend/build macro、CLI による上書きはありません。

## 実行時の詳細

環境のコピーとキー削除は `subprocess.Popen()` より前に実行され、削除後の辞書が `dsh` の `env` として渡されます。このコード自体は標準出力・標準エラーへ警告を出しません。`Popen` の起動結果や失敗は通常の子プロセス起動として呼び出し元に返り、この環境変数に固有の終了・失敗処理はありません。

## 根拠

- `integrations/harness/tool_flow_e2e.py:430-445` — `start_agent()` が親環境をコピーし、`ELECTRON_RUN_AS_NODE` を値によらず削除してから `dsh` に渡す。
- `integrations/harness/tool_flow_e2e.py:515` — ハーネスの agent 起動経路から `start_agent()` を呼び出す。

候補一覧にはこの名前がありますが、通常の Strata 実行系による読み取りは確認できず、実装参照は上記のハーネスだけでした。`docs/work/IMPLEMENTATION_STATUS.md` にも Electron 利用時の過去の記述がありますが、これは現在の Strata 実行コードによる読み取り・転送を示す根拠ではないため、現行動作としては扱っていません。
