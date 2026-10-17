# `SMOKE_LOG`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

この名前は Strata エンジンの設定ではなく、会話キャッシュ・キャンセル復帰・セッション保存の各テストスクリプトが、エンジンのログファイル名を上書きするために読みます。通常の `strata` 実行経路における読み取り箇所は確認できません。候補一覧にある名前ですが、ここで見つかった参照はすべてテスト用ツール内です。

## 値と判定

3つのテストスクリプトはいずれも `os.environ.get("SMOKE_LOG", cfg["log"])` を使います。

| 環境変数 | テストスクリプトが選ぶログ先 |
|---|---|
| 未設定 | 入力 JSON の `cfg["log"]` |
| 設定あり（空文字を含む） | 環境変数の文字列そのもの |

値を数値や真偽値に変換しません。環境変数が空文字で設定されている場合も `cfg["log"]` には戻りません。空文字は `StrataEngine` に渡されるとログファイルを開かない指定として扱われます（`serve/server.py` では `log` が偽なら `subprocess.DEVNULL` を stderr に使います）。ただし `batch_groups_cache_test.py` は後で `open(log, ...)` するため、空文字ではその読み込みに失敗します。

## 有効になる条件

この変数を読むのは次のテスト用ツールに限られます。通常のサーバー設定やエンジン機能を切り替える条件はありません。

- `tools/batch_groups_cache_test.py`
- `tools/cancel_park_test.py`
- `tools/session_pressure_test.py`

これらのスクリプトを実行しない場合、リポジトリ内に `SMOKE_LOG` を読む Strata 所有コードは確認できません。`serve/server.py:2858-2875` の `child_env()` は親プロセス環境をコピーするため値は子エンジンの環境にも継承されますが、エンジン側のソースにはこの名前を読む処理がありません。

## 実行時の詳細

3つのテストは選んだパスを `StrataEngine(..., log=...)` に渡します。`StrataEngine` は空でないパスを追記モードで開き、起動時の行を書き、エンジンの stderr をそのファイルへ接続します。パスが空ならファイルを開かず、stderr を `subprocess.DEVNULL` に向けます。これによりテスト用ログの保存先が変わりますが、生成・推論処理の設定値にはなりません。値はテストスクリプト起動時に参照され、その後の環境変更を再読込する処理はありません。

## 根拠

- `tools/batch_groups_cache_test.py:31-33,77-78` — 環境変数または `cfg["log"]` を選び、エンジンに渡し、後で同じパスを開く。
- `tools/cancel_park_test.py:29-31` — 選んだログパスを `StrataEngine` に渡す。
- `tools/session_pressure_test.py:28-30` — 選んだログパスを `StrataEngine` に渡す。
- `serve/server.py:793-799,816-843` — `StrataEngine` のログ処理、追記オープン、stderr の接続。
- `serve/server.py:2858-2875` — 子エンジンの環境は親環境のコピーから作られる。
- HEAD 全体での完全一致検索では、上記以外に `SMOKE_LOG` の参照はありません。テスト用コードを除くエンジン実装での読み取りは確認できません。
