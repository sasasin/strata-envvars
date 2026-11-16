# `STRATA_NATIVE_REPO`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

Host UI のソース checkout モードで、ネイティブ Strata リポジトリの初期候補パスを指定する。Host UI はこのパスを使って `setup.py`、`tools/strata_mcp.py`、`serve/server.py` を持つ checkout を選び、MCP 接続と `serve/server.py` の起動に使う。推論エンジン自体の挙動を切り替える変数ではない。`apps/host/server/native-control.mjs:48, 118, 124-127, 564`。

## 値と判定

`createNativeControl` の引数既定値で `process.env.STRATA_NATIVE_REPO ?? resolve(ROOT, '../../Strata')` として読み取る。`??` のため未設定（`undefined`）のときだけ Host UI 内で計算した既定パスを使い、空文字も指定値として残る。文字列の真偽値判定、trim、大小文字変換、数値変換はしない。`repo()` は `realpathSync(preferences.repo)` で実在パスへ解決し、3 ファイルの存在を確認する。`apps/host/server/native-control.mjs:27, 48-51, 118`。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| ソース checkout モード | `resolve(ROOT, '../../Strata')` を初期候補にする | 実在し、`setup.py`・`tools/strata_mcp.py`・`serve/server.py` を含むディレクトリのパス | 空文字、存在しないパス、または必須ファイルのいずれかがないパス。空白だけの値も trim されず、その名前のパスとして解決される |
| packaged mode（Control がある場合） | 同左の環境変数候補は使われない | 該当なし | 環境変数値は `repo()` の選択に使われない |

パスの形式・実在性は Node.js の `realpathSync` に委ねられ、相対パスも禁止されていないため、プロセスの作業ディレクトリから解決される。無効なパスを選んだときは `repo()` が `Choose the Strata repository folder containing setup.py and tools/strata_mcp.py.` を投げる。空文字や不存在パスでは `realpathSync` 自体のエラーになり得る。`apps/host/server/native-control.mjs:118`。

## 有効になる条件

- `apps/host/server/index.mjs:129-130` が `findControl()` の結果を Host に渡し、`native-control.mjs:69` が `packaged=!!control` とする。`control` がないソース checkout モードでこの環境変数による候補パスが有効になる。packaged mode では `repo()` は `installRoot()` を返すため、`STRATA_NATIVE_REPO` は参照パスを変えない。`apps/host/server/native-control.mjs:69, 113, 118`。
- `directory/native-host.json` がすでに存在して `repo` が保存されていると、その値が環境変数より優先される。環境変数はファイルを読むときの fallback 初期値に限られる。`apps/host/server/native-control.mjs:48-51`。
- UI のインストール選択（`configure({repository})`）は `preferences.repo` を更新して検証後に `native-host.json` へ保存するため、その後は保存値が使われる。実行中モデルまたは実行中ジョブがある間は変更を拒否する。CLI 引数による上書き経路はこの変数の読取・利用コードにはない。`apps/host/server/native-control.mjs:168`。

## 実行時の詳細

環境変数は `createNativeControl` の既定引数が評価されるときに読み取られ、`preferences` が初期化される。保存ファイルがあればその `repo` 値を使う。プロセス中に環境変数だけを書き換えても `preferences` は再読込されない。UI からの `configure` は選択値を検証・保存し、ネイティブ接続を切って状態を更新する。`apps/host/server/native-control.mjs:48-51, 118, 168`。

ソース checkout では `repo()` の結果が `tools/strata_mcp.py` の起動パスと作業ディレクトリになり、モデル起動時の `serve/server.py` のパスと作業ディレクトリにもなる。子プロセスには `process.env` の複製を渡す（Python の文字コード設定を上書きし、MCP 側ではさらに Host の `STRATA_API_KEY` を削除する）が、`STRATA_NATIVE_REPO` を子プロセス側で参照するコードは見つからなかった。`apps/host/server/native-control.mjs:123-127, 564`; `apps/host/server/control-runtime.mjs:82-85`。

## ログと測定値

この変数に関する専用ログや測定値はない。初期状態の更新処理では `repo()` の失敗が捕捉され、`snapshot.error` にエラーメッセージが入り、`available:false` となる。UI からの不正なリポジトリ選択は `configure` の呼び出しをエラーで終了し、旧 `preferences` に戻す。`apps/host/server/native-control.mjs:118, 166, 168`。

## 根拠

- `apps/host/server/native-control.mjs:48-51, 69, 113, 118-127, 166-168, 564`: 環境変数の読取、既定値、保存値との関係、モード分岐、パス検証、読取失敗と子プロセス起動。
- `apps/host/server/index.mjs:128-130`: Control の有無を Host に渡す。
- `apps/host/server/control-runtime.mjs:77-85`: ソース checkout のサーバー子プロセス環境。
- `apps/host/docs/README.md:27-30`: Host UI のソース checkout 用パス指定としての説明。コード上の必須ファイル検査は `native-control.mjs:118` による。
