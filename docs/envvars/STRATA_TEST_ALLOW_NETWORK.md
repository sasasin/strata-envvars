# `STRATA_TEST_ALLOW_NETWORK`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

この変数は Strata 本体の実行時設定ではなく、リポジトリルートの `conftest.py` が pytest プロセスに導入するネットワークガードの例外スイッチである。環境変数が文字列 `1` のとき、ガードが監視する外向き IP 接続と名前解決を許可する。それ以外では、loopback 等の明示的な例外以外のネットワーク接続・名前解決を拒否する。通常の Strata CLI やサーバーの通信挙動を変更する読み取り箇所は確認できない（`conftest.py:69-79,108-109,139-175`）。

## 値と判定

`_network_allowed()` は `os.environ.get(...) == "1"` を毎回評価する。文字列全体の完全一致であり、真偽値や数値への変換はしない（`conftest.py:108-109`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| pytest のネットワークガード | ガードを迂回しない | `1` | 空文字、`0`、`true`、`TRUE`、` 1`、`1 `、`01`、その他すべて |

## 有効になる条件

- リポジトリルートの `conftest.py` が読み込まれた pytest プロセス内で有効。通常の Strata 実行ファイルや別プロセス向けの設定ではない（`conftest.py:69-83,173-179`）。
- `socket.socket.connect` / `connect_ex` による IPv4/IPv6 の接続判定、および `socket.getaddrinfo` による名前解決判定で参照される（`conftest.py:139-175`）。
- 値が有効でも、ガードが対象にしない AF_UNIX 等のローカルソケットは元から通る。loopback も値にかかわらず通る。UDP の非 loopback `connect()` は値が無効でも例外扱いで通るが、利用箇所として記録される。IPv4 の RFC 5737 文書用アドレス 3 範囲も TCP 接続判定を通る例外である（`conftest.py:139-149`）。
- 子プロセスの socket API はこの Python プロセス内の差し替え対象ではない。`conftest.py` の説明では子プロセスは対象外としている（`conftest.py:69-79`）。

## 実行時の詳細

`conftest.py` 読み込み時に、このプロセスの `socket.socket.connect`、`connect_ex`、`getaddrinfo` をガード関数へ差し替える。環境変数の値はモジュール読み込み時に保存せず、各接続・名前解決の判定時に `_network_allowed()` から読み直すため、テスト中に `os.environ` を変更した場合も次の判定から反映される（`conftest.py:108-109,136-175`）。

接続判定は IP ソケット以外を素通しにし、loopback または値 `1` なら実際の socket 関数へ進む。それ以外では UDP connect と IPv4 文書用アドレスを例外として記録して通し、残りは接続先と発生元を `_reached` に追加して `ConnectionRefusedError` を送出する。名前解決は loopback、自ホスト名、または値 `1` を許可し、それ以外は `_reached` に記録して `socket.gaierror` を送出する（`conftest.py:139-170`）。

各テストに自動適用される `_no_network` fixture はテスト開始時に `_reached` を空にし、終了時に到達記録が残っていればそのテストを `pytest.fail` にする。したがって、コードが接続拒否や名前解決失敗を捕捉しても、記録が残る限りテスト終了時にも失敗となる。値 `1` の判定は毎回行われるため、固定の起動時キャッシュはない（`conftest.py:178-189`）。

## ログと測定値

拒否される接続では `ConnectionRefusedError` に `a test reached the network (<host>:<port>): fake it, or set STRATA_TEST_ALLOW_NETWORK=1 in a live test` が入り、拒否される名前解決では `socket.gaierror` に `a test looked up <host>: fake it, or set STRATA_TEST_ALLOW_NETWORK=1 in a live test` が入る。fixture 終了時の失敗文は `<nodeid> reached the network: <host/source entries> (fake it, or set STRATA_TEST_ALLOW_NETWORK=1 in a live test)` である（`conftest.py:150-151,167-169,185-189`）。

環境変数による許可は `_allowed` の例外利用一覧には記録されない。値が無効なときに通る UDP connect、自ホスト名の名前解決、文書用アドレスはテスト単位で記録され、利用があれば pytest 終了時に `network guard: allowances used` セクションへ表示される（`conftest.py:85-92,192-199`）。測定値の記載はない。

## 根拠

- `conftest.py:69-79,108-109` — ガードの目的と環境変数の完全一致判定。
- `conftest.py:136-175` — socket API の差し替え、接続・名前解決の許可と拒否。
- `conftest.py:178-199` — テスト終了時の失敗と許可例外の集計。
- `tests/terminal/test_net_guard.py:46-55,123-131` — 各テストが外部設定を外してガードを検査し、値 `1` の設定後に接続・名前解決を通すことを確認。
- `tools/test_qwen4_intake.py:426-431` — ライブ Hugging Face テストが自分のテスト範囲で値 `1` を設定する例。
