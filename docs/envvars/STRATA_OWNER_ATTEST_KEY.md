# `STRATA_OWNER_ATTEST_KEY`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。外部ライブラリの環境変数は対象外です。

## 役割

この変数は、`strata_control` が起動した所有サーバーの起動内容（設定ファイルのバイト列と argv）をサーバー自身に証明させ、管理側が照合するための一時秘密鍵です。通常の設定スイッチではありません。管理側は起動ごとに32バイトの乱数鍵を作り、その16進表現を子サーバーの環境へ設定すると同時に、同じ鍵で期待する attestation を計算します。サーバーは読んだ鍵で attestation を計算し、テレメトリーの instance 情報へ載せます。管理側は readiness 検証で値を比較します。

根拠: `strata_control/runtime.py:854-862`, `serve/launch_identity.py:15-22`, `serve/server.py:9079-9085,9300-9304,7178-7182`, `strata_control/readiness.py:84-110`。

## 値と判定

| 状態 | サーバー側の判定 |
|---|---|
| 未設定 | `os.environ.pop(..., None)` は `None` を返す。`--owner-fd` が指定されていれば起動を拒否する。指定されていなければ attestation を作らない。 |
| 空文字 | `--owner-fd` がある場合、形式検査に失敗して起動を拒否する。ない場合は読み捨てられ、無視される。 |
| 有効な形式 | 小文字の16進数字 `[0-9a-f]` がちょうど64文字。`bytes.fromhex()` で32バイトに変換する。 |
| 無効な形式 | 大文字、空白、`0x` 接頭辞、桁数違い、その他の文字を含む値は `--owner-fd` がある場合に拒否される。 |

値を真偽値や数値として parse したり、既定鍵へ fallback したりしません。`strata_control` は `os.environ.copy()` で親環境を複製した後、生成した鍵でこの名前を上書きしてサーバー子プロセスへ渡します。CLI 引数や設定ファイルから鍵を指定する経路はありません。

根拠: `strata_control/runtime.py:857-877`, `serve/server.py:9079-9085`。

## 有効になる条件

サーバー側で鍵を必須とする条件は、隠し CLI 引数 `--owner-fd` が指定されていることです。管理ランタイムはサーバー起動 argv に `--owner-fd` を加え（Windows は `0`、それ以外は継承 pipe の fd）、同時に鍵を子環境へ設定します。通常の直接起動で `--owner-fd` がなければ、変数が設定済みでもサーバーは値を取り除くだけで attestation を生成しません。

OS による違いは鍵の形式や計算ではなく、管理側が owner pipe を渡す方法です。モデル/backend の状態は鍵生成・サーバー側計算の条件ではありません。readiness 検証では unloaded モデルでも attestation を照合します。

根拠: `strata_control/runtime.py:852-877`, `serve/server.py:8985-8988,9067-9085`, `strata_control/readiness.py:113-120`。

## 実行時の詳細

管理側は各 launch で `secrets.token_bytes(32)` を生成し、`launch_identity.attestation()` に鍵、読み込んだ設定バイト列、起動 argv を渡して期待値を計算します。子環境には鍵の小文字 hex 文字列を設定します。attestation は `strata-owned-launch-v1\0` の識別子、設定と argv の長さ・内容を連結したメッセージに対する HMAC-SHA256 の hex 表現です。サーバーは設定ファイル読込後に環境変数を一度 `pop` し、owner 起動時は形式を検査して attestation を計算します。値を cache する helper はなく、このサーバー起動中の再読込もありません。

サーバーは計算結果を `Service.launch_attestation` に保持し、`/v1/telemetry` の instance 情報に追加します。管理側の readiness 検証は報告値が期待値と一致するかを定数時間比較します。不一致・欠落は `probe_launch_attestation_mismatch` となり、管理ランタイムの status は failed（制御側 `exit_code: 6`）になります。鍵が owner 起動時に未設定または不正なら `argparse` の `ap.error("owned server needs a private launch attestation key")` を通り、サーバー起動に失敗します。サーバー標準出力・標準エラーは管理側の profile server log にまとめられます。

根拠: `strata_control/runtime.py:857-877,907-920,951-972`, `serve/launch_identity.py:15-22`, `serve/server.py:9074-9085,9300-9304,7178-7182`, `strata_control/readiness.py:84-110`。

## 根拠

- 環境変数名の全参照: `strata_control/runtime.py:860`（子環境へ設定）、`serve/server.py:9079`（サーバーが取得して環境から除去）。
- 管理起動時の生成・子プロセスへの引き渡し: `strata_control/runtime.py:852-877`。
- サーバー側の必須条件・形式検査・attestation 計算: `serve/server.py:9074-9085`。
- attestation のメッセージ構成と HMAC-SHA256: `serve/launch_identity.py:15-22`。
- テレメトリーへの公開と管理側照合: `serve/server.py:7178-7182`, `strata_control/readiness.py:84-110`。
