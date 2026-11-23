# `STRATA_MODELS_DIR`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

App Host が新しいモデルライブラリに使う既定パスを指定する。値が空でなく、保存済みの `state.modelsDir` がない場合、ホストは値を実行 OS のパス規則で絶対パス化してモデルディレクトリ候補にする。モデルファイルの配置・検出、モデル用ディスク容量の表示、およびネイティブエンジンのダウンロード準備にこのディレクトリが使われる。モデルそのものの読み込みを起動時に行わせる設定ではない（`app/host/server/model-directory-default.mjs:8-11`; `app/host/server/store.mjs:62-89,306-308`; `app/host/server/models.mjs:32-44,129`; `app/host/server/index.mjs:141,184,306-315`; `app/host/server/native-control.mjs:273`).

## 値と判定

| 条件（実行環境） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| App Host の初期化時 | `Documents/Strata/Models` を既定候補にする（OS ごとの Documents 解決は下記） | 空でない文字列。`path.resolve` に渡し、相対値はホストの現在作業ディレクトリ基準で絶対化する | 空文字 `''` は falsy のため未設定と同じ。`0`、`false`、`true` は文字列として真なのでパスとして扱われ、論理値としては解釈されない |
| `state.modelsDir` が保存済み | 環境変数の有無にかかわらず保存済みディレクトリ | 保存済みパスが優先される | 該当なし |

環境変数は `process.env.STRATA_MODELS_DIR` の真偽値だけで判定し、数値変換、真偽文字列の比較、空白除去、値全体の別形式検証はしない。したがって `''` は採用されない一方、`'0'`、`'false'`、空白だけの値は候補になる。値があると `defaultModelDirectory()` は `path.resolve(value)` を返す。区切り文字、ドライブ文字、相対パスの意味は実行 OS の `node:path` に従う（`app/host/server/model-directory-default.mjs:8-11`）。

保存済みパスがない場合も、環境変数が常に選択結果を決めるわけではない。`pickModelsDirectory()` はまず保存済み `state.modelsDir` を返し、次に環境変数が空でない場合を除いて `STRATA_HOME/models` 以下に既存の GGUF 重みがあればそれを保持する。どちらにも該当しなければ環境変数由来の候補を作成して読み書き・実行可能性を確認し、成功すればその realpath を使う。作成・確認に失敗すると `STRATA_HOME/models` に fallback する（`app/host/server/store.mjs:62-85`）。

環境変数由来の候補が作れない場合や使えない場合の fallback は、`STRATA_HOME/models` と警告である。警告文は `Strata could not use <候補> for models (<エラーコードまたはメッセージ>), so models go to <fallback>. You can pick another folder in Settings.`。`MODELS_DIR_NOTICE` が空でない場合、起動時に `[strata] ` を付けて `console.warn` に出す（`app/host/server/store.mjs:77-89`）。

候補パス自体の既定値は OS によって異なる。Windows は Documents の Known Folder を取得し、取得に失敗した場合は `<home>/Documents`。Linux は `STRATA_DOCUMENTS_DIR`、`XDG_DOCUMENTS_DIR` または `user-dirs.dirs` の値を解決し、有効な絶対パスが得られなければ `<home>/Documents`。macOS 等のその他の OS は `<home>/Documents`。いずれも末尾に `Strata/Models` を付ける（環境変数が空でないときはこの既定値解決を使わない。`app/host/server/model-directory-default.mjs:8-25`）。

他の優先順位・相互作用:

- `state.modelsDir`（ホストの `STRATA_HOME/data/state.json` 由来）が `STRATA_MODELS_DIR` より優先される。ホストの CLI 引数でこの環境変数を上書きする処理は確認できない（`app/host/server/store.mjs:30-32,52-63,69-70,85`）。
- `STRATA_MODELS_DIR` が非空なら、保存済みパスがないときに限り、`STRATA_HOME/models` 内の既存重みを優先する分岐を抑止する（`app/host/server/store.mjs:74-85`）。
- ネイティブエンジン準備時、選択済みディレクトリが既定 Documents パスと一致する場合、ホストは `data_dir` を一段上のディレクトリに変換してモデルの `models` 配下が同じ場所になるよう調整する。環境変数が非空ならこの既定パス用変換を行わない。ただし `STRATA_HOME/models` を保持している経路の互換リンク処理が先にある（`app/host/server/store.mjs:91-111`; `app/host/server/native-control.mjs:273`）。
- デスクトップ更新確認では、Rust 側が `STRATA_MODELS_DIR` を含むカスタムプロファイル変数群について、未設定または空でないものを検出する。値のパスは読み取らず、非空の場合に更新 verdict の `customProfileEnv` に名前を含め、ホストは「そのランチャーで再起動するように」という警告を表示する。これはモデル保存先の選択とは別の診断経路である（`app/desktop/src-tauri/src/updater.rs:28-36,73-79,181-197`; `app/host/server/updates.mjs:109-123`）。

