# `STRATA_CONTROL_DIR`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata App Host が使う Strata Control（同梱 Python ランタイムと Control CLI）の候補ディレクトリを指定します。主にデスクトップアプリが同梱 Control の場所をホストへ渡すための変数です。設定パスは最優先候補になりますが、他の候補も検索され、バンドルのバージョンが最も新しいものが選ばれます。

これは Strata の C++ 推論エンジン向け設定ではありません。ソースチェックアウトでは、完全な Control バンドルがこの環境変数などから見つからない限り、Host は `control = null` のまま従来の経路を保ちます。

## 値と判定

| 値 | Host の扱い |
|---|---|
| 未設定 | 環境変数由来の候補を作らず、Host 隣の `control` と、あれば components 内の更新版を探索します。 |
| 空文字 | JavaScript の truthy 判定で候補から除外されます。未設定と同じく、この値由来の候補はありません。 |
| 空でない文字列 | `path.resolve()` で絶対パスに解決し、その場所を候補にします。相対パスは Host の現在の作業ディレクトリ基準です。前後空白の除去や環境変数展開はしません。 |
| 不完全な候補 | 対象 OS の bundled Python、`strata.py`、`strata_control` の3つすべてが存在しなければ候補を黙って飛ばします。 |

文字列の数値変換や真偽文字列の解析はありません。パスとして扱うため、`1` や `true` もその名前のパスです。候補の `BUNDLE.json` は任意で、読めない・JSON として不正ならバンドル情報なしとして続行します。

## 有効になる条件

- `apps/host/server/index.mjs` が初期化時に `findControl()` を呼び、候補が Host の必須ファイル確認を通る必要があります。チェックする Python は Windows では `<dir>/python/python.exe`、それ以外では `<dir>/python/bin/python3` です。
- 比較対象は環境変数の候補、Host の隣の `control`、`STRATA_COMPONENTS_DIR` または OS 既定 components 配下の `control/active.json` が指す更新版です。更新ポインターは JSON の `folder` が `^[\w.+-]+$` に合う場合だけ候補になります。
- 有効な候補が複数なら、`BUNDLE.json` の `version`（更新版ではそれがなければポインターの `version`）をドットで分け、各部分を `parseInt(..., 10) || 0` として数値比較します。バージョンが同じ場合は候補順で先のものを維持するため、同梱候補が同版以下なら環境変数候補が優先されます。より新しい隣接版または更新版は環境変数候補より選ばれます。
- デスクトップ Tauri シェルは起動時に resources/control 内の bundled Python と `strata.py` が存在するとき `STRATA_CONTROL_DIR` をその場所でホストプロセスに設定します。ホスト側の完全性チェックでは追加で `strata_control` も必要です。

## 実行時の詳細

`findControl()` はモジュール初期化時に一度実行され、その結果が `CONTROL` および `createControl()` の値として保持されます。通常のホスト実行中に環境変数を変更しても再探索されません。見つかった Control の CLI は、`controlEnvironment()` が作る子プロセス環境に `STRATA_CONTROL_DIR: control.dir` として引き継がれます。Host は同じ `control.dir` を作業ディレクトリにし、選ばれたバンドルの Python と `strata.py` を起動します。

環境変数が空、候補が不完全、または他候補より古い場合に、この変数専用のログや警告はありません。全候補が無効なら `findControl()` は `null` を返し、`createControl()` も `null` を返します。選択された Control の起動に失敗すると `ControlError`（`code: control_missing`、`Strata Control could not start: ...`）になり、子プロセスが応答しない場合はタイムアウトで kill され `control_timeout` と `Strata Control did not answer within ...` になります。各 Control 操作は結果 JSON や stderr を使って失敗を上位へ返します。

## 根拠

- `apps/host/server/control-runtime.mjs:22-24,59-75` — OS ごとの Python パス、環境変数候補、必須ファイル確認、バージョン比較と選択。
- `apps/host/server/control-runtime.mjs:26-43,46-49` — components の場所と更新版ポインターの解決、バージョン比較。
- `apps/host/server/index.mjs:122-124` — Host 初期化時の一度の探索と Control 生成。
- `apps/host/server/control-runtime.mjs:88-103,124-130` — 選択したディレクトリの子プロセスへの転送と CLI 起動。
- `apps/host/server/control-runtime.mjs:137-162,167-174` — 起動・timeout・Control エラー経路。
- `apps/desktop/src-tauri/src/main.rs:220-235` — Tauri シェルによる同梱ディレクトリの確認と環境設定。
- `packaging/README.md:92-97` — パッケージ説明も Host が同梱 Control を `STRATA_CONTROL_DIR` 経由で見つけると記載。実際の選択条件は上記 Host 実装に従います。
