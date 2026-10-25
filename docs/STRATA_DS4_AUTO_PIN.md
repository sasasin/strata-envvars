# `STRATA_DS4_AUTO_PIN`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek-V4.1 用サーバーが、system/developer メッセージとそれに続く会話の間に共有 prefix を自動設定するかを制御します。同じ system prompt と tools を使う agent/sub-agent のリクエストでは、その境界をエンジンに `pin=N` として渡し、共有開始位置の checkpoint を保持させます。エンジンの checkpoint/prefix 機能自体を無効化する変数ではなく、サーバーが自動で境界を指定する処理を止めます。

## 値と判定

| 値 | 自動設定 |
|---|---|
| 未設定 | 有効（既定値は文字列 `"1"`） |
| 文字列が正確に `0` | 無効 |
| それ以外（`1`、`00`、`false`、空文字を含む） | 有効 |

数値変換や truthy 判定ではなく、Python の文字列 `== "0"` で比較します。空文字や `00` は無効になりません。判定は `Service.deepseek_shared_start()` の呼び出しごとに行われるため、起動時に一度だけ値を固定する実装ではありません。ソースに子プロセスへの転送処理はありません。

## 有効になる条件

環境変数が有効でも、自動 prefix の作成にはすべて次の条件が必要です。

- サービスの model family が `deepseek41`。
- `prepare()` に `req` が渡されており、既にクライアント指定の `req["strata_prefix"]` がない。
- 画像を含まないリクエスト。
- メッセージ列の先頭に1件以上の `system` または `developer` メッセージが連続し、その後に少なくとも1件の別 role のメッセージがある。

先頭から連続した system/developer メッセージ数を `K` として `{"messages": K}` を設定します。system/developer メッセージがない場合、またはそれらが全メッセージを占める場合は何も設定しません。クライアントが `strata_prefix` を指定した場合はこの自動設定を行わず、クライアント指定が優先されます。

## 実行時の詳細

`Service.prepare()` はプロンプトを encode した後、DeepSeek-V4.1 かつ `req` があり、既存 prefix がなく、画像もない場合に `deepseek_shared_start(messages)` を呼びます。正の `K` が返ると `req["strata_prefix"] = {"messages": K}` を設定し、続けて `resolve_prefix()` が rendered prompt/token IDs に照らして token 数へ解決します。最終的に engine key の組み立て処理は `{"tokens": N}` の正整数を `pin=N` としてエンジンに渡します。画像を含むクライアント指定 prefix は `resolve_prefix()` 側で無視されますが、この環境変数による自動指定の経路には入りません。

`pin=N` は先頭 N token の共有 prefix として扱われます。`DETAILS.md` の説明では、エンジンは境界の checkpoint を保持し、後続の質問がそこから再開できるようにします。これはサーバーが prefix を指定する仕組みと、その後のエンジン動作を分けた説明です。

## 根拠

- `serve/server.py:4821-4824,4921-4927`: `prepare()` の前提、DeepSeek-V4.1/req/prefix/画像の条件、自動指定と解決。
- `serve/server.py:4929-4943`: 環境変数の既定値と完全一致比較、連続する system/developer メッセージ数の判定。
- `serve/server.py:3940-3949,8449`: family の設定と `deepseek41` 判定への接続。
- `serve/server.py:1452-1459`: 解決済み token prefix を `pin=N` としてエンジンキーへ追加。
- `docs/DETAILS.md:1166-1178`: pinned shared prefix の説明と適用要件（`--prompt-cache 3` 以上）。
- `docs/DEEPSEEK41.md:84-87`: DeepSeek-V4.1 の system prompt/tools checkpoint を保持する機能と、この変数を `0` にした場合の説明。
