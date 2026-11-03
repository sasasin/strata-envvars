# `E2E_WINDOW`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`apps/host/scripts/agent-lost-e2e.mjs` 専用の E2E スクリプトが、モデルのコンテキスト窓として扱う数値です。Strata の通常の CLI やサーバー起動時に全体設定として読む変数ではありません。スクリプトはこの値を Harness bridge に渡し、スクリプト自身がモデルサーバーを起動する場合はサーバー設定の `--max-context` にも渡します。

## 値と判定

スクリプトのモジュール読み込み時に `Number(env('E2E_WINDOW', '65536'))` で一度評価します。共通関数 `env` は `process.env[name] ?? fallback` を返すため、未設定の場合だけ既定値が使われます。

| 入力 | `WINDOW` の値 | コード上の扱い |
|---|---:|---|
| 未設定 | `65536` | 既定値 |
| `65536` | `65536` | 10 進数値に変換 |
| 空文字 | `0` | 空文字も設定値として残り、`Number('')` の結果を使う |
| 空白だけ | `0` | `Number()` の変換結果を使う |
| `12.5` | `12.5` | 小数も拒否・丸めせず保持 |
| `abc` | `NaN` | エラー処理や fallback はこのスクリプト内にない |
| `-1` | `-1` | 負値の検査・clamp はこのスクリプト内にない |

文字列比較や整数 parse はせず、`Number()` の変換結果をそのまま使います。CLI 引数による `WINDOW` の上書きはありません。`E2E_CUT_WINDOW` は `cut` シナリオで Harness bridge に別の値を渡しますが、コメントにある通りエンジン側の窓は `WINDOW` のままです。

## 有効になる条件

- この変数を読むのは Node.js で `apps/host/scripts/agent-lost-e2e.mjs` を実行した場合です。OS、GPU backend、build macro による分岐はこの読み取り箇所にはありません。
- `E2E_BASE_URL` が空または未設定なら、スクリプトは `WINDOW` を `--max-context` の値として `server.json` の engine args に入れ、`serve/server.py` を子プロセス起動します。
- `E2E_BASE_URL` が設定されている場合は既存モデルサーバーを使い、新しい server config を作成しません。この経路でも `WINDOW` は bridge の `localInstances` に渡す `context` として使われます。
- `E2E_ENGINE_ARGS` は起動時の追加 engine args ですが、`E2E_WINDOW` 自体を bridge の context に反映する処理とは別です。`--max-context` の重複引数時の扱いはこの環境変数の変換処理では検証していません。

## 実行時の詳細

`WINDOW` はスクリプトのトップレベル定数なので、環境値はスクリプト読み込み時に一度読み取られます。実行中の環境変更を再読するコードはありません。

既存サーバーを使わない場合、生成する `server.json` の `args` に `['--max-context', String(WINDOW)]` を設定します。その config を `serve/server.py --config ...` に渡して起動します。Strata のサーバーコードは engine args 内の `--max-context` に続く値を `int()` で読み、無い場合は 4096 とします（`serve/server.py:1101`）。したがって `NaN` や小数表記など整数にできない入力は、サーバー側で整数変換できない値として渡されます。E2E スクリプト側には事前検証や代替値への置換がありません。

bridge は `localInstances()` のモデル情報に `context: WINDOW` を設定します。Harness の profile 生成はこの context を `contextWindow` としてルートに載せ、ローカルルートの応答予算計算にも使います（`apps/host/server/agent/profile.mjs:235-247`）。したがって既存サーバー利用時は、サーバー自体の設定値を変更せず、E2E bridge がモデル窓として申告する値を変えます。

スクリプトには、`STRATA_HARNESS_DIR` 未設定時の stderr 出力 `STRATA_HARNESS_DIR is not set` と終了コード 2、モデルサーバーが ready にならない場合の stderr 出力 `the engine did not become ready` と終了コード 4 があります。これらは E2E 全体の失敗経路であり、`E2E_WINDOW` の不正値を個別に診断するログはありません。通常完了時は結果行を出し、失敗行が一つでもあれば終了コード 1、なければ 0 です。

## 根拠

- `apps/host/scripts/agent-lost-e2e.mjs:3-21`: スクリプトの用途、引数、E2E 専用の環境変数一覧。
- `apps/host/scripts/agent-lost-e2e.mjs:29-39`: env helper、既定値、`Number()` 変換、トップレベルでの評価。
- `apps/host/scripts/agent-lost-e2e.mjs:44,58-84,86-108`: Harness 必須条件、既存サーバー分岐、engine config と `--max-context`、子プロセス起動、bridge への context 渡し。
- `apps/host/scripts/agent-lost-e2e.mjs:194-199`: cut シナリオでは bridge の context のみ `E2E_CUT_WINDOW` に差し替えること。
- `serve/server.py:1101`: `--max-context` の引数値を整数に変換する処理と、引数がない場合の既定値。
- `apps/host/server/agent/profile.mjs:235-247`: local instance の `context` をルートの `contextWindow` に使い、出力予算計算に渡す処理。
- `apps/host/scripts/agent-lost-e2e.mjs:88-95,207-209`: ready 待ち失敗、結果表示、終了コード。
