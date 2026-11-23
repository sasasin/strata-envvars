# `STRATA_MODEL_PORT`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Terminal 同梱 MCP ツール `terminal/tools/strata_mcp.py` がローカルのモデルサーバーを見つける際の優先既定 port を指定する。値は `Strata.configured_default_port()` が読む。Strata エンジンの待受 port を直接変更する処理ではない。MCP の検出では、明示 port や現在のサーバー/モデル設定が先に候補となり、この変数はその候補群に追加される。モデル設定に port がない場合には起動先の既定値にもなる（`terminal/tools/strata_mcp.py:1627-1639,1646-1660,871-872,2763-2777`）。

Host アプリは選択済みの `modelPort` が整数 `1024..65535` の場合に、起動する `strata_mcp.py` 子プロセスへ文字列値を設定する。これは host 側の設定値の転送であり、host 自身がこの環境変数を読み取る処理ではない（`app/host/server/control-runtime.mjs:110-120`; `app/host/server/native-control.mjs:195-203`）。

## 値と判定

`os.environ.get(...) or ""` で取得後、前後の空白を `.strip()` し、`str.isdigit()` が真なら `int()` に変換する。変換後に `1 <= p <= 65535` なら採用し、それ以外は `None` として扱う（`terminal/tools/strata_mcp.py:1627-1634`）。

| 条件 | unset / 空文字 | 有効になる値 | 無効になる値 |
|---|---|---|---|
| Terminal MCP の port 検出 | unset または空文字は `None`。既定 port は `DEFAULT_PORT`（8080） | `isdigit()` が真で `int()` に変換でき、範囲内となる数字列。前後空白は除去される。例: `1`, `8080`, `65535`, ` 18501 ` | `0`, `65536`, `-1`, `+1`, `1.0`, `0anything`, `true`。通常の非数字列や範囲外は `None` になり既定 port に fallback する。一方 `²` のように `isdigit()` は真でも `int()` が受理しない値は `ValueError` になる |

数字としての全体妥当性を `isdigit()` で判定するため、`0anything` の先頭だけを数値として読むことはない。ただし `isdigit()` の真偽だけで `int()` の成功を保証しない文字もあり、その変換例外はこの箇所で捕捉されず呼び出し元へ伝わる。大文字小文字の概念はない。通常の非数字列や範囲外値について、無効値を理由とする警告や例外はなく、fallback する（`terminal/tools/strata_mcp.py:1629-1639`）。

## 有効になる条件

- Terminal MCP の port 判定で、呼び出し側から明示 `port` が渡されていないこと。`ports(port)` は truthy な `port` があればその一つだけを返す（`terminal/tools/strata_mcp.py:1646-1648`）。
- status / stop / benchmark の探索では、実行中サーバー状態と各モデル設定に記録された有効 port が候補列の先頭に置かれる。設定 port がある場合も環境変数の有効 port は重複しない形で追加される。環境変数が無効なら、既定 8080 の追加探索は候補が空の場合に限られる（`terminal/tools/strata_mcp.py:1649-1660,2365-2370,2915-2925`）。
- モデル設定の `port` がないときは `describe_config()` が `default_port()` を使うため、環境変数が有効ならその値、無効/未設定なら 8080 が使われる。`strata_start` の引数 `port` が指定されればそちらが優先される（`terminal/tools/strata_mcp.py:867-872,2763-2777,1636-1639`）。
- Host アプリが環境変数を子プロセスへ渡す場合は、host 設定の `modelPort` が整数かつ `1024..65535` にあることが条件。MCP 自身の読み取り範囲 `1..65535` とは下限が異なる（`app/host/server/control-runtime.mjs:114-120`; `app/host/server/native-control.mjs:199-203`）。
- 環境変数が有効でも、対象 port で Strata が応答するとは限らない。MCP は `127.0.0.1:<port>/health` を probe し、応答が Strata の health 応答でなければ非 Strata port として記録する（`terminal/tools/strata_mcp.py:1686-1702`）。

## 実行時の詳細

`configured_default_port()` は値を `static` 変数などに cache せず、呼ばれるたびに `os.environ` を読む。`default_port()`、`ports()`、`describe_config()` などの呼び出しに応じて評価されるため、MCP プロセス稼働中に環境を書き換えれば、その後の判定には反映される（`terminal/tools/strata_mcp.py:1627-1659,867-872`）。

明示 port がない探索では、まず MCP の保存済み server port と各 `strata-*.json` の設定 port を集め、次に有効な `STRATA_MODEL_PORT` を追加する。設定/実行中 port が一つもない場合に限り、環境値が無効または未設定で、さらに `STRATA_NO_DEFAULT_PORT` が無効なとき 8080 を fallback 候補にする。fallback 8080 が以前に非 Strata と判定済みなら候補にしない。重複候補は除去される（`terminal/tools/strata_mcp.py:1642-1660`）。

候補 port の probe は `127.0.0.1:<port>/health` を照会する。port を受け付けない場合や health endpoint が応答しない場合は `None`、Strata 以外の応答なら `other: true` の情報となる。`strata_start` では引数 port、モデル設定 port、既定 port の順に起動 port を決める（`terminal/tools/strata_mcp.py:1686-1702,2763-2785`）。

## ログと測定値

この環境変数の読み取り・妥当性判定自体に固有のログ出力はない。ポートが Strata として見つからない場合の上位ツールの結果やエラーは、実際に呼んだ MCP tool に依存する。たとえば benchmark は候補サーバーがない場合 `Strata is not running: start it first (strata_start)` を `ToolError` として返す（`terminal/tools/strata_mcp.py:2915-2925`）。該当する測定値はない。

## 根拠

- `terminal/tools/strata_mcp.py:1625-1660` — 値の読み取り・変換・既定値・probe 候補の選択。
- `terminal/tools/strata_mcp.py:867-872,2763-2785` — モデル設定と起動 port の優先順位。
- `terminal/tools/strata_mcp.py:1686-1702,2915-2925` — probe と未稼働時の観測可能な結果。
- `app/host/server/control-runtime.mjs:110-120`、`app/host/server/native-control.mjs:195-203` — host が MCP 子プロセスへ設定値を渡す条件。
