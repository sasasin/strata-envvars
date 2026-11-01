# `WORKDIR`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`WORKDIR` は Strata 本体の実行設定ではありません。`apps/host/scripts/agent-flow-s4b.mjs` と `apps/host/scripts/agent2-flow.mjs` のブラウザー E2E フローで、エージェント操作後にホスト側ワークスペース内のファイルを確認するために読み取られます。アプリや engine の作業ディレクトリを設定したり、子プロセスへ転送したりする処理は、この名前についてはありません。

## 値と判定

両スクリプトともモジュール初期化時に `process.env.WORKDIR` をそのまま `const WORKDIR` に代入します。文字列の trim、解決、正規化、数値変換、ディレクトリ存在確認はありません。Node.js の環境変数値は文字列で、後続の条件は JavaScript の truthiness に従います。

| 値 | `agent-flow-s4b.mjs` | `agent2-flow.mjs` |
|---|---|---|
| 未設定 | `WORKDIR` が falsy。ファイル存在・内容の2検査を省略 | goal 検査の `!!WORKDIR` が false となり、その検査を FAIL にする。time-skip のファイル検査は省略 |
| 空文字 | 未設定と同じ | 未設定と同じ |
| 空でない文字列 | `join(WORKDIR, 'hello.py')` で確認。存在すれば内容も読む | `join(WORKDIR, 'goal-done.txt')` で確認。time-skip では `notes.md` の前後を読み取り比較 |

先頭・末尾の空白を含む文字列もそのままパスの一部です。相対パスは Node プロセスの現在ディレクトリを基準にファイル API で扱われます。無効値専用の fallback やエラーメッセージはありません。パスが存在しない場合、`existsSync` による検査は false になります。time-skip 経路で `WORKDIR` が truthy だと `notes.md` の後続 `readFileSync` を行うため、ファイルが作られないなど読み取りに失敗すれば例外経路になります。

## 有効になる条件

- 2つのスクリプトを Node.js で直接起動した場合に限り参照されます。`apps/host/package.json` の標準 scripts にこの2ファイルの専用起動項目はありません（`flow` と `flows` は別スクリプトです）。
- 値の採取は起動時のモジュール評価時です。後から `process.env.WORKDIR` を変更しても、保存済みの `WORKDIR` は再評価されません。
- `agent-flow-s4b.mjs` は値が truthy の場合だけ、helpers の承認後に `hello.py` の存在を検査し、編集後にはファイルが存在するときだけ内容が `hello world` を含むか検査します。未設定ならこれらの検査を飛ばします。
- `agent2-flow.mjs` は `/goal` フローで truthy な `WORKDIR` と `goal-done.txt` の存在を必須検査します。したがって未設定・空文字では、この検査自体が FAIL になります。`/time-skip` フローでは truthy なときだけ `notes.md` の前後内容を検査し、未設定・空文字ならファイル内容の検証を省きます。
- `STRATA_URL` は必須で、未設定時は `WORKDIR` の検査に入る前に `STRATA_URL is required` を stderr に出して終了コード 2 で終了します。その他の CLI 引数や環境変数との `WORKDIR` 値の優先順位はありません。

## 実行時の詳細

これらは実アプリを Chrome で操作するホスト側フロー検証スクリプトです。`WORKDIR` はチャットへの指示やサーバー設定に使われず、スクリプト自身のファイル検査にのみ使われます。`agent-flow-s4b.mjs` は `existsSync` で `hello.py` を確認し、存在する場合に `readFileSync` で内容を検査します。`agent2-flow.mjs` は `goal-done.txt` の存在を確認し、time-skip の Keep / Put back 操作の前後に `notes.md` を読み取って比較します。スクリプト内に `WORKDIR` 配下へ直接書き込む処理はありません。time-skip の Keep / Put back は UI 操作として実行されます。

通常のチェック失敗は `ok` / `FAIL` を stdout に出し、最後に `process.exit(failed ? 1 : 0)` で終了します。`agent2-flow.mjs` の try 内でファイル読み取りなどが例外になった場合は `ERROR` と例外メッセージを stdout に出し、失敗フラグを立てて最終的に終了コード 1 になります。`agent-flow-s4b.mjs` の catch は `FAIL` と例外メッセージを stdout に出し、失敗フラグを立てます。`WORKDIR` 自体に関する警告ログはありません。

## 根拠

- `apps/host/scripts/agent-flow-s4b.mjs:13-15,20-30` — 環境の説明と起動時の読み取り。
- `apps/host/scripts/agent-flow-s4b.mjs:113-126` — `hello.py` の存在・内容検査。
- `apps/host/scripts/agent-flow-s4b.mjs:153-161` — 例外表示と終了コード。
- `apps/host/scripts/agent2-flow.mjs:4-13,19-26` — 起動例、環境の説明、起動時の読み取り。
- `apps/host/scripts/agent2-flow.mjs:125-132` — `WORKDIR` を必須にする goal 検査。
- `apps/host/scripts/agent2-flow.mjs:147-169` — `notes.md` の読み取りと time-skip 後の比較。
- `apps/host/scripts/agent2-flow.mjs:171-180` — 例外表示と終了コード。
- `apps/host/package.json:7-27` — package scripts。上記2フロー専用の項目はありません。
