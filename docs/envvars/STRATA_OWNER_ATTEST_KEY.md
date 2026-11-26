# `STRATA_OWNER_ATTEST_KEY`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

管理 runtime がサーバー子プロセスへ起動ごとの秘密鍵を渡し、サーバーが読み込んだ run config のバイト列と起動引数に対する HMAC-SHA256 の attestation を生成するための内部受け渡し変数です。runtime は同じ鍵で期待値を計算しておき、サーバーの `/v1/telemetry` が返す attestation と比較します。これにより管理 runtime の readiness 検証で、起動時の config と引数を確認します。モデルの計算設定を直接変更する利用者向けスイッチではありません（`terminal/strata_control/runtime.py:1051-1074`, `terminal/serve/server.py:9276-9282`, `terminal/serve/launch_identity.py:15-21`, `terminal/strata_control/readiness.py:114-123`）。

## 値と判定

サーバーは `os.environ.pop("STRATA_OWNER_ATTEST_KEY", None)` で一度読み、同時に自身の環境から削除します。管理 runtime は `secrets.token_bytes(32).hex()` を設定するので、通常渡される値は 32 バイトの秘密値を表す小文字 hexadecimal 64 文字です。CLI 引数や config による代替値・優先順位はありません（`terminal/strata_control/runtime.py:1054-1059`, `terminal/serve/server.py:9276-9282`）。

| 起動条件 | 未設定 | 有効値 | 無効値 |
|---|---|---|---|
| `--owner-fd` あり（管理 runtime のサーバー） | 起動を拒否 | `[0-9a-f]` に一致する 64 文字。例: `0` を 64 個並べた値 | 空文字、`0` が 63 個の値、`A` が 64 個の値、`g` が 64 個の値、空白を含む値。いずれも起動を拒否 |
| `--owner-fd` なし（通常のサーバー） | attestation なしで続行 | 値の内容にかかわらず使用しない | 値の内容にかかわらず使用しない |

有効性は数値変換ではなく正規表現の全体一致で判定します。前後の空白を除去せず、大文字小文字を区別します。owner mode で判定を通った値だけ `bytes.fromhex` で鍵へ戻します。`--owner-fd` がない場合も `pop` 自体は実行されますが、その値は検証されません（`terminal/serve/server.py:9276-9282`）。

## 有効になる条件

- 管理 runtime の `Host._launch` がサーバー子プロセス環境を作るときに値を設定します。既存の親環境に同名変数があっても、新しく生成した鍵で上書きします。この設定は Windows と POSIX の両方の起動分岐より前に行われます（`terminal/strata_control/runtime.py:1049-1074`）。
- サーバー側では `--owner-fd` が指定されている場合だけ、鍵の存在と形式が必須です。欠落または不正値なら `ap.error("owned server needs a private launch attestation key")` で起動を拒否します（`terminal/serve/server.py:9278-9282`）。
- 管理外の通常起動では鍵は attestation に使われず、環境から取り除かれます。OS、engine backend、build macro、モデルのロード状態による値の判定差はありません。attestation の生成後に runtime が照合する経路は管理 runtime の readiness 検証です（`terminal/serve/server.py:9276-9282`, `terminal/strata_control/runtime.py:1105-1118`, `terminal/strata_control/readiness.py:96-123`）。

## 実行時の詳細

`Host._launch` は 32 バイトを暗号学的乱数で生成し、その hex 表現を子環境へ入れます。同じ鍵・source config の読み込み時バイト列・サーバー引数から、起動前に期待 attestation を計算して保存します。サーバーは引数と config を読み込んだ後に環境値を取り出し、検査に通れば同じ材料から attestation を計算します。`launch_identity.attestation` は config バイト列と JSON 化した引数を長さ付きで連結し、HMAC-SHA256 の lowercase hex digest を返します（`terminal/strata_control/runtime.py:987-991`, `terminal/strata_control/runtime.py:1040-1059`, `terminal/serve/server.py:9266-9282`, `terminal/serve/launch_identity.py:15-21`）。

サーバーは鍵を `pop` した後に engine 用の環境を `child_env(cfg, ...)` から構成するため、この鍵を engine の環境へ引き継ぎません。attestation は `Service` に保持され、telemetry の `instance.launch_attestation` に含まれます。runtime は `/v1/telemetry` の `instance.id` と attestation を確認し、期待値と一致しなければ readiness を失敗にします（`terminal/serve/server.py:9276-9282`, `terminal/serve/server.py:9391-9394`, `terminal/serve/server.py:9492-9497`, `terminal/serve/server.py:7460-7463`, `terminal/strata_control/readiness.py:114-123`）。

環境値の読み取りはサーバープロセスの起動時に一度です。関数内 static cache やリクエストごとの再読込はありません。起動後に外部から環境を変更しても、取り出し済みの鍵や生成済み attestation は変わりません。管理 runtime の起動ごとに鍵を新規生成し、子プロセス環境へ明示設定します（`terminal/serve/server.py:9276-9282`, `terminal/strata_control/runtime.py:1054-1074`）。

## ログと測定値

owner mode で鍵が未設定または不正形式の場合、サーバーは parser error `owned server needs a private launch attestation key` を出して起動を拒否します。runtime の telemetry に attestation がない、または期待値と一致しない場合、readiness は `probe_launch_attestation_mismatch` を返し、managed status は失敗状態としてこの error を報告します。通常サーバーで値を読み捨てたときや、attestation の照合成功時に、この変数専用のログはありません（`terminal/serve/server.py:9278-9282`, `terminal/strata_control/readiness.py:120-123`, `terminal/strata_control/runtime.py:1111-1118`, `terminal/strata_control/runtime.py:1164-1169`）。

## 根拠

- `terminal/strata_control/runtime.py:1040-1074` — 鍵生成、環境への設定、Windows/POSIX のサーバー起動。
- `terminal/serve/server.py:9266-9282` — config と引数の取得、環境値の取り出し、owner mode の形式検査と attestation 生成。
- `terminal/serve/launch_identity.py:15-21` — HMAC 入力と計算。
- `terminal/serve/server.py:7460-7463, 9391-9394, 9492-9497` — telemetry への設定と、engine 環境を組み立てる位置。
- `terminal/strata_control/readiness.py:96-123` — readiness 側の telemetry attestation 検証。
- `terminal/strata_control/runtime.py:1105-1118, 1151-1172` — 検証結果を managed status に反映。
