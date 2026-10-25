# `strata engine calibrate`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata engine calibrate` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/calibration.py` |
| 操作 | 計画、測定、結果レビュー、適用、ロールバックのいずれか一つ |

## 役割

選択した run config と実行環境に対して、エンジン設定の decode-speed sweep を行い、測定報告を作成・レビューしたうえで設定へ適用または元に戻すコマンドです。測定と適用は別操作です。測定だけでは run config を変更せず、適用前には結果レビューを行います。これは複数リクエストの serving throughput、TTFT、または複数 GPU serving のベンチマークではありません（`strata_control/calibration.py:1-5`、`docs/TERMINAL.md:160`）。

`--profile` には保存済み profile 名、または明示的な run-config JSON パスを指定できます。パス形式は拡張子 `.json`、絶対パス、または `/`・`\\` を含む値で判定され、profile 名へフォールバックしません（`strata_control/profiles.py:382-388`）。

## 基本的な使い方

まず読み取り専用の計画を確認し、測定、レビュー、適用をそれぞれ明示的に実行します。

```sh
strata engine calibrate --profile four-gpu --plan --output json
strata engine calibrate --profile four-gpu --measure --exclusive --out /absolute/path/to/calibration.json
strata engine calibrate --profile four-gpu --review-result /absolute/path/to/calibration.json --output json
strata engine calibrate --profile four-gpu --apply-result /absolute/path/to/calibration.json --exclusive
```

適用済みの状態を戻す場合は、先に rollback review を行います。

```sh
strata engine calibrate --profile four-gpu --review-rollback /absolute/path/to/calibration.json --output json
strata engine calibrate --profile four-gpu --rollback-result /absolute/path/to/calibration.json --exclusive
```

parser は `--profile` を必須とし、6つの操作フラグを相互排他かつ必須にしています（`strata_cli/cli.py:174-189`）。

## 実行モード

| モード | 主な指定 | 動作 |
| --- | --- | --- |
| 計画 | `--plan` | config の digest、選択モデル・デバイス、測定対象設定、部品の事前確認を表示します。エンジン起動・config 書き込みは行いません。 |
| 測定 | `--measure --exclusive --out REPORT.json` | decode sweep を実行し、新規レポートを保存します。測定設定自体はまだ適用しません。 |
| 結果レビュー | `--review-result REPORT.json` | 候補設定と鮮度・適用可能性を表示します。読み取り専用です。 |
| 適用 | `--apply-result REPORT.json --exclusive` | 候補を短い smoke generation で確認し、バックアップを保存してから run config と setup の記憶済み設定を更新します。 |
| rollback review | `--review-rollback REPORT.json` | 適用記録、バックアップ、現在の config/settings が一致し復元可能か確認します。読み取り専用です。 |
| rollback | `--rollback-result REPORT.json --exclusive` | 適用前の config/settings を smoke generation 後に復元します。 |

計画表示上の測定時間目安は約15〜30分です。必要なコンポーネントが不足すると計画の `component_preflight` は失敗し、doctor の実行を案内します（`strata_control/calibration.py:95-111`、`strata_cli/cli.py:1114-1126`）。

## 主な動作と副作用

- 測定報告は新規ファイルとして作成され、既存ファイルは上書きしません。出力先ディレクトリは事前に存在する必要があります。レポートは最大2 MiBで、測定値に加えて run config、engine、calibration tool、hardware identity などに結び付く情報を含みます（`strata_control/calibration.py:289-336`）。
- レポートは現在の profile/config、engine、calibration tool、ハードウェア識別子、必要モデルファイルのメタデータと照合されます。作成後30日超、対象構成の変更、レポート内容の変更などは適用不可になります。モデルファイルは完全な内容 hash ではなくメタデータのみで確認されます（`strata_control/calibration.py:146-166,339-385`）。
- 適用時は候補エンジンで少なくとも1 token の生成を確認し、owner-only の rollback evidence を作成してから run config と setup settings を更新します。書き込み失敗時は両方を復元しようとし、復元にも失敗した場合はバックアップからの手動復旧が必要になる旨を返します。設定を更新しても稼働中モデルには自動反映されないため、利用にはモデルの再起動が必要です（`strata_control/calibration.py:526-626`、`docs/TERMINAL.md:160`）。
- 適用と rollback はそれぞれ適用前・適用後の状態がレビュー時から変わっていないことを確認します。rollback は保存済みの直前 config/settings を smoke-test し、現在状態が適用後の hash と一致する場合だけ復元します（`strata_control/calibration.py:646-749`）。
- `--exclusive` は GPU を使う他プロセスが停止済みであるという operator の確認です。CLI は測定・適用・rollback でこれを必須にします。さらに calibration は設定 port の稼働確認と managed Strata runtime の排他 lease を行います。これらの lease は Strata 管理経路間の競合を防ぎますが、直接起動した旧 server、無関係な GPU プロセス、Windows 上の排他制御までは保証しません（`strata_cli/cli.py:1062-1110`、`strata_control/calibration.py:205-229`、`docs/TERMINAL.md:160`）。
- Terminal archive に `setup.py` と `tools/calibrate.py` がない場合、測定・レビュー・適用に必要な full Strata folder がなく失敗します。両ファイルを含む checkout を import 可能にするか、`STRATA_INSTALL_DIR` でそのフォルダーを指定する必要があります（`strata_control/calibration.py:41-64,67-79`）。

## 出力とエラー

`--output human|json` は出力形式を選び、既定値は `human` です。`--json` は one-shot parser 群に追加される `--output json` の alias です。`--quiet` も追加されますが、抑制処理は共通 CLI wrapper が扱います（`strata_cli/cli.py:187-189,508-515`）。計画・review は結果を表示し、適用可能性のないレビューは終了コード6です。計画の component preflight が失敗すると終了コード5になります（`strata_cli/cli.py:1076-1126`）。

引数組み合わせの不正は終了コード2です（例: 測定時に `--exclusive` または `--out` がない、計画に `--out` を併用、適用・rollback に `--exclusive` がない）。測定先が既にある場合も上書きを避けて拒否します（`strata_cli/cli.py:1062-1106`、`strata_control/calibration.py:289-296`）。その他、profile/config/engine/component の不備、古い報告、稼働中 server、smoke generation やファイル操作の失敗は、該当する `ProfileError` / CLI error と終了コードで返されます。測定キャンセルはコード130です（`strata_control/calibration.py:150-151,205-229,308-315,539-620,684-744`、`strata_cli/cli.py:2166-2193`）。

## 関連文書

- [CLI オプション索引](../../../README.md) — `strata engine calibrate` の各 option 文書。
- Strata source checkout の `docs/TERMINAL_QUICKSTART.md` — calibration の一連の利用例。
- Strata source checkout の `docs/TERMINAL.md` — calibration の前提条件、レビュー、適用、rollback の詳細。

## 根拠

- Strata `strata_cli/cli.py:174-189,508-515` — コマンド parser、必須・相互排他操作、出力形式、`--json` / `--quiet`。
- Strata `strata_cli/cli.py:1048-1126,2142-2143` — profile journal 経路、各操作の dispatch、出力と終了条件。
- Strata `strata_control/profiles.py:382-388` — profile 名または run-config path の解決。
- Strata `strata_control/calibration.py:41-79,95-111,146-166,205-229,270-360,363-385,388-409,526-626,646-749` — full-folder 条件、計画、排他、測定・報告検証・review・適用・rollback。
- Strata `docs/TERMINAL_QUICKSTART.md:64-87`、`docs/TERMINAL.md:160` — 利用例と操作上の制約。
