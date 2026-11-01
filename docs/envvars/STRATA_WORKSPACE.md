# `STRATA_WORKSPACE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

ホストサーバーが使う既定 workspace のパスを指定します。主に初回起動時に作られる primary workspace の場所と名前を決め、そこからセッションの作業フォルダー、workspace のファイル一覧、workspace 配下の skill 配置などに使われます。対象は `apps/host/server/index.mjs` の Strata ホストです。変数を読んでいるのはこのファイルだけで、候補一覧にある他の一致はテストや開発用起動スクリプトが子プロセスへ値を渡す箇所です。

## 値と判定

| 環境値 | 判定・結果 |
|---|---|
| 未設定 | `Documents/Strata/Workspace` を先に試し、作成できなければ `<user home>/Strata/Workspace` を作成します。両方失敗した場合は user home を既定値にします。user home は `USERPROFILE`、次に `HOME`、最後に Node.js の `homedir()` です。workspace 名は `Strata` です。 |
| 空文字 | JavaScript の falsy 値として未設定と同じ扱いです。 |
| 空でない値 | 文字列全体を `path.resolve()` に渡して絶対パスにします。相対パスはホストプロセスの現在ディレクトリー基準です。workspace 名は解決後のパスの `basename()` です。 |

値を数値や真偽値として parse せず、空白除去、存在確認、ディレクトリー検査、範囲制限もこの判定箇所ではしません。したがって空白だけの値も設定値として扱われ、`resolve()` 後のパスが使われます。明示値のパスが存在しなくても、ここでは代替パスへ fallback したり、そのディレクトリーを作成したりしません。初回ルートの保存後は API から別 workspace を追加・選択できます。

## 有効になる条件

- ホストサーバーが起動し、`server/index.mjs` が評価されること。OS、推論 backend、モデル状態、サーバーの `--dist` モードによる判定分岐はありません。
- `STRATA_WORKSPACE` は起動時の default workspace を決めますが、保存済み `workspaces.json` に workspace があれば、その配列が通常そのまま使われます。例外は、先頭項目が `id: 'root'` で、保存パスがアプリ自身のディレクトリー内にある場合で、この旧形式の root は起動時に環境値から決めた `WORKSPACE` と `WORKSPACE_NAME` に移されます。
- primary workspace の既定は `workspaces[0]?.path ?? WORKSPACE` です。チャットではセッションに選択済みのフォルダー、workspace ID で選ばれたパスが既定ルートより優先されます。`STRATA_WORKSPACE` 自体に CLI 引数や別環境変数との優先順位はありません。

## 実行時の詳細

`defaultWorkspace()` と `WORKSPACE_NAME` がホストモジュールの初期化時に `process.env.STRATA_WORKSPACE` を参照し、その結果は `WORKSPACE` / `WORKSPACE_NAME` 定数になります。稼働中に環境変数を書き換えても再評価されません。未設定時は `mkdirSync(..., { recursive: true })` で候補を順に作成し、両方失敗しても追加ログなしで user home を返します。明示値の場合は `resolve()` しただけで、パス操作の失敗は後続処理で初めて表面化します (`apps/host/server/index.mjs:102-115`)。

保存済み workspace を読み込めない場合（初回を含む）は `{ id: 'root', name: WORKSPACE_NAME, path: WORKSPACE }` を初期値にします。保存済みリストの読み込み失敗は握りつぶされて初回扱いとなり、後に workspace 保存が失敗した場合は stderr に `workspaces · could not persist` とエラーメッセージを出します (`apps/host/server/index.mjs:491-507,517-523`)。ホスト起動時には stdout に `workspace    ·  <WORKSPACE>` を表示します (`apps/host/server/index.mjs:280-286`)。

既定ルートは、チャット実行時にセッション固有フォルダーまたは指定 workspace がない場合の `workspacePath` となり、host の agent に渡されます (`apps/host/server/index.mjs:605-639`)。API の workspace 一覧・ファイル参照でも default root に使われ、アプリ配下へのパス逸脱は HTTP 400 で拒否されます (`apps/host/server/index.mjs:1688-1712`)。ただしこれらの実行時の参照は、先に述べた保存済み primary workspace があればそちらを用います。

## 根拠

- 環境値の既定値、空値判定、パス解決、名前決定: `apps/host/server/index.mjs:102-115`
- 初回 workspace と保存済み workspace、旧 root の移行: `apps/host/server/index.mjs:485-507`
- 保存エラーの観測ログ: `apps/host/server/index.mjs:517-523`
- 起動時の workspace 表示: `apps/host/server/index.mjs:280-286`
- チャットでの作業パス選択と agent への受け渡し: `apps/host/server/index.mjs:605-639`
- workspace API の既定 root とファイルパス検査: `apps/host/server/index.mjs:1688-1712`
- 候補一覧: `docs/envvars/000_envvers.md:1658`
