# `STRATA_PORT_NOTICE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

デスクトップアプリが希望した待受ポートを確保できず、別の空きポートで起動した場合に、App Host から UI へ「希望ポートと実際に使うポート」を渡す通知値です。Host は値を `/api/shell` の応答に含め、UI は警告トーストを一度表示します。

通常の desktop 起動ではシェルが子 Host に設定します。Host を直接起動する場合も `process.env` から読むため、外部から渡された値が同じ形式なら通知になります。

## 値と判定

Host の `parsePortNotice()` は `String(value ?? '')` に対して次の正規表現を適用します。

```text
/^busy:(\d{1,5}):(\d{1,5})$/
```

一致すれば2つの部分を `Number()` で数値化し、`{ wanted, used }` を返します。一致しなければ `null` です。文字列全体との完全一致であり、前後の空白、符号、空の項目、6桁以上、末尾の改行や追加文字は受け付けません。数字は1〜5桁ですが、ポートとしての範囲検証はしません。そのため、たとえば `busy:0:99999` も構文上は受け付けられます。未設定および `null` は空文字列に変換されて `null` になります。空文字も同様です。

デスクトップシェルが生成する値は `busy:<wanted>:<used>` です。`wanted` は設定ファイルで選んだポート、または既定の `47831`、`used` は空きポート選択で取得したポートです。いずれも `u16` の待受ポートとして作られます。

根拠: `apps/host/server/shell-prefs.mjs:59-62`, `apps/desktop/src-tauri/src/main.rs:250-274`, `apps/desktop/src-tauri/src/shell.rs:55-63`。

## 有効になる条件

- デスクトップシェルのポート事前確認で希望ポートへの bind が失敗し、その後 `pick_port()` が空きポートを取得できた場合にシェルが通知値を作ります。bind の失敗理由はコード上で個別分類せず、すべてこの fallback 経路に入ります。
- 希望ポートは `shell-prefs.json` の有効な設定（1024〜65535）があればそれを使い、設定が `0`、欠落、範囲外、または読み込み不能なら既定値 `47831` を使います。CLI 引数や別環境変数による上書きはこの経路にありません。
- `pick_stable_port()` とその Host 起動経路には `#[cfg(not(target_os = "linux"))]` が付いています。したがって、このシェル側の自動生成は Linux ではコンパイル対象になりません。
- Host 側の読み取り自体は OS や desktop フラグでガードされていません。値がある場合、`/api/shell` の `portNotice` として返します。

## 実行時の詳細

シェルは起動時に希望ポートへ loopback bind を試し、成功すればポート通知を消去します。失敗した場合は一時ポートを選び、`PORT_NOTICE` に書いた文字列を子 Host 起動時に `cmd.env("STRATA_PORT_NOTICE", notice)` で渡します。この設定を行わないときは `Command` の既定動作により親プロセスの環境が継承されるため、親に同名変数が設定済みなら Host に残ります。設定する場合は継承値をシェル生成値で上書きします。

Host は `shellState()` の呼び出しごとに `process.env.STRATA_PORT_NOTICE` を読み、解析結果を `/api/shell` の JSON の `portNotice` フィールドに入れます。値を別の場所へ保存する処理や、Host 内でのキャッシュはありません。アプリ UI は初回の live 接続後に `/api/shell` を取得し、`portNotice` が非 null なら `warn` トーストを一度出します。表示文は「使用中のポート」「今回起動したポート」、および希望ポートで保存したチャットと設定が Strata がそのポートを再び使えるまで表示されないことを知らせます。ブラウザーまたは古い Host で API 呼び出しが失敗した場合は例外を無視します。

この変数自体がログ、終了コード、プロセス失敗を発生させる処理はありません。希望ポート確保後、Host が実際に bind する前に競合が起きる race はシェル側コメントに記されていますが、その Host 起動エラーはこの通知値の解析とは別経路です。

根拠: `apps/desktop/src-tauri/src/main.rs:240-274,442-492,495-537`, `apps/host/server/index.mjs:133-143,1950-1956`, `apps/host/src/lib/store.ts:509-518,757-790`。

## 根拠

- 環境変数を実際に読む箇所は `apps/host/server/index.mjs:142` の `process.env.STRATA_PORT_NOTICE` です。
- シェルが子プロセスへ渡す箇所は `apps/desktop/src-tauri/src/main.rs:484-486`、通知値を組み立てる箇所は `apps/desktop/src-tauri/src/shell.rs:60-63` です。
- 形式と解析規則は `apps/host/server/shell-prefs.mjs:55-62`、UI の警告表示は `apps/host/src/lib/store.ts:512-518` です。
- `apps/host/tests/gh-app-features.test.mjs:99-101,205-217` に parser と API 応答のテスト例がありますが、本調査ではテストや build を実行していません。
- `docs/release-notes-0.2.7.md:25` は busy port 時の警告と、別ポートで起動することを記載しています。上記の実装経路と一致します。
