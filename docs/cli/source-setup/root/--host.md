# `--host`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh`、`START-HERE.bat`、`SETUP.bat`、更新 wrapper から委譲） |
| オプション | `--host` |
| 別名 | なし |
| 値 | サーバーが bind するホスト名または IP アドレス。文字列。省略時は既存設定、または `127.0.0.1` |

## 役割

セットアップで作成するモデル別設定、または既存モデルの次回起動に使う設定に、HTTP サーバーの待受先を指定します。`127.0.0.1` はこの PC 内だけ、`0.0.0.0` はネットワークインターフェース全体で待ち受けます。後者では API キーが推奨されています（`setup.py:8473-8475`）。

## 使い方

```sh
./setup.sh --host 0.0.0.0 --api-key SET-A-KEY
```

Windows では `START-HERE.bat --host 0.0.0.0 --api-key SET-A-KEY` と指定できます。`SETUP.bat` や `update.sh` / `UPDATE.bat` も引数を `setup.py` に渡します（`setup.sh:8-13,56`、`START-HERE.bat:27-34`、`SETUP.bat:1-2`、`update.sh:53-55`、`UPDATE.bat:56-58`）。

## 値と既定値

- parser は値を一つ受け取ります。`type`、`choices`、独自のホスト名 validation は指定されていません（`setup.py:8473-8475`）。
- 新規設定で省略すると `host` は設定ファイルに書かれず、サーバー側の既定値 `127.0.0.1` が使われます（`serve/server.py:8288`、`serve/server.py:7718-7722`）。
- 空文字列は parser で値として渡せますが、設定へコピーする処理は `if a.host` の場合だけなので、空文字列は上書き値になりません（`setup.py:7685-7688,8140-8143,8388-8391,9669-9672`）。
- 値は指定したモデルの設定に保存されます。通常起動時に `--host` を付けると `_start` が設定を更新して書き戻すため、次回起動にも残ります。通常起動で省略した場合は保存済みの値が使われます（`setup.py:6745-6771,8677-8691`）。
- `--setup` で既存モデルを再設定すると、`--host` を指定した値は新しい設定に入ります。省略時、`host` は setup が管理するキーとして扱われ、旧設定からの一般的な引き継ぎ対象ではありません（`setup.py:6162-6167,6177-6188,7685-7688,8129-8147`）。

## 実行時の動作

Linux / Windows の通常 parser で受けた値は、モデル別 JSON の `host` に格納されます。セットアップ後の起動は `serve/server.py` を `--config` 付きで起動し、server は明示的な server CLI 値、設定の `host`、`127.0.0.1` の順で bind 先を決めます（`setup.py:7675-7688,8129-8147,9669-9730`、`setup.py:6775-6776`、`serve/server.py:8288`）。

通常起動に `--host` を付けた場合も、設定ファイルへ保存してからサーバーを起動します。起動時には指定アドレスでの bind が実行され、起動メッセージに URL が出ます（`setup.py:6766-6776`、`serve/server.py:7718-7724,8615-8638`）。`localhost`、IP アドレス、`0.0.0.0` などを渡せますが、Strata 側で値を正規化・解決する処理は確認できません。

適用経路には次の差があります。

- macOS の Metal setup は独自 parser でも `--host` を受け取り、設定に保存します（`setup.py:7314-7318,8418-8419`、`metal/setup_mac.py:327-358,530-550`）。
- macOS の Control setup は `setup.py` の共通 parser 後に `mac_control_setup` へ進み、同じ値を設定に保存します（`setup.py:8561-8562`、`setup.py:8381-8405`）。
- `--update` は更新処理を実行して終了し、`update_install` は `a.host` を参照・適用しません（`setup.py:8617-8619`、`setup.py:6682-6709`）。
- `--check` や未対応 preview family の確認だけで早期終了する経路では、サーバー設定の作成まで進まず、値は待受先に反映されません（`setup.py:8179-8204,8559-8564,8697`）。
- Intel SYCL は parser 後に別の setup へ引数を転送します。`sycl/setup_intel.py` に `--host` parser はなく、転送先での受理・適用は確認できません（`setup.py:7321-7344,8561-8564`）。

## 適用条件と副作用

任意の値を受け取りますが、実際に bind できるかは起動時に OS の socket 処理で決まります。サーバーはモデル読み込み前に bind を試し、`OSError` の場合は listen error を argparse の usage error として報告します（`serve/server.py:8305-8308`）。

`0.0.0.0` など loopback 以外で待ち受けると、server は他デバイス向け URL を表示します。API key が未設定でも起動を拒否せず、警告を表示します。LAN 接続可能性は Windows Firewall 等にも左右されます（`serve/server.py:8624-8638`）。`--host` 自体は API 認証を設定しません。認証には別オプション `--api-key` が必要です。

設定・起動に伴う副作用として、setup 経路ではモデル別 JSON と起動スクリプトを書き、通常起動で明示した値は JSON を更新します（`setup.py:6312-6340,6766-6771,9729-9730`）。bind 失敗時のエラーは server 起動時に発生し、モデル読込前に終了します（`serve/server.py:8305-8308`）。

## 出力とエラー

- 新規 setup で非 loopback の値を指定すると、セットアップ完了メッセージに他デバイスからの利用案内が出ます。API key がない場合は未設定の旨も表示します（`setup.py:9740-9747`）。
- 起動成功時は bind 先 URL と、loopback 以外なら LAN アドレスが表示されます。API key がなければ、誰でも到達可能な接続元が利用できる旨の警告も表示されます（`serve/server.py:8615-8638`）。
- bind できない値や使用中ポートでは listen 問題を usage error として出し、server は status `2` で終了します（`serve/server.py:8305-8308`）。この場合、通常の setup 呼び出し元では起動プロセスの失敗として表面化します。

## 根拠

- 共通 parser: `setup.py:8473-8475`
- 設定への反映と通常起動時の永続化: `setup.py:6745-6776,7675-7688,8129-8147,8381-8405,9669-9730`
- 設定キー・再セットアップの引き継ぎ規則: `setup.py:6162-6188,6312-6340`
- server の優先順位、bind、listen error、待受 URL と警告: `serve/server.py:7718-7724,8288-8308,8615-8638`
- wrapper の引数委譲: `setup.sh:8-13,56`、`START-HERE.bat:27-34`、`SETUP.bat:1-2`、`update.sh:53-55`、`UPDATE.bat:56-58`
- macOS parser と設定経路: `setup.py:7314-7318,8418-8419`、`metal/setup_mac.py:327-358,530-550`
- update / preview / SYCL の適用範囲: `setup.py:6682-6709,7321-7344,8179-8204,8561-8564,8617-8619`
