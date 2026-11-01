# `NO_PROXY`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata のサーバーは `NO_PROXY` を自身の通信判定には使わず、`--offline` 指定時に起動する子プロセス向け環境へ `NO_PROXY=*` を設定します。同じ環境には小文字名 `no_proxy=*` も設定します。Strata が行うのは設定と子プロセスへの引き渡しまでで、これらの名前を解釈する外部プログラムの動作は本書の対象外です。

## 値と判定

Strata は既存の `NO_PROXY` の値を読み取って parse したり、内容を検証したりしません。サーバーの `child_env()` はまず親プロセス環境を複製し、設定ファイルの `env` 項目も反映します。その後 `offline=True` の場合に限り、offline policy の固定値で上書きします。

| 状況 | 子プロセス用 `NO_PROXY` |
|---|---|
| `--offline` 指定あり | `*`。親環境や設定ファイルの `env.NO_PROXY` より優先 |
| `--offline` 指定なし、親環境に設定あり | 親環境の値を引き継ぐ。ただし設定ファイルの `env.NO_PROXY` があればそちらで上書き |
| `--offline` 指定なし、親環境に未設定 | 設定ファイルの `env.NO_PROXY` があればその値。なければ子環境でも未設定 |

環境変数の空文字を含め、Strata は通常時の値に特別な扱いをしません。`--offline` 時には空文字も含め、固定値 `*` で上書きします。小文字の `no_proxy` も同様に固定値 `*` になります。優先順位は CLI の `--offline` による policy 設定が設定ファイルの `env` より後です。

## 有効になる条件

- Strata サーバーの CLI で `--offline` を指定した場合に限り、`NO_PROXY=*` と `no_proxy=*` が子環境に設定されます（`serve/server.py:9000-9001,3765-3777`、`strata_control/offline.py:47-61`).
- `--offline` は MCP/tool subprocesses の起動とリモート画像 URL の取得を禁じるサーバーモードのオプションです。起動時に MCP サーバーまたは `before_load` コマンドがあると CLI parser error で拒否されます。また offline policy がネットワークを必要とする profile 要件を返した場合も起動を拒否します（`serve/server.py:9173-9184`）。
- backend、OS、モデル状態による `NO_PROXY` 固有の条件分岐はありません。offline の環境設定は GPU/backend の環境設定後に適用されるため、設定ファイルの同名値も offline policy が上書きします（`serve/server.py:3759-3777`）。

## 実行時の詳細

`child_env()` は親環境を複製し、GPU/backend 設定と構成ファイルの `env` を反映した後、offline 時に `OFFLINE_ENV` を追加します。ここで `NO_PROXY` と `no_proxy` をそれぞれ `*` にします。通常の Strata エンジン起動ではこの結果を `StrataEngine(..., env=env)` に渡し、replica と split serving の各エンジンにも同じ `child_env(..., offline=offline)` を渡します（`serve/server.py:3747-3777,8704-8711,8770-8777,9273-9279`）。

Strata は `NO_PROXY` を参照して自身の URL 可否を決めません。Strata 自身の offline URL 判定は `check_url()` が行いますが、これは `NO_PROXY` の値とは独立しています（`strata_control/offline.py:90-119`）。offline policy が拒否する profile は `--offline cannot be strict for this profile: ...`、旧来の MCP/before_load 条件は `--offline requires MCP servers and before_load commands to be disabled in this profile` という parser error になります。`NO_PROXY` 固有のログや終了経路はありません（`serve/server.py:9173-9184`）。

`strata_control.offline.child_environment()` にも環境を作る helper があり、offline 時には同じ定数を設定し、offline でない時は policy 変数を除去します（`strata_control/offline.py:122-136`）。ただし本 commit のサーバー実装はこの helper を呼ばず、`OFFLINE_ENV` 定数を直接使います。実際のサーバー経路で offline でない場合、`child_env()` は親環境を複製したままなので、`NO_PROXY` は削除されず継承されます。

## 根拠

- `strata_control/offline.py:44-61` — `OFFLINE_ENV` に `NO_PROXY=*` と `no_proxy=*` を定義。
- `serve/server.py:3747-3777` — 親環境の複製、設定ファイル `env` の適用、offline policy による上書き。
- `serve/server.py:9000-9001,9173-9184` — `--offline` オプションと profile 条件による起動拒否。
- `serve/server.py:8704-8711,8770-8777,9273-9279` — replica、split、通常エンジンへの環境引き渡し。
- `strata_control/offline.py:90-119` — Strata の URL 判定は `NO_PROXY` を参照しない。

`docs/DETAILS.md` に `NO_PROXY` 固有の説明は見つかりませんでした。リポジトリ内の `packaging/smoke_terminal.py:79-80` とテスト（`tests/tuning/test_offline.py:82-86` など）にも値の設定・確認がありますが、上記の実行時挙動の根拠は本番コードに限定しています。
