# `STRATA_MODELS_DIR`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata ホストが使うモデル保存先の既定候補を明示する環境変数です。保存済みフォルダーがない場合、ホストは値を候補として作成・検査します。モデル一覧・ファイル探索・空き容量表示や native engine の準備先は、最終的に選ばれた `MODELS_DIR` を使います（`apps/host/server/model-directory-default.mjs:8-19`、`apps/host/server/store.mjs:61-87`、`apps/host/server/models.mjs:32-51,129`、`apps/host/server/native-control.mjs:162-164`）。

これは `apps/host/server` の設定です。通常の C++ 推論 engine がこの名前を読む実装は確認できません。検索結果にある `apps/desktop/scripts/*` や `apps/host/tests/*` の多くは、テスト対象プロセスへ値を渡す側です。

## 値と判定

| 環境値 | 判定と結果 |
|---|---|
| 未設定 | `defaultModelDirectory()` は OS ごとの Documents 配下を既定候補にします。ホストは後述の保存済み設定・既存ライブラリも考慮します。 |
| 空文字 | JavaScript の falsy 判定で未設定と同じです。明示的な空パスとしては扱いません。 |
| 空でない文字列 | `path.resolve()` で絶対パスに変換し、モデルディレクトリの既定候補にします。相対値はホストの現在の作業ディレクトリ基準です。値の trim、形式検証、存在確認はこの変換時には行いません。 |
| 候補を作成・利用できない | 起動時の `mkdirSync` / 読み書き実行権限確認が失敗すると、`STRATA_HOME/models` に fallback し、警告を記録します。 |

`defaultModelDirectory()` には数値変換や値域制限はありません。パスとして不正な値でファイル操作が失敗した場合は fallback 対象になります（`apps/host/server/model-directory-default.mjs:8-10`、`apps/host/server/store.mjs:67-81`）。

## 有効になる条件

- `apps/host/server` のホストプロセスで有効です。backend や GPU の種類による分岐はありません。ホスト起動時に `store.mjs` が `defaultModelDirectory()` を呼びます（`apps/host/server/store.mjs:7,60-61`）。
- `STRATA_MODELS_DIR` が空でない場合、その絶対化したパスが Documents 等から作る既定候補より優先されます。ただし、保存状態の `state.modelsDir` がある場合は `pickModelsDirectory()` がそれを最初に返すため、保存済みフォルダーが環境変数より優先されます（`apps/host/server/store.mjs:50-58,67-68,83`）。
- 保存済みフォルダーがない場合、環境変数が未設定なら `STRATA_HOME/models` 内に GGUF ファイルがあるとその既存ライブラリを保持します。環境変数が空でない場合はこの既存ライブラリ優先判定を飛ばし、環境変数の候補を使います（`apps/host/server/store.mjs:72-75,83`）。
- 空でない環境変数の候補を作成・利用できなければ `STRATA_HOME/models` に fallback します。したがって有効な値でも、保存済み状態がある場合や候補へのアクセスに失敗した場合には、そのパスが実際の保存先にならないことがあります（`apps/host/server/store.mjs:67-81,83`）。
- 既定候補の生成には `STRATA_DOCUMENTS_DIR`、Windows の既知 Documents フォルダー、Linux の `XDG_DOCUMENTS_DIR`（または `user-dirs.dirs`）、最後の `home/Documents` が関係します。これらは `STRATA_MODELS_DIR` が空または未設定の場合に限る経路です（`apps/host/server/model-directory-default.mjs:11-19`）。
- CLI 引数による `STRATA_MODELS_DIR` の上書き・優先順位はありません。ホストの Settings でモデルフォルダーを変更すると、選んだパスを状態ファイルに保存し、同じプロセス内の `MODELS_DIR` も更新します。次回起動時はその保存値が環境変数より優先されます（`apps/host/server/store.mjs:131-139`）。

## 実行時の詳細

`store.mjs` のモジュール初期化時に状態ファイルを読み、環境変数から既定候補を作って `MODELS_PICK` と `MODELS_DIR` を初期化します。選択結果はプロセス内の `MODELS_DIR` として保持されるため、起動後にプロセス環境を書き換えても再評価されません。Settings からの変更だけは `MODELS_DIR` を更新します（`apps/host/server/store.mjs:50-61,83-87,131-139`）。

`STRATA_MODELS_DIR` の候補を採用する前に `pickModelsDirectory()` は再帰作成し、読み書き実行権限を確認して実パスを採用します。失敗時は `STRATA_HOME/models` を使い、stderr に `[strata] Strata could not use <候補> for models (<エラーコードまたはメッセージ>), so models go to <fallback>. You can pick another folder in Settings.` の形式で警告します（`apps/host/server/store.mjs:75-86`）。起動時には標準出力にも `models dir   ·  <選択パス>` を出し、host の状態応答にも `modelsDir` と `modelsDirNotice` を含めます（`apps/host/server/index.mjs:280-301`）。

選ばれたパスはモデルファイルの探索・配置と容量情報に使われ、native engine の準備時には `modelsDirectory()` として渡されます（`apps/host/server/models.mjs:32-51,129`、`apps/host/server/hardware.mjs:75-80`、`apps/host/server/index.mjs:164`）。native 準備先の調整では、環境変数が空でないときは Documents 既定位置向けの `models` / `Models` 整合処理を行わず、入力されたディレクトリをそのまま返します（`apps/host/server/store.mjs:90-109`）。

## 根拠

- 値から既定候補への変換と、Documents 系の fallback: `apps/host/server/model-directory-default.mjs:7-19`
- 状態読み込み・既存ライブラリ判定・候補の検査、fallback と警告: `apps/host/server/store.mjs:50-87`
- native engine 準備先の扱い: `apps/host/server/store.mjs:90-109`、呼び出しへの接続 `apps/host/server/native-control.mjs:162-164`
- 起動時のログと応答への公開: `apps/host/server/index.mjs:280-301`
- 選択先を使うモデル探索と容量表示: `apps/host/server/models.mjs:32-51,129`、`apps/host/server/hardware.mjs:75-80`
