# `STRATA_LLAMA_SERVER`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。対象は Strata 所有コードであり、起動された llama.cpp 側の動作は含めない。

## 役割

Strata のホストアプリが管理する `llama-server` の実行ファイル候補を指定します。値はコマンドライン引数や設定ファイルとして解析されず、実行ファイルのパスとして扱われます。指定パスが存在すれば、同梱エンジン、固定の Homebrew パス、PATH 上の候補より優先して選ばれます（`apps/host/server/supervisor.mjs:60-106`）。

これは Strata の C++ 推論エンジンが読む環境変数ではありません。調査対象 commit での参照は `apps/host/server/supervisor.mjs:65` のみで、ホストアプリのエンジン監督機能に属します。

## 値と判定

`process.env.STRATA_LLAMA_SERVER` を JavaScript の真偽値で判定し、truthy ならその文字列をそのまま候補パスにします。数値変換、trim、引用符除去、実行可能性の検査はありません（`apps/host/server/supervisor.mjs:62-66`）。

| 値 | Strata の扱い |
|---|---|
| 未設定、空文字 `""` | falsy のため候補に加えない。探索は同梱エンジン等へ進む。 |
| その他の文字列（`"0"`、空白だけの文字列を含む） | truthy のため文字列そのものを候補パスにする。 |
| 指定パスが存在しない | `existsSync` が false となり選択されず、次の候補へ進む。 |
| 指定パスが存在する | 最初の存在候補として選ばれる。ファイル種別や実行権限まではここで検査しない。 |

候補順は、環境変数で指定したパス、`MODELS_DIR` の隣の `engine` 以下の同梱版、`/opt/homebrew/bin/llama-server` と `/usr/local/bin/llama-server`、最後に `resolveBinary()` が調べる PATH 上の `llama-server` です。PATH 探索は前段候補が存在しない場合にだけ行われます（`apps/host/server/supervisor.mjs:67-106`、PATH helper は `apps/host/server/util.mjs:54-59`）。この変数に対応する CLI 引数や別の値による上書きはありません。

## 有効になる条件

- `findBinary()` が呼ばれると候補探索に使われます。エンジンを実際に起動するときは `resolveBinary()` がこれを呼び、選んだパスを起動対象にします（`apps/host/server/supervisor.mjs:93-107,212-224`）。
- ホストアプリは候補探索をエンジン状態・チューニング画面等でも使います。実際のモデルロードでは `STRATA_REAL_ENGINE=1` のとき `REAL` が true になり、`models.load()` が supervisor を再起動します。未設定などで `REAL` が false の場合はモデルロードをシミュレートし、supervisor のプロセスを起動しません（`apps/host/server/models.mjs:12-20,207-235`）。環境変数単独でモデルロードや推論を開始するわけではありません。
- 環境変数が指定されても、そのパスが存在しなければ選ばれません。指定パスが存在するが起動できない場合はその候補が選択され、探索時点で別候補へ切り替える処理はありません（`apps/host/server/supervisor.mjs:90-106,218-246`）。

## 実行時の詳細

値は `findBinary()` の呼び出しごとに `process.env` から読み取られ、環境変数専用の static cache はありません。選択した binary は supervisor の `state` に記録されます。モデルロード時の `start()` は、同じモデル ID と port ですでに running なら直ちに現在の状態を返すため、その場合は再探索しません（`apps/host/server/supervisor.mjs:62-66,93-107,212-219`）。

選ばれたパスは `spawn(binary.path, state.args, ...)` に渡されます。子プロセス用環境は `{ ...process.env, LLAMA_CACHE: ... }` で作られるため、この変数も値が設定されていれば子プロセス環境に引き継がれます。Strata がこの名前で行う処理は実行ファイル選択と環境の継承までです（`apps/host/server/supervisor.mjs:242-246`）。

起動前に候補が見つからない場合、supervisor は状態を `error` にし、`No llama-server binary found. Download the engine from Settings → Engine.` を設定して例外を投げます（`apps/host/server/supervisor.mjs:218-223`）。候補を起動した後は、子の stdout/stderr をログへ転送し、早期終了時は終了コードを含むエラー、90 秒（既定）のヘルス確認で応答しない場合は `Engine did not become healthy in time` を扱います。起動失敗時には状態を `error` にして停止処理を行います（`apps/host/server/supervisor.mjs:193-210,251-280`）。

## 根拠

- 全直接参照: `apps/host/server/supervisor.mjs:65`。
- 候補の構築・存在確認・優先順: `apps/host/server/supervisor.mjs:60-106`。
- PATH 探索 helper: `apps/host/server/util.mjs:54-59`。
- supervisor による選択と起動、子プロセス環境: `apps/host/server/supervisor.mjs:212-246`。
- ログ、終了、health timeout の処理: `apps/host/server/supervisor.mjs:193-210,251-280`。
- 実際のモデルロードから supervisor を呼ぶ箇所: `apps/host/server/models.mjs:207-235`。
