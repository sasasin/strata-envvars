# `E2E_PROFILE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Strata 同梱の `apps/host/scripts/agent-lost-e2e.mjs` が、E2E 用に起動するエンジンの引数へ expert profile のパスを加えるかを決めます。通常の Strata 起動経路が `E2E_PROFILE` を読む実装は見つかりません。この変数は同スクリプト内でパスとして扱われ、ファイルが存在すると `--expert-profile <path>` を生成設定の `args` に加えます。スクリプトはその設定を `serve/server.py` に渡して E2E 用サーバーを起動します（`apps/host/scripts/agent-lost-e2e.mjs:63-79`）。

## 値と判定

値は文字列として読み、真偽値や数値への変換、空白除去、形式検証はしません。共通 helper は `process.env[name] ?? fallback` なので、未設定時だけ既定値を使い、空文字はそのまま値として扱います（`apps/host/scripts/agent-lost-e2e.mjs:30-31,63`）。

| 状態 | `profile` の値 | 結果 |
|---|---|---|
| 未設定 | `join(HOME, 'bwm/cnt3/data/expert-profile.bin')` | 既定パスを存在確認する |
| 設定あり（空文字を含む） | 設定文字列そのもの | そのパスを存在確認する |
| 存在するパス | 上記いずれか | `--expert-profile` とパスを `args` に加える |
| 存在しないパス | 上記いずれか | 引数を加えず、そのまま続行する |

`HOME` も unset の場合は空文字となり、既定パスは `join('', 'bwm/cnt3/data/expert-profile.bin')` の結果になります。`existsSync(profile)` が false でも、この変数を理由とするログや終了はありません。必須ファイルとして検査されるのは pack、2 個の GGUF、MTP、実行ファイルで、profile はその検査対象に含まれません（`apps/host/scripts/agent-lost-e2e.mjs:31,59-70`）。

## 有効になる条件

- スクリプト起動時に `STRATA_HARNESS_DIR` が必要です。未設定なら `STRATA_HARNESS_DIR is not set` を stderr に出して終了コード 2 となり、profile の設定処理には進みません（`apps/host/scripts/agent-lost-e2e.mjs:44,58-63`）。
- `E2E_BASE_URL` が unset または空文字の場合に限り、同スクリプトが自前のサーバー設定を作ります。そのとき `E2E_PROFILE` を読み、存在するパスだけを引数へ追加します。`E2E_BASE_URL` が空でない場合は既存サーバーを使うため、自前の設定作成ブロックを通らず `E2E_PROFILE` を参照しません（`apps/host/scripts/agent-lost-e2e.mjs:34,58-79,86`）。
- `E2E_ENGINE_ARGS` は生成された基本引数の後ろに追加されます。これに `--expert-profile <別パス>` を含めると、エンジンの引数解析は各 `--expert-profile` を順に処理して `o.expert_profile` に代入するため、後ろの指定が先の指定を置き換えます（`apps/host/scripts/agent-lost-e2e.mjs:69-71`; `src/program/generate.cpp:3639`）。

## 実行時の詳細

`E2E_PROFILE` の評価は `agent-lost-e2e.mjs` のサーバー設定作成時に一度行われます。対象パスが存在すれば設定 JSON の `args` に CLI 引数として保存され、存在しなければ profile 引数なしでサーバーが起動します。したがって、この変数自体を Strata エンジンが読むのではなく、E2E スクリプトが `--expert-profile` 引数へ橋渡しします。同スクリプトはサーバー子プロセスへ環境を継承させますが、ソース全体の `E2E_PROFILE` 完全一致検索で確認できた読み取りはこのスクリプトの helper 呼び出しだけです。実行中に親プロセスの環境値を変えて再評価する経路はありません（`apps/host/scripts/agent-lost-e2e.mjs:30,63,68-79`）。

`--expert-profile` はエンジン側で引数として `o.expert_profile` に格納されます（`src/program/generate.cpp:3639`）。この文書では、E2E スクリプトがプロファイルファイルの内部形式やエンジン側での読み込み結果を検証しているとは扱いません。ファイル存在確認は引数を付ける条件に限られます。

## 根拠

- `apps/host/scripts/agent-lost-e2e.mjs:30-31` — nullish fallback helper と `HOME` の読み取り。
- `apps/host/scripts/agent-lost-e2e.mjs:34,58-79` — 既存サーバー分岐、profile の既定値、存在確認、設定引数、サーバー起動。
- `apps/host/scripts/agent-lost-e2e.mjs:44,59-70` — harness 必須チェックと profile 以外の必須ファイル検査。
- `src/program/generate.cpp:3639` — `--expert-profile` 引数の解析と代入。
