# `STRATA_REPLICA_START`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata サーバーのデータ並列 replica を初期化するとき、各 engine の開始を逐次行うか、スレッドで同時に行うかを選びます。`serve/server.py` がこの変数を読む唯一の箇所です。これは replica の有効化や数を決めず、すでに replica group が選ばれて `start_replicas()` に入った場合の開始方法だけを変えます。

## 値と判定

| 値 | 動作 |
|---|---|
| 未設定 | 並列開始 |
| `serial` と完全一致 | 逐次開始 |
| 空文字、`Serial`、`serial `、その他すべて | 並列開始 |

実装は `os.environ.get("STRATA_REPLICA_START", "") == "serial"` の完全一致です。空白除去、大小文字変換、真偽値・数値への変換はありません。範囲や無効値エラーもありません。未設定時と未一致時の既定動作は、各 engine の開始関数をスレッド群で動かす方式です。

## 有効になる条件

- Strata サーバーモードで、設定または `--replicas` により複数の GPU group が構成され、`gpu_groups()` が空でない場合に限り参照されます。`--replicas` は設定の `replicas` を上書きします。replica 設定がない場合や group が一つ以下なら通常の単一 engine 経路となり、この変数は使われません。
- `--engine mock` や `start_split()` 経路では `start_replicas()` に入らないため影響しません。
- CLI 引数や設定項目から開始順を指定する経路はありません。この環境変数の判定は replica 設定・GPU group の決定後に行われます。
- lazy 起動では `StrataEngine` の初期化が子プロセスを起動せずに戻るため、この分岐が順序づけるのは engine オブジェクトの作成です。通常起動では各 `StrataEngine` の初期化が子 engine の `READY` を待ってから戻るため、逐次モードでは次の replica の開始は前の初期化完了後になります。

## 実行時の詳細

`serial` の場合、`start_replicas()` は replica index 順に `one(i)` を呼びます。それ以外は全 replica 用の thread を作成・開始し、すべて join します。`one(i)` は replica ごとの設定・環境を用意して `StrataEngine` を作り、例外は収集して次の replica の開始を続けます。したがって `serial` は失敗した replica の時点で即座に中断する設定ではありません。

各 child の環境は `child_env()` が親の `os.environ` をコピーして作ります。候補名の全参照検索では、Strata が child 起動後に `STRATA_REPLICA_START` を読む箇所は見つかりませんでした。よって確認できる効果はサーバー側の初期開始順です。設定値に対応した専用ログはありません。起動時には replica group の案内が出て、開始失敗時には `[strata] replica ... did not start ...`、共有 arena の条件によっては再試行案内または全 replica の個別 arena への fallback が出ます。

値は `start_replicas()` が呼ばれるたびにその場で参照され、static cache はありません。通常の server 起動では一度評価されます。共有 arena で失敗して再帰的に `start_replicas()` を呼び直す経路では再評価されます。子 engine の後続 restart は保存済み起動情報を使い、replica の初期化順を再選択しません。

## 根拠

- 全候補名の完全一致検索で該当する読み取りは `serve/server.py:8715` の一箇所です。比較条件と逐次・並列の分岐は `serve/server.py:8715-8723`。
- replica の構成は `--replicas` の設定反映 `serve/server.py:9117-9118`、group 判定と `start_replicas()` / split / 単一 engine の選択は `serve/server.py:9261-9279`。group の数値指定・リスト指定の条件は `serve/replicas.py:55-84`。
- 各 replica の engine 作成、失敗収集、arena による再試行、最終失敗は `serve/server.py:8704-8747`。初期案内は `serve/server.py:8695-8702`。
- child 環境が親環境のコピーであることは `serve/server.py:3747-3760`。engine が lazy 時に初期化を返る箇所は `serve/server.py:1017-1045`。通常時の子プロセス起動と `READY` 待機は `serve/server.py:1074-1110`。
- `STRATA_REPLICA_PROFILE` は `setup.py:10348-10358` で replica profile の自動設定に使われますが、名前が異なり、本変数の値判定とは別です。
