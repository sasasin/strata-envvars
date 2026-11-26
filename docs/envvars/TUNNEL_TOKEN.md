# `TUNNEL_TOKEN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

この名前は Strata サーバー自身が `process.env.TUNNEL_TOKEN` から設定を読む環境変数ではない。Web UI の「自分のドメイン」モードで入力・検証されたトンネルトークンを、Strata が `cloudflared` 子プロセスの環境変数 `TUNNEL_TOKEN` に設定して渡すために使う。クイックトンネルでは入力トークンを使わず、この変数を子プロセス環境に設定しない。Strata はトークンをコマンドライン引数に含めず、保存設定や応答状態にも含めない（`app/host/server/cloudflare.mjs:55-75`）。

## 値と判定

`start(body)` は `mode === 'domain'` の場合だけ `String(body.token ?? '').trim()` でリクエスト値を文字列化して前後の空白を除去し、正規表現 `/^[A-Za-z0-9+/=_-]{20,8192}$/` で全体を検証する。従って ASCII の英大文字・小文字、数字、`+ / = _ -` のみからなる 20〜8192 文字が受理される。空文字、19 文字以下、8193 文字以上、空白を含む値、その他の文字を含む値は拒否される。前後の空白は trim 後に判定されるため除去されるが、途中の空白は拒否される。`true` / `false` の特別扱いや数値変換はない（`app/host/server/cloudflare.mjs:58-60`）。

| 条件 | 未設定・空値 | 有効になる値 | 無効になる値 |
|---|---|---|---|
| `mode === 'domain'` | `body.token` が欠落または `null` なら空文字となり拒否。空文字・空白だけも trim 後に拒否 | 許可文字のみの 20〜8192 文字。例: `A` を20個並べた値、または20文字以上の `A-Za-z0-9+/=_-` の組み合わせ | 19文字以下（`true`、`0anything` など）、8193文字以上、許可文字以外を含む値、途中に空白を含む値 |
| `mode === 'quick'` | `body.token` の有無を問わず、内部値は空文字 | 該当なし。トークンを要求しない | トークン値による拒否はない。モード自体が `quick` / `domain` 以外なら別途拒否 |
| 子プロセス環境 | Strata の起動環境から継承した `TUNNEL_*` は一旦すべて除去 | domain モードで検証済みの非空入力値だけが `env.TUNNEL_TOKEN` に設定される | Strata プロセスにあらかじめ設定した `TUNNEL_TOKEN` は引き継がれず、domain 入力の代わりにもならない |

## 有効になる条件

- Web UI で `domain` モードを選び、hostname と token を入力して接続を実行する。UI は token を `/api/serving/tunnel` への `start` リクエストに含める（`app/host/src/components/CloudflareDialog.tsx:14-16,62-64,97`、`app/host/src/lib/store.ts:1302-1304`）。
- サーバーは `mode` が `quick` または `domain` であることを要求する。domain モードではトークン検証に加え hostname も検証される（`app/host/server/cloudflare.mjs:8-11,56-60`）。
- `cloudflared` が見つかるか自動準備でき、Strata 自身の同じ tunnel が既に稼働中でないことが必要。条件を満たさない場合は起動を拒否する（`app/host/server/cloudflare.mjs:63-69`）。
- 稼働中 `cloudflared` のコマンドラインに同じ 20 文字以上の入力 token が含まれる場合も「Strata 自身の tunnel」と判定して二重起動を拒否する。検出対象コマンドラインは照合用にのみ保持し、PID 以外は表示しない。別 token の tunnel は他プロセスとして扱い、起動を妨げない（`app/host/server/cloudflare.mjs:67-68`; `app/host/server/cloudflared-find.mjs:129-132,161-186`）。
- OS や Strata の GPU backend による分岐はこのトークンの受け渡しにはない。Strata は値を `cloudflared` に渡すところまでを実装し、受け取った外部プログラム側での解釈は本書の対象外。
- Strata のプロセス環境や CLI 引数からの値の優先順位はない。domain UI リクエストの入力が子プロセスに渡される値であり、quick モードではトークンを渡さない（`app/host/server/cloudflare.mjs:58-60,71-75`）。

## 実行時の詳細

トークンはサーバーへの `start` リクエストごとに取り出して検証され、関数内にキャッシュされない。domain モードの入力値は実行中の外部プロセス起動時に子プロセス専用の環境オブジェクトへコピーされる。コピー元の環境から `TUNNEL_` で始まるキーをすべて削除してから、検証済み token が truthy の場合に限り `TUNNEL_TOKEN` を設定する。親である Strata の `process.env` 自体は書き換えない。quick モードでは token は空文字のため設定されない（`app/host/server/cloudflare.mjs:58-60,69-75`）。

引数は `tunnel ... run`（domain）または `tunnel ... --url <originUrl>`（quick）で、どちらにも token は含まれない。起動したプロセスの stdout / stderr は Strata が接続状態の判定用に読み、quick URL と `Registered tunnel connection` の両方を検出すると connected 状態にする。接続待ちの既定 timeout は 45,000 ms。これは Strata 側の状態判定であり、外部プログラムの token 検証の詳細を示すものではない（`app/host/server/cloudflare.mjs:13,74-89`）。

## ログと測定値

Strata は token をコマンドライン引数、ログ、保存設定、API 応答に出さないと実装コメントで明記している（`app/host/server/cloudflare.mjs:70-75`）。無効な domain token は `Paste the tunnel token from Cloudflare, not the full installation command.` のエラーとなり、API ルートは HTTP 400 とエラーメッセージを返す（`app/host/server/cloudflare.mjs:60`, `app/host/server/index.mjs:1703-1705`）。子プロセス起動失敗時の表示は `Cloudflared could not start. Check the installation and try again.`、子プロセス終了時は `Cloudflared stopped. Check your network, token and Cloudflare configuration, then reconnect.`、45秒の既定待ち時間を超えた場合は `Cloudflare did not connect in time. Check your internet connection and tunnel setup, then try again.`（`app/host/server/cloudflare.mjs:86-89`）。測定値は該当なし。

## 根拠

- UI の入力と送信: `app/host/src/components/CloudflareDialog.tsx:14-16,62-64,97`; API クライアント: `app/host/src/lib/store.ts:1302-1304`。
- モード・値検証・子環境への受け渡し・起動判定: `app/host/server/cloudflare.mjs:55-89`。
- 既存コネクターの検出と同一 token の照合: `app/host/server/cloudflared-find.mjs:129-174`。
- API エラー応答: `app/host/server/index.mjs:1702-1705`。
- 関連資料 `docs/DETAILS.md:719` は一般的な `cloudflared tunnel --url` の例を説明するが、この UI の `TUNNEL_TOKEN` 受け渡し仕様は説明していない。
