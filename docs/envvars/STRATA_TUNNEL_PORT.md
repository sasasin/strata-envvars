# `STRATA_TUNNEL_PORT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata 所有ソースを調査し、外部ライブラリの環境変数動作は対象外。

## 役割

ホストサーバーが Cloudflare トンネルの接続先にする loopback HTTP listener のポート候補を指定します。環境変数の値をそのまま固定ポートとして bind するのではなく、数値化した値を優先候補として空きポートを探索します。トンネル用 listener はホスト起動時に準備されますが、実際に listen するのは `/api/serving/tunnel` からトンネルを開始するときです。

## 値と判定

`apps/host/server/index.mjs` は `process.env.STRATA_TUNNEL_PORT ?? PORT + 2` を `Number(...)` に渡します。環境変数が未設定の場合は、`STRATA_PORT`（未設定時8791）に2を足した値が優先候補です。設定された空文字は nullish fallback の対象にならず、`Number('')` は `0` になります。

| 値の例 | 優先候補と処理 |
|---|---|
| 未設定 | `PORT + 2`。通常の `PORT` 既定値では8793。 |
| `''`, `'0'`, 空白のみ | 数値0。`findFreePort` がポート0を probe し、OS が割り当てた一時ポートを返す。 |
| 有効な整数ポート（例: `'9000'`） | そのポートから上向きに空きを探索する。 |
| 数値化できない文字列、負数、小数 | 数値変換自体は厳密な文字列形式検査ではない。probe に Node が受け付けないポート値が渡ると例外となり、top-level `await` を通じてホスト初期化が失敗し得る。 |
| 65535を超える数値 | 範囲外の候補は helper が読み飛ばし、最後にポート0で一時ポートを試す。 |

`Number` による JavaScript の数値変換なので、文字列全体を10進整数として検証する独自処理や clamp はありません。`findFreePort` は候補ポートを最大20個試し（優先候補から上方向）、ホストの `PORT` と share listener のポートを skip します。候補で空きが見つからなければポート0を試し、それも bind できなければ元の優先値を返します。probe はポートを一度 listen して閉じるため、選択後の実 bind までに競合する可能性があります。

## 有効になる条件

- Strata の Node.js host server を起動する経路で読み取られます。読み取りに OS/backend/GPU/build macro 条件はありません。
- CLI 引数や設定ファイルによる上書きは、この値を決める式にはありません。関連する `STRATA_PORT` は host 自身のポートと、未設定時の tunnel 候補に影響します。share listener の `STRATA_SHARE_PORT` は探索前に選ばれ、tunnel helper の skip 対象になります。
- `STRATA_TUNNEL_PORT` はポート選択にのみ影響します。トンネルを自動で開始する値ではなく、トンネル開始操作がなければ `tunnelOrigin` は listen しません。

## 実行時の詳細

モジュール初期化中に `tunnelPort` を一度選び、同じポートを `createLocalShare` の `port` と `http://127.0.0.1:<port>` の origin URL に設定します。以後プロセス環境を書き換えても選択済みポートは再評価されません。Cloudflare トンネルの開始時には、connector の準備などの後で `origin.start()` が呼ばれ、`127.0.0.1` に bind します。bind が失敗すると `local-share.mjs` は `listenProblem` の文言を含む例外にし、Cloudflare 開始処理は error 状態を設定して例外を返します。`POST /api/serving/tunnel` のハンドラーはそのメッセージを HTTP 400 のエラー応答にします。環境変数そのものについての専用ログや警告はありません。

起動時の probe は一時的な bind 可能性を調べるだけです。開始時に同じポートを取得できない場合、エラー文は `Strata cannot listen on 127.0.0.1:<port> (...)` の形になります（Node の具体的なエラー内容による）。`findFreePort` が probe で範囲外等の値を処理できず例外を出した場合は、host の `server.listen(PORT, HOST, ...)` より前の初期化中に失敗します。

## 根拠

- `apps/host/server/index.mjs:100` — `STRATA_PORT` の数値化と既定値8791。
- `apps/host/server/index.mjs:944-950` — share listener の先行選択、対象変数の読み取り、tunnel origin と Cloudflare origin URL への反映。
- `apps/host/server/ports.mjs:13-18,21-30` — probe の bind/close、最大20候補、skip、範囲外候補の扱い、ポート0 fallback。
- `apps/host/server/local-share.mjs:8-12,35-37` — loopback listener のポート設定と bind 時のエラー変換。
- `apps/host/server/cloudflare.mjs:55-75,91-93` — start 操作で origin listener を開始し、失敗時に error state を設定して再送出する流れ。
- `apps/host/server/index.mjs:1584-1587` — tunnel start API と HTTP 400 エラー応答。
- `apps/host/server/index.mjs:2256-2263` — host listener の起動と listen error の終了処理。環境変数値の probe はこの箇所より前に行われる。

`000_envvers.md` には候補名として掲載されています。本番ソースでの値読み取りは `apps/host/server/index.mjs:947` の1箇所で確認しました。他の候補名参照は host/desktop のテスト起動時に子プロセス環境を設定する用途です。