## 有効になる条件

- 対象は `app/host/server/store.mjs` を読み込む App Host プロセス。値はホスト起動時のモジュール初期化でモデル既定値と `MODELS_DIR` に反映される。
- 保存済み `state.modelsDir` があると、その値が環境変数より優先される。
- 新しい既定候補が使われるには、ディレクトリ作成と `R_OK | W_OK | X_OK` の確認が成功する必要がある。失敗時は `STRATA_HOME/models` に fallback し、理由を警告する。
- 既存の `STRATA_HOME/models` に GGUF 重みがあり、環境変数が空または未設定なら、その既存ライブラリを優先する。
- ネイティブ準備時のパス変換は入力ディレクトリが既存であること、`MODELS_DIR_NOTICE` が空であることなどにも依存する。保存済みディレクトリや既存モデル個別の run data folder が選ばれる場合は、既定値用変換の対象にならない（`app/host/server/store.mjs:91-111`; `app/host/server/native-control.mjs:273`）。
- CUDA/HIP/SYCL 等の backend や GPU の有無は、この環境変数によるホスト側パス選択の条件ではない。モデル起動時にロードするかどうかも別の制御であり、ホスト起動時には記憶済みモデルをロードしない（`app/host/server/index.mjs:306-308`）。

## 実行時の詳細

ホストの `store.mjs` 初期化時に状態ファイルを読み、次に `defaultModelDirectory()` を呼んで環境変数から既定候補を決め、`pickModelsDirectory()` の結果を `MODELS_DIR` に保持する。ディレクトリ決定はプロセス起動ごとに行われ、実行中に `process.env.STRATA_MODELS_DIR` を変更しても `DEFAULT_MODELS_DIRECTORY` や `MODELS_DIR` は再計算されない。環境変数を再読する `nativeDataDirectory()` の分岐だけは呼び出し時点の `process.env` を参照する（`app/host/server/store.mjs:62-89,92-111`）。

選択された `MODELS_DIR` は、モデルファイル探索とダウンロード先のパス生成、インストール状態判定、ライブラリの空き容量表示に使われる。`/api/hardware` のディスク情報にも含まれる。ホスト起動時に `models dir   ·  <パス>` を標準出力へ表示する（`app/host/server/models.mjs:32-44,46-51,129`; `app/host/server/hardware.mjs:75-80`; `app/host/server/index.mjs:310-315`）。

ネイティブエンジン準備では、既存モデル固有のデータフォルダーや UI の保存済みダウンロード先がなければ `MODELS_DIR` が入力候補となり、`nativeDataDirectory()` による `data_dir` 調整後に準備引数へ渡される。したがって値はモデル配置先を選ぶが、環境変数だけで既存モデルの実行設定や記憶済み保存先を移動するわけではない（`app/host/server/index.mjs:184`; `app/host/server/native-control.mjs:273`）。

## ログと測定値

測定値の記載はない。観測できる出力は、選択したパスの起動時標準出力 `models dir   ·  <パス>` と、既定候補を利用できず fallback した場合の `[strata] Strata could not use ...` 警告。更新確認で値が非空なら、設定画面の更新結果に `This session uses custom profile paths (STRATA_MODELS_DIR). Reopen Strata through that launcher after updating to keep the same profile.` を含める。モデルディレクトリ変更 API は候補ディレクトリが無効な場合 HTTP 400 と `validateModelsDirectory()` のエラー文を返すが、この検証は環境変数自体の parse ではない（`app/host/server/store.mjs:82-89,114-130`; `app/host/server/index.mjs:315,1566-1571`; `app/desktop/src-tauri/src/updater.rs:193-196`; `app/host/server/updates.mjs:113-123`）。

## 根拠

- `app/host/server/model-directory-default.mjs:8-25` — 環境変数の truthy 判定、絶対パス化、OS 別 Documents 既定候補。
- `app/host/server/store.mjs:52-89` — 状態読み込み、既定候補と保存済みパスの優先順位、既存重み保持、fallback と警告。
- `app/host/server/store.mjs:91-111,114-141` — ネイティブ用ディレクトリ調整と、UI/API からの保存先変更。
- `app/host/server/models.mjs:32-44,46-51,129` — モデルパス、ディスク検出・利用量。
- `app/host/server/index.mjs:306-315,141,184,1545-1549,1566-1589` — 起動時ロードなし、ログ、依存サービスへの供給、API。
- `app/host/server/hardware.mjs:75-80`; `app/host/server/native-control.mjs:273` — ハードウェア情報とネイティブ準備への利用。
- `app/desktop/src-tauri/src/updater.rs:28-36,73-79,181-197`; `app/host/server/updates.mjs:109-123` — 空でない設定の検出と更新警告。
