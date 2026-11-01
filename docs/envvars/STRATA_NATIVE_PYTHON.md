# `STRATA_NATIVE_PYTHON`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata の未コミット変更はありません（`main...origin/main`）。外部ライブラリの環境変数動作は対象外。

## 役割

App Host が Python コマンドを選ぶときの明示指定です。`STRATA_PYTHON` が空でなく設定されていればそちらが先に選ばれ、そうでなければこの変数が選ばれます。選ばれた値は実行ファイル名またはパスとしてそのまま使われます。主な対象は source checkout の native control plane（カタログ用 `tools/strata_mcp.py`、自動調整、engine 更新など）と、Host が起動する tuning / Time-skip CLI です。環境変数を読む実装は `apps/host/server/python-resolver.mjs:33-38`、呼び出し元は `apps/host/server/native-control.mjs:97-106,408-414` と `apps/host/server/index.mjs:763-768,903-912` です。

## 値と判定

文字列の parse、trim、Python のバージョン確認、ファイル存在確認はしません。JavaScript の `||` による選択です。

| `STRATA_PYTHON` | `STRATA_NATIVE_PYTHON` | resolver の選択 |
|---|---|---|
| 空でない値 | 任意 | `STRATA_PYTHON` の値 |
| 未設定または空文字 | 空でない値 | `STRATA_NATIVE_PYTHON` の値 |
| 未設定または空文字 | 未設定または空文字 | `control.python`（Control がある場合）、それ以外は repo の `.venv` が存在すればその Python。残りは OS 別 fallback |

値 `"0"`, `"false"`, 空白だけの文字列、相対パスなども空でなければ明示指定として扱います。指定先の存在・起動可否を resolver は検査せず、明示指定の場合 `pythonStarts()` の probe も通りません。`STRATA_PYTHON` が空文字なら対象変数に進み、対象変数も空文字なら未設定時と同じ候補選択に進みます。根拠: `apps/host/server/python-resolver.mjs:23-29,33-53`。

両変数とも空の場合の候補は、Control が渡された場合は `control.python`、次に repo が指定され `.venv` の候補ファイルが存在する場合はその Python、Windows では `py -3` の起動確認後に `python.exe` の起動確認、POSIX では Homebrew の Python 3.11 / 3.10 の存在確認後に `python3` です。Windows の候補がどれも起動できない場合は未確認の `python.exe` を返します。POSIX の `python3` も起動確認なしです。resolver 上は Windows / POSIX の候補差がありますが、`STRATA_NATIVE_PYTHON` 自体の値判定に OS 条件はありません。

## 有効になる条件

- Python resolver を通る処理で有効です。source checkout の native control は `python()` 経由で resolver を呼び、カタログ接続クライアント、自動調整、rollback / engine update などに選択値を使います（`apps/host/server/native-control.mjs:55,97-106,408-414`）。native model の通常 load は別経路で `venvPython(repo())` を直接使い、`.venv` がなければ `The Strata Python environment is missing. Use Download / repair first.` で止まります。この箇所では対象変数による interpreter 選択をしません（`apps/host/server/native-control.mjs:326-342`）。
- Host 起動時に作る tuning / Time-skip 用 interpreter にも適用されます。`index.mjs` は resolver の結果を一度 `PYTHON` に束縛し、両 CLI の command と args に渡します（`apps/host/server/index.mjs:763-768,903-912`）。この呼び出しでは `CONTROL` も渡されますが、非空の `STRATA_PYTHON` / `STRATA_NATIVE_PYTHON` は `control.python` より優先します（`python-resolver.mjs:33-39`）。
- Packaged native control の一部は resolver を使いません。native catalog client と自動調整は Control の Python を直接選び、子プロセス環境から `STRATA_NATIVE_PYTHON` と `STRATA_PYTHON` を削除します（`native-control.mjs:55,104-106`; `control-runtime.mjs:88-103,125-130`）。ただし Host 全体の tuning / Time-skip 用 resolver 呼び出しは別で、明示変数があればそちらを選びます。
- 明示指定された command が起動できない場合、値を別の Python に置き換える fallback はありません。native client 起動ではエラーが snapshot に入り、初期化要求は失敗し得ます（`native-control.mjs:101-113`）。CLI 実行では spawn の `error` が呼び出し元へ返り、Time-skip は `could not start the Time-skip command: ...` として失敗結果にします（`index.mjs:839-854`; `timeskip.mjs:302-310,322-330`）。

## 実行時の詳細

`resolvePython()` の既定引数 `env=process.env` から値を読みます。Host の `index.mjs` はモジュール初期化時に一度 resolver を呼ぶため、そこから作る tuning / Time-skip の interpreter 選択はその時点の値です。native control の source checkout 側 `python()` は呼び出しごとに resolver を呼びますが、既定の cache は Map で、キーに repo、Control の Python、両環境変数の現在値、platform を含みます。値が変われば別キーで再選択し、同じキーの成功結果は再利用します。`fallback` 結果だけは cache しません（`python-resolver.mjs:31-35,54-56`; `native-control.mjs:97-98`）。

明示値は command として直接 spawn されます。source native-control の Python 子プロセスには Host の `process.env` を spread して渡すため、この変数も子プロセス環境に残ります（`native-control.mjs:55,104-106,414`）。一方 packaged Control 用環境では明示的に削除されます（`control-runtime.mjs:88-103`）。ここで確認できる Strata の動作は選択・子プロセスへの環境引き継ぎ・削除までです。起動された Python、GPU driver、外部ライブラリがこの変数をどう解釈するかは本調査では扱いません。

`apps/host/docs/native-engine-handover.md:40-42` はこの変数を明示 interpreter 選択として記載しています。実装ではさらに `STRATA_PYTHON` が優先し、native model の load は resolver ではなく repo の `.venv` を直接指定します。したがって同資料の「otherwise installed virtual environment or an available system Python」という説明は resolver の優先順を簡略化した記述であり、load 経路に対象変数が適用される根拠にはなりません。

## 根拠

- `apps/host/server/python-resolver.mjs:23-29,31-56` — 明示値判定、優先順位、未設定時の OS 別候補、cache。
- `apps/host/server/native-control.mjs:55,97-113,326-342,408-414` — source / packaged native-control の interpreter 選択、子プロセス、model load の別経路。
- `apps/host/server/index.mjs:763-768,835-854,903-912` — Host 起動時の選択と tuning / Time-skip への適用。
- `apps/host/server/timeskip.mjs:291-310,322-330` — 選択済み command の起動と起動失敗の返却。
- `apps/host/server/control-runtime.mjs:88-103,124-130` — packaged Control 子プロセス環境での両 Python 指定変数の除去。
- `apps/host/docs/native-engine-handover.md:40-42` — 利用者向け説明との照合。
