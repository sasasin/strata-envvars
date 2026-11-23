# `STRATA_NO_DEFAULT_PORT`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。

## 役割

Strata の Python MCP ツールが、明示ポート・実行中サーバー・モデル設定から探索ポートを得られない場合に、最後の候補として `127.0.0.1:8080` を自動探索する動作を止めます。これは MCP のサーバー発見対象を絞る設定であり、Strata 推論サーバーの bind port やサーバー起動時の既定ポートを変更しません。読み取りは `terminal/tools/strata_mcp.py` の `Strata.no_default_port()`、候補選択は `Strata.ports()` です（`terminal/tools/strata_mcp.py:1636-1660`）。

Strata ホストアプリは MCP 用 Python 子プロセスを起動する際、設定されたモデルポートが `8080` 以外なら `STRATA_NO_DEFAULT_PORT=1` をその子プロセス環境に加えます。ソース checkout のホスト経路では既存の `process.env` を引き継いでからこの値を重ね、packaged 経路では `installerEnvironment()` が同じ条件で値を加えます（`app/host/server/native-control.mjs:92-105,195-202`、`app/host/server/control-runtime.mjs:88-119`）。

## 値と判定

`os.environ.get(...) or ""` で取得し、前後の空白を `.strip()` で除去し、小文字化してから文字列全体を `("1", "true", "yes", "on")` と照合します。数値変換は行いません（`terminal/tools/strata_mcp.py:1641-1644`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| Python MCP が `no_default_port()` を評価する場合 | 無効（8080 fallback を許す） | `1`, `true`, `yes`, `on`。大文字小文字は無視し、前後の空白は除去する | 空文字、`0`, `false`, `off`, `01`, `1anything`, `yes please` |

空文字と未設定はいずれも無効です。例えば `" TRUE "` は有効、`"0"` と `"0anything"` は無効です。値が有効でも 8080 だけを除外し、設定や実行状態から得たポートは除外しません（`terminal/tools/strata_mcp.py:1642-1660`）。

## 有効になる条件

- MCP の `Strata.ports(port)` にポート引数がない（または falsy）こと。truthy な明示ポートはそのまま単一要素のリストで返り、この環境変数を評価しません（`terminal/tools/strata_mcp.py:1646-1648`）。
- サーバー状態とモデル設定から有効なポート（整数 `1..65535`）が一つも見つからないこと。いずれかがあればこの変数に関係なく、そのポート群を探索し、8080 を fallback として追加しません（`terminal/tools/strata_mcp.py:1649-1659`）。
- モデル設定に `port` キーがない場合、`describe_config()` は `default_port()` をその設定のポートとして返します。`STRATA_MODEL_PORT` も未設定・無効ならこれは `8080` なので、設定ファイルがあるだけで `ps` に 8080 が入り、本変数では除外されません。これは「他の既知ポートがないときだけ fallback を抑制する」という条件の例外的に見える重要な差です（`terminal/tools/strata_mcp.py:1637-1639,852-872,1649-1659`）。
- `STRATA_MODEL_PORT` に有効な値が設定されていないこと。有効な設定値は `1..65535` の数字文字列で、これがあるとそのポートを候補にして本変数の判定を通りません（`terminal/tools/strata_mcp.py:1627-1634,1651-1659`）。
- 上記の条件がそろった場合、本変数が有効なら 8080 を追加しません。本変数が無効でも、同じ MCP プロセス内の探索で 8080 が「Strata 以外の listener」と判定済みなら追加しません（`terminal/tools/strata_mcp.py:592,1655-1659,1690-1699`）。

ホストアプリの子プロセスでは、モデルポート設定が `8080` 以外（未設定を含む）ならホスト側が値 `1` を設定します。`8080` の場合はこの変数を上書きしません。packaged 経路では `probeDefaultPort` が false かつ `modelPort !== 8080` のとき `installerEnvironment()` が `1` を付けます（`app/host/server/native-control.mjs:93-105,199-202`、`app/host/server/control-runtime.mjs:114-119`）。

## 実行時の詳細

`no_default_port()` は関数呼び出しごとに `os.environ` を読み、関数内 `static` やインスタンス属性に判定値を保存しません。そのため後続の `ports()` 呼び出しでは、その時点の Python 環境マッピングが評価されます。ただし、有効な明示ポート、既知ポート、または有効な `STRATA_MODEL_PORT` が先に見つかる経路では短絡され、本変数の読み取りに進みません（`terminal/tools/strata_mcp.py:1627-1659`）。

探索結果を利用する主な MCP 経路は `strata_status()`、`strata_stop()`、`strata_benchmark()`、`strata_connect_info()` です。したがって設定が有効で他の候補もない場合、これらの自動探索は 8080 に接続しません。`strata_status` はその場合「Strata is not running」と返し、`strata_benchmark` は対象が見つからず `Strata is not running: start it first (strata_start)` で失敗します。`strata_connect_info` は稼働サーバーを検出できなくても設定情報から接続先を提示し得ます。明示ポートの指定はこれらの自動候補選択を迂回します（`terminal/tools/strata_mcp.py:2365-2369,2390-2398,2874-2875,2915-2925,2957-2978`）。

8080 に接続を試みた結果をキャッシュするのは環境変数の真偽値ではなく `_non_strata_ports` です。8080 が応答しない場合は削除され、Strata 以外の応答なら登録され、Strata 応答なら削除されます。この記録は `Strata` インスタンス内で保持されます（`terminal/tools/strata_mcp.py:592,1690-1699`）。

## ログと測定値

本変数の判定だけを理由に出すログはありません。観測できる違いは MCP ツールの探索結果・返却文・エラーです。`docs/DETAILS.md` は一般利用時の既定アドレスを `127.0.0.1:8080` と記載していますが（`docs/DETAILS.md:27-35`）、本変数が制御するのは MCP における「他の候補がない場合の fallback 探索」です。測定値は該当しません。

## 根拠

- `terminal/tools/strata_mcp.py:1627-1660` — `STRATA_MODEL_PORT` と `STRATA_NO_DEFAULT_PORT` の読み取り、値判定、候補選択。
- `terminal/tools/strata_mcp.py:2365-2369,2390-2398,2874-2875,2915-2925,2957-2978` — 候補探索の呼び出しと結果。
- `terminal/tools/strata_mcp.py:592,1690-1699` — 非 Strata listener のインスタンス内記録。
- `app/host/server/native-control.mjs:92-105,195-202`、`app/host/server/control-runtime.mjs:88-119` — ホストアプリが MCP 子プロセスへ設定する条件。
- `docs/DETAILS.md:27-35` — 一般向け既定アドレスの記述。
