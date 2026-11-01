# `E2E_DOCS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`apps/host/scripts/context-e2e.mjs` が実エンジンとの手動 E2E 実行で使う、モデル・pack・MTP データのルートディレクトリです。ホストアプリ本体や通常の `serve/server.py` の環境設定として読む箇所は見つかりませんでした。候補一覧には掲載されていますが、実際の参照はこの E2E スクリプトに限られます（`apps/host/scripts/context-e2e.mjs:26-34`、`docs/envvars/000_envvers.md:348`）。

## 値と判定

| 状態 | `DOCS` に使う値 | 結果 |
|---|---|---|
| 未設定 | `C:\Users\AI-Server\Documents\Strata` | この既定ルートを使う |
| 空文字を設定 | 空文字 | 空文字のまま使う。既定値には戻さない |
| その他の文字列 | 設定値そのまま | `path.join` に渡して各データのパスを組み立てる |

共通 helper は `process.env[name] ?? fallback` であり、空文字を含む設定値を採用します。数値変換、文字列の真偽判定、空白除去、範囲検査、CLI による上書きはありません。`DOCS` はスクリプトのモジュール初期化時に `const` として決まり、その後の環境変更を読み直しません（`apps/host/scripts/context-e2e.mjs:25-34`）。

## 有効になる条件

`node scripts/context-e2e.mjs` でこのスクリプトを実行したときに参照されます。Windows 向けの既定パスがコードに埋め込まれています。`E2E_BASE_URL` が空でない場合は既存サーバーを使うモードになり、新しいサーバーを起動しません。そのモードでは `E2E_DOCS` から作った値は設定 JSON に書かれるだけで、その設定をサーバーへ渡さず、モデルファイルの存在確認にも使いません（`apps/host/scripts/context-e2e.mjs:33-37,47-61,78-80`）。

## 実行時の詳細

通常モードでは `E2E_DOCS` を基に次のパスを作り、設定 JSON に渡します。

- `models/gyro-Gyro-S/Qwen3.8-Flash-Next-Gyro-S-TQ1_0.gguf`（`--native` と `--ple-gguf` にも指定）
- `packs/gyro-gyro-s`（`--pack`）とその `tokenizer`
- `mtp/rt`（`--mtp`）

このモードでは起動前に `ENGINE` と GGUF の存在を調べます。GGUF が見つからない場合は `missing: <パス>` を stderr に出し、終了コード 2 で終了します。pack と MTP の存在をこのスクリプト自身が事前検査する処理はありません。子サーバー起動後のそれらのパスの扱いは、ここで確認した `E2E_DOCS` 読み取り処理だけからは断定できません（`apps/host/scripts/context-e2e.mjs:33,47-49,55-61,78-80`）。

## 根拠

- `apps/host/scripts/context-e2e.mjs:25-34`: `process.env[name] ?? fallback` helper、既定値、起動時定数、派生する GGUF パス。
- `apps/host/scripts/context-e2e.mjs:47-49`: 起動条件と、Engine/GGUF がない場合の stderr・終了コード 2。
- `apps/host/scripts/context-e2e.mjs:55-61`: pack、GGUF、MTP、tokenizer のパスを含むサーバー設定。
- `apps/host/scripts/context-e2e.mjs:78-80`: 既存サーバーモードでは子サーバーを起動しない条件。
- `docs/envvars/000_envvers.md:348`: 調査候補一覧での掲載。
