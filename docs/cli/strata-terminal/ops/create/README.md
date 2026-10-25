# `strata ops create`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops create` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/recipes.py` |
| 作成するもの | profile に結び付いた型付き operation recipe |

## 役割

指定した profile と名前で、後から plan・run できるローカル recipe を新規作成します。recipe は任意のシェルコマンドではなく、対応済みの operation kind と型付きパラメーターを保存します。`create` は recipe ファイルを作るだけで、restart、校正測定、components 検証などの operation 自体は実行しません。operation の確認には `ops plan`、実行には `ops run` を使います。

## 使い方

```sh
strata ops create restart-copy --profile four-gpu --kind runtime.restart
strata ops create check-copy --profile four-gpu --kind components.verify --output json
```

`NAME` と `--profile PROFILE` には小文字英字・数字・`_`・`-` のみを使えます。`--kind` は必須です。作成後は [`strata ops show`](../show/README.md) で内容を確認し、必要なら [`strata ops edit`](../edit/README.md) または [`strata ops set`](../set/README.md) で設定し、[`strata ops plan`](../plan/README.md) で効果を確認してから [`strata ops run`](../run/README.md) を実行します。

## 作成できる recipe

| `--kind` | 初期パラメーター | 概要 |
| --- | --- | --- |
| `runtime.restart` | `startup_wait_s: 300` | 保存 profile を使う runtime restart recipe。 |
| `engine.calibrate.measure` | profile directory の `.reports` を指す絶対 `report_dir` | decode speed の校正測定 recipe。実行時には毎回 `ops run --exclusive` が必要です。 |
| `components.verify` | なし | installed component の検証 recipe。後から `live=true` を設定すると preview と実行の両方で GPU inventory も照会します。 |

## 実行時の動作と副作用

- parser は `NAME`、必須の `--profile`、必須の `--kind` を受け付けます。kind は上表の3値に限定されます。`--output` は `human` / `json`（既定値 `human`）を選び、`--json` は `--output json` の alias、`--quiet` は人向け情報表示を抑える共通 option です。
- profile の存在を確認し、recipe を profile 配下の `.ops/<profile>/<name>.json` に作成します。recipe directory は作成時に用意され、POSIX では owner-only mode `0700` を要求します。ファイルは排他的な新規作成で mode `0600` とし、既存ファイルを上書きしません。
- 保存する JSON には schema version `1`、profile、recipe ID、kind、params が含まれます。作成後に読み直して revision を返します。
- 名前または profile ID が規則に合わない、kind が未対応、profile がない、recipe 名が既に使われている、保存先の種類・権限が不正などの場合は失敗します。POSIX 以外の ACL 動作はこのコード調査だけでは確認していません。
- `--output json`（または `--json`）では成功時に recipe と revision を含む JSON を stdout に出します。human 出力では作成名・kind・revision を表示します。失敗時は stderr のエラー表示、または JSON error を返し、該当する `ProfileError` の終了コードを使います。

## 注意点

`components.verify` の `live` 設定や calibration の `report_dir` など、初期値以外の値は別途 recipe の edit/set 操作で設定します。calibration recipe は測定結果を作る経路であり、その report の review/apply は別コマンドです。recipe 作成だけでは GPU 照会・runtime restart・calibration 測定は行われません。

## 関連文書

- [CLI 索引](../../../README.md) — `strata ops` の全コマンドと option 文書
- [`strata ops init`](../init/README.md) — 標準 recipe 群の初期化
- [`strata ops plan`](../plan/README.md) — operation の preview
- [`strata ops run`](../run/README.md) — recipe の実行

## 根拠

- `strata_cli/cli.py:255-272,508-515` — `ops` のサブコマンド登録、`create` の引数、共有 `--json` / `--quiet` parser 定義。
- `strata_cli/cli.py:1391-1415,2160-2161` — `ops create` の dispatch、recipe 作成と成功出力。
- `strata_cli/cli.py:527-542,2166-2188` — success/error 出力形式と例外時の終了コード処理。
- `strata_control/recipes.py:28-35,38-59` — 対応 kind、profile/name validation、保存 directory と POSIX 権限条件。
- `strata_control/recipes.py:93-150` — recipe の schema validation、kind ごとの初期値、排他的な新規ファイル作成・mode・revision 読み直し。
- `docs/TERMINAL.md:96-122` — 利用例、kind の operation 内容、plan/run の使い分け。
