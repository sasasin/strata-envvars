# `STRATA_CLOUDFLARED_SEARCH`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Desktop host の Cloudflare connector (`cloudflared`) 候補探索を狭める。値が文字列 `own` と完全一致し、かつ `STRATA_CLOUDFLARED` に truthy な値がないとき、候補を Strata の connector folder と optional connector component folder に限定する。`PATH` や通常のシステム配置場所を調べなくなる。これは connector を選ぶ範囲だけを変え、選ばれた connector の実行可能性やバージョン判定は変えない（`app/host/server/cloudflared-find.mjs:42-70,95-110`）。

## 値と判定

`connectorCandidates` は既定で `env = process.env` を受け取り、`env.STRATA_CLOUDFLARED_SEARCH === 'own'` だけを特別扱いする。文字列全体の大文字小文字を区別した完全一致であり、trim や真偽値・数値への変換はない（`app/host/server/cloudflared-find.mjs:43-49`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| Desktop host の connector 探索 | 通常探索（Strata folder、component folder、`PATH`、通常のシステム配置場所） | `own` のみ。Strata folder と component folder だけを候補にする | 空文字、`OWN`、`Own`、` own`、`own `、`0`、`1`、`true`、`false`、`0anything`、その他すべて。通常探索を続ける |

ただし、`STRATA_CLOUDFLARED` が truthy（空でない文字列）の場合はその値だけを候補として先に返し、この変数による探索制限は適用されない。`STRATA_CLOUDFLARED` が未設定または空文字なら `own` 判定へ進む（`app/host/server/cloudflared-find.mjs:43-49`）。

## 有効になる条件

- この読み取り箇所は Desktop host の Node.js サーバーにある。`createConnectorInstaller` が既定の `process.env` を受け取り、その env を `findConnector` に渡す（`app/host/server/cloudflared-install.mjs:34-42`）。
- 起動時に connector installer を構成した後、host は `cloudflare.inspect()` を呼び、connector の場所を調べる（`app/host/server/index.mjs:1002-1004`; `app/host/server/cloudflare.mjs:25-26`）。
- `STRATA_CLOUDFLARED` が truthy なら、指定パスの候補一つだけを検査するため `STRATA_CLOUDFLARED_SEARCH` は探索結果を変えない（`app/host/server/cloudflared-find.mjs:43-49`）。
- `own` で限定された候補に使用可能な connector がなければ探索結果は `found: null` になり得る。その後 `ensure()` が呼ばれる経路では installer の既存手順へ進むため、この変数自体は自動セットアップを禁止しない（`app/host/server/cloudflared-find.mjs:95-110`; `app/host/server/cloudflared-install.mjs:46-52,90-93`）。
- 候補が見つかった後は通常どおり実行可能性と `--version` を調べ、実行できない候補や最低バージョン未満の候補を飛ばす（`app/host/server/cloudflared-find.mjs:73-110`）。
- この変数を設定ファイルや CLI 引数から上書きする経路は、調査した Desktop host の呼び出しにはない。installer の `search` 引数はプログラム内から探索を制御できるが、host の生成箇所では渡されず、候補関数の既定値 `true` が使われる（`app/host/server/cloudflared-install.mjs:34-42`; `app/host/server/index.mjs:1002`; `app/host/server/cloudflared-find.mjs:43,48`）。

## 実行時の詳細

通常探索では Strata の connector folder、optional component folder、`PATH` 上の各フォルダー、OS ごとの通常配置場所を順に候補化する。`own` は `search` を `false` にして早期 return するため、最初の二つの候補は残し、`PATH` とシステム配置場所は追加しない（`app/host/server/cloudflared-find.mjs:45-70`）。

値は候補配列の生成ごとに `env` オブジェクトから参照され、`STRATA_CLOUDFLARED_SEARCH` 自体を static cache する処理はない。installer は初期化時に `process.env` を既定引数として保持し、起動時の inspect、API の inspect、tunnel start / prepare からの locate で `findConnector` を再度呼ぶ（`app/host/server/cloudflared-install.mjs:34-45,90-93`; `app/host/server/index.mjs:1002-1004,1702-1704`; `app/host/server/cloudflare.mjs:25-32,55-66`）。したがって、同じプロセス内で `process.env` の値が変更されれば次の検索に反映される。プロセス起動後に親シェル側で環境を変更しても、既に起動した host の環境は変更されない。

トンネル subprocess の起動時には `process.env` を複製し、`TUNNEL_` で始まるキーだけを削除して渡すため、この変数は設定されていれば子プロセスの env にも残る。Strata ソースでは、その子プロセス側での意味や使用は確認できない（`app/host/server/cloudflare.mjs:71-75`）。

検索で候補が得られなかった場合、`inspect()` はその結果を返し、トンネル開始または connector 準備の経路では `ensure()` により既存のセットアップ手順が呼ばれる。対象変数を理由に Strata が出す専用ログやエラー分岐はない（`app/host/server/cloudflared-install.mjs:43-52,90-93`; `app/host/server/cloudflare.mjs:25-35,63-66`）。

## ログと測定値

この変数の値や `own` 判定をログに出す処理、または変数固有の測定値はない。候補探索後の結果は host の tunnel 状態として返され、候補が使えない場合の表示・失敗は共通の探索／installer 経路で処理される（`app/host/server/cloudflared-find.mjs:95-125`; `app/host/server/cloudflared-install.mjs:43-52`; `app/host/server/index.mjs:1702-1704`）。

## 根拠

- `app/host/server/cloudflared-find.mjs:42-70` — env の既定値、明示 connector パスとの優先関係、`own` 判定、候補範囲。
- `app/host/server/cloudflared-find.mjs:73-125` — 候補検査、探索結果、共通の skipped 理由文。
- `app/host/server/cloudflared-install.mjs:34-52,90-93` — env と検索処理の受け渡し、locate と setup の呼び出し。
- `app/host/server/cloudflare.mjs:25-35,55-66` — inspect、prepare、start における connector の再検索。
- `app/host/server/index.mjs:1002-1004,1702-1704` — Desktop host での installer 生成、起動時 inspect、tunnel API の呼び出し。
