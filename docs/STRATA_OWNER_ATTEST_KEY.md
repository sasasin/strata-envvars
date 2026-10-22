# `STRATA_OWNER_ATTEST_KEY`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

所有者管理ランタイムが起動したサーバーに、読み込んだ設定ファイルのバイト列と起動引数を結び付ける launch attestation を作らせるための一時鍵です。`strata runtime start` / `restart` の所有者プロセスは起動ごとに32バイトの乱数を作り、その小文字16進表現を子サーバーの環境へ渡します。サーバーは値から HMAC-SHA256 を計算し、Telemetry の instance 情報に含めます。所有者プロセスは自身で計算した期待値と照合して、実際に起動したサーバーが対象の設定内容・引数を読んだことを確認します。

これは配布元の署名やモデルファイルのハッシュではありません。通常のフォアグラウンドサーバーで同名変数を設定しても、この attestation は作られません。

## 値と判定

サーバーは起動引数を parse した後に `os.environ.pop("STRATA_OWNER_ATTEST_KEY", None)` で値を一度取り出し、サーバープロセスの環境から削除します。

| サーバー起動条件 | 未設定 | 設定値 |
|---|---|---|
| `--owner-fd` あり | エラー終了 | ASCII 小文字16進数64文字だけを受け付ける。32バイトの鍵へ変換して attestation を計算する |
| `--owner-fd` なし | attestation なし | 値を取り出して破棄する。値の形式検査・attestation 計算はしない |

`--owner-fd` ありの場合、空文字、大文字の16進数、長さ違い、16進数以外の文字を含む値は拒否されます。拒否時の実装メッセージは `owned server needs a private launch attestation key` で、`argparse` の `ap.error()` を通じて usage とエラーが stderr に出力され、プロセスは終了します。数値や真偽値としての parse はありません。

## 有効になる条件

- `strata_control.runtime` の所有者ホストが管理するサーバー起動であること。所有者ホストは毎回 `secrets.token_bytes(32)` で鍵を作り、環境のコピーに `STRATA_OWNER_ATTEST_KEY` として設定します。したがって、所有者ホストの外から設定した値はこの起動経路では上書きされます。
- サーバーに `--owner-fd` が渡されていること。所有者ホストは Windows では標準入力の pipe を、POSIX では pipe の file descriptor を `--owner-fd` に渡します。
- サーバーで読み込まれた値が64文字の小文字16進数であること。

値を設定するだけでは所有者ホストの検証処理は有効になりません。所有者ホストは自分が生成した期待値を保持し、ready-file の instance ID を確認した後に Telemetry へ照会します。照合できない・一致しない場合、readiness verification は失敗し、その状態は起動失敗として報告されます。

## 実行時の詳細

サーバーは設定ファイルを読み取ったバイト列 `config_bytes` と、`sys.argv[1:]`（または関数に渡された `argv`）を `launch_identity.attestation()` に渡します。関数は引数リストを JSON 化し、固定 domain prefix `strata-owned-launch-v1\0`、設定バイト列の長さと内容、JSON 引数の長さと内容を連結して HMAC-SHA256 を計算し、64文字の小文字16進数で返します。所有者ホストも子プロセス起動前に同じ関数を同じ設定バイト列・サーバー引数で呼び、期待値を保持します。

サーバーは計算結果を Service に設定します。Telemetry の instance snapshot は値がある場合だけ `launch_attestation` フィールドを返します。所有者ホストの readiness verifier は Telemetry の `instance.id` を期待する instance ID と確認し、報告された `launch_attestation` を期待値と定時間比較します。一致しない場合は `probe_launch_attestation_mismatch`、フィールドがない場合も同じエラーになります。所有者側の検証を通過した後、readiness 処理はモデル ID と状態の検証へ進みます。

値はサーバー起動時に一度だけ取り出されます。運転中の環境変数変更を読み直すコードはありません。秘密鍵そのものは Telemetry に出さず、照合用 MAC のみが返されます。`docs/TERMINAL.md` はこの照合を「private MAC」と説明しており、設定・引数の起動時点での照合であって、起動後のファイル変更を継続監視する機能ではないとしています。

## 根拠

- `strata_control/runtime.py:793-812,835-862`: 所有者ホストによる鍵生成、環境への設定、子サーバー起動、期待 MAC の保持と verifier 呼び出し。
- `serve/server.py:7996-7997,8024-8035`: 実際の起動引数・設定バイト列、環境変数の pop、所有者 fd 条件と値の検証・MAC 計算。
- `serve/launch_identity.py:15-21`: 鍵長検査、MAC の入力形式と HMAC-SHA256 計算。
- `serve/server.py:6273-6276,8210-8215`: Service への設定と Telemetry snapshot への出力。
- `strata_control/readiness.py:84-110`: 期待値形式、instance ID と launch attestation の照合、エラー名。
- `docs/TERMINAL.md:94`: 所有者ランタイムの設計説明と MAC の適用範囲。
