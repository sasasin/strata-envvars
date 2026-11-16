# `STRATA_HOME`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

host/server は `STRATA_HOME` をアプリ用データルートの最優先候補として読み、選ばれたディレクトリの下に `models` と `data` を作成します。状態 JSON は `data/state.json`、同梱エンジンのインストール先は `<HOME>/engine` です。`HOME` は別途 `homedir()/.strata`、`process.cwd()/.strata` へフォールバックします。host の `store.mjs` が一度解決して export する値であり、host の `index.mjs` はその `DATA_DIR` を chat store や他の状態ストアへ渡します。`apps/host/server/store.mjs:14-32`, `apps/host/server/index.mjs:123-127`, `apps/host/server/engine-install.mjs:13-18`

同梱 Python の `strata repair-access` 経路では、設定値がユーザーのデータルートとしてアクセス権修復の対象一覧に加わります。この Python 側の用途は host の保存先選択とは別です。`strata_control/private_files.py:418-433, 509-527`; 呼び出し元は `strata_cli/cli.py:2117-2126, 2129-2137`。

## 値と判定

| 条件 | 未設定 | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| host/server のデータルート | `homedir()/.strata` を試す | 空でないパス文字列（例: `/var/lib/strata`）。そのパスに `models` と `data` を再帰作成できれば採用 | 未設定・空文字は候補から除外。`0` や `false` も特別な真偽値として解釈せず、文字どおりのディレクトリ名として試す。作成に失敗した候補は不採用 |
| 同梱 Python の修復対象ルート | `STRATA_HOME` 由来のルートを追加しない | 空でない文字列を `Path` にし、`user_roots()` では `resolve()` できたルートを追加。`known_roots()` では存在するルートだけを追加 | 未設定・空文字は追加しない。`0` や `false` もパスとして扱う。`known_roots()` は存在しないパスを除外 |

host 側は文字列の trim、絶対パス検査、正規化、値の内容検証を行いません。相対パスは Node の現在の作業ディレクトリ基準でファイルシステム操作されます。候補列は `STRATA_HOME`、`homedir()/.strata`、`process.cwd()/.strata` の順で、各候補について `models`、次に `data` を `mkdirSync(..., { recursive: true })` します。例外は候補ごとに握りつぶして次へ進み、最初に両方を作れた候補を返します。Python の `user_roots()` は値が truthy なら追加して `resolve()` の `OSError` を除外し、`known_roots()` は存在確認後に小文字化した文字列で重複を除きます。`apps/host/server/store.mjs:14-27`; `strata_control/private_files.py:418-433, 509-527`

## 有効になる条件

- host/server では Node host が `store.mjs` を import して `resolveHome()` を実行する経路で適用されます。指定パスに `models` と `data` の両方を作成できることが採用条件です。先行候補が失敗すると後続候補に移るため、設定した `STRATA_HOME` が使われない場合があります。候補をすべて使えない場合は例外になります。`apps/host/server/store.mjs:14-30`
- `STRATA_MODELS_DIR` はモデル置き場の別設定です。`defaultModelDirectory()` はそれを優先候補にし、`pickModelsDirectory()` は保存済み `state.modelsDir` があればそれを優先します。`STRATA_HOME` を設定しても、新規モデルの置き場が常に `<STRATA_HOME>/models` になるわけではありません。preferred の作成・アクセス確認に失敗した場合は `<HOME>/models` にフォールバックし、notice を生成します。`apps/host/server/model-directory-default.mjs:8-20`; `apps/host/server/store.mjs:60-87`
- Python 側の `repair_access()` と `repair_known_roots()` は Windows 以外では修復を行いません。`repair_known_roots()` は Windows で既知ルートを走査します。CLI の `repair-access` はこの処理を明示実行し、通常の CLI 処理でも PermissionError の再試行経路から呼ばれます。`strata_control/private_files.py:445-476, 530-540`; `strata_cli/cli.py:2098-2114, 2117-2137`
- `STRATA_HOME` が設定されているだけでは修復は始まりません。`repair-access` の実行、または CLI の対象処理で PermissionError が起きることが必要です。ファイル共有違反の場合は既知ルート修復ではなく 1.5 秒待って再試行します。`strata_cli/cli.py:2102-2114`

## 実行時の詳細

host は `store.mjs` のモジュール評価時に `HOME` を計算し、その時点で `models` と `data` のディレクトリを作成します。続いて `DATA_DIR`、`STATE_FILE`、モデル置き場が定まり、JSON state を読み込みます。host 起動後に `process.env.STRATA_HOME` を変更しても、既に export 済みの `HOME` や `DATA_DIR` は再解決されません。`state.json` がない、読み込みや JSON parse に失敗する場合は既定 state を使います。更新時は `data/state.json` へ保存し、`save()` の書き込み失敗は `[strata] could not persist state:` を stderr に出します。`apps/host/server/store.mjs:14-60, 146-157`

Python の `user_roots()` / `known_roots()` は呼び出しごとに `os.environ` を参照します。前者は Windows の `repair_access()` が指定ファイルの所有ルート判定を行う際に使用し、後者は `repair_known_roots()` が走査するルートを作る際に使用します。`known_roots()` は存在する `STRATA_HOME` 自体を走査ルートに加えます。ディレクトリ走査は上限 `limit=20000` 件で止まり、`models` など `_SKIP_DIRS` のサブディレクトリは再帰しません。`strata_control/private_files.py:418-442, 445-453, 505-527, 530-568`

## ログと測定値

host の候補がすべて失敗すると `Error('No writable data directory found — set STRATA_HOME to a writable path')` を投げます。host の起動経路でこの例外を捕捉して別候補を追加するコードは `store.mjs` にありません。モデル用 preferred path が使えず `<HOME>/models` に戻る場合は `[strata] ${MODELS_DIR_NOTICE}` を `console.warn` します。state 保存に失敗すると `[strata] could not persist state:` を `console.error` します。`apps/host/server/store.mjs:18-27, 83-87, 146-152`

Windows CLI の明示的な `repair-access` は human 出力で `checked … entries, repaired …, could not repair …` を表示し、失敗数が 0 より大きい場合はアクセス拒否時の案内も表示して終了コード 5 を返します。JSON 出力時は `ok` とレポートを出力します。PermissionError の自動再試行経路はこのサマリを出力せず、再実行後も失敗した場合にエラーコード 5 のエラーを返します。`strata_cli/cli.py:2102-2114, 2117-2126`

## 根拠

- host の値の候補順・作成・失敗: `apps/host/server/store.mjs:14-32`
- state とモデル置き場の初期化・保存: `apps/host/server/store.mjs:50-87, 131-157`
- host のデータルート利用: `apps/host/server/index.mjs:123-127, 284-291`; エンジン置き場: `apps/host/server/engine-install.mjs:13-18`
- 別モデル置き場の優先設定: `apps/host/server/model-directory-default.mjs:8-20`; `apps/host/server/store.mjs:67-87`
- Python 側の環境値参照と Windows 修復範囲: `strata_control/private_files.py:418-453, 509-540`
- CLI からの自動・明示呼び出しと出力: `strata_cli/cli.py:2098-2137`
