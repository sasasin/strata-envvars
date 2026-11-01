# `STRATA_CLOUDFLARED`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`cloudflared` 実行ファイルの場所を明示し、Strata が Cloudflare トンネル用 connector として探索・起動するファイルを指定します。対象は `strata launch` のターミナル経路と Host アプリのサーバー経路です。Strata エンジン本体の設定ではありません。

どちらの実装でも、値が有効な明示パスとして扱われると通常の PATH や標準配置場所を探索しません。候補一覧 `docs/envvars/000_envvers.md` にある同名は、Python 実装と Host アプリ実装の両方で実際に環境値へアクセスしていることを確認しました。

## 値と判定

| 経路 | 未設定・空文字 | 非空値 | 変換・検査 |
|---|---|---|---|
| `strata launch` | `os.environ.get(..., "").strip()` が空になり、PATH と通常の配置場所を順に探索 | 前後の空白を除いた文字列を唯一の候補にする | パス文字列として扱う。ファイルであることを確認し、Windows 以外では実行可能であることも確認する。バージョン確認に通る候補を採用する |
| Host アプリ | `env.STRATA_CLOUDFLARED` が falsy なら通常探索へ進む | 指定値を加工せず唯一の候補にする | Node.js の真偽値判定。空白だけの値も候補になる。ファイル・実行可否を検査し、実行した `--version` 出力を検査する |

両方とも文字列全体をパスとして使い、`1` / `0` のようなフラグ値としては解釈しません。明示パスが実行不能・不正・古い場合、PATH などにある別の `cloudflared` へはフォールバックしません。Python 経路は候補が見つからないものとして利用不可になり、Host アプリは候補検査で記録した失敗理由を表示・返却できる経路です。

## 有効になる条件

- `strata launch` では共有方法の候補表示、Cloudflare tunnel が選ばれた際の開始、connector 不足判定に使われます。Cloudflare 以外のアクセス方法を選んだだけではトンネルを開始しません（`strata_cli/launch/access.py:242-282,376-383`）。
- Host アプリでは `apps/host/server/index.mjs` が connector installer を作成し、起動時の `cloudflare.inspect()` と tunnel 準備・開始から検索を呼びます（`apps/host/server/index.mjs:949-951`, `apps/host/server/cloudflared-install.mjs:34-45`, `apps/host/server/cloudflare.mjs:25-36,55-75`）。Node 実装は `env` 引数の既定値に `process.env` を使います（`apps/host/server/cloudflared-install.mjs:34-40`, `apps/host/server/cloudflared-find.mjs:43-48`）。
- OS による実行ファイル名は Python で `cloudflared.exe` / `cloudflared` に分岐し（`strata_cli/launch/access.py:75-92`）、Host 側も `win32` で `.exe` を選びます（`apps/host/server/cloudflared-find.mjs:45-47`）。値自体に OS 別の解釈や backend 条件はありません。
- Host アプリには別変数 `STRATA_CLOUDFLARED_SEARCH=own` があり、明示パスが空のときだけ PATH と標準配置場所の探索を止めます。`STRATA_CLOUDFLARED` が非空なら先に単一候補を返すため、この検索制限値はその場合に探索結果を変えません（`apps/host/server/cloudflared-find.mjs:43-59`）。

## 実行時の詳細

### `strata launch`

`_cloudflared_places()` が呼ばれるたびに環境を読みます。値が未設定か、空または空白だけなら PATH の各ディレクトリ、続いて OS ごとの通常配置場所を候補にします。明示値が非空なら `.strip()` 後のパス一つだけを返すので、存在しない・実行できない・バージョン条件を満たさない場合も他の場所は試しません（`strata_cli/launch/access.py:70-94,124-137`）。

候補は通常ファイルであり、Windows 以外では実行可能である必要があります。Strata は候補に `--version` を付けて実行し、終了コード 0 かつ出力に `cloudflared` またはバージョン表記があるものを受理します。バージョン表記 `YYYY.M.P` が得られた場合は `2022.1.0` 以上を要します。認識可能な版がなくても `cloudflared` の文字があり正常終了すれば版なしとして受理します（`strata_cli/launch/access.py:66,97-121,124-132`）。検査結果はプロセス内の `_cf_seen` に `(path, mtime)` キーでキャッシュされます。環境変数や候補リスト自体を固定する cache はありません。

見つからないと Cloudflare access option は未準備として表示され、トンネル開始はインストール案内を返します（`strata_cli/launch/access.py:242-255,270-273,381-383`）。実行開始時は選ばれたパスで `tunnel --no-autoupdate --url http://127.0.0.1:<port>` を起動します。起動後、45 秒（既定）以内にログから Quick Tunnel URL が得られなければプロセスを停止し、タイムアウト相当のメッセージを返します（`strata_cli/launch/access.py:376-423`）。この変数は実行ファイルの選択に使われ、子プロセスへ同名の値を設定・転送する処理はありません。

### Host アプリ

`connectorCandidates()` は値が非空なら `{ path: 値, source: 'setting' }` 一件だけを返します。空または未設定なら Strata 管理フォルダー、任意 component フォルダー、PATH、標準配置場所の順で候補を作ります。`findConnector()` は候補ごとにファイル・実行可否と `--version` を検査し、`2022.1.0` 以上の最初の有効候補を選びます。明示値が候補として使われた場合、失敗後に他の既設パスへ進むことはありません（`apps/host/server/cloudflared-find.mjs:20-21,42-70,73-110`）。

明示先が見つからない場合、`connector.ensure()` は取得処理へ進めることがあります。検索失敗理由が記録されていれば `skippedMessage()` によるエラーで止まり、なければ acquisition 許可を確認して connector を自動取得・検証し、Strata 管理フォルダーへ保存します（`apps/host/server/cloudflared-install.mjs:43-52,55-88`）。ただし、環境値は変わらず、次の検索も同じ明示パス一件を優先します。アプリが起動する connector 子プロセスの環境は `process.env` の複製であり、`TUNNEL_` で始まる他変数だけ削除されます。`STRATA_CLOUDFLARED` は子プロセスの環境変数として明示設定・転送されません（`apps/host/server/cloudflare.mjs:71-75`）。

実行ファイルが起動できない場合、または tunnel が登録・接続する前に停止した場合はアプリの tunnel 状態が error になり、起動不能・終了・接続 timeout のメッセージが返ります（`apps/host/server/cloudflare.mjs:50-53,64-68,86-92`）。

## 根拠

- 候補の Python 環境読み取り、優先順、実行確認: `strata_cli/launch/access.py:70-94,97-137`
- Python CLI での使用と観測結果: `strata_cli/launch/access.py:242-282,376-423`
- Host アプリの環境値判定と候補探索: `apps/host/server/cloudflared-find.mjs:42-70,95-110`
- Host アプリの探索・自動準備の呼び出し: `apps/host/server/cloudflared-install.mjs:34-52,55-93`, `apps/host/server/index.mjs:949-951`
- Host アプリの connector 起動・失敗経路: `apps/host/server/cloudflare.mjs:25-36,50-92`
- `docs/DETAILS.md` には Cloudflare tunnel の一般的な利用例（`docs/DETAILS.md:621`）はありますが、この変数固有の挙動説明は確認できませんでした。
