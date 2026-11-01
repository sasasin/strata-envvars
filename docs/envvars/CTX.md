# `CTX`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `main...origin/main` で、未コミット変更はありません。`CTX` は通常の `strata` エンジン設定として読まれるのではなく、確認できた二つの同梱ツールが読む値です。

## 役割

`tools/dsv41/bytecheck.sh` では、比較実行する DSV41 エンジンへ `--max-context` の値を渡します。既定値は 8192 です。このスクリプトは base/new の二つの実行ファイルで logits と greedy token を比較するための検査ツールです。

`apps/host/scripts/agent-http.mjs` では、`connect` サブコマンドで登録するテスト用 API モデルに `contextMax` を付けます。これはそのモデルのコンテキスト上限情報として `/api/model-providers` へ送られます。通常の host や engine 起動時に `CTX` を読む箇所は確認できませんでした。

## 値と判定

| 読み取り元 | 未設定・空文字 | 設定値 | 変換・無効値 |
|---|---|---|---|
| `tools/dsv41/bytecheck.sh` | `${CTX:-8192}` により未設定または空文字は `8192` に置換される | `--max-context` の後ろへシェル展開した文字列を渡す | スクリプト内の数値検証や clamp はない。通常は単一の数値文字列を想定するが、展開は未引用なので空白による分割や pathname expansion が起こり得る。エンジンの `--max-context` 引数解析は `std::atoll` を使い、値の数値全体性を検査しない。 |
| `apps/host/scripts/agent-http.mjs` の `connect` | `process.env.CTX` が falsy（未設定または空文字）なら `contextMax` フィールド自体を省略 | truthy な文字列を `Number(...)` で変換して `contextMax` に設定 | 数字でない文字列は `NaN`、空白だけの文字列は `0`、`0` や負数は数値として送られる。host 側の `numeric()` は有限かつ 0 以上の数値だけを受理し、それ以外を `null` に正規化する。正の上限値や整数であることの検証はない。 |

`bytecheck.sh` が実行する `maya-ds4` は `--max-context` を `std::atoll` で読み取ります。`strata generate` でも同じ CLI 名を受理しますが、`CTX` を直接参照する engine コードは確認できません。したがって CTX と CLI 引数が併用される優先順位はなく、bytecheck のスクリプトが環境値から CLI 引数を組み立てています。

## 有効になる条件

- `tools/dsv41/bytecheck.sh` を実行した場合に限り、そのプロセスで `CTX` が参照されます。値は `windows` / `chunked` / `drafter` の各比較用起動に共通引数として渡されます。空文字を含め未設定と同様に 8192 になります。
- `apps/host/scripts/agent-http.mjs connect <baseUrl> <modelId>` の場合に限り `CTX` がモデル登録リクエストへ反映されます。ほかのサブコマンドでは参照されません。接続先のモデル上限を超える値など、モデル固有の妥当性はこのスクリプトでは検査しません。
- OS、GPU backend、build macro、モデル状態による `CTX` 自体の分岐はありません。シェルスクリプトは Bash、HTTP ツールは Node.js の `process.env` を使います。

## 実行時の詳細

`bytecheck.sh` はスクリプト起動時に `common` 文字列を作り、各 build/check の実行コマンドへ展開します。エンジン側で負値・0・上限超過などが受理されるかは `--max-context` CLI の処理によります。通常の `strata generate` では値を `std::atoll` で読み、0 以下、最大値超過、prompt と generation を収容できない値は stderr にエラーを出して終了コード 2 で返します（`src/program/generate.cpp`）。この検証は通常エンジンの CLI に対するもので、bytecheck の `maya-ds4` 実行に同じ境界検証があるとはこの調査では確認できていません。

`agent-http.mjs` は `connect` 分岐を実行した時点で `CTX` を読み、`contextMax` を含めた JSON を host の `/api/model-providers` に POST します。どちらのツールにも値を保持する static cache はなく、シェルスクリプトは実行ごと、HTTP ツールは `connect` 処理ごとに環境を参照します。bytecheck は `CTX` 自体を子エンジンへ環境変数として渡さず、CLI 引数に変換します。host は有限かつ 0 以上の数値を保存し、それ以外は `null` とします。保存に成功すればスクリプトは `saved` を出力します。リクエスト失敗時は共通 HTTP helper が status と応答内容を含む例外を投げます。`CTX` の値をログに出す処理はありません。

## 根拠

- `tools/dsv41/bytecheck.sh:7-12,26-49,51-67` — 用途、`CTX` の既定値、`--max-context` への展開、比較実行と出力。
- `apps/host/scripts/agent-http.mjs:11-14,18-23,79-82` — スクリプトの用途、HTTP 例外、`connect` 時の `CTX` 読み取りと送信。
- `apps/host/server/index.mjs:1065-1068` — `/api/model-providers` POST の保存処理とエラー応答。
- `apps/host/server/model-providers.mjs:50-51,86-93` — `contextMax` の有限・非負数値判定と保存。
- `src/dsv41/ds4_main.cpp:1314-1320` — DSV41 CLI の `--max-context` を `std::atoll` で読む処理。
- `src/program/generate.cpp:990,3031-3032,3918-3925` — `strata generate` の CLI 既定説明、`std::atoll` による引数解析、範囲・prompt/generation 検証と終了経路。
