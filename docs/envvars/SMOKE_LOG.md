# `SMOKE_LOG`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

同梱の会話キャッシュ・セッション用 smoke test 3本で、Strata engine の stderr ログ保存先を設定ファイルの `log` 値から上書きします。エンジン本体の環境変数設定ではなく、テストスクリプトが `StrataEngine` に渡すログファイル名です。通常の CLI やサーバー起動経路で `SMOKE_LOG` を読む箇所は確認できませんでした。

## 値と判定

3スクリプトはいずれも `os.environ.get("SMOKE_LOG", cfg["log"])` を使います。文字列の parse、trim、範囲検査はありません。

| 状態 | 選ばれる値と結果 |
|---|---|
| 未設定 | 設定 JSON の必須キー `log`。通常のログ保存先として `StrataEngine` に渡す |
| 設定済み・空でない文字列 | その文字列をログパスとして使用。`StrataEngine` が追記モードで開き、子エンジンの stderr をそこへ接続する |
| 設定済み・空文字 | 空文字がそのまま選ばれ、`cfg["log"]` には戻らない。`StrataEngine` は偽値として扱い stderr を `DEVNULL` に接続する |

パスの存在・書き込み可能性は環境変数の読み取り時には検査されません。空でないが開けないパスでは `open(log, "a")` が例外になります。`cfg["log"]` 自体がない場合、環境変数が未設定なら `KeyError` になります。

## 有効になる条件

対象は `tools/session_pressure_test.py`、`tools/batch_groups_cache_test.py`、`tools/cancel_park_test.py` の実行時です。環境変数は各スクリプトのトップレベルで一度評価され、後から環境を変更しても選択済みの `log` には反映されません。CLI 引数による `SMOKE_LOG` の指定経路はありません。`STRATA_EXE` はエンジン実行ファイルを別途上書きしますが、ログ先の選択には関与しません。

空文字の後続挙動はスクリプト間で異なります。session pressure と cancel/park はログなしで続行します。一方、batch groups cache はエンジン終了後に `open(log)` でログを検査するため、空文字の場合は `open("")` が失敗します。

## 実行時の詳細

- `session_pressure_test.py` と `cancel_park_test.py` は選択したパスを `StrataEngine(..., log=...)` に渡します（それぞれ `tools/session_pressure_test.py:28-30`、`tools/cancel_park_test.py:29-31`）。
- `batch_groups_cache_test.py` も同じ選択を行い、そのパスを `StrataEngine` に渡した後、終了時に同じファイルを開いて engine log の正規表現を集計します（`tools/batch_groups_cache_test.py:31-33,70-79`）。
- `serve/server.py:1017-1024,1043-1048` では、`StrataEngine` が `log` を保持し、通常起動時に真値なら追記モードでファイルを開き、偽値なら `subprocess.DEVNULL` を選びます。`serve/server.py:1076-1079` で子エンジンの stderr をその出力先へ接続します。起動時にログパスを開けない場合は `OSError` を呼び出し元へ送出します。
- これらのスクリプトは `child_env(cfg)` でエンジン環境も作ります。`serve/server.py:3747-3760` は親環境を複製するため `SMOKE_LOG` も通常は子環境に含まれますが、設定の `env` に同名キーがあればその値で上書きされます。Strata の読み取り箇所は上記3スクリプトだけで、エンジン側がこの値を読む参照はありません。ログ先の選択は子環境への転送値ではなく、親 Python プロセスが `log` 引数として行います。

この値自体に専用の警告・終了コード処理はありません。ファイルを開く失敗は通常の Python 例外として起動を妨げます。batch groups cache では空文字による後段のログ読込失敗も同様に未処理例外になります。

## 根拠

- 全参照検索では、環境値の読み取りは `tools/session_pressure_test.py:30`、`tools/batch_groups_cache_test.py:32`、`tools/cancel_park_test.py:31` の3箇所でした。
- ログ出力先の選択と engine 起動は `serve/server.py:1017-1024,1043-1048,1076-1079`、子環境の継承と設定上書きは `serve/server.py:3747-3760` にあります。
- `batch_groups_cache_test.py` の終了時ログ読込は `tools/batch_groups_cache_test.py:77-79` にあります。
